#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise local name-service replies and the RAM worker without real device access."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

CONTROL = Path(__file__).resolve().parents[1] / 'diagnostics/modem-control'


class PassiveRmtfsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, content, executable=False):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if executable:
            path.chmod(0o755)
        return path

    def digest(self, name):
        return hashlib.sha256((self.root / name).read_bytes()).hexdigest()

    def fixture(self):
        self.write('etc/fx0-rmtfs-trial', 'native-r50-passive-rmtfs\n')
        self.write('sys/kernel/notes', 'synthetic kernel notes')
        self.write('etc/fx0-rmtfs-notes.sha256', self.digest('sys/kernel/notes') + '\n')
        self.write('modules/qrtr.ko', 'mock QRTR core')
        self.write('etc/fx0-rmtfs-inputs.sha256', self.digest('modules/qrtr.ko') + '  modules/qrtr.ko\n')
        self.write('sys/module/module/parameters/sig_enforce', 'Y\n')
        self.write('proc/cmdline', 'module.sig_enforce=1\n')
        self.write('proc/sys/kernel/random/boot_id', '01234567-0123-0123-0123-0123456789ab\n')
        self.write('proc/sys/kernel/tainted', '0\n')
        self.write('proc/uptime', '12.34 20.00\n')
        self.write('proc/mounts', 'rootfs / rootfs rw 0 0\ndevtmpfs /dev devtmpfs rw 0 0\n')
        self.write('proc/modules', '')
        self.write('dev/mem', 'mock legacy memory node')
        self.write('dev/qcom_rmtfs_mem1', 'mock character device')
        meta = 'sys/class/rmtfs/qcom_rmtfs_mem1/'
        self.write(meta + 'phys_addr', '0x0fd80000\n')
        self.write(meta + 'size', '0x00180000\n')
        self.write(meta + 'client_id', '1\n')
        (self.root / 'tmp').mkdir()
        self.write('bin/uname', '#!/bin/sh\necho 6.18.59-fx0-dmp\n', True)
        self.write('bin/insmod', '''#!/bin/sh
set -eu
r=$FX0_RMTFS_TEST_ROOT
test "$1" = "$r/modules/qrtr.ko"
test ! -e "$r/dev/mem"
printf 'qrtr 500 0 - Live 0x00000000\n' >"$r/proc/modules"
echo load >>"$r/trace"
''', True)
        self.write('bin/rmmod', '''#!/bin/sh
set -eu
r=$FX0_RMTFS_TEST_ROOT
test "$1" = qrtr
test ! -e "$r/up"
echo unload >>"$r/trace"
: >"$r/proc/modules"
''', True)
        self.write('bin/qrtr-local-rmtfs', '''#!/bin/sh
r=$FX0_RMTFS_TEST_ROOT
state=absent
test ! -e "$r/up" || state=present
test "$1" = "$state" || exit 1
echo "$state" >>"$r/trace"
''', True)
        self.write('bin/rmtfs', '''#!/usr/bin/env python3
import os
from pathlib import Path
import signal
import sys
import time

root = Path(os.environ['FX0_RMTFS_TEST_ROOT'])
assert sys.argv[1:] == ['-r', '-o', str(root / 'tmp/rmtfs-passive/storage')]
assert list((root / 'tmp/rmtfs-passive/storage').iterdir()) == []
up = root / 'up'
def stop(*_):
    up.unlink()
    with (root / 'trace').open('a') as trace:
        trace.write('exit\\n')
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
fd = root / f'proc/{os.getpid()}/fd/3'
fd.parent.mkdir(parents=True)
fd.symlink_to('/dev/qcom_rmtfs_mem1')
with (root / 'trace').open('a') as trace:
    trace.write('start\\n')
up.touch()
time.sleep(10)
stop()
''', True)

    def worker(self):
        # Only the device inode type is mocked. The worker runs unmodified.
        wrapper = '''
function [ {
    if [[ "$1" == -c && "$2" == "$FX0_RMTFS_TEST_ROOT/dev/qcom_rmtfs_mem1" ]]; then
        builtin [ -f "$2" ]
    else
        builtin [ "$@"
    fi
}
source "$1"
'''
        env = os.environ | {'FX0_RMTFS_TEST_ROOT': str(self.root),
                            'PATH': str(self.root / 'bin') + ':' + os.environ['PATH']}
        return subprocess.run(['bash', '-c', wrapper, 'fixture', str(CONTROL / 'rmtfs-passive.sh')],
                              env=env, capture_output=True, text=True, timeout=15)

    def test_passive_order_and_single_attempt(self):
        self.fixture()
        result = self.worker()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('RMTFS_PASSIVE_PASS', result.stdout)
        trace = self.root / 'trace'
        order = ['load', 'absent', 'start', 'present', 'exit', 'absent', 'unload']
        self.assertEqual(trace.read_text().splitlines(), order)
        self.assertIn('already attempted', self.worker().stderr)
        self.assertEqual(trace.read_text().splitlines(), order)

    def test_reject_before_mutating(self):
        self.fixture()
        cases = [
            ('proc/mounts', 'rootfs / rootfs rw 0 0\ndevtmpfs /dev devtmpfs rw 0 0\n/dev/test /disk ext4 rw 0 0\n',
             'RAM-only mounts and devtmpfs'),
            ('proc/uptime', '120.00 20.00\n', 'RAM boot deadline'),
            ('sys/class/rmtfs/qcom_rmtfs_mem1/client_id', '2\n', 'RFSA client ID'),
            ('proc/modules', 'qrtr_smd 500 0 - Live 0x00000000\n', 'module set'),
            ('modules/qrtr.ko', 'altered QRTR core', 'DT and payload digests'),
            ('sys/class/remoteproc/remoteproc0/state', 'offline\n', 'unexpected path'),
        ]
        for name, contents, expected in cases:
            with self.subTest(name=name):
                path = self.root / name
                original = path.read_text() if path.exists() else None
                self.write(name, contents)
                result = self.worker()
                self.assertEqual(result.returncode, 1)
                self.assertIn(expected, result.stderr)
                self.assertTrue((self.root / 'dev/mem').is_file())
                self.assertFalse((self.root / 'trace').exists())
                if original is None:
                    path.unlink()
                    path.parent.rmdir()
                else:
                    path.write_text(original)

    def test_name_service_notification_validation(self):
        source = self.write('observer-test.c', '''
#define main observer_main
#include "qrtr-local-rmtfs.c"
#undef main
#include <assert.h>

int main(void)
{
    struct sockaddr_qrtr from = {AF_QIPCRTR, 1, QRTR_PORT_CTRL};
    struct qrtr_ctrl_pkt packet = {.cmd = htole32(QRTR_TYPE_NEW_SERVER)};

    assert(classify(&packet, 20, &from, sizeof(from), 1) == END_OF_LIST);
    packet.server.service = htole32(14);
    packet.server.instance = htole32(1);
    packet.server.node = htole32(1);
    packet.server.port = htole32(14);
    assert(classify(&packet, 20, &from, sizeof(from), 1) == SERVER);
    assert(classify(&packet, 19, &from, sizeof(from), 1) == INVALID);
    assert(classify(&packet, 21, &from, sizeof(from), 1) == INVALID);
    assert(classify(&packet, 20, &from, sizeof(from) - 1, 1) == INVALID);
    assert(classify(&packet, 20, &from, sizeof(from), 2) == INVALID);
    from.sq_port = 14;
    assert(classify(&packet, 20, &from, sizeof(from), 1) == INVALID);
    from.sq_port = QRTR_PORT_CTRL;
    packet.server.instance = htole32(2);
    assert(classify(&packet, 20, &from, sizeof(from), 1) == INVALID);
    packet.server.instance = htole32(1);
    packet.cmd = htole32(QRTR_TYPE_DEL_SERVER);
    assert(classify(&packet, 20, &from, sizeof(from), 1) == INVALID);
    return 0;
}
''')
        binary = self.root / 'observer-test'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-I', str(CONTROL),
                        str(source), '-o', str(binary)], check=True)
        subprocess.run([binary], check=True)


if __name__ == '__main__':
    unittest.main()
