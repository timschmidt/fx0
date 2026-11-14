#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Time finite RAW captures and retain kernel/cam evidence on the pinned r1 boot."""


import argparse


import hashlib


import json

import statistics


import os


from pathlib import Path


import re


import shutil


import signal


import subprocess


import tempfile


import time


SYS = Path('/sys')


CAMERAS = {
    'front': ('imx132', 'camera@36', 1976, 1200, 2472),
    'back': ('imx179', 'camera@10', 1640, 1232, 2056),
}


FRAMES = 24


FRAME_RECORD = re.compile(r'\bseq:\s*(\d+)\s+bytesused:\s*(\d+)')




NOTES_SHA = '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'


FRAME_PREFIX = 'fx0-camera-queue-r1-01-'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return Path(path).read_text().strip()


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=8)
    require(result.returncode == 0, f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout.strip()


def sensor_nodes():
    nodes = {}
    for node in (SYS / 'class/video4linux').glob('v4l-subdev*'):
        name = read(node / 'name')
        match = re.fullmatch(r'(imx132|imx179) \d+-([0-9a-f]{4})', name)
        if not match:
            continue
        model, address = match.groups()
        expected = {'imx132': ('0036', 'camera@36', 0x36), 'imx179': ('0010', 'camera@10', 0x10)}[model]
        require(model not in nodes, 'duplicate sensor model')
        require(address == expected[0], 'wrong sensor I2C address')
        require((node / 'device/driver').resolve().name == model, 'wrong sensor driver')
        of = node / 'device/of_node'
        require(of.resolve().name == expected[1], 'wrong sensor firmware node')
        require((of / 'compatible').read_bytes() == ('sony,' + model + '\0').encode(), 'wrong sensor compatible')
        require((of / 'reg').read_bytes() == expected[2].to_bytes(4, 'big'), 'wrong sensor firmware address')
        nodes[model] = node
    require(set(nodes) == {'imx132', 'imx179'}, 'incomplete sensor inventory')
    return nodes


def find_cameras():
    nodes = sensor_nodes()
    listing = command('cam', '-l')
    cameras = {}
    for label, (sensor, suffix, *_geometry) in CAMERAS.items():
        matches = re.findall(rf'^\s*(\d+):.*Internal {label} camera.*{suffix}\)', listing, re.MULTILINE)
        require(len(matches) == 1 and sensor in nodes, f'unexpected {label} camera inventory')
        cameras[label] = (matches[0], '/dev/' + nodes[sensor].name,
                          nodes[sensor] / 'device/power/runtime_status')
    require(len({row[0] for row in cameras.values()}) == 2, 'duplicate camera indices')
    return cameras


def idle_camera_owners():
    owners = set()
    for proc in Path('/proc').glob('[0-9]*'):
        try:
            for descriptor in (proc / 'fd').iterdir():
                try:
                    target = os.readlink(descriptor)
                except FileNotFoundError:
                    continue
                if target.startswith(('/dev/media', '/dev/video', '/dev/v4l-subdev')):
                    require(read(proc / 'comm') == 'wireplumber' and
                            os.readlink(proc / 'exe') == '/usr/bin/wireplumber', 'camera application already owns a device')
                    owners.add(int(proc.name))
        except FileNotFoundError:
            continue
    return sorted(owners)


def usb_power():
    usb = SYS / 'class/power_supply/smbb-usbin'
    battery = SYS / 'class/power_supply/smbb-bif'
    udc = SYS / 'class/udc/ci_hdrc.0'
    return {'USB_online': read(usb / 'online'), 'gadget_state': read(udc / 'state'),
            'USB_speed': read(udc / 'current_speed'), 'battery_status': read(battery / 'status')}


def require_usb(power):
    require((power['USB_online'], power['gadget_state'], power['USB_speed']) ==
            ('1', 'configured', 'high-speed'), 'native USB connection changed')


def native_state(boot_id):
    boot = read('/proc/sys/kernel/random/boot_id')
    require(boot == boot_id and command('uname', '-r') == '6.18.63-fx0-vibrator-alpine', 'native r1 identity changed')
    require(hashlib.sha256((SYS / 'kernel/notes').read_bytes()).hexdigest() == NOTES_SHA,
            'kernel notes do not match installed r1')
    require(read('/proc/sys/kernel/tainted') == '0', 'kernel taint')
    require(hashlib.sha256(Path('/lib/apk/db/installed').read_bytes()).hexdigest() ==
            'b106cfa76000084e240f6b1e40496a06b52f5d1820593364f8b13bfb54c9665f', 'installed package cohort changed')
    camss = SYS / 'bus/platform/devices/fda0ac00.camss'
    require((camss / 'driver').resolve().name == 'qcom-camss', 'CAMSS driver changed')
    require((camss / 'iommu_group').exists(), 'CAMSS has no IOMMU group')
    iommu = SYS / 'bus/platform/devices/fda44000.iommu'
    require((iommu / 'driver').resolve().name == 'qcom-iommu', 'VFE IOMMU driver changed')
    require((iommu / 'of_node/compatible').read_bytes() == b'qcom,msm8226-vfe-iommu\0', 'wrong VFE IOMMU')
    require((camss / 'of_node/iommus').read_bytes() == (iommu / 'of_node/phandle').read_bytes() + b'\0' * 4,
            'CAMSS is not attached to VFE context zero')
    temperatures = [int(read(path)) for path in sorted((SYS / 'class/thermal').glob('thermal_zone*/temp'))]
    require(len(temperatures) == 2 and all(-40000 <= value < 60000 for value in temperatures), 'temperature bounds')
    services = {name: command('systemctl', 'is-active', name) for name in ('upower', 'tinydm', 'iio-sensor-proxy')}
    require(set(services.values()) == {'active'}, 'native service state')
    power = usb_power()
    require_usb(power)
    return {'boot_id': boot, 'temperatures_mC': temperatures, 'services': services,
            'Sway_PID': int(command('pgrep', '-x', 'sway')), 'power': power, 'kernel_taint': 0}


def pattern(node):
    match = re.fullmatch(r'test_pattern:\s*(\d+)(?:\s+\([^)]*\))?',
                         command('v4l2-ctl', '-d', node, '-C', 'test_pattern'))
    require(match, 'cannot read test_pattern control')
    return int(match[1])


def idle(cameras):
    for _ in range(25):
        state = {name: read(path) for name, (_, _, path) in cameras.items()}
        if set(state.values()) == {'suspended'}:
            return state
        time.sleep(0.1)
    raise ValueError(f'camera runtime PM did not return to suspended: {state}')


def bars(frame, width, height, stride):
    def pixel(x, y):
        group, index = divmod(x, 4)
        start = y * stride + group * 5
        return (frame[start + index] << 2) | ((frame[start + 4] >> (2 * index)) & 3)

    expected = ((1, 1, 0, 0, 1, 1, 0, 0), (1, 1, 1, 1, 0, 0, 0, 0),
                (1, 1, 1, 1, 0, 0, 0, 0), (1, 0, 1, 0, 1, 0, 1, 0))
    columns = [((2 * index + 1) * width // 16) & ~1 for index in range(8)]
    levels = []
    for y in (2, (height // 2) & ~1, height - 4):
        observed = [[pixel(x + dx, y + dy) for x in columns] for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1))]
        dark = [value for values, bits in zip(observed, expected) for value, bit in zip(values, bits) if not bit]
        light = [value for values, bits in zip(observed, expected) for value, bit in zip(values, bits) if bit]
        # Verify the pattern order and contrast through startup. Absolute
        # black level for a real scene is a separate sensor calibration test.
        require(min(light) - max(dark) >= 700 and max(dark) - min(dark) <= 64
                and max(light) - min(light) <= 64, f'unexpected RGGB bars at row {y}: {observed}')
        levels.append({'row': y, 'dark': [min(dark), max(dark)], 'light': [min(light), max(light)]})
    return levels


DETAIL = re.compile(r'^(\d+)\.(\d{6}) \(([0-9.]+) fps\).*?\bseq:\s*(\d+)\s+bytesused:\s*(\d+)', re.M)
KNOWN_IDLE = re.compile(r'^qcom-camss fda0ac00\.camss: Missing ready buf [01] 4!$')


def parse_frames(text, size, count=FRAMES):
    frames = [{'timestamp_ns': int(sec) * 1_000_000_000 + int(usec) * 1000,
               'printed_fps': float(fps), 'sequence': int(sequence), 'bytesused': int(used)}
              for sec, usec, fps, sequence, used in DETAIL.findall(text)]
    require(len(frames) == count, 'frame record count mismatch')
    require(all(row['bytesused'] == size for row in frames), 'frame byte count mismatch')
    first = frames[0]['sequence']
    require([row['sequence'] for row in frames] == list(range(first, first + count)), 'delivered sequence gap')
    require(all(a['timestamp_ns'] < b['timestamp_ns'] for a, b in zip(frames, frames[1:])),
            'nonmonotonic buffer completion timestamps')
    return frames


def journal_anchor():
    text = command('journalctl', '-k', '-b', '-n', '1', '--show-cursor', '--no-pager')
    match = re.search(r'^-- cursor: (.+)$', text, re.M)
    require(match, 'kernel journal cursor unavailable')
    return match[1]


def journal_after(cursor):
    text = command('journalctl', '-k', '-b', '--after-cursor', cursor, '--no-pager', '-o', 'json')
    rows = []
    for line in text.splitlines():
        row = json.loads(line)
        require(isinstance(row.get('MESSAGE'), str), 'nontext kernel journal message')
        rows.append({'monotonic_usec': int(row['__MONOTONIC_TIMESTAMP']),
                     'priority': int(row['PRIORITY']), 'message': row['MESSAGE']})
    return rows


def issues(rows):
    result = []
    for row in rows:
        camera = re.search(r'camss|imx132|imx179|csid|csiphy|\bvfe\b|ispif|\bcci\b', row['message'], re.I)
        serious = re.search(r'underrun|context fault|iommu.*fault|kernel bug|oops:|kernel panic|watchdog', row['message'], re.I)
        if serious or row['priority'] <= 3 or (camera and row['priority'] <= 5):
            result.append(row)
    return result


def correlate(row, frames, exited_ns):
    when = row['monotonic_usec'] * 1000
    previous = [frame for frame in frames if frame['timestamp_ns'] <= when]
    following = [frame for frame in frames if frame['timestamp_ns'] > when]
    if not previous:
        phase = 'before first delivered buffer'
    elif following:
        phase = 'between delivered buffers'
    elif when <= exited_ns:
        phase = 'after last delivered buffer, before cam exit observed'
    else:
        phase = 'after cam exit observed'
    return row | {'phase': phase, 'previous_sequence': previous[-1]['sequence'] if previous else None,
                  'next_sequence': following[0]['sequence'] if following else None,
                  'bracketing_interval_ns': following[0]['timestamp_ns'] - previous[-1]['timestamp_ns']
                  if previous and following else None}


def capture_timed(directory, camera, write_frames):
    width, height, stride = 3280, 2464, 4104
    index, node, runtime = camera
    size = height * stride
    log = directory / 'cam.log'
    events = []
    def event(name, **values):
        events.append({'name': name, 'monotonic_ns': time.monotonic_ns()} | values)
    event('case_begin')
    cursor = journal_anchor()
    before_write = after_write = None
    power = None
    error = None
    exit_status = None
    exited_ns = None
    require(pattern(node) == 0, 'test pattern already enabled')
    try:
        args = ['cam', '-c', index, f'-C{FRAMES}', '-s', f'role=raw,width={width},height={height}']
        if write_frames:
            args.append('-F' + str(directory / 'frame-#'))
        event('cam_spawn_request')
        with log.open('w') as stream, subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT,
                                                       start_new_session=True) as child:
            event('cam_spawn_returned', PID=child.pid)
            deadline = time.monotonic() + 8
            observed_count = -1
            try:
                while child.poll() is None and time.monotonic() < deadline:
                    completed = len(FRAME_RECORD.findall(read(log)))
                    if completed != observed_count:
                        event('stdout_completion_count', count=completed)
                        observed_count = completed
                    if before_write is None and completed >= 4 and read(runtime) == 'active':
                        require(pattern(node) == 0, 'unexpected live test pattern')
                        before_write = completed
                        event('pattern_enable_begin', completed=completed)
                        command('v4l2-ctl', '-d', node, '-c', 'test_pattern=2')
                        require(pattern(node) == 2, 'live pattern write did not stick')
                        after_write = len(FRAME_RECORD.findall(read(log)))
                        event('pattern_enable_end', completed=after_write)
                        power = usb_power()
                    time.sleep(0.02)
                exit_status = child.poll()
                exited_ns = time.monotonic_ns()
                event('cam_exit_observed', returncode=exit_status)
                require(exit_status == 0, 'cam did not exit successfully within deadline')
            finally:
                if child.poll() is None:
                    os.killpg(child.pid, signal.SIGINT)
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        os.killpg(child.pid, signal.SIGKILL)
                        child.wait(timeout=2)
                    event('owned_cam_stopped', returncode=child.returncode)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
        error = type(failure).__name__ + ': ' + str(failure)
    finally:
        event('pattern_restore_begin')
        command('v4l2-ctl', '-d', node, '-c', 'test_pattern=0')
        require(pattern(node) == 0, 'test pattern not restored')
        event('pattern_restore_end')
    text = read(log) if log.exists() else ''
    sample = {'write_frames': write_frames, 'events': events, 'cam_stdout': text,
              'cam_exit_status': exit_status, 'capture_error': error, 'frame_records': [],
              'frames': 0, 'consecutive_pattern_frames': None,
              'test_pattern_restored': True, 'power_during_capture': power}
    try:
        require(error is None, error)
        require(before_write is not None and after_write is not None and power is not None, 'live pattern/USB observation missing')
        require_usb(power)
        frames = parse_frames(text, size)
        sample['frame_records'] = frames
        sample['frames'] = len(frames)
        intervals = [b['timestamp_ns'] - a['timestamp_ns'] for a, b in zip(frames, frames[1:])]
        median = statistics.median(intervals)
        sample.update(intervals_ns=intervals, median_interval_ns=median,
                      intervals_over_1_5_median=[i for i, value in enumerate(intervals) if value > median * 1.5])
        files = sorted(directory.glob('frame-*'))
        require(len(files) == (FRAMES if write_frames else 0), 'unexpected saved frame count')
        if write_frames:
            good = []
            for position, path in enumerate(files):
                require(path.stat().st_size == size, 'saved frame byte count')
                if position < before_write:
                    continue
                try:
                    bars(path.read_bytes(), width, height, stride)
                    good.append(position)
                except ValueError:
                    require(position < after_write + 4, 'missing bars after pattern settle')
            require(good and good == list(range(min(good), FRAMES)) and len(good) >= 12,
                    'insufficient consecutive sampled pattern frames')
            sample['consecutive_pattern_frames'] = len(good)
        sample['transfer_checks_passed'] = True
    except (OSError, ValueError) as failure:
        sample['transfer_checks_passed'] = False
        sample['capture_error'] = type(failure).__name__ + ': ' + str(failure)
    event('case_analysis_end')
    rows = journal_after(cursor)
    sample['kernel_messages'] = rows
    sample['kernel_issues'] = issues(rows)
    sample['correlated_kernel_issues'] = [correlate(row, sample['frame_records'], exited_ns or time.monotonic_ns())
                                          for row in sample['kernel_issues']]
    return sample


def trial_timed(boot, progress):
    cursor = journal_anchor()  # Before cam -l or any capture.
    report = {'initial': native_state(boot), 'cases': [], 'diagnostic_complete': False,
              'clean_kernel_window': False}
    shm = Path('/dev/shm')
    require(any(row.split()[1:3] == [str(shm), 'tmpfs'] for row in read('/proc/mounts').splitlines()), 'frames require tmpfs')
    require(not list(shm.glob(FRAME_PREFIX + '*')), 'prior owned frame workspace remains')
    require(shutil.disk_usage(shm).free >= 288 * 1024 * 1024, 'frame tmpfs headroom')
    require(int(re.search(r'^MemAvailable:\s+(\d+) kB$', read('/proc/meminfo'), re.M)[1]) >= 400 * 1024,
            'capture memory headroom')
    report['idle_camera_owner_PIDs'] = idle_camera_owners()
    cameras = find_cameras()
    report['initial_sensor_PM'] = idle(cameras)
    report['inventory_kernel_messages'] = journal_after(cursor)
    require(not issues(report['inventory_kernel_messages']), 'unexpected kernel diagnostic during camera discovery')
    progress(report)
    try:
        for index, write_frames in enumerate([True, False, True, False, True, False]):
            with tempfile.TemporaryDirectory(prefix=FRAME_PREFIX, dir=shm) as scratch:
                sample = capture_timed(Path(scratch), cameras['back'], write_frames)
            sample['case_index'] = index
            sample['sensors_PM_after_close'] = idle(cameras)
            report['cases'].append(sample)
            progress(report)
            require(sample['transfer_checks_passed'], sample['capture_error'])
            require(all(KNOWN_IDLE.fullmatch(row['message']) for row in sample['kernel_issues']),
                    'new kernel diagnostic; stopping remaining cases')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
        report['diagnostic_error'] = type(failure).__name__ + ': ' + str(failure)
    report['final_sensor_PM'] = idle(cameras)
    report['final'] = native_state(boot)
    report['patterns_after'] = {name: pattern(node) for name, (_, node, _) in cameras.items()}
    report['owned_frame_workspaces_after'] = len(list(shm.glob(FRAME_PREFIX + '*')))
    report['kernel_messages_in_full_window'] = journal_after(cursor)
    report['kernel_issues_in_full_window'] = issues(report['kernel_messages_in_full_window'])
    report['clean_kernel_window'] = not report['kernel_issues_in_full_window']
    report['diagnostic_complete'] = (len(report['cases']) == 6 and 'diagnostic_error' not in report and
                                     report['patterns_after'] == {'front': 0, 'back': 0} and
                                     report['owned_frame_workspaces_after'] == 0 and
                                     report['initial']['Sway_PID'] == report['final']['Sway_PID'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    def terminate(_signal, _frame):
        raise RuntimeError('bounded diagnostic service requested termination')
    signal.signal(signal.SIGTERM, terminate)
    progress_path = args.report.with_name('progress.json')
    def progress(result):
        temporary = progress_path.with_suffix('.new')
        temporary.write_text(json.dumps(result) + '\n')
        temporary.replace(progress_path)
    try:
        result = trial_timed(args.boot_id, progress)
    except BaseException as error:
        result = json.loads(progress_path.read_text()) if progress_path.exists() else {}
        result.update(diagnostic_complete=False, worker_error=type(error).__name__ + ': ' + str(error))
        with args.report.open('x') as stream:
            stream.write(json.dumps(result) + '\n')
        raise
    with args.report.open('x') as stream:
        stream.write(json.dumps(result) + '\n')
    print(json.dumps({'diagnostic_complete': result['diagnostic_complete'],
                      'clean_kernel_window': result['clean_kernel_window'], 'cases': len(result['cases'])}))
    raise SystemExit(0 if result['diagnostic_complete'] else 1)


if __name__ == '__main__':
    main()


