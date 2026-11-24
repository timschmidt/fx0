#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Bounded regular-file O_DIRECT integrity trial on the installed Fx0 root.

No block device is opened for writing. The synthetic payload is retained for
a separately authorized boot/persistence check, then explicit cleanup.
"""
import argparse
import datetime
import hashlib
import json
import mmap
import os
from pathlib import Path
import struct
import time
import uuid

BLOCK = 1024 * 1024
SECTOR = 512
FILE_BYTES = 512 * BLOCK
ROUNDS = 4
RESERVE = 2 * 1024 * BLOCK
MAX_SECONDS = 15 * 60


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def pattern(run_id, round_, block):
    """Every 512-byte sector has a run/round/absolute-sector tag."""
    token = uuid.UUID(run_id).bytes
    template = hashlib.shake_256(b'fx0-emmc-v1' + token + struct.pack('<I', round_)).digest(SECTOR)
    data = bytearray(template * (BLOCK // SECTOR))
    for at in range(0, BLOCK, SECTOR):
        struct.pack_into('<8s16sIIQ', data, at, b'FX0EMMC1', token, round_,
                         round_ ^ 0xffffffff, (block * BLOCK + at) // SECTOR)
    return data


def write_round(fd, run_id, round_, blocks, progress):
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    with mmap.mmap(-1, BLOCK) as buffer:
        for block in range(blocks):
            buffer[:] = pattern(run_id, round_, block)
            require(os.write(fd, buffer) == BLOCK, 'short direct write')
            digest.update(buffer)
            progress('write', (block + 1) * BLOCK)
    os.fsync(fd)
    return digest.hexdigest()


def read_round(fd, run_id, round_, blocks, progress):
    digest = hashlib.sha256()
    os.lseek(fd, 0, os.SEEK_SET)
    with mmap.mmap(-1, BLOCK) as buffer:
        for block in range(blocks):
            require(os.readv(fd, [buffer]) == BLOCK, 'short direct read')
            expected = pattern(run_id, round_, block)
            if buffer[:] != expected:
                offset = next(i for i, (actual, wanted) in enumerate(zip(buffer[:], expected)) if actual != wanted)
                raise RuntimeError('payload mismatch at byte ' + str(block * BLOCK + offset))
            digest.update(buffer)
            progress('read', (block + 1) * BLOCK)
    require(os.fstat(fd).st_size == blocks * BLOCK, 'payload length changed')
    return digest.hexdigest()


def native_snapshot(expected_boot):
    require(os.uname().release == '6.18.59-fx0-dmp', 'unexpected installed kernel')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    require(boot == expected_boot, 'native boot changed')
    require(Path('/proc/sys/kernel/tainted').read_text().strip() == '0', 'kernel tainted')
    root = [line.split() for line in Path('/proc/mounts').read_text().splitlines() if line.split()[1] == '/']
    require(len(root) == 1 and root[0][0:3] == ['/dev/mmcblk0p35', '/', 'ext4'] and 'rw' in root[0][3].split(','), 'unexpected native root mount')
    require(Path('/sys/class/block/mmcblk0/removable').read_text().strip() == '0', 'root disk is removable')
    require(Path('/sys/class/block/mmcblk0p35/start').read_text().strip() == '786432', 'root partition moved')
    require(Path('/sys/class/block/mmcblk0p35/size').read_text().strip() == '29990879', 'root partition resized')
    policy = Path('/sys/devices/system/cpu/cpufreq/policy0')
    require([(policy / name).read_text().strip() for name in ['scaling_governor', 'scaling_min_freq', 'scaling_max_freq']] == ['schedutil', '300000', '787200'], 'native CPU policy changed')
    require(Path('/sys/class/power_supply/smbb-usbin/online').read_text().strip() == '1', 'USB input absent')
    temps = [int(path.read_text()) for path in sorted(Path('/sys/class/thermal').glob('thermal_zone*/temp'))]
    require(len(temps) == 2 and all(-40000 <= temp < 60000 for temp in temps), 'temperature outside trial bounds')
    return {'boot_id': boot, 'temperatures_mC': temps,
            'mmc_stat': list(map(int, Path('/sys/class/block/mmcblk0/stat').read_text().split())),
            'ext4_errors': int(Path('/sys/fs/ext4/mmcblk0p35/errors_count').read_text())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    require(str(uuid.UUID(args.run_id)) == args.run_id, 'noncanonical run ID')
    require(str(uuid.UUID(args.boot_id)) == args.boot_id, 'noncanonical boot ID')
    directory = Path('/var/tmp') / ('fx0-emmc-integrity-' + args.run_id)
    require(Path(__file__).absolute().parent == directory, 'worker outside its exact trial directory')
    require(directory.resolve() == directory, 'trial path contains a symlink')
    require(os.stat(directory).st_dev == os.stat('/').st_dev, 'trial directory is not on the native root')
    require(os.stat(directory).st_uid == 0 and os.stat(directory).st_mode & 0o777 == 0o700, 'trial directory ownership/mode')
    started = time.monotonic()
    report = {'run_id': args.run_id, 'initial_boot_id': args.boot_id,
              'worker_PID': os.getpid(),
              'started_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'state': 'preflight', 'file_bytes': FILE_BYTES, 'rounds_required': ROUNDS,
              'rounds': [], 'samples': [], 'O_DIRECT': True,
              'raw_block_device_writes': False, 'cross_boot_persistence': 'not yet tested'}
    def save():
        temporary = directory / 'result.json.new'
        temporary.write_text(json.dumps(report, indent=2) + '\n')
        temporary.replace(directory / 'result.json')
    save()
    directory_fd = None
    fd = None
    try:
        initial = native_snapshot(args.boot_id)
        report['before'] = initial
        require(initial['ext4_errors'] == 0, 'existing filesystem errors')
        space = os.statvfs(directory)
        report['available_bytes_before'] = space.f_bavail * space.f_frsize
        require(report['available_bytes_before'] >= FILE_BYTES + RESERVE, 'insufficient free space')
        directory_fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        fd = os.open('payload.bin', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_DIRECT,
                     0o600, dir_fd=directory_fd)
        for round_ in range(ROUNDS):
            report.update(state='running', round=round_, phase='write', confirmed_phase_bytes=0)
            save()
            def progress(phase, done):
                require(time.monotonic() - started < MAX_SECONDS, 'trial time budget exhausted')
                if done % (8 * BLOCK) == 0:
                    snapshot = native_snapshot(args.boot_id)
                    require(snapshot['ext4_errors'] == initial['ext4_errors'], 'new ext4 error')
                    require(os.statvfs(directory).f_bavail * space.f_frsize >= RESERVE, 'free-space reserve reached')
                    report['samples'].append({'elapsed_seconds': time.monotonic() - started,
                                              'round': round_, 'phase': phase, 'bytes': done,
                                              'temperatures_mC': snapshot['temperatures_mC']})
                    report.update(phase=phase, confirmed_phase_bytes=done)
                    save()
            begin = time.monotonic()
            written = write_round(fd, args.run_id, round_, FILE_BYTES // BLOCK, progress)
            write_seconds = time.monotonic() - begin
            require(os.fstat(fd).st_size == FILE_BYTES, 'unexpected payload length')
            os.close(fd)
            fd = os.open('payload.bin', os.O_RDONLY | os.O_NOFOLLOW | os.O_DIRECT, dir_fd=directory_fd)
            report.update(phase='read', confirmed_phase_bytes=0)
            save()
            begin = time.monotonic()
            read = read_round(fd, args.run_id, round_, FILE_BYTES // BLOCK, progress)
            require(read == written, 'round checksum differs')
            report['rounds'].append({'round': round_, 'bytes_written': FILE_BYTES, 'bytes_directly_read': FILE_BYTES,
                                     'sha256': read, 'write_and_fsync_seconds': write_seconds,
                                     'read_and_verify_seconds': time.monotonic() - begin})
            os.close(fd)
            fd = None
            if round_ + 1 < ROUNDS:
                fd = os.open('payload.bin', os.O_WRONLY | os.O_NOFOLLOW | os.O_DIRECT, dir_fd=directory_fd)
        os.fsync(directory_fd)
        after = native_snapshot(args.boot_id)
        require(after['ext4_errors'] == 0, 'filesystem errors at completion')
        expected_sectors = FILE_BYTES * ROUNDS // SECTOR
        require(after['mmc_stat'][2] - initial['mmc_stat'][2] >= expected_sectors, 'block read accounting below verified payload')
        require(after['mmc_stat'][6] - initial['mmc_stat'][6] >= expected_sectors, 'block write accounting below written payload')
        report.update(state='complete-awaiting-persistence', after=after,
                      elapsed_seconds=time.monotonic() - started,
                      retained_payload_sha256=report['rounds'][-1]['sha256'],
                      retained_payload_round=ROUNDS - 1)
    except Exception as error:
        report.update(state='failed', error=str(error), elapsed_seconds=time.monotonic() - started)
        raise
    finally:
        if fd is not None:
            os.close(fd)
        if directory_fd is not None:
            os.close(directory_fd)
        report['finished_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        save()
    print(json.dumps({'state': report['state'], 'verified_rounds': len(report['rounds']),
                      'retained_payload_sha256': report['retained_payload_sha256']}), flush=True)


if __name__ == '__main__':
    main()
