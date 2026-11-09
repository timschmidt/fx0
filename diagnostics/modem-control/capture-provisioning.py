#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture five fixed Fx0 provisioning partitions to a fresh private phone folder.

Run on the installed r50 phone. Source block devices are opened read-only;
only new regular backup files under /var/lib/fx0-rollback are written. This
excludes the modem firmware partition and never restores or starts anything.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

PARTITIONS = {
    'persist': (14, 212992, 65536),
    'modemst1': (17, 409600, 6144),
    'modemst2': (18, 415744, 6144),
    'fsg': (20, 425984, 6144),
    'fsc': (21, 432128, 1024),
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def copy_exact(source, target, size, expected_sha256, required_rdev=None):
    """Copy bounded bytes once; regular-file fixtures may omit required_rdev."""
    source_fd = os.open(source, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        info = os.fstat(source_fd)
        if required_rdev is not None:
            require(stat.S_ISBLK(info.st_mode) and info.st_rdev == required_rdev,
                    'Source device changed before open')
        with os.fdopen(os.dup(source_fd), 'rb', buffering=0) as stream:
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb', buffering=0) as out:
                remaining, hasher = size, hashlib.sha256()
                while remaining:
                    data = stream.read(min(1024 * 1024, remaining))
                    require(data, 'Source ended before declared size')
                    require(out.write(data) == len(data), 'Short backup write')
                    hasher.update(data)
                    remaining -= len(data)
                require(stream.read(1) == b'', 'Source exceeds declared size')
                require(hasher.hexdigest() == expected_sha256, 'Source changed while copying')
                out.flush()
                os.fsync(out.fileno())
        require(target.stat().st_size == size and digest(target) == expected_sha256, 'Backup reread mismatch')
    finally:
        os.close(source_fd)


def command(args):
    return subprocess.check_output(args, text=True, timeout=40).strip()


def native_guard(boot_id):
    require(Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot_id, 'Native boot changed')
    require(command(['uname', '-r']) == '6.18.59-fx0-dmp', 'Expected installed r50 kernel')
    require(Path('/proc/sys/kernel/tainted').read_text().strip() == '0', 'Kernel is tainted')
    require(Path('/sys/firmware/devicetree/base/soc/remoteproc@fc880000/status').read_bytes() == b'disabled\0', 'MSS must remain disabled')
    require('qcom_q6v5_mss' not in [row.split()[0] for row in Path('/proc/modules').read_text().splitlines()], 'MSS module loaded')
    require(command(['systemctl', 'is-system-running']) == 'running', 'Native startup not complete')
    require(not command(['systemctl', 'list-jobs', '--no-legend']), 'Pending service jobs')
    require(not command(['systemctl', '--failed', '--no-legend']), 'Failed services')
    for name in ['rmtfs', 'rmt_storage']:
        require(subprocess.run(['pgrep', '-x', name], capture_output=True).returncode == 1, 'Remote storage process active')
    services = {name: command(['systemctl', 'show', name, '-p', 'ActiveState', '-p', 'MainPID'])
                for name in ['upower', 'ModemManager', 'tinydm', 'iio-sensor-proxy']}
    require(all('ActiveState=active' in value for value in services.values()), 'Required native service inactive')
    remoteprocs = sorted(((path/'name').read_text().strip(), (path/'state').read_text().strip())
                         for path in Path('/sys/class/remoteproc').glob('remoteproc*'))
    require(remoteprocs == [('adsp', 'running'), ('fb204000.remoteproc', 'running')], 'Unexpected remote processor')
    return {'services': services, 'remoteprocs': remoteprocs,
            'raw_boot_sha256': command(['sha256sum', '/dev/mmcblk0p15']).split()[0]}


def source_devices():
    devices = {}
    for name, (number, start, sectors) in PARTITIONS.items():
        device = Path('/dev') / ('mmcblk0p' + str(number))
        sys = Path('/sys/class/block') / device.name
        require((Path('/dev/disk/by-partlabel')/name).resolve() == device, 'Partition label mismatch')
        info = device.lstat()
        require(stat.S_ISBLK(info.st_mode), 'Expected a real block device')
        require(int((sys/'start').read_text()) == start and int((sys/'size').read_text()) == sectors,
                'Partition offset/size mismatch')
        devices[name] = {'device': str(device), 'start_sector': start, 'sectors': sectors,
                         'bytes': sectors*512, 'rdev': info.st_rdev}
    source_ids = {row['rdev'] for row in devices.values()}
    for line in Path('/proc/mounts').read_text().splitlines():
        fields = line.split()
        try:
            info = Path(fields[0]).stat()
        except OSError:
            continue
        if stat.S_ISBLK(info.st_mode) and info.st_rdev in source_ids:
            require('ro' in fields[3].split(','), 'Provisioning partition mounted writable')
    # Do not retain unrelated process paths, command lines or descriptor data.
    for fd in Path('/proc').glob('[0-9]*/fd/*'):
        try:
            info = fd.stat()
            if not stat.S_ISBLK(info.st_mode) or info.st_rdev not in source_ids:
                continue
            flags = next(row.split()[1] for row in (fd.parent.parent/'fdinfo'/fd.name).read_text().splitlines()
                         if row.startswith('flags:'))
            require(int(flags, 8) & os.O_ACCMODE == os.O_RDONLY, 'Provisioning block device has an open writer')
        except (FileNotFoundError, ProcessLookupError):
            continue
    return devices


def capture(destination, boot_id, expected_sha256):
    destination = Path(destination)
    parent = Path('/var/lib/fx0-rollback')
    require(destination.parent == parent and parent.resolve() == parent and parent.is_dir(), 'Unexpected backup location')
    require(not destination.exists() and not destination.is_symlink(), 'Backup slot already exists')
    require(command(['findmnt', '-n', '-o', 'SOURCE,FSTYPE', '-T', str(parent)]) == '/dev/mmcblk0p35 ext4', 'Backup must use native rootfs')
    before = native_guard(boot_id)
    devices = source_devices()
    require(set(expected_sha256) == set(devices), 'Expected hash set must name exactly five provisioning partitions')
    available = os.statvfs(parent)
    require(available.f_bavail*available.f_frsize > 2*sum(row['bytes'] for row in devices.values()) + 64*1024*1024, 'Insufficient backup space')
    source_before = {name: digest(Path(row['device'])) for name, row in devices.items()}
    require(source_before == expected_sha256, 'Provisioning differs from the selected baseline')
    destination.mkdir(mode=0o700)
    state = {'PID': os.getpid(), 'state': 'capturing once', 'BOOT_or_restore_requested': False}
    state_path = destination/'capture-controller.json'
    state_path.write_text(json.dumps(state, indent=2)+'\n'); state_path.chmod(0o600)
    try:
        for name, row in devices.items():
            copy_exact(Path(row['device']), destination/(name+'.img'), row['bytes'], source_before[name], row['rdev'])
        require(source_devices() == devices, 'Source map changed')
        source_after = {name: digest(Path(row['device'])) for name, row in devices.items()}
        require(source_after == source_before, 'Provisioning set changed during capture')
        require(native_guard(boot_id) == before, 'Native identity/services changed')
        record = {'schema': 'fx0-current-provisioning-v1', 'complete': True,
                  'recorded_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(), 'native_boot_id': boot_id,
                  'destination': str(destination), 'destination_storage': '/dev/mmcblk0p35 ext4',
                  'source_devices_opened_read_only': True, 'source_set_stable_before_through_after': True,
                  'snapshot_files_fsynced_and_reread': True, 'native_state_unchanged': True,
                  'firmware_partition_included': False, 'partitions': {}}
        for name, row in devices.items():
            record['partitions'][name] = {key: value for key, value in row.items() if key != 'rdev'}
            record['partitions'][name].update(file=name+'.img', sha256=source_before[name], source_after_sha256=source_after[name])
        data=(json.dumps(record, indent=2)+'\n').encode()
        fd=os.open(destination/'manifest.json', os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        state.update(state='terminal', returncode=0)
    except BaseException:
        state.update(state='terminal', returncode=1)
        raise
    finally:
        state_path.write_text(json.dumps(state, indent=2)+'\n')
        with state_path.open('rb') as stream:os.fsync(stream.fileno())
        fd=os.open(destination, os.O_RDONLY|os.O_DIRECTORY);os.fsync(fd);os.close(fd)
    return record


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--destination', required=True, type=Path)
    parser.add_argument('--expect-boot-id', required=True)
    parser.add_argument('--expected-sha256-json', required=True, help='Private JSON map; do not publish provisioning digests')
    args=parser.parse_args()
    print(json.dumps(capture(args.destination,args.expect_boot_id,json.loads(args.expected_sha256_json)),indent=2))


if __name__=='__main__':main()
