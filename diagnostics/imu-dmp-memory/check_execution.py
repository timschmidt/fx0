#!/usr/bin/env python3
"""Bounded MPU6515 DMP execution/FIFO diagnostic, with interrupts masked.

Protocol constants follow the manufacturer MPU6515 driver at Android kernel
commit 04a77e80d63a6b792970c8567447f70d76ac7be4. No firmware is embedded here.
This is not a production IIO ABI or system-suspend wake implementation.
"""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import signal
import struct
import subprocess
import time

from check_memory import Memory, RegisterPort, START, SIZE, RAM_SIZE, IMAGE_SHA256

REGS = (0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x23, 0x38,
        0x6a, 0x6b, 0x6c, 0x6d, 0x70, 0x71)
RUN_COUNTER = 384


class FifoDecoder:
    def __init__(self):
        self.pending = bytearray()
        self.accel = []
        self.quaternion_xyz = []

    def feed(self, data):
        self.pending.extend(data)
        while len(self.pending) >= 2:
            header = struct.unpack_from('>H', self.pending)[0] & 0xfff0
            if header not in (0x4000, 0x0400):
                raise ValueError(f'unexpected DMP FIFO header 0x{header:04x}')
            size = 8 if header == 0x4000 else 16
            if len(self.pending) < size:
                break
            if header == 0x4000:
                self.accel.append(struct.unpack_from('>hhh', self.pending, 2))
            else:
                self.quaternion_xyz.append(struct.unpack_from('>iii', self.pending, 4))
            del self.pending[:size]


def count_fifo(port):
    for _ in range(4):
        high = port.read(0x72)
        low = port.read(0x73)
        if high == port.read(0x72):
            return (high << 8) | low
    raise RuntimeError('FIFO count is changing too quickly to read coherently')


def private_write(path, data):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'wb') as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())


def restore_registers(port, saved):
    for reg in REGS:
        if reg != 0x38:
            port.write(reg, saved[reg])
    port.write(0x38, saved[0x38])
    # MEM_START_ADDR is an auto-advancing cursor, not a readback control.
    # Reading it increments it (confirmed independently on this MPU6515).
    # Address every memory transfer explicitly and leave a canonical cursor.
    port.write(0x6e, 0)
    actual = {reg: port.read(reg) for reg in saved}
    different = {hex(reg): {'expected': value, 'actual': actual[reg]}
                 for reg, value in saved.items() if actual[reg] != value}
    if different:
        raise RuntimeError('configuration restoration failed: ' + json.dumps(different))


@contextmanager
def session(snapshot):
    devices = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
               if (p / 'name').read_text().strip() == 'mpu6515']
    if len(devices) != 1:
        raise RuntimeError('expected one bound MPU6515')
    device = devices[0]
    control = Path('/sys/bus/i2c/devices/0-0068/power/control')
    if device.resolve().parent != control.parent.parent.resolve():
        raise RuntimeError('not the verified Fx0 I2C sensor')
    policy = control.read_text().strip()
    service = 'iio-sensor-proxy.service'
    active = subprocess.run(['systemctl', 'is-active', '--quiet', service]).returncode == 0
    state = subprocess.run(['systemctl', 'is-enabled', service], text=True, capture_output=True)
    masked = state.stdout.strip().startswith('masked')
    if masked and active:
        raise RuntimeError('cannot restore an active, already-masked service')
    port = RegisterPort(Path('/sys/kernel/debug/iio') / device.name / 'direct_reg_access')
    mem = Memory(port)
    ctx = {'port': port, 'memory': mem, 'ram_changed': False, 'restored': False}
    saved_regs = None
    saved_ram = None
    mask_created = False
    try:
        if not masked:
            mask_created = True
            subprocess.run(['systemctl', 'mask', '--runtime', '--now', service], check=True)
        else:
            subprocess.run(['systemctl', 'stop', service], check=True)
        control.write_text('on\n')
        if (control.parent / 'runtime_status').read_text().strip() != 'active':
            raise RuntimeError('runtime power is not active')
        if (device / 'buffer/enable').read_text().strip() != '0':
            raise RuntimeError('raw capture is active')
        if any(p.read_text().strip() != '0' for p in (device / 'events').glob('*_en')):
            raise RuntimeError('motion events are active')
        if port.read(0x75) != 0x74:
            raise RuntimeError('wrong sensor identity')
        if port.read(0x6a) != 0 or port.read(0x38) != 0:
            raise RuntimeError('sensor engine, FIFO or interrupts already configured')
        if count_fifo(port):
            raise RuntimeError('FIFO is not empty before test')
        saved_regs = {reg: port.read(reg) for reg in REGS}
        saved_ram = mem.read(START, RAM_SIZE - START)
        if mem.read(START, len(saved_ram)) != saved_ram:
            raise RuntimeError('DMP RAM is not stable while quiesced')
        private_write(snapshot, saved_ram)
        private_write(Path(str(snapshot) + ".registers.json"),
                      json.dumps(saved_regs, sort_keys=True).encode())
        print('Saved full writable DMP RAM recovery snapshot', flush=True)
        yield ctx
    finally:
        try:
            if saved_regs is not None:
                try:
                    port.write(0x38, 0)
                    port.write(0x6a, 0)
                    port.write(0x6c, 0x3f)
                    port.write(0x6a, 0x04)  # Discard only this test's FIFO.
                    time.sleep(0.005)
                    port.write(0x6a, 0)
                    if ctx['ram_changed']:
                        mem.write(START, saved_ram)
                        if mem.read(START, len(saved_ram)) != saved_ram:
                            raise RuntimeError('full DMP RAM restoration failed')
                finally:
                    restore_registers(port, saved_regs)
                ctx['restored'] = True
        finally:
            try:
                control.write_text(policy + '\n')
            finally:
                if mask_created:
                    subprocess.run(['systemctl', 'unmask', '--runtime', service], check=True)
                if active:
                    subprocess.run(['systemctl', 'start', service], check=True)


