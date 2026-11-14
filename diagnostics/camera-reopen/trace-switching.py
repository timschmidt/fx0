#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Trace the original five-session camera switching workload on the pinned r1 boot."""
import argparse
import hashlib
import importlib.util
import json
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
FAULT = re.compile(r'underrun|context fault|iommu.*fault|kernel bug|oops:|watchdog|'
                   r'(?:camss|imx132|imx179|csid|csiphy|vfe|ispif|cci).*(?:error|fail|timeout|overflow)', re.I)
NOTES_SHA = '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
FRAME_PREFIX = 'fx0-camera-trace-switching-01-'

spec = importlib.util.spec_from_file_location('owned_helpers', Path(__file__).with_name('pause-queue-test.py'))
helpers = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helpers)
OwnedClient = helpers.OwnedClient
from queue_trace import ROOT, TraceLease, private_json, parse_private_trace, verify_markers, recover_claim
classifier_spec = importlib.util.spec_from_file_location('kernel_classifier', Path(__file__).with_name('check-kernel-window.py'))
classifier = importlib.util.module_from_spec(classifier_spec)
classifier_spec.loader.exec_module(classifier)
INSTANCE = 'fx0-camera-switching-01'
WORKLOAD = [('front', None), ('back', None), ('front', None), ('back', None), ('back', (3280, 2464, 4104))]


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


def capture(directory, label, camera, geometry, mark):
    width, height, stride = geometry or CAMERAS[label][2:]
    index, node, runtime = camera
    size = height * stride
    log = directory / 'cam.log'
    power = None
    before_write = after_write = None
    require(pattern(node) == 0, f'{label} test pattern already enabled')
    try:
        args = ['cam', '-c', index, f'-C{FRAMES}', '-s', f'role=raw,width={width},height={height}',
                '-F' + str(directory / 'frame-#')]
        with log.open('w') as stream, subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True) as child:
            owner = None
            deadline = time.monotonic() + 8
            try:
                owner = OwnedClient(child)
                mark('CHILD_STARTED')
                while child.poll() is None and time.monotonic() < deadline:
                    if before_write is None:
                        completed = len(FRAME_RECORD.findall(read(log)))
                        if completed >= 4 and read(runtime) == 'active':
                            # Libcamera initialization clears the rear sensor's pattern.
                            require(pattern(node) == 0, 'unexpected live test pattern')
                            before_write = completed
                            mark('PATTERN_SET_BEGIN')
                            command('v4l2-ctl', '-d', node, '-c', 'test_pattern=2')
                            mark('PATTERN_SET_END')
                            require(pattern(node) == 2, 'live test pattern write did not stick')
                            after_write = len(FRAME_RECORD.findall(read(log)))
                            observed = usb_power()
                            if child.poll() is None:
                                power = observed
                    time.sleep(0.03)
                require(child.returncode == 0, f'{label} capture incomplete: {read(log)[-2000:]}')
            finally:
                if owner is not None:
                    owner.close()
                elif child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=2)
                mark('CHILD_EXITED')
    finally:
        command('v4l2-ctl', '-d', node, '-c', 'test_pattern=0')
        mark('PATTERN_RESTORED')
        require(pattern(node) == 0, 'test pattern was not restored')

    require(power is not None, 'capture completed before concurrent USB sample')
    require_usb(power)
    records = [(int(seq), int(used)) for seq, used in FRAME_RECORD.findall(read(log))]
    require(len(records) == FRAMES and all(used == size for _, used in records),
            f'{label} V4L2 frame accounting: {records}')
    first = records[0][0]
    require([seq for seq, _ in records] == list(range(first, first + FRAMES)), 'frame sequence gap')
    frames = sorted(directory.glob('frame-*'))
    require(len(frames) == FRAMES, f'{label} frame file count {len(frames)}')
    levels = {}
    for position, path in enumerate(frames):
        require(path.stat().st_size == size, f'{label} frame byte count')
        if position < before_write:
            continue
        try:
            levels[position] = bars(path.read_bytes(), width, height, stride)
        except ValueError:
            if position >= after_write + 4:
                raise ValueError(f'{label} missing color bars in frame {position}') from None
    require(levels and list(levels) == list(range(min(levels), FRAMES)) and len(levels) >= 12,
            f'{label} did not deliver twelve consecutive patterned frames')
    return {'camera': label, 'width': width, 'height': height, 'stride': stride,
            'frames': FRAMES, 'bytes_per_frame': size, 'first_sequence': first, 'last_sequence': records[-1][0],
            'completed_before_pattern_write': before_write, 'completed_after_pattern_write': after_write,
            'first_pattern_position': min(levels), 'consecutive_pattern_frames': len(levels),
            'last_frame_RGGB_bar_levels': levels[FRAMES - 1], 'power_during_capture': power,
            'test_pattern_restored': True, 'frames_timed': helpers.parse_frames(read(log), size)}



