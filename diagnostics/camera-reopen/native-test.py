#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the two Fx0 camera pipelines with sensor-generated bars on native r50."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tempfile
import time

SYS = Path('/sys')
CAMERAS = {
    'front': ('imx132 3-0036', 'camera@36', 1976, 1200, 2472),
    'back': ('imx179 3-0010', 'camera@10', 1640, 1232, 2056),
}
FRAMES = 24
FRAME_RECORD = re.compile(r'\bseq:\s*(\d+)\s+bytesused:\s*(\d+)')
FAULT = re.compile(r'underrun|context fault|iommu.*fault|kernel bug|oops:|watchdog|'
                   r'(?:camss|imx132|imx179|csid|csiphy|vfe|ispif|cci).*(?:error|fail|timeout|overflow)', re.I)
NOTES_SHA = 'cb8ff4d80009dbd0b4542ce5d28d7ce10e4d84e0db4e332c749ff8ae18a08269'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return Path(path).read_text().strip()


def command(*args):
    result = subprocess.run(args, capture_output=True, text=True, timeout=8)
    require(result.returncode == 0, f'{args[0]} failed ({result.returncode}): {result.stderr.strip()}')
    return result.stdout.strip()


def find_cameras():
    listing = command('cam', '-l')
    nodes = {read(node / 'name'): node for node in (SYS / 'class/video4linux').glob('v4l-subdev*')}
    cameras = {}
    for label, (sensor, suffix, *_geometry) in CAMERAS.items():
        matches = re.findall(rf'^\s*(\d+):.*Internal {label} camera.*{suffix}\)', listing, re.MULTILINE)
        require(len(matches) == 1 and sensor in nodes, f'unexpected {label} camera inventory')
        cameras[label] = (matches[0], '/dev/' + nodes[sensor].name,
                          nodes[sensor] / 'device/power/runtime_status')
    require(len({row[0] for row in cameras.values()}) == 2, 'duplicate camera indices')
    return cameras


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
    require(boot == boot_id and command('uname', '-r') == '6.18.59-fx0-dmp', 'native r50 identity changed')
    require(hashlib.sha256((SYS / 'kernel/notes').read_bytes()).hexdigest() == NOTES_SHA,
            'kernel notes do not match installed r50')
    require(read('/proc/sys/kernel/tainted') == '0', 'kernel taint')
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


def capture(directory, label, camera):
    _, _, width, height, stride = CAMERAS[label]
    index, node, runtime = camera
    size = height * stride
    log = directory / 'cam.log'
    power = None
    before_write = after_write = None
    require(pattern(node) == 0, f'{label} test pattern already enabled')
    try:
        args = ['cam', '-c', index, f'-C{FRAMES}', '-s', f'role=raw,width={width},height={height}',
                '-F' + str(directory / 'frame-#')]
        with log.open('w') as stream, subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT) as child:
            deadline = time.monotonic() + 8
            try:
                while child.poll() is None and time.monotonic() < deadline:
                    if before_write is None:
                        completed = len(FRAME_RECORD.findall(read(log)))
                        if completed >= 4 and read(runtime) == 'active':
                            # Libcamera initialization clears the rear sensor's pattern.
                            require(pattern(node) == 0, 'unexpected live test pattern')
                            before_write = completed
                            command('v4l2-ctl', '-d', node, '-c', 'test_pattern=2')
                            require(pattern(node) == 2, 'live test pattern write did not stick')
                            after_write = len(FRAME_RECORD.findall(read(log)))
                            observed = usb_power()
                            if child.poll() is None:
                                power = observed
                    time.sleep(0.03)
                require(child.returncode == 0, f'{label} capture incomplete: {read(log)[-2000:]}')
            finally:
                if child.poll() is None:
                    child.send_signal(signal.SIGINT)
                    try:
                        child.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait(timeout=2)
    finally:
        command('v4l2-ctl', '-d', node, '-c', 'test_pattern=0')
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
            'test_pattern_restored': True}


def trial(boot):
    report = {'initial': native_state(boot), 'captures': []}
    shm = Path('/dev/shm')
    mounts = [row.split() for row in read('/proc/mounts').splitlines()]
    require(any(row[1:3] == [str(shm), 'tmpfs'] for row in mounts), 'frame storage is not tmpfs')
    require(shutil.disk_usage(shm).free >= 96 * 1024 * 1024, 'insufficient frame storage')
    cameras = find_cameras()
    report['initial_camera_PM'] = idle(cameras)
    anchor = command('journalctl', '-k', '-b', '-n', '1', '--show-cursor', '--no-pager')
    cursor = re.search(r'^-- cursor: (.+)$', anchor, re.MULTILINE)
    require(cursor, 'kernel journal cursor unavailable')
    try:
        for label in ('front', 'back', 'front', 'back'):
            with tempfile.TemporaryDirectory(prefix='fx0-camera-bars-', dir=shm) as scratch:
                sample = capture(Path(scratch), label, cameras[label])
            sample['PM_after_close'] = idle(cameras)
            report['captures'].append(sample)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        report['capture_error'] = str(error)
    report['final_camera_PM'] = idle(cameras)
    report['final'] = native_state(boot)
    report['camera_patterns_after'] = {name: pattern(node) for name, (_, node, _) in cameras.items()}
    log = command('journalctl', '-k', '-b', '--after-cursor', cursor[1], '--no-pager', '-o', 'short-monotonic')
    report['new_kernel_faults'] = [line for line in log.splitlines() if FAULT.search(line)]
    report['passed'] = (len(report['captures']) == 4 and not report['new_kernel_faults'] and
                        report['camera_patterns_after'] == {'front': 0, 'back': 0} and
                        report['initial']['Sway_PID'] == report['final']['Sway_PID'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True, help='current verified native r50 boot UUID')
    args = parser.parse_args()
    print(json.dumps(trial(args.boot_id)))


if __name__ == '__main__':
    main()
