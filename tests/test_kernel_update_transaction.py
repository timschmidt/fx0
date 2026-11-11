# SPDX-License-Identifier: MIT
import hashlib
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'diagnostics/kernel-maintenance/update_transaction.py'
spec = importlib.util.spec_from_file_location('kernel_transaction', SOURCE)
transaction = importlib.util.module_from_spec(spec)
spec.loader.exec_module(transaction)


class Operations:
    def __init__(self, failures=()):
        self.failures = set(failures)
        self.calls = []
    def call(self, name):
        self.calls.append(name)
        if name in self.failures:
            raise RuntimeError(name)
    def preflight(self): self.call('preflight')
    def install(self): self.call('install')
    def verify_candidate(self): self.call('verify-candidate')
    def hooks_terminal(self): return 'hooks-active' not in self.failures
    def rollback(self): self.call('rollback')
    def verify_rollback(self): self.call('verify-rollback')
    def record(self, stage, **kwargs): self.calls.append(stage)


class TransactionTests(unittest.TestCase):
    def test_success_does_not_rollback(self):
        ops = Operations(); transaction.execute(ops)
        self.assertEqual(ops.calls, ['preflight', 'install', 'verify-candidate', 'updated-and-verified'])
    def test_preflight_failure_never_installs_or_restores(self):
        ops = Operations(['preflight'])
        with self.assertRaises(RuntimeError): transaction.execute(ops)
        self.assertEqual(ops.calls, ['preflight'])
    def test_install_and_verification_failures_restore_and_verify(self):
        for fault in ['install', 'verify-candidate']:
            with self.subTest(fault=fault):
                ops = Operations([fault])
                with self.assertRaises(transaction.RolledBack): transaction.execute(ops)
                self.assertEqual(ops.calls[-3:], ['rollback', 'verify-rollback', 'rolled-back'])
    def test_active_hooks_never_verify_or_rollback(self):
        for failures in [['hooks-active'], ['install', 'hooks-active']]:
            with self.subTest(failures=failures):
                ops = Operations(failures)
                with self.assertRaises(transaction.HooksActive): transaction.execute(ops)
                self.assertNotIn('verify-candidate', ops.calls)
                self.assertNotIn('rollback', ops.calls)
                self.assertEqual(ops.calls[-1], 'stopped-hooks-active')
    def test_rollback_failure_keeps_both_errors(self):
        ops = Operations(['verify-candidate', 'verify-rollback'])
        with self.assertRaises(transaction.RollbackFailed) as caught: transaction.execute(ops)
        self.assertEqual(str(caught.exception), 'verify-rollback')
        self.assertEqual(str(caught.exception.__cause__), 'verify-candidate')
        self.assertEqual(ops.calls[-1], 'rollback-failed')


class BootTailTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.backup = Path(self.temp.name)/'backup'; self.target = Path(self.temp.name)/'target'
        self.original = b'L' * 524288 + b'K' * 2048
        self.backup.write_bytes(self.original); self.target.write_bytes(self.original)
        self.digest = hashlib.sha256(self.original).hexdigest()
    def restore(self, offset=524288, digest=None):
        return transaction.restore_boot_tail(self.backup, self.target, offset, digest or self.digest)
    def test_restores_only_tail_even_with_short_writes(self):
        self.target.write_bytes(self.original[:524288] + b'X' * 2048)
        writes = []; real = transaction.os.pwrite
        def short_write(fd, data, offset):
            writes.append(offset); self.assertGreaterEqual(offset, 524288)
            return real(fd, data[:513], offset)
        with patch.object(transaction.os, 'pwrite', short_write): result = self.restore()
        self.assertTrue(result['written']); self.assertEqual(result['first_write_offset'], 524288)
        self.assertEqual(self.target.read_bytes(), self.original); self.assertGreater(len(writes), 1)
    def test_unchanged_partition_does_not_write(self):
        with patch.object(transaction.os, 'pwrite', side_effect=AssertionError('unexpected write')):
            self.assertFalse(self.restore()['written'])
    def test_wrong_prefix_size_backup_or_offset_never_writes(self):
        for fault in ['prefix', 'size', 'backup', 'unaligned', 'zero', 'past-end']:
            with self.subTest(fault=fault):
                self.target.write_bytes(self.original)
                if fault == 'prefix': self.target.write_bytes(b'X' + self.original[1:])
                if fault == 'size': self.target.write_bytes(self.original[:-1])
                before = self.target.read_bytes()
                offset = {'unaligned': 513, 'zero': 0, 'past-end': len(self.original)}.get(fault, 524288)
                with patch.object(transaction.os, 'pwrite', side_effect=AssertionError('unexpected write')):
                    with self.assertRaises(ValueError): self.restore(offset, '0'*64 if fault == 'backup' else None)
                self.assertEqual(self.target.read_bytes(), before)
    def test_short_initial_read_never_writes(self):
        with patch.object(transaction.os, 'pread', return_value=self.original[:524288]):
            with patch.object(transaction.os, 'pwrite', side_effect=AssertionError('unexpected write')):
                with self.assertRaises(OSError): self.restore()
    def test_missing_write_progress_stops(self):
        self.target.write_bytes(self.original[:524288] + b'X' * 2048)
        with patch.object(transaction.os, 'pwrite', return_value=0):
            with self.assertRaises(OSError): self.restore()
    def test_readback_corruption_fails(self):
        self.target.write_bytes(self.original[:524288] + b'X' * 2048)
        real = transaction.os.pread; calls = []
        def corrupt(fd, size, offset):
            data = real(fd, size, offset); calls.append(1)
            return data if len(calls) == 1 else data[:-1] + b'X'
        with patch.object(transaction.os, 'pread', corrupt):
            with self.assertRaises(OSError): self.restore()


if __name__ == '__main__': unittest.main()
