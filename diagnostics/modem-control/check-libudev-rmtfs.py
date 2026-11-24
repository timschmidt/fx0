#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise a static ARM libudev client with read-only synthetic sysfs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

CASES = ['attributes', 'cached-attributes', 'missing-attribute', 'missing-device', 'repeat']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--probe', required=True, type=Path)
    parser.add_argument('--daemon', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--qemu', type=Path, default=Path('/usr/bin/qemu-arm-static'))
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    out = args.output.resolve()
    sys = out/'sys'
    device = sys/'devices/platform/fx0-synthetic/qcom_rmtfs_mem1'
    device.mkdir(parents=True)
    (device/'uevent').write_text('MAJOR=240\nMINOR=1\nDEVNAME=qcom_rmtfs_mem1\n')
    (device/'phys_addr').write_text('0fd80000\n')
    (device/'size').write_text('00180000\n')
    (sys/'dev/char').mkdir(parents=True)
    (sys/'dev/char/240:1').symlink_to('../../devices/platform/fx0-synthetic/qcom_rmtfs_mem1')
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    before = {str(p.relative_to(sys)): sha(p) for p in sys.rglob('*') if p.is_file()}
    prefix = ['bwrap', '--unshare-all', '--die-with-parent', '--ro-bind', str(args.qemu.resolve()), '/qemu',
              '--dev', '/dev', '--proc', '/proc', '--tmpfs', '/tmp', '--tmpfs', '/run',
              '--ro-bind', str(sys), '/sys']
    results = []
    for case in CASES:
        command = prefix+['--ro-bind', str(args.probe.resolve()), '/probe', '/qemu', '-strace', '/probe', case]
        p = subprocess.run(command, capture_output=True, text=True, timeout=15)
        (out/(case+'.stdout')).write_text(p.stdout)
        (out/(case+'.strace')).write_text(p.stderr)
        results.append({'case': case, 'returncode': p.returncode,
                        'passed': p.returncode==0 and 'LIBUDEV_RMTFS_CASE_PASS '+case in p.stdout,
                        'command': command})
    command = prefix+['--ro-bind', str(args.daemon.resolve()), '/rmtfs', '/qemu', '-strace', '/rmtfs', '-h']
    p = subprocess.run(command, capture_output=True, text=True, timeout=15)
    (out/'early-CLI.stdout').write_text(p.stdout)
    (out/'early-CLI.strace').write_text(p.stderr)
    if p.returncode != 1 or 'Unknown option:' not in p.stderr:
        raise ValueError('expected early unsupported-option exit')
    if any(token in p.stderr for token in ['socket(', '/dev/qcom_', '/dev/uio', '/sys/class/remoteproc']):
        raise ValueError('early CLI unexpectedly entered device/service code')
    for relative, digest in before.items():
        if sha(sys/relative) != digest:
            raise ValueError('synthetic sysfs changed')
    record = {'passed': sum(row['passed'] for row in results), 'failed': sum(not row['passed'] for row in results),
              'cases': results, 'fixture_sha256': before, 'fixture_unchanged': True,
              'probe_sha256': sha(args.probe), 'daemon_sha256': sha(args.daemon),
              'early_CLI': {'returncode': p.returncode, 'command': command, 'exits_before_device_and_socket_calls': True},
              'actual_phone_operations': 0, 'physical_devices_and_host_sysfs_exposed': False,
              'scope': 'Five real libudev APIs with synthetic read-only sysfs and isolated /run; full daemon only early CLI. No RMTFS memory mapping or lifecycle qualification.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({key: record[key] for key in ['passed', 'failed', 'fixture_unchanged', 'actual_phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