def configure(mem):
    # Identity sensor frame; mounting conversion belongs to the eventual ABI.
    writes = [(1127, bytes([0x4c, 0xcd, 0x6c])),
              (1152, bytes([0x36, 0x56, 0x76])),
              (1131, bytes([0x0c, 0xc9, 0x2c])),
              (1138, bytes([0x26, 0x46, 0x66]))]
    # Only accelerometer and 6-axis quaternion output, at 25 Hz each.
    for addr, on, off in [(1770, True, 0x12), (1804, False, 0x12),
                          (1666, False, 0x13), (1701, True, 0x13),
                          (1736, False, 0x12), (1838, False, 0x12),
                          (1872, False, 0x12), (1636, False, 0x0e)]:
        writes.append((addr, bytes([0xa3, 0xa3]) if on else bytes([0xf4, off])))
    writes += [(1983, b'\xfe'), (2807, b'\xf4\x03'),
               (744, b'\x00\x07'), (736, bytes(2)),
               (730, b'\x00\x07'), (722, bytes(2)),
               (454, bytes(2)), (452, bytes(2)), (436, bytes(4)),
               (RUN_COUNTER, bytes(4)), (456, bytes(4))]
    for addr, data in writes:
        mem.write(addr, data)
        if mem.read(addr, len(data)) != data:
            raise RuntimeError(f'DMP configuration readback failed at 0x{addr:x}')


def run(firmware, snapshot, capture, seconds):
    image = firmware.read_bytes()
    if len(image) != SIZE or hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('not the pinned reference image')
    if not 0.5 <= seconds <= 5:
        raise ValueError('execution interval must be 0.5 to 5 seconds')
    if capture.exists() or snapshot.exists():
        raise FileExistsError('recovery/capture outputs must be new files')
    decoder = FifoDecoder()
    raw = bytearray()
    started = time.monotonic()
    with session(snapshot) as ctx:
        port, mem = ctx['port'], ctx['memory']
        ctx['ram_changed'] = True
        mem.write(START, image)
        if mem.read(START, SIZE) != image:
            raise RuntimeError('image readback failed')
        configure(mem)
        print('Verified image and bounded output configuration', flush=True)
        read_counter = lambda: int.from_bytes(mem.read(RUN_COUNTER, 4), 'big')
        off_before = read_counter()
        time.sleep(0.15)
        off_after = read_counter()
        if off_before != off_after:
            raise RuntimeError('run counter changed with DMP disabled')
        # 1 kHz / (4 + 1), 188 Hz gyro LPF, 2000 dps, 2 g, 1 KiB FIFO.
        for reg, value in [(0x19, 4), (0x1a, 1), (0x1b, 0x18), (0x1c, 0),
                           (0x1d, 0x40), (0x23, 0), (0x38, 0),
                           (0x70, 0x04), (0x71, 0x00), (0x6b, 0x09), (0x6c, 0)]:
            port.write(reg, value)
        time.sleep(0.05)
        port.write(0x6a, 0x0c)
        time.sleep(0.01)
        port.write(0x6a, 0xc0)
        end = time.monotonic() + seconds
        max_fifo = 0
        while time.monotonic() < end:
            count = count_fifo(port)
            max_fifo = max(max_fifo, count)
            if count >= 992:
                raise RuntimeError('DMP FIFO overflow risk')
            if count:
                data = bytes(port.read(0x74) for _ in range(count))
                raw.extend(data)
                decoder.feed(data)
            time.sleep(0.02)
        on_counter = read_counter()
        port.write(0x6a, 0)
        port.write(0x6a, 0x04)
        time.sleep(0.01)
        port.write(0x6a, 0)
        stopped_before = read_counter()
        time.sleep(0.15)
        stopped_after = read_counter()
        private_write(capture, raw)
        result = {'disabled_counter_before': off_before, 'disabled_counter_after': off_after,
                  'running_counter': on_counter, 'stopped_counter_before': stopped_before,
                  'stopped_counter_after': stopped_after, 'fifo_bytes': len(raw),
                  'max_fifo_bytes': max_fifo, 'accel_packets': len(decoder.accel),
                  'six_axis_quaternion_packets': len(decoder.quaternion_xyz),
                  'partial_packet_bytes': len(decoder.pending), 'interrupts_enabled': False,
                  'accel_sample': decoder.accel[0] if decoder.accel else None,
                  'quaternion_xyz_sample': decoder.quaternion_xyz[0] if decoder.quaternion_xyz else None}
        print(json.dumps(result), flush=True)
        if on_counter <= off_after or stopped_before != stopped_after:
            raise RuntimeError('DMP execution counter control failed')
        if len(decoder.accel) < 3 or len(decoder.quaternion_xyz) < 3:
            raise RuntimeError('insufficient decoded DMP output')
    result['ram_and_config_restored'] = ctx['restored']
    result['memory_cursor_canonicalized'] = True
    result['seconds_total'] = round(time.monotonic() - started, 3)
    result['qualification'] = 'Bounded DMP execution and decoded FIFO only; no IIO ABI or wake pass.'
    return result


def main():
    def interrupted(signum, frame):
        raise InterruptedError('DMP execution test interrupted')
    for sig in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(sig, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    for arg in ('firmware', 'snapshot', 'capture'):
        parser.add_argument('--' + arg, type=Path, required=True)
    parser.add_argument('--seconds', type=float, default=2)
    args = parser.parse_args()
    print(json.dumps(run(args.firmware, args.snapshot, args.capture, args.seconds), indent=2))


if __name__ == '__main__':
    main()
