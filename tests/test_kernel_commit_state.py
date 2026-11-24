import base64
import copy
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest import mock

source = Path(__file__).resolve().parents[1] / 'diagnostics/kernel-maintenance/commit_state.py'
spec = importlib.util.spec_from_file_location('kernel_commit_state', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class CommitStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fx0-commit-')
        self.root = Path(self.temp.name)
        for name in [module.EXECUTOR, module.TRACKER_PARENT, '/etc/apk']:
            (self.root / name.lstrip('/')).mkdir(parents=True)
        self.tracker = self.root / module.TRACKER.lstrip('/')
        self.tracker.write_bytes(b'original inventory\n')
        os.setxattr(self.tracker, 'user.fx0-test', b'original')
        self.policy = self.root / 'etc/apk/interactive'
        self.policy.write_bytes(b'')
        self.directory = self.root / module.EXECUTOR.lstrip('/')
        self.body = b'#!/bin/sh\nexit 0\n'
        self.name = 'package-1-r0.trigger'
        rows = {}
        for name in [*module.MUTABLE, '/etc/apk', '/etc/apk/interactive']:
            path = self.root / name.lstrip('/')
            st = path.lstat()
            row = dict(mode=stat.S_IMODE(st.st_mode), uid=st.st_uid, gid=st.st_gid,
                       mtime_ns=st.st_mtime_ns, xattrs={key: os.getxattr(path, key, follow_symlinks=False).hex() for key in os.listxattr(path, follow_symlinks=False)})
            if path.is_dir():
                row['kind'] = 'directory'
            else:
                row.update(kind='file', size=st.st_size, sha256=module.digest(path.read_bytes()))
            rows[name] = row
        self.capture = dict(format='fx0-kernel-commit-state-v1', paths=rows,
                            directory_membership={module.EXECUTOR: [], module.TRACKER_PARENT: ['installed.units'], '/etc/apk': ['interactive']},
                            inventory_base64=base64.b64encode(self.tracker.read_bytes()).decode(),
                            owned_executor_scripts={self.name: dict(size=len(self.body), sha256=module.digest(self.body), body_base64=base64.b64encode(self.body).decode())})
        self.state = module.CommitState(self.root, self.capture, skip_selinux_for_host_fixture=True)

    def tearDown(self):
        self.temp.cleanup()

    def script(self):
        path = self.directory / self.name
        path.write_bytes(self.body)
        return path

    def test_generated_inventory_and_recovery_preserve_original_metadata(self):
        self.state.verify_original()
        generated = b'/usr/lib/systemd/system/example.service type=file mtime=123\n'
        self.tracker.write_bytes(generated)
        self.state.verify_generated(generated.replace(b'123', b'456'))
        os.setxattr(self.tracker, 'user.fx0-test', b'changed')
        os.setxattr(self.tracker, 'user.fx0-extra', b'remove')
        self.script()
        self.assertEqual(self.state.restore(hooks_terminal=True), [self.name])
        self.assertEqual(self.tracker.read_bytes(), b'original inventory\n')
        self.assertEqual(os.getxattr(self.tracker, 'user.fx0-test'), b'original')
        self.assertNotIn('user.fx0-extra', os.listxattr(self.tracker))
        self.state.verify_original()

    def test_zero_status_cannot_substitute_for_correct_generated_inventory(self):
        self.tracker.write_bytes(b'/usr/lib/systemd/system/wrong.service type=file mtime=123\n')
        with self.assertRaisesRegex(AssertionError, 'inventory differs'):
            self.state.verify_generated(b'/usr/lib/systemd/system/correct.service type=file mtime=123\n')

    def test_inventory_parser_refuses_malformed_and_duplicate_rows(self):
        good = b'/usr/lib/systemd/system/example.service type=file mtime=123\n'
        for data in [b'', b'wrong but nonempty\n', good + good, good.replace(b'type=file', b'type=unknown')]:
            with self.subTest(data=data), self.assertRaises(AssertionError):
                module.inventory_identity(data)

    def test_pending_hooks_refuse_before_cleanup_or_write(self):
        path = self.script()
        self.tracker.write_bytes(b'preserve\n')
        with mock.patch.object(module.os, 'open') as opened:
            with self.assertRaisesRegex(AssertionError, 'hooks must be reaped'):
                self.state.restore(hooks_terminal=False)
            opened.assert_not_called()
        self.assertTrue(path.exists())
        self.assertEqual(self.tracker.read_bytes(), b'preserve\n')

    def test_unknown_entry_preserves_all_executor_files_and_inventory(self):
        known = self.script()
        unknown = self.directory / 'unknown'
        unknown.write_bytes(b'preserve')
        self.tracker.write_bytes(b'changed\n')
        with self.assertRaisesRegex(AssertionError, 'Unknown executor'):
            self.state.restore(hooks_terminal=True)
        self.assertTrue(known.exists() and unknown.exists())
        self.assertEqual(self.tracker.read_bytes(), b'changed\n')

    def test_modified_known_script_is_preserved(self):
        path = self.script()
        path.write_bytes(b'X' + self.body[1:])
        with self.assertRaises(AssertionError):
            self.state.restore(hooks_terminal=True)
        self.assertTrue(path.exists())

    def test_executor_symlink_and_hardlink_refused_without_target_read(self):
        outside = self.root / 'outside'
        outside.write_bytes(self.body)
        path = self.directory / self.name
        for kind in ['symlink', 'hardlink']:
            with self.subTest(kind=kind):
                if kind == 'symlink':
                    path.symlink_to(outside)
                else:
                    os.link(outside, path)
                with mock.patch.object(module.os, 'open') as opened:
                    with self.assertRaises(AssertionError):
                        self.state.cleanup_executor(hooks_terminal=True)
                    opened.assert_not_called()
                path.unlink()
        self.assertEqual(outside.read_bytes(), self.body)

    def test_changed_configuration_refuses_recovery_writes(self):
        self.policy.write_bytes(b'changed')
        self.tracker.write_bytes(b'preserve')
        with self.assertRaises(AssertionError):
            self.state.restore(hooks_terminal=True)
        self.assertEqual(self.tracker.read_bytes(), b'preserve')

    def test_corrupt_capture_refused_before_target_writes(self):
        capture = copy.deepcopy(self.capture)
        capture['inventory_base64'] = base64.b64encode(b'wrong').decode()
        with self.assertRaises(AssertionError):
            module.CommitState(self.root, capture)
        self.state.verify_original()

    def test_unknown_generated_tracker_sibling_refused(self):
        sibling = self.tracker.parent / 'unexpected'
        sibling.write_bytes(b'preserve')
        with self.assertRaises(AssertionError):
            self.state.restore(hooks_terminal=True)
        self.assertEqual(sibling.read_bytes(), b'preserve')

    def test_tracker_symlink_refused(self):
        outside = self.root / 'outside'
        outside.write_bytes(b'preserve')
        self.tracker.unlink()
        self.tracker.symlink_to(outside)
        with self.assertRaises(AssertionError):
            self.state.restore(hooks_terminal=True)
        self.assertEqual(outside.read_bytes(), b'preserve')

    def test_symlink_parent_escape_refused(self):
        self.policy.unlink()
        self.policy.parent.rmdir()
        outside = self.root / 'outside'
        outside.mkdir()
        self.policy.parent.symlink_to(outside)
        with self.assertRaisesRegex(AssertionError, 'Invalid canonical parent'):
            module.CommitState(self.root, self.capture)


if __name__ == '__main__':
    unittest.main()
