#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure camera recovery from an explicitly owned client pause on pinned r1."""


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


FRAME_PREFIX = 'fx0-camera-pause-r1-01-'


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


class OwnedClient:
    """Pin one Popen child by pidfd and verify its private session before group cleanup."""
    def __init__(self, child, stop_timeout=2):
        require(isinstance(child, subprocess.Popen), 'expected owned Popen child')
        require(0 < stop_timeout <= 2, 'invalid child cleanup deadline')
        require(child.poll() is None, 'child already exited')
        require(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'pidfd support required')
        self.child = child
        self.stop_timeout = stop_timeout
        self.paused = False
        self.closed = False
        self.pidfd = None
        self.identity = self._identity()
        require(self.identity[0:3] == (os.getpid(), child.pid, child.pid), 'child lacks its own owned session')
        try:
            self.pidfd = os.pidfd_open(child.pid, 0)
            self._verify()
        except BaseException:
            if self.pidfd is not None:
                os.close(self.pidfd)
            raise

    def _stat(self):
        text = Path('/proc', str(self.child.pid), 'stat').read_text()
        fields = text[text.rindex(')') + 2:].split()
        return fields

    def _identity(self):
        fields = self._stat()
        return (int(fields[1]), int(fields[2]), int(fields[3]), int(fields[19]))

    def _verify(self):
        require(not self.closed and self.child.poll() is None, 'owned child is not live')
        require(self._identity() == self.identity, 'owned child identity changed')

    def _signal(self, number):
        signal.pidfd_send_signal(self.pidfd, number)

    def pause(self):
        self._verify()
        require(not self.paused, 'child already paused')
        self._signal(signal.SIGSTOP)
        self.paused = True
        deadline = time.monotonic() + 1
        while time.monotonic() < deadline:
            self._verify()
            if self._stat()[0] in ('T', 't'):
                return
            time.sleep(0.001)
        raise RuntimeError('owned child did not acknowledge stop')

    def resume(self):
        if not self.paused:
            return
        try:
            self._signal(signal.SIGCONT)
        except ProcessLookupError:
            require(self.child.poll() is not None, 'lost live owned child')
        self.paused = False
        deadline = time.monotonic() + 1
        while self.child.poll() is None and time.monotonic() < deadline:
            self._verify()
            if self._stat()[0] not in ('T', 't'):
                return
            time.sleep(0.001)
        require(self.child.poll() is not None, 'owned child did not acknowledge resume')

    def close(self):
        if self.closed:
            return
        try:
            self.resume()
            if self.child.poll() is None:
                self._group_signal_if_live(signal.SIGINT)
                try:
                    self.child.wait(timeout=self.stop_timeout)
                except subprocess.TimeoutExpired:
                    self._group_signal_if_live(signal.SIGKILL)
                    self.child.wait(timeout=self.stop_timeout)
        except BaseException:
            # Even a failed resume/identity check must not leave our pinned
            # primary child stopped. Never use an unverified group here.
            if self.child.poll() is None:
                for number in (signal.SIGCONT, signal.SIGKILL):
                    try:
                        self._signal(number)
                    except ProcessLookupError:
                        pass
                self.child.wait(timeout=self.stop_timeout)
            raise
        finally:
            os.close(self.pidfd)
            self.closed = True

    def _group_signal_if_live(self, number):
        if self.child.poll() is not None:
            return
        try:
            self._verify()
        except (ValueError, FileNotFoundError):
            if self.child.poll() is not None:
                return
            raise
        try:
            os.killpg(self.child.pid, number)
        except ProcessLookupError:
            pass

    def __enter__(self):
        return self

    def __exit__(self, *_exception):
        self.close()


def correlate_pause(row, frames, exited_ns, events):
    result = correlate(row, frames, exited_ns)
    names = {event['name']: event['monotonic_ns'] for event in events}
    when = row['monotonic_usec'] * 1000
    if 'unpaused_control' in names:
        phase = 'unpaused control'
    elif not all(name in names for name in ['pause_request', 'pause_acknowledged', 'resume_request', 'resume_acknowledged']):
        phase = 'pause timing incomplete'
    elif when < names['pause_request']:
        phase = 'before pause request'
    elif when < names['pause_acknowledged']:
        phase = 'stop acknowledgement pending'
    elif when <= names['resume_request']:
        phase = 'client confirmed stopped'
    elif when <= names['resume_acknowledged']:
        phase = 'resume acknowledgement pending'
    else:
        phase = 'after resume acknowledged'
    return result | {'client_pause_phase': phase}