def alias_rows(rows):
    aliases, output = {}, []
    for row in rows:
        row = dict(row)
        token = row.pop('owner_private', None)
        if token is not None:
            aliases.setdefault(token, 'owner' + str(len(aliases) + 1))
            row['owner_alias'] = aliases[token]
        if row['event'].startswith('vb2_v4l2_'):
            require(row['minor'] == 0, 'unexpected video minor in filtered trace')
        elif row['event'].startswith('vb2_'):
            require(row['type'] == 9, 'unexpected buffer type in filtered trace')
        output.append(row)
    require(all('owner_private' not in row for row in output), 'raw owner token retained')
    return output


def session_evidence(rows, captures):
    result = []
    for index, capture_result in enumerate(captures):
        begin, end = 'CASE_' + str(index) + '_BEGIN', 'CASE_' + str(index) + '_END'
        starts = [row for row in rows if row.get('marker') == begin]
        ends = [row for row in rows if row.get('marker') == end]
        require(len(starts) == len(ends) == 1, 'session markers missing or duplicated')
        start, finish = starts[0]['trace_ns'], ends[0]['trace_ns']
        require(start < finish, 'session marker ordering')
        selected = [row for row in rows if start <= row['trace_ns'] <= finish]
        counts = {event: sum(row['event'] == event for row in selected)
                  for event in ['vb2_qbuf', 'vb2_dqbuf', 'vb2_buf_queue', 'vb2_buf_done',
                                'vb2_v4l2_buf_queue', 'vb2_v4l2_buf_done']}
        require(all(count > 0 for count in counts.values()), 'session trace event family missing')
        done = [row for row in selected if row['event'] == 'vb2_v4l2_buf_done']
        for frame in capture_result['frames_timed']:
            matches = [row for row in done if row['sequence'] == frame['sequence']
                       and 0 <= row['timestamp_ns'] - frame['timestamp_ns'] < 1000]
            require(len(matches) == 1, 'delivered buffer lacks unique trace timestamp/sequence match')
        result.append({'case': index, 'start_trace_ns': start, 'end_trace_ns': finish,
                       'event_counts': counts, 'delivered_frames_matched': len(capture_result['frames_timed'])})
    return result


def recover(workspace):
    record = workspace / 'trace.claim.json'
    trace = recover_claim(record) if record.exists() else {'not_created': True}
    require(not (ROOT / 'instances' / INSTANCE).exists(), 'owned trace instance remains')
    for claim in workspace.glob('frame-*.claim.json'):
        row = json.loads(claim.read_text())
        path = Path(row['path'])
        require(path.parent == Path('/dev/shm') and path.name.startswith(FRAME_PREFIX), 'invalid frame cleanup namespace')
        if path.exists():
            info = path.stat()
            require(not path.is_symlink() and (info.st_dev, info.st_ino) == (row['device'], row['inode']),
                    'frame cleanup identity changed')
            idle_camera_owners()
            shutil.rmtree(path)
    idle_camera_owners()
    nodes = sensor_nodes()
    restored = []
    for model, path in nodes.items():
        node = '/dev/' + path.name
        if pattern(node) != 0:
            command('v4l2-ctl', '-d', node, '-c', 'test_pattern=0')
            restored.append(model)
    for _ in range(25):
        if all(read(path / 'device/power/runtime_status') == 'suspended' for path in nodes.values()):
            break
        time.sleep(0.1)
    require(all(read(path / 'device/power/runtime_status') == 'suspended' for path in nodes.values()), 'sensor remains active')
    require(all(pattern('/dev/' + path.name) == 0 for path in nodes.values()), 'test pattern remains enabled')
    require(not list(Path('/dev/shm').glob(FRAME_PREFIX + '*')), 'owned frame workspace remains')
    private_json(workspace / 'stop-post.json', {'trace': trace, 'owned_instance_absent': True,
                                             'owned_frames_absent': True, 'sensors_idle_patterns_off': True, 'patterns_restored_by_recovery': restored})


