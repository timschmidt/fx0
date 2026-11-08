#!/usr/bin/env python3
"""Root-only MPU6515 DMP RAM upload/readback diagnostic; never enables the DMP.

Uses the bound driver's mutex-protected debugfs register access with runtime
power held on. Refuses active buffers, motion events, FIFO or DMP execution.
The original RAM contents, register selection and service/power state are
restored. This is an upload-path check, not a firmware-execution or wake pass.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import signal
import os
import time

IMAGE_SHA256 = 'eabe2b79d93565358cca83864fece47d7dca5d5826bfbdab2d79ed75996076aa'
START = 0x20
SIZE = 2943
RAM_SIZE = 12 * 256
BANK = 0x6d
ADDRESS = 0x6e
DATA = 0x6f
USER_CTRL = 0x6a


def segments(address, length):
    if address < START or length <= 0 or address + length > RAM_SIZE:
        raise ValueError('transfer must remain in DMP RAM, excluding reserved bytes')
    while length:
        size = min(length, 256 - address % 256)
        yield address, size
        address += size
        length -= size


class RegisterPort:
    def __init__(self, path):
        self.path = path

    def read(self, register):
        self.path.write_text(f'0x{register:02x}\n')
        return int(self.path.read_text().strip(), 0)

    def write(self, register, value):
        self.path.write_text(f'0x{register:02x} 0x{value:02x}\n')


class Memory:
    def __init__(self, port):
        self.port = port

    def _select(self, address):
        self.port.write(BANK, address >> 8)
        self.port.write(ADDRESS, address & 255)

    def read(self, address, length):
        result = bytearray()
        for start, size in segments(address, length):
            for offset in range(size):
                # Debugfs performs a separate register transaction per read.
                # Do not assume the memory pointer survives that transaction.
                self._select(start + offset)
                result.append(self.port.read(DATA))
        return bytes(result)

    def write(self, address, data):
        offset = 0
        for start, size in segments(address, len(data)):
            for index, value in enumerate(data[offset:offset + size]):
                self._select(start + index)
                self.port.write(DATA, value)
            offset += size


def run(firmware, snapshot):
    image = firmware.read_bytes()
    if len(image) != SIZE or hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('not the pinned MPU6515 reference image')
    devices = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
               if (p / 'name').read_text().strip() == 'mpu6515']
    if len(devices) != 1:
        raise ValueError('expected exactly one bound MPU6515')
    device = devices[0]
    debug = Path('/sys/kernel/debug/iio') / device.name / 'direct_reg_access'
    control = Path('/sys/bus/i2c/devices/0-0068/power/control')
    # Require the board node rather than guessing another sensor/bus mapping.
    if device.resolve().parent != control.parent.parent.resolve():
        raise ValueError('MPU6515 is not on the verified Fx0 bus/address')
    previous_control = control.read_text().strip()
    service = 'iio-sensor-proxy.service'
    active = subprocess.run(['systemctl', 'is-active', '--quiet', service]).returncode == 0
    status = subprocess.run(['systemctl', 'is-enabled', service], capture_output=True, text=True)
    already_masked = status.stdout.strip().startswith('masked')
    if already_masked and active:
        raise RuntimeError("cannot restore an active, already-masked sensor service")
    masked_here = False
    original = None
    wrote = False
    restored = False
    registers = None
    port = RegisterPort(debug)
    started = time.monotonic()
    try:
        if not already_masked:
            masked_here = True
            subprocess.run(['systemctl', 'mask', '--runtime', '--now', service], check=True)
        else:
            subprocess.run(['systemctl', 'stop', service], check=True)
        control.write_text('on\n')
        if (control.parent / 'runtime_status').read_text().strip() != 'active':
            raise RuntimeError('runtime power did not resume')
        if (device / 'buffer/enable').read_text().strip() != '0':
            raise RuntimeError('raw capture buffer is active')
        if any(p.read_text().strip() != '0' for p in (device / 'events').glob('*_en')):
            raise RuntimeError('sensor events are active')
        if port.read(0x75) != 0x74:
            raise RuntimeError('unexpected WHO_AM_I')
        user_control = port.read(USER_CTRL)
        if user_control & 0xc0:
            raise RuntimeError('DMP or FIFO is already running')
        registers = (port.read(BANK), port.read(ADDRESS))
        if registers[0] & ~0x0f or registers[0] >= 12:
            raise RuntimeError('unexpected memory bank selection')
        memory = Memory(port)
        original = memory.read(START, SIZE)
        if memory.read(START, SIZE) != original:
            raise RuntimeError('DMP RAM is not stable while quiesced')
        fd = os.open(snapshot, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(original)
            f.flush()
            os.fsync(f.fileno())
        print('Saved private pre-write DMP RAM snapshot', flush=True)
        wrote = True  # Restore even if a write fails part way through.
        memory.write(START, image)
        if memory.read(START, SIZE) != image:
            raise RuntimeError('firmware RAM readback mismatch')
        print('Verified all reference image bytes in DMP RAM', flush=True)
        memory.write(START, original)
        if memory.read(START, SIZE) != original:
            raise RuntimeError('original RAM restoration mismatch')
        restored = True
        if port.read(USER_CTRL) != user_control or port.read(0x75) != 0x74:
            raise RuntimeError('unexpected engine or identity change')
    finally:
        try:
            try:
                if wrote and not restored and original is not None:
                    memory = Memory(port)
                    memory.write(START, original)
                    if memory.read(START, SIZE) != original:
                        raise RuntimeError('failed to restore original DMP RAM')
            finally:
                if registers is not None:
                    port.write(BANK, registers[0])
                    port.write(ADDRESS, registers[1])
        finally:
            control.write_text(previous_control + '\n')
            if masked_here:
                subprocess.run(['systemctl', 'unmask', '--runtime', service], check=True)
            if active:
                subprocess.run(['systemctl', 'start', service], check=True)
    return {'who_am_i': '0x74', 'firmware_bytes': len(image),
            'firmware_sha256': IMAGE_SHA256, 'all_banks_verified': True,
            'original_ram_restored': restored, 'dmp_enabled': False,
            'seconds': round(time.monotonic() - started, 3),
            'qualification': 'RAM transport only; no DMP execution, events or wake qualification.'}


def main():
    def interrupted(signum, frame):
        raise InterruptedError("DMP memory test interrupted")
    signal.signal(signal.SIGTERM, interrupted)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True, help='new private recovery file')
    args = parser.parse_args()
    print(json.dumps(run(args.firmware, args.snapshot), indent=2))


if __name__ == '__main__':
    main()