def capture_pause(directory, camera, inject_pause):
    width, height, stride = 3280, 2464, 4104
    index, node, runtime = camera
    log = directory / 'cam.log'
    events = []
    def event(name, **values):
        events.append({'name': name, 'monotonic_ns': time.monotonic_ns()} | values)
    event('case_begin')
    cursor = journal_anchor()
    before_write = after_write = None
    intervention_done = False
    power = None
    error = None
    exit_status = exited_ns = None
    require(pattern(node) == 0, 'test pattern already enabled')
    try:
        args = ['cam', '-c', index, f'-C{FRAMES}', '-s', f'role=raw,width={width},height={height}']
        event('cam_spawn_request')
        with log.open('w') as stream:
            child = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            try:
                owned = OwnedClient(child)
            except BaseException:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=2)
                raise
            with owned:
                event('cam_spawn_returned', PID=child.pid, PGID=owned.identity[1], SID=owned.identity[2],
                      start_ticks=owned.identity[3])
                deadline = time.monotonic() + 8
                observed_count = -1
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
                    if not intervention_done and completed >= 8 and before_write is not None:
                        require(completed <= FRAMES - 8, 'insufficient buffers remain for matched intervention')
                        if inject_pause:
                            event('pause_request', completed=completed)
                            owned.pause()
                            event('pause_acknowledged')
                            try:
                                time.sleep(0.250)
                            finally:
                                event('resume_request')
                                owned.resume()
                                event('resume_acknowledged')
                        else:
                            event('unpaused_control', completed=completed)
                        intervention_done = True
                    time.sleep(0.01)
                exit_status = child.poll()
                exited_ns = time.monotonic_ns()
                event('cam_exit_observed', returncode=exit_status)
                require(exit_status == 0, 'cam did not exit within capture deadline')
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as failure:
        error = type(failure).__name__ + ': ' + str(failure)
    finally:
        event('pattern_restore_begin')
        command('v4l2-ctl', '-d', node, '-c', 'test_pattern=0')
        require(pattern(node) == 0, 'test pattern not restored')
        event('pattern_restore_end')
    text = read(log) if log.exists() else ''
    sample = {'inject_pause': inject_pause, 'events': events, 'cam_stdout': text,
              'cam_exit_status': exit_status, 'capture_error': error, 'frame_records': [], 'frames': 0,
              'test_pattern_restored': True, 'power_during_capture': power}
    try:
        require(error is None, error)
        require(intervention_done and power is not None and after_write is not None, 'missing live intervention/control sample')
        require_usb(power)
        frames = parse_frames(text, height * stride)
        sample['frame_records'] = frames
        sample['frames'] = len(frames)
        intervals = [b['timestamp_ns'] - a['timestamp_ns'] for a, b in zip(frames, frames[1:])]
        median = statistics.median(intervals)
        sample.update(intervals_ns=intervals, median_interval_ns=median,
                      intervals_over_1_5_median=[i for i, value in enumerate(intervals) if value > median * 1.5])
        require(not list(directory.glob('frame-*')), 'unexpected frame file output')
        sample['transfer_checks_passed'] = True
    except (OSError, ValueError) as failure:
        sample.update(transfer_checks_passed=False, capture_error=type(failure).__name__ + ': ' + str(failure))
    event('case_analysis_end')
    rows = journal_after(cursor)
    sample['kernel_messages'] = rows
    sample['kernel_issues'] = issues(rows)
    sample['correlated_kernel_issues'] = [correlate_pause(row, sample['frame_records'], exited_ns or time.monotonic_ns(), events)
                                          for row in sample['kernel_issues']]
    return sample


def trial_pause(boot, progress):
    require(hasattr(os, 'pidfd_open') and hasattr(signal, 'pidfd_send_signal'), 'native pidfd support required')
    cursor = journal_anchor()
    report = {'initial': native_state(boot), 'cases': [], 'diagnostic_complete': False, 'clean_kernel_window': False}
    shm = Path('/dev/shm')
    require(any(row.split()[1:3] == [str(shm), 'tmpfs'] for row in read('/proc/mounts').splitlines()), 'log storage requires tmpfs')
    require(not list(shm.glob(FRAME_PREFIX + '*')), 'prior owned workspace remains')
    require(int(re.search(r'^MemAvailable:\s+(\d+) kB$', read('/proc/meminfo'), re.M)[1]) >= 400 * 1024,
            'capture memory headroom')
    report['idle_camera_owner_PIDs'] = idle_camera_owners()
    cameras = find_cameras()
    report['initial_sensor_PM'] = idle(cameras)
    report['inventory_kernel_messages'] = journal_after(cursor)
    require(not issues(report['inventory_kernel_messages']), 'unexpected diagnostic during discovery')
    progress(report)
    try:
        for index, pause in enumerate([False, True, False, True, False, True]):
            with tempfile.TemporaryDirectory(prefix=FRAME_PREFIX, dir=shm) as scratch:
                sample = capture_pause(Path(scratch), cameras['back'], pause)
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
        result = trial_pause(args.boot_id, progress)
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
