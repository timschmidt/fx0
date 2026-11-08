#!/usr/bin/env python3
"""Bounded awake SMD arming/event observation; run with other sensor consumers stopped."""
import argparse
import array
import csv
import fcntl
import json
import os
from pathlib import Path
import select
import signal
import struct
import subprocess


def irq_count():
    for line in Path('/proc/interrupts').read_text().splitlines():
        if 'inv_mpu' in line:
            counts = []
            for token in line.split(':', 1)[1].split():
                if not token.isdigit():
                    break
                counts.append(int(token))
            return sum(counts)
    raise RuntimeError('IMU IRQ counter not found')


def main():
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--announce-motion', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.seconds <= 120:
        parser.error('--seconds must be between 1 and 120')
    output = args.output.resolve()
    output.mkdir(mode=0o700, exist_ok=False)
    devices = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
               if (p / 'name').read_text().strip() == 'mpu6515']
    if len(devices) != 1:
        raise RuntimeError('expected one MPU6515')
    device = devices[0]
    enable = device / 'events/in_activity_still_change_falling_en'
    if enable.read_text().strip() != '0' or (device / 'buffer/enable').read_text().strip() != '0':
        raise RuntimeError('sensor is already in use')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    fd = os.open('/dev/' + device.name, os.O_RDONLY | os.O_NONBLOCK)
    event_fd = None
    result = {}
    try:
        value = array.array('i', [0])
        fcntl.ioctl(fd, 0x80046990, value, True)  # _IOR('i', 0x90, int)
        event_fd = value[0]
        os.set_blocking(event_fd, False)
        before = irq_count()
        enable.write_text('1\n')
        result['armed_readback'] = enable.read_text().strip()
        port = Path('/sys/kernel/debug/iio') / device.name / 'direct_reg_access'
        def register(address):
            port.write_text(f'0x{address:02x}\n')
            return int(port.read_text().strip(), 0)
        result['registers_armed'] = {hex(address): register(address) for address in (0x23, 0x38, 0x6a, 0x72, 0x73)}
        assert result['registers_armed']['0x23'] == 0
        assert result['registers_armed']['0x38'] == 2
        assert result['registers_armed']['0x6a'] & 0xc0 == 0x80
        assert result['registers_armed']['0x72'] == result['registers_armed']['0x73'] == 0

        result['runtime_status_armed'] = Path('/sys/bus/i2c/devices/0-0068/power/runtime_status').read_text().strip()
        if args.announce_motion:
            print('ARMED: physical motion window is open', flush=True)
        ready, _, _ = select.select([event_fd], [], [], args.seconds)
        events = []
        if ready:
            data = os.read(event_fd, 16 * 16)
            if len(data) % 16:
                raise RuntimeError('partial IIO event')
            for offset in range(0, len(data), 16):
                code, timestamp = struct.unpack_from('=Qq', data, offset)
                events.append({'code': hex(code), 'timestamp_ns': timestamp})
        if events and args.announce_motion:
            print('DMP EVENT RECEIVED', flush=True)
        result['events'] = events
        result['observation_seconds_requested'] = args.seconds
        result['irq_delta'] = irq_count() - before
        result['armed_after_interval'] = enable.read_text().strip()
    finally:
        try:
            enable.write_text('0\n')
        finally:
            if event_fd is not None:
                os.close(event_fd)
            os.close(fd)
    result['disabled_readback'] = enable.read_text().strip()
    result['raw_after'] = [int((device / f'in_accel_{axis}_raw').read_text()) for axis in 'xyz']
    reader = Path(__file__).with_name('read_quaternion.py')
    with (output / 'quaternion-after-smd.csv').open('x') as out, (output / 'quaternion-after-smd.log').open('x') as err:
        completed = subprocess.run(['python3', str(reader), '--seconds', '3'], stdout=out, stderr=err, timeout=30)
        out.flush(); os.fsync(out.fileno())
        err.flush(); os.fsync(err.fileno())
    if completed.returncode:
        raise RuntimeError((output / 'quaternion-after-smd.log').read_text())
    with (output / 'quaternion-after-smd.csv').open() as stream:
        result['quaternion_samples_after'] = len(list(csv.DictReader(stream)))
    result['boot_id_unchanged'] = Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
    result['scope'] = 'Awake arming/status observation only. No commanded physical motion or suspend/wake qualification.'
    with (output / 'manifest.json').open('x') as stream:
        json.dump(result, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
