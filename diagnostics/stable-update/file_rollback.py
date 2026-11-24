"""Restore an explicitly captured package-file namespace from verified archives.

This helper does not stop package hooks, write a boot partition, or authorize a
native transaction. The caller must establish exclusive ownership beforehand.
"""
import hashlib
import io
import os
from pathlib import Path
import stat
import tarfile
import tempfile


def sha_file(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


class FileRollback:
    def __init__(self, root, manifest, base_archive, delta_archive, delta_sha256,
                 *, skip_selinux_for_host_fixture=False):
        self.root = Path(root).resolve(strict=True)
        assert self.root != Path('/'), 'Live-root activation requires a separate controller'
        assert manifest['format'] == 'fx0-stable-file-delta-v1'
        assert sha_file(base_archive) == manifest['base_archive_sha256']
        assert sha_file(delta_archive) == delta_sha256
        self.rows = manifest['paths']
        self.skip_selinux = skip_selinux_for_host_fixture
        self.data = {}
        with tarfile.open(base_archive, 'r:gz') as base, tarfile.open(delta_archive, 'r:gz') as delta:
            archives = {'base_archive_member': base, 'delta_archive_member': delta}
            for archive in archives.values():
                members = archive.getmembers()
                assert len({m.name for m in members}) == len(members)
                assert all(not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
            for name, row in self.rows.items():
                assert name.startswith('/') and '..' not in Path(name).parts
                assert name != '/' and row['kind'] in {'absent', 'directory', 'symlink', 'file'}
                if row['kind'] == 'file':
                    if 'hardlink_to' in row:
                        peer = self.rows[row['hardlink_to']]
                        assert peer['kind'] == 'file' and 'hardlink_to' not in peer
                        assert (peer['sha256'], peer['size']) == (row['sha256'], row['size'])
                    else:
                        source = row['data_source']
                        assert len(source) == 1
                        source_kind, member_name = next(iter(source.items()))
                        archive = archives[source_kind]
                        member = archive.getmember(member_name)
                        assert member.isfile() and member.size == row['size']
                        data = archive.extractfile(member).read()
                        assert hashlib.sha256(data).hexdigest() == row['sha256']
                        self.data[name] = data
        self.preflight()

    def target(self, name):
        path = self.root / name.lstrip('/')
        parent = self.root
        for part in Path(name).parts[1:-1]:
            parent = parent / part
            assert not parent.is_symlink(), ('Symlink in canonical parent', name)
            if parent.exists():
                assert parent.is_dir(), ('Non-directory parent', name)
        return path

    def preflight(self):
        for name in self.rows:
            self.target(name)

    @staticmethod
    def remove(path):
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            return
        if stat.S_ISDIR(mode):
            path.rmdir()  # Refuse to erase unrecorded descendants.
        else:
            path.unlink()

    def restore(self, *, stop_after=None):
        self.preflight()
        changes = 0

        def checkpoint():
            nonlocal changes
            changes += 1
            if stop_after is not None and changes >= stop_after:
                raise InterruptedError('Fixture interruption after %d captured paths' % changes)

        ordered = sorted(self.rows, key=lambda n: (len(Path(n).parts), n))
        for name in reversed(ordered):
            if self.rows[name]['kind'] == 'absent':
                self.remove(self.target(name))
                checkpoint()
        for name in ordered:
            row, path = self.rows[name], self.target(name)
            if row['kind'] == 'directory':
                if path.is_symlink() or (path.exists() and not path.is_dir()):
                    self.remove(path)
                path.mkdir(exist_ok=True)
                checkpoint()
        for name in ordered:
            row, path = self.rows[name], self.target(name)
            if row['kind'] in {'absent', 'directory'} or 'hardlink_to' in row:
                continue
            if row['kind'] == 'symlink':
                self.remove(path)
                path.symlink_to(row['target'])
            else:
                if path.is_dir() and not path.is_symlink():
                    self.remove(path)
                fd, temporary = tempfile.mkstemp(prefix='.fx0-restore-', dir=path.parent)
                try:
                    with os.fdopen(fd, 'wb') as stream:
                        stream.write(self.data[name])
                        stream.flush()
                        os.fsync(stream.fileno())
                    os.replace(temporary, path)
                finally:
                    if os.path.lexists(temporary):
                        os.unlink(temporary)
            checkpoint()
        for name in ordered:
            row = self.rows[name]
            if 'hardlink_to' in row:
                path = self.target(name)
                self.remove(path)
                os.link(self.target(row['hardlink_to']), path, follow_symlinks=False)
                checkpoint()
        for name in reversed(ordered):
            row, path = self.rows[name], self.target(name)
            if row['kind'] == 'absent':
                continue
            os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
            if row['kind'] != 'symlink':
                os.chmod(path, row['mode'], follow_symlinks=False)
            ignored = {'security.selinux'} if self.skip_selinux else set()
            actual_attrs = set(os.listxattr(path, follow_symlinks=False)) - ignored
            expected_attrs = set(row['xattrs']) - ignored
            for key in actual_attrs - expected_attrs:
                os.removexattr(path, key, follow_symlinks=False)
            for key in expected_attrs:
                os.setxattr(path, key, bytes.fromhex(row['xattrs'][key]), follow_symlinks=False)
            os.utime(path, ns=(row['mtime_ns'], row['mtime_ns']), follow_symlinks=False)

    def verify(self):
        groups = {}
        for name, row in self.rows.items():
            path = self.target(name)
            if row['kind'] == 'absent':
                assert not os.path.lexists(path), name
                continue
            observed = path.lstat()
            assert (stat.S_IMODE(observed.st_mode), observed.st_uid, observed.st_gid) == (
                row['mode'], row['uid'], row['gid']), name
            assert observed.st_mtime_ns == row['mtime_ns'], name
            if row['kind'] == 'directory':
                assert stat.S_ISDIR(observed.st_mode), name
            elif row['kind'] == 'symlink':
                assert stat.S_ISLNK(observed.st_mode) and os.readlink(path) == row['target'], name
            else:
                assert stat.S_ISREG(observed.st_mode) and observed.st_size == row['size'], name
                assert sha_file(path) == row['sha256'], name
                assert observed.st_nlink == row['nlink'], name
                leader = row.get('hardlink_to', name)
                identity = (observed.st_dev, observed.st_ino)
                if leader in groups:
                    assert groups[leader] == identity, name
                groups[leader] = identity
            ignored = {'security.selinux'} if self.skip_selinux else set()
            actual = {k: os.getxattr(path, k, follow_symlinks=False).hex()
                      for k in os.listxattr(path, follow_symlinks=False) if k not in ignored}
            expected = {k: v for k, v in row['xattrs'].items() if k not in ignored}
            assert actual == expected, name
