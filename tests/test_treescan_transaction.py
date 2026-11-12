"""Focused guards for the live treescan controller; native APK tests are separate."""
import hashlib
import importlib.util
import os
from pathlib import Path
import stat
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'diagnostics/stable-update/treescan_transaction.py'
SPEC = importlib.util.spec_from_file_location('treescan_transaction', SOURCE)
controller = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(controller)


class SnapshotGuards(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='treescan-guard-')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        files = {name: ('original ' + name).encode() for name in controller.FILES}
        files[controller.LOCK] = b''
        files['/usr/bin/not-owned'] = b'leave unchanged'
        names = set(controller.DIRECTORIES)
        for name in names:
            (self.root / name.lstrip('/')).mkdir(parents=True, exist_ok=True)
        for name in files:
            path = self.root / name.lstrip('/')
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(files[name])
            path.chmod(0o600 if name == controller.LOCK else 0o644)
            names.add(name)
        names.update('/' + str(path.relative_to(self.root))
                     for path in self.root.rglob('*') if path.is_dir())
        self.rows = {}
        for name in sorted(names):
            path = self.root / name.lstrip('/')
            metadata = path.lstat()
            row = dict(kind='directory' if path.is_dir() else 'file',
                       mode=stat.S_IMODE(metadata.st_mode), uid=metadata.st_uid, gid=metadata.st_gid,
                       mtime_ns=metadata.st_mtime_ns,
                       xattrs={k: os.getxattr(path, k).hex() for k in os.listxattr(path)})
            if path.is_file():
                data = path.read_bytes()
                row.update(size=len(data), nlink=1, sha256=hashlib.sha256(data).hexdigest())
            self.rows[name] = row
        self.rows['/absent/old-kernel/path'] = dict(kind='absent')
        manifest = dict(paths=self.rows, directory_membership={controller.EXECUTOR: []})
        self.snapshot = controller.Snapshot(self.root, manifest, {n: files[n] for n in controller.FILES})

    def tearDown(self):
        self.temporary.cleanup()

    def test_exact_recovery_preserves_lock_inode_and_real_dual_locks(self):
        before = self.snapshot.target(controller.LOCK).stat().st_ino
        self.snapshot.target(controller.ELF).write_bytes(b'candidate')
        self.snapshot.target(controller.WORLD).write_bytes(b'changed world')
        with self.snapshot.locked():
            self.snapshot.locks()
            self.snapshot.restore(hooks_terminal=True)
            self.snapshot.locks()
            self.assertEqual(self.snapshot.verify(), {})
        self.assertEqual(self.snapshot.target(controller.LOCK).stat().st_ino, before)

    def test_unowned_change_refuses_every_recovery_write(self):
        elf = self.snapshot.target(controller.ELF)
        elf.write_bytes(b'candidate')
        self.snapshot.target('/usr/bin/not-owned').write_bytes(b'unexpected')
        with self.snapshot.locked():
            with self.assertRaises(AssertionError):
                self.snapshot.restore(hooks_terminal=True)
            self.assertEqual(elf.read_bytes(), b'candidate')

    def test_active_hooks_refuse_recovery(self):
        elf = self.snapshot.target(controller.ELF)
        elf.write_bytes(b'candidate')
        with self.snapshot.locked():
            with self.assertRaises(AssertionError):
                self.snapshot.restore(hooks_terminal=False)
            self.assertEqual(elf.read_bytes(), b'candidate')

    def test_reopening_lock_is_detected_as_lost_posix_lock(self):
        with self.assertRaisesRegex(AssertionError, 'Both real APK lock types'):
            with self.snapshot.locked():
                descriptor = os.open(self.snapshot.target(controller.LOCK), os.O_RDONLY)
                os.close(descriptor)

    def test_absent_parent_allowed_but_symlink_and_file_ancestors_refused(self):
        self.assertEqual(self.snapshot.target('/missing/old/kernel'), self.root / 'missing/old/kernel')
        (self.root / 'dangling').symlink_to('missing')
        with self.assertRaises(AssertionError):
            self.snapshot.target('/dangling/path')
        with self.assertRaises(AssertionError):
            self.snapshot.target('/usr/bin/not-owned/path')

    def test_unknown_executor_preserves_all_entries(self):
        directory = self.snapshot.target(controller.EXECUTOR)
        (directory / '000-unknown').write_bytes(b'unowned')
        (directory / 'busybox-1.37.0-r31.trigger').write_bytes(b'known')
        ops = controller.TreescanUpdate.__new__(controller.TreescanUpdate)
        ops.snapshot = self.snapshot
        ops.owned_scripts = {'busybox-1.37.0-r31.trigger': b'known'}
        ops.hooks_terminal = lambda: True
        with self.snapshot.locked():
            with self.assertRaisesRegex(AssertionError, 'Unknown executor'):
                ops.cleanup_executor()
        self.assertEqual(sorted(p.name for p in directory.iterdir()),
                         ['000-unknown', 'busybox-1.37.0-r31.trigger'])


if __name__ == '__main__':
    unittest.main()
