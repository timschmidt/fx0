#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the maintained-r1 passive worker against synthetic RAM state."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('passive_parent',ROOT/'tests/test_rmtfs_passive.py')
parent=importlib.util.module_from_spec(spec)
spec.loader.exec_module(parent)
WORKER=ROOT/'diagnostics/modem-control/rmtfs-passive-r1.sh'


class PassiveR1Test(parent.PassiveRmtfsTest):
    def fixture(self):
        super().fixture()
        self.write('etc/fx0-rmtfs-trial','native-r1-passive-rmtfs-01\n')
        self.write('proc/cmdline','module.sig_enforce=1 fx0.native_trial=r1-rmtfs-passive-01\n')
        self.write('proc/sys/kernel/modprobe','/bin/false\n')
        self.write('bin/uname','#!/bin/sh\necho 6.18.63-fx0-vibrator-alpine\n',True)
        self.write('usr/bin/rmtfs',(self.root/'bin/rmtfs').read_text(),True)
        (self.root/'bin/rmtfs').unlink()
        self.write('bin/fx0-native-return','synthetic independent return helper',True)
        self.write('tmp/fx0-native-return-armed',f'PID={os.getpid()}\nDEADLINE=180\nTOKEN=fx0.native_trial=r1-rmtfs-passive-01\n').chmod(0o600)
        (self.root/f'proc/{os.getpid()}').mkdir(parents=True)
        (self.root/f'proc/{os.getpid()}/exe').symlink_to('/bin/fx0-native-return')
        (self.root/'lib').symlink_to('usr/lib')
        for name,target in [('libc.musl-armv7.so.1','ld-musl-armhf.so.1'),('libqrtr.so.1','libqrtr.so.1.2'),('libudev.so.1','libudev.so.1.6.3')]:
            self.write('usr/lib/'+target,'synthetic '+target)
            (self.root/'usr/lib'/name).symlink_to(target)
        files=['modules/qrtr.ko','usr/bin/rmtfs','bin/fx0-native-return','usr/lib/ld-musl-armhf.so.1','usr/lib/libqrtr.so.1.2','usr/lib/libudev.so.1.6.3']
        self.write('etc/fx0-rmtfs-inputs.sha256',''.join(self.digest(name)+'  '+name+'\n' for name in files))

    def worker(self):
        # As in the parent fixture, only character-device inode type is mocked.
        wrapper='''
function [ {
    if [[ "$1" == -c && "$2" == "$FX0_RMTFS_TEST_ROOT/dev/qcom_rmtfs_mem1" ]]; then
        builtin [ -f "$2" ]
    else
        builtin [ "$@"
    fi
}
source "$1"
'''
        env=os.environ|{'FX0_RMTFS_TEST_ROOT':str(self.root),'PATH':str(self.root/'bin')+':'+os.environ['PATH']}
        return subprocess.run(['bash','-c',wrapper,'fixture',str(WORKER)],env=env,capture_output=True,text=True,timeout=15)

    def refused_without_mutation(self,expected):
        result=self.worker()
        self.assertEqual(result.returncode,1,result.stdout+result.stderr)
        self.assertIn(expected,result.stderr)
        self.assertTrue((self.root/'dev/mem').is_file())
        self.assertFalse((self.root/'trace').exists())

    def test_return_helper_must_be_armed_and_current(self):
        for marker in ['PID=1\nDEADLINE=420\nTOKEN=fx0.native_trial=r1-rmtfs-passive-01\n',f'PID={os.getpid()}\nDEADLINE=180\nTOKEN=fx0.native_trial=reproducible-r2-01\n']:
            with self.subTest(marker=marker):
                self.fixture()
                self.write('tmp/fx0-native-return-armed',marker).chmod(0o600)
                self.refused_without_mutation('return helper marker identity')
                # Each subcase uses a new owned synthetic tree.
                self.tmp.cleanup();self.setUp()

    def test_missing_return_helper_refused(self):
        self.fixture();(self.root/'tmp/fx0-native-return-armed').unlink()
        self.refused_without_mutation('return helper not armed')

    def test_autoload_enabled_refused(self):
        self.fixture();self.write('proc/sys/kernel/modprobe','/sbin/modprobe\n')
        self.refused_without_mutation('module autoload disabled')

    def test_wrong_library_link_refused(self):
        self.fixture();link=self.root/'usr/lib/libqrtr.so.1';link.unlink();link.symlink_to('libudev.so.1.6.3')
        self.refused_without_mutation('QRTR library link')


if __name__=='__main__':
    unittest.main()