def trial(boot, workspace):
    report = {'initial': native_state(boot), 'captures': [], 'passed': False}
    shm = Path('/dev/shm')
    require(any(row.split()[1:3] == [str(shm), 'tmpfs'] for row in read('/proc/mounts').splitlines()), 'frame storage is not tmpfs')
    require(not list(shm.glob(FRAME_PREFIX + '*')), 'prior owned frame workspace remains')
    require(shutil.disk_usage(shm).free >= 288 * 1024 * 1024, 'insufficient frame tmpfs space')
    available = int(re.search(r'^MemAvailable:\s+(\d+) kB$', read('/proc/meminfo'), re.M)[1])
    require(available >= 400 * 1024, 'insufficient memory headroom')
    report['idle_camera_owner_PIDs'] = idle_camera_owners()
    cursor = helpers.journal_anchor()
    lease = TraceLease(INSTANCE, workspace / 'trace.claim.json')
    try:
        with lease:
            lease.start()
            try:
                lease.marker('WORKLOAD_BEGIN')
                cameras = find_cameras()
                report['initial_camera_PM'] = idle(cameras)
                for index, (label, geometry) in enumerate(WORKLOAD):
                    prefix = 'CASE_' + str(index) + '_'
                    lease.marker(prefix + 'BEGIN')
                    with tempfile.TemporaryDirectory(prefix=FRAME_PREFIX, dir=shm) as scratch:
                        directory = Path(scratch)
                        info = directory.stat()
                        private_json(workspace / ('frame-' + str(index) + '.claim.json'),
                                     {'path': str(directory), 'device': info.st_dev, 'inode': info.st_ino})
                        try:
                            sample = capture(directory, label, cameras[label], geometry,
                                             lambda label: lease.marker(prefix + label))
                        finally:
                            if (directory / 'cam.log').exists():
                                shutil.copyfile(directory / 'cam.log', workspace / ('cam-' + str(index) + '.private.log'))
                    sample['PM_after_close'] = idle(cameras)
                    lease.marker(prefix + 'END')
                    report['captures'].append(sample)
                    private_json(workspace / 'progress.json', report)
                report['final_camera_PM'] = idle(cameras)
                report['camera_patterns_after'] = {name: pattern(node) for name, (_, node, _) in cameras.items()}
            finally:
                lease.marker('WORKLOAD_END')
                text, data = lease.stop_dump(workspace / 'queue.private.trace')
                report['trace_capture'] = data
                private_rows = parse_private_trace(text)
                report['trace_marker_count'] = verify_markers(private_rows)
                rows = alias_rows(private_rows)
                private_json(workspace / 'decoded.aliases.json', rows)
                require(data['no_lost_events'], 'trace loss detected')
                report['session_trace_evidence'] = session_evidence(rows, report['captures'])
    except BaseException as error:
        report['worker_error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        report['trace_cleanup'] = lease.cleanup
        report['buffer_sizing'] = lease.sizing
        report['kernel_messages'] = helpers.journal_after(cursor)
        report['kernel_classification'] = classifier.classify(report['kernel_messages'])
        report['owned_frame_workspaces_after'] = len(list(shm.glob(FRAME_PREFIX + '*')))
        report['final'] = native_state(boot)
        report['passed'] = (len(report['captures']) == 5 and 'worker_error' not in report
                            and report['kernel_classification']['clean_kernel_window']
                            and report['owned_frame_workspaces_after'] == 0
                            and report.get('camera_patterns_after') == {'front': 0, 'back': 0}
                            and report['initial']['Sway_PID'] == report['final']['Sway_PID'])
        private_json(workspace / 'result.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', required=True, type=Path)
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    boot = 'e134d38d-f8b1-4115-8bff-8e91f69d1d01'
    require(read('/proc/sys/kernel/random/boot_id') == boot, 'boot changed')
    require(hashlib.sha256((SYS / 'kernel/notes').read_bytes()).hexdigest() == NOTES_SHA, 'kernel changed')
    if args.recover:
        recover(args.workspace)
        return
    def stop(_signal, _frame):
        raise RuntimeError('bounded owned camera service stopped')
    signal.signal(signal.SIGTERM, stop)
    report = trial(boot, args.workspace)
    print(json.dumps({'passed': report['passed'], 'captures': len(report['captures'])}))
    raise SystemExit(0 if report['passed'] else 1)


if __name__ == '__main__':
    main()
