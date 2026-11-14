#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject stale/partial console evidence and repeated worker submissions."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('serial_protocol',ROOT/'diagnostics/modem-control/passive_serial.py')
protocol=importlib.util.module_from_spec(spec);spec.loader.exec_module(protocol)
NONCE='0123456789abcdef'
BOOT='01234567-89ab-cdef-0123-456789abcdef'


class PassiveSerialTest(unittest.TestCase):
    def probe(self):
        return ('PROBE_'+NONCE+'_BEGIN\nRELEASE='+protocol.RELEASE+'\nBOOT='+BOOT+'\nCMD=module.sig_enforce=1 '+protocol.TOKEN+'\nNOTES='+protocol.NOTES+'  /sys/kernel/notes\nUPTIME=12.4 1.2\nPROBE_'+NONCE+'_END\n').encode()

    def result(self):
        return ('RUN_'+NONCE+'_BEGIN\nRMTFS_PASSIVE_BEGIN '+BOOT+'\nRMTFS_LOCAL_SERVICE_ABSENT\nRMTFS_LOCAL_SERVICE_PRESENT\nRMTFS_RFSA_OPEN /dev/qcom_rmtfs_mem1\nRMTFS_LOCAL_SERVICE_ABSENT\nRMTFS_PASSIVE_PASS\nRUN_'+NONCE+'_RC=0\n').encode()

    def test_checked_new_identity(self):
        self.assertEqual(protocol.parse_probe(self.probe(),NONCE,'previous')['boot_id'],BOOT)
        self.assertEqual(protocol.parse_probe(self.probe().replace(b'\n',b'\r\n'),NONCE,'previous')['boot_id'],BOOT)

    def test_partial_and_echo_only_are_not_evidence(self):
        self.assertIsNone(protocol.parse_probe(protocol.probe_command(NONCE),NONCE,'previous'))
        self.assertIsNone(protocol.parse_probe(self.probe().split(b'PROBE_'+NONCE.encode()+b'_END')[0],NONCE,'previous'))
        self.assertIsNone(protocol.parse_result(protocol.worker_command(NONCE),NONCE,BOOT))

    def test_stale_or_wrong_probe_refused(self):
        for old,new in [(protocol.NOTES,'0'*64),(protocol.TOKEN,'fx0.native_trial=reproducible-r2-01'),('UPTIME=12.4','UPTIME=90.0'),('module.sig_enforce=1','module.sig_enforce=0')]:
            with self.subTest(old=old):
                with self.assertRaises(ValueError):protocol.parse_probe(self.probe().replace(old.encode(),new.encode()),NONCE,'previous')
        with self.assertRaises(ValueError):protocol.parse_probe(self.probe(),NONCE,BOOT)

    def test_duplicate_identity_frame_refused(self):
        with self.assertRaises(ValueError):protocol.parse_probe(self.probe()*2,NONCE,'previous')

    def test_publication_and_withdrawal_sequence_passes(self):
        self.assertTrue(protocol.parse_result(self.result(),NONCE,BOOT)['passed'])

    def test_missing_mapping_wrong_boot_and_failure_do_not_pass(self):
        for data in [self.result().replace(b'RMTFS_RFSA_OPEN /dev/qcom_rmtfs_mem1\n',b''),self.result().replace(BOOT.encode(),b'wrong-boot'),self.result().replace(b'_RC=0',b'_RC=1'),self.result().replace(b'RMTFS_PASSIVE_PASS',b'RMTFS_PASSIVE_FAIL bad')]:
            with self.subTest(data=data):self.assertFalse(protocol.parse_result(data,NONCE,BOOT)['passed'])

    def test_duplicate_result_refused(self):
        with self.assertRaises(ValueError):protocol.parse_result(self.result()*2,NONCE,BOOT)

    def test_short_write_and_exception_are_never_retried(self):
        for writer in [lambda command:len(command)-1,lambda command:(_ for _ in ()).throw(OSError('uncertain'))]:
            once=protocol.Once()
            with self.assertRaises((RuntimeError,OSError)):once.send(writer,b'worker\n')
            with self.assertRaises(RuntimeError):once.send(lambda command:len(command),b'worker\n')

    def test_nonce_cannot_inject_shell_text(self):
        with self.assertRaises(ValueError):protocol.worker_command('x; reboot')


if __name__=='__main__':unittest.main()
