# SPDX-License-Identifier: MIT
"""Private workspace ownership and disposable, actual host child processes."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'diagnostics/modem-control/passive_runtime.py'
spec = importlib.util.spec_from_file_location('passive_runtime', SOURCE)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name)

    def test_claim_survives_close_and_rejects_reuse(self):
        journal = runtime.AttemptJournal(self.directory)
        journal.update({'BOOT_attempted': True})
        journal.close()
        self.assertEqual((self.directory/'attempt.claim').stat().st_mode & 0o777, 0o600)
        self.assertEqual((self.directory/'controller.json').stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError):
            runtime.AttemptJournal(self.directory)
        self.assertTrue(json.loads((self.directory/'controller.json').read_text())['BOOT_attempted'])

    def test_existing_state_or_claim_symlink_is_not_followed(self):
        for filename in ['controller.json', 'attempt.claim']:
            with self.subTest(filename=filename):
                directory = self.directory/filename
                directory.mkdir(mode=0o700)
                target = directory/'sentinel'
                target.write_text('unchanged')
                (directory/filename).symlink_to(target)
                with self.assertRaises(FileExistsError):
                    runtime.AttemptJournal(directory)
                self.assertEqual(target.read_text(), 'unchanged')

    def test_nonprivate_workspace_rejected(self):
        self.directory.chmod(0o755)
        with self.assertRaises(RuntimeError):
            runtime.AttemptJournal(self.directory)
        self.assertFalse((self.directory/'attempt.claim').exists())

    def test_crashed_process_cannot_be_restarted_in_same_workspace(self):
        code = '''import importlib.util,os,sys
spec=importlib.util.spec_from_file_location('runtime',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
j=m.AttemptJournal(sys.argv[2]);j.update({'BOOT_attempted':True});os._exit(0)
'''
        child = subprocess.Popen([sys.executable, '-B', '-c', code, str(SOURCE), str(self.directory)])
        self.assertEqual(child.wait(timeout=5), 0)
        with self.assertRaises(FileExistsError):
            runtime.AttemptJournal(self.directory)

    def test_only_one_process_can_claim_workspace(self):
        code = '''import importlib.util,sys
spec=importlib.util.spec_from_file_location('runtime',sys.argv[1]);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
try:j=m.AttemptJournal(sys.argv[2])
except FileExistsError:raise SystemExit(2)
j.update({'claimed':True});j.close()
'''
        children = [subprocess.Popen([sys.executable, '-B', '-c', code, str(SOURCE), str(self.directory)]) for _ in range(2)]
        self.assertEqual(sorted(child.wait(timeout=5) for child in children), [0, 2])

    def test_failed_state_fsync_retains_claim_and_previous_state(self):
        journal = runtime.AttemptJournal(self.directory)
        self.addCleanup(journal.close)
        journal.update({'phase': 'before intent'})
        with mock.patch.object(runtime.os, 'fsync', side_effect=OSError('fsync failed')):
            with self.assertRaises(OSError):
                journal.update({'BOOT_attempted': True})
        self.assertEqual(json.loads((self.directory/'controller.json').read_text()), {'phase': 'before intent'})
        self.assertTrue((self.directory/'attempt.claim').exists())
        self.assertFalse(list(self.directory.glob('.controller-*.tmp')))

    def test_update_requires_live_owner_and_file_then_directory_fsync(self):
        journal = runtime.AttemptJournal(self.directory)
        self.addCleanup(journal.close)
        real = runtime.os.fsync
        observed = []
        def fsync(descriptor):
            observed.append(descriptor == journal.fd)
            return real(descriptor)
        with mock.patch.object(runtime.os, 'fsync', side_effect=fsync):
            journal.update({'phase': 'intent'})
        self.assertEqual(observed, [False, True])
        with mock.patch.object(runtime.os, 'getpid', return_value=journal.owner + 1):
            with self.assertRaises(RuntimeError):
                journal.update({'wrong owner': True})
        journal.close()
        with self.assertRaises(RuntimeError):
            journal.update({'closed': True})


class ChildTests(unittest.TestCase):
    def child(self, source, *args):
        child = subprocess.Popen([sys.executable, '-B', '-c', source, *args],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        def cleanup():
            if child.poll() is None:
                child.kill()
            child.wait(timeout=3)
        self.addCleanup(cleanup)
        return child

    def test_actual_success_and_failure_exit_statuses(self):
        for status in [0, 7]:
            child = self.child('raise SystemExit(' + str(status) + ')')
            result = runtime.wait_owned(child, 3)
            self.assertEqual(result['returncode'], status)
            self.assertTrue(result['owned_child_reaped'])
            self.assertFalse(result['process_deadline_expired'])

    def test_actual_expired_child_is_terminated_and_reaped(self):
        child = self.child('import time;time.sleep(3)')
        result = runtime.wait_owned(child, .05, terminate_grace=.5, kill_grace=.5)
        self.assertEqual(result['returncode'], -signal.SIGTERM)
        self.assertTrue(result['process_deadline_expired'])
        self.assertFalse(result['kill_requested'])

    def test_actual_SIGTERM_ignoring_child_requires_kill_and_reap(self):
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory)/'ready'
            child = self.child('import signal,time,sys;from pathlib import Path;signal.signal(signal.SIGTERM,signal.SIG_IGN);Path(sys.argv[1]).write_text("ready");time.sleep(3)', str(ready))
            deadline = time.monotonic() + 2
            while not ready.exists() and time.monotonic() < deadline:
                self.assertIsNone(child.poll())
                time.sleep(.01)
            self.assertTrue(ready.exists())
            result = runtime.wait_owned(child, .03, terminate_grace=.03, kill_grace=.5)
            self.assertEqual(result['returncode'], -signal.SIGKILL)
            self.assertTrue(result['kill_requested'])

    def test_unreaped_or_invalid_child_cannot_be_success(self):
        child = mock.Mock()
        child.wait.side_effect = subprocess.TimeoutExpired('fixture child', .01)
        child.poll.return_value = None
        with self.assertRaises(runtime.UnreapedChild):
            runtime.wait_owned(child, .01, terminate_grace=.01, kill_grace=.01)
        self.assertEqual(child.wait.call_count, 3)
        child = mock.Mock()
        child.wait.return_value = None
        child.poll.return_value = None
        with self.assertRaises(runtime.UnreapedChild):
            runtime.wait_owned(child, 1)


if __name__ == '__main__':
    unittest.main()
