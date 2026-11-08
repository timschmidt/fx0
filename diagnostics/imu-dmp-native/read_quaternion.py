#!/usr/bin/env python3
"""Bounded reader for the staged native MPU6515 quaternion ABI (not stock kernels)."""
import argparse
from decimal import Decimal
import os
from pathlib import Path
import select
import signal
import struct
import sys
import time


def restore_configuration(saved, scan_files):
    failures = []
    # IIO validates every set bit against available_scan_masks. Clear the
    # exclusive quaternion mask before re-enabling a saved raw mask.
    for path in scan_files:
        try:
            path.write_text('0\n')
        except OSError as error:
            failures.append(f'{path}: {error}')
    for path, value in saved.items():
        try:
            path.write_text(value + '\n')
        except OSError as error:
            failures.append(f'{path}: {error}')
    if failures:
        raise RuntimeError('capture configuration restore failed: ' + '; '.join(failures))


def capture(device, seconds):
    scan = device / 'scan_elements'
    quat = scan / 'in_rot_quaternion_en'
    stamp = scan / 'in_timestamp_en'
    expected = ('le' if sys.byteorder == 'little' else 'be') + ':s32/32X4>>0'
    if (scan / 'in_rot_quaternion_type').read_text().strip() != expected:
        raise RuntimeError('unexpected quaternion scan format')
    if (scan / 'in_timestamp_type').read_text().strip() != expected[:2] + ':s64/64>>0':
        raise RuntimeError('unexpected timestamp format')
    scale = Decimal((device / 'in_rot_quaternion_scale').read_text().strip())
    if scale != Decimal(1) / (1 << 30):
        raise RuntimeError('quaternion scale is not precise Q30; update the IIO formatter')
    enabled = device / 'buffer/enable'
    if enabled.read_text().strip() != '0':
        raise RuntimeError('capture buffer is already in use')
    events = device / 'events/in_accel_x|y|z_roc_rising_en'
    if events.exists() and events.read_text().strip() != '0':
        raise RuntimeError('disable ordinary wake-on-motion before DMP capture')
    scan_files = list(scan.glob('*_en'))
    files = scan_files + [device / 'buffer/length']
    saved = {p: p.read_text().strip() for p in files}
    trigger = device / 'trigger/current_trigger'
    saved[trigger] = trigger.read_text().strip()
    fd = None
    pending = bytearray()
    samples = 0
    last = None
    try:
        for path in scan.glob('*_en'):
            path.write_text('0\n')
        quat.write_text('1\n')
        stamp.write_text('1\n')
        trigger.write_text('mpu6515-dev' + device.name.split('device')[1] + '\n')
        (device / 'buffer/length').write_text('64\n')
        fd = os.open('/dev/' + device.name, os.O_RDONLY | os.O_NONBLOCK)
        enabled.write_text('1\n')
        end = time.monotonic() + seconds
        print('timestamp_ns,w,x,y,z', flush=True)
        while time.monotonic() < end:
            ready, _, _ = select.select([fd], [], [], min(0.2, max(0, end-time.monotonic())))
            if not ready:
                continue
            try:
                data = os.read(fd, 32 * 64)
            except BlockingIOError:
                continue
            if not data:
                raise RuntimeError('IIO device closed during capture')
            pending.extend(data)
            while len(pending) >= 32:
                w, x, y, z, timestamp = struct.unpack_from('=iiii8xq', pending)
                del pending[:32]
                if last is not None and timestamp <= last:
                    raise RuntimeError('nonmonotonic quaternion timestamp')
                last = timestamp
                print(f'{timestamp},{w/2**30:.9f},{x/2**30:.9f},{y/2**30:.9f},{z/2**30:.9f}', flush=True)
                samples += 1
        if not samples or pending:
            raise RuntimeError('no complete capture or incomplete final scan')
        return samples
    finally:
        try:
            enabled.write_text('0\n')
        finally:
            if fd is not None:
                os.close(fd)
            restore_configuration(saved, scan_files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seconds', type=float, default=5)
    args = parser.parse_args()
    if not 0.5 <= args.seconds <= 60:
        parser.error('--seconds must be between 0.5 and 60')
    devices = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
               if (p / 'name').read_text().strip() == 'mpu6515'
               and (p / 'scan_elements/in_rot_quaternion_en').exists()]
    if len(devices) != 1:
        parser.error('expected exactly one MPU6515 with native quaternion channel')
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    print(f'# {capture(devices[0], args.seconds)} samples', file=sys.stderr)


if __name__ == '__main__':
    main()
