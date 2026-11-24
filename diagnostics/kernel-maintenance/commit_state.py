# SPDX-License-Identifier: GPL-2.0-only
"""Narrow backup guard for APK's executor and systemd commit inventory.

The caller owns the package transaction and must reap every hook before cleanup.
Only the captured inventory file and two fixed directories can be restored.
"""
import base64
import hashlib
import os
from pathlib import Path
import re
import stat
import tempfile

EXECUTOR = '/usr/lib/apk/exec'
TRACKER_PARENT = '/var/lib/systemd-apk'
TRACKER = TRACKER_PARENT + '/installed.units'
MUTABLE = {EXECUTOR, TRACKER_PARENT, TRACKER}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def inventory_identity(data):
    """Validate unit identities independently of treescan 0.1's invalid ARM mtime.

    That helper uses %zd for time_t; observed 32-bit ARM output is unstable.
    Callers must verify captured file timestamps directly, outside this output.
    """
    result = {}
    for line in data.decode('utf-8').splitlines():
        match = re.fullmatch(r'(/usr/lib/systemd/(?:system|user)/[^\s]+) type=(file|dir|symlink) mtime=(-?[0-9]+)', line)
        assert match and '..' not in Path(match[1]).parts, 'Malformed unit inventory'
        assert match[1] not in result, 'Duplicate unit inventory path'
        result[match[1]] = match[2]
    assert result, 'Empty unit inventory'
    return result


class CommitState:
    def __init__(self, root, capture, *, skip_selinux_for_host_fixture=False):
        self.root = Path(root).resolve(strict=True)
        self.capture = capture
        self.skip_selinux = skip_selinux_for_host_fixture
        assert not self.skip_selinux or self.root != Path('/')
        assert capture['format'] == 'fx0-kernel-commit-state-v1'
        self.rows = capture['paths']
        assert MUTABLE <= self.rows.keys()
        assert self.rows[EXECUTOR]['kind'] == self.rows[TRACKER_PARENT]['kind'] == 'directory'
        assert self.rows[TRACKER]['kind'] == 'file'
        assert capture['directory_membership'][EXECUTOR] == []
        assert capture['directory_membership'][TRACKER_PARENT] == ['installed.units']
        self.data = base64.b64decode(capture['inventory_base64'], validate=True)
        assert len(self.data) == self.rows[TRACKER]['size']
        assert digest(self.data) == self.rows[TRACKER]['sha256']
        self.owned = capture['owned_executor_scripts']
        for name, row in self.owned.items():
            assert Path(name).name == name and name not in {'', '.', '..'}
            assert 0 < row['size'] <= 65536
            content = base64.b64decode(row['body_base64'], validate=True)
            assert len(content) == row['size'] and digest(content) == row['sha256']
        for name in self.rows:
            self.target(name)

    def target(self, name):
        assert name.startswith('/') and name != '/' and '..' not in Path(name).parts
        path = self.root
        for part in Path(name).parts[1:-1]:
            path /= part
            assert not path.is_symlink() and path.is_dir(), 'Invalid canonical parent: ' + name
        return path / Path(name).name

    def attributes(self, path):
        return {key: os.getxattr(path, key, follow_symlinks=False).hex()
                for key in os.listxattr(path, follow_symlinks=False)
                if not (self.skip_selinux and key == 'security.selinux')}

    def expected_attributes(self, row):
        return {key: value for key, value in row['xattrs'].items()
                if not (self.skip_selinux and key == 'security.selinux')}

    def verify_row(self, name, *, content=True, mtime=False):
        row, path = self.rows[name], self.target(name)
        st = path.lstat()
        assert (stat.S_IMODE(st.st_mode), st.st_uid, st.st_gid) == (row['mode'], row['uid'], row['gid']), name
        assert self.attributes(path) == self.expected_attributes(row), name
        if row['kind'] == 'directory':
            assert stat.S_ISDIR(st.st_mode), name
        elif row['kind'] == 'symlink':
            assert stat.S_ISLNK(st.st_mode) and os.readlink(path) == row['target'], name
        else:
            assert row['kind'] == 'file' and stat.S_ISREG(st.st_mode), name
            if content:
                assert st.st_size == row['size'] and digest(path.read_bytes()) == row['sha256'], name
        if mtime:
            assert st.st_mtime_ns == row['mtime_ns'], name

    def verify_immutable_inputs(self):
        for name in self.rows.keys() - MUTABLE:
            # Atomic replacement of world changes its containing directory mtime.
            self.verify_row(name, mtime=name != '/etc/apk')
        for name, children in self.capture['directory_membership'].items():
            if name not in MUTABLE:
                assert sorted(p.name for p in self.target(name).iterdir()) == children, name

    def verify_directories(self, *, mtime=False):
        for name in [EXECUTOR, TRACKER_PARENT]:
            self.verify_row(name, mtime=mtime)
            assert sorted(p.name for p in self.target(name).iterdir()) == self.capture['directory_membership'][name], name

    def verify_original(self):
        self.verify_immutable_inputs()
        self.verify_directories(mtime=True)
        self.verify_row(TRACKER, mtime=True)

    def verify_generated(self, expected_bytes):
        assert expected_bytes
        self.verify_immutable_inputs()
        self.verify_directories()
        self.verify_row(TRACKER, content=False)
        path = self.target(TRACKER)
        assert inventory_identity(path.read_bytes()) == inventory_identity(expected_bytes), 'Commit hook inventory differs from current captured unit inputs'
        assert path.stat().st_nlink == 1

    def cleanup_executor(self, *, hooks_terminal):
        assert hooks_terminal, 'All owned hooks must be reaped before executor cleanup'
        self.verify_row(EXECUTOR)
        directory = self.target(EXECUTOR)
        assert not (directory.stat().st_mode & 0o022)
        entries = sorted(directory.iterdir())
        assert all(p.name in self.owned for p in entries), 'Unknown executor entry; preserve all files'
        identities = {}
        owner = self.rows[EXECUTOR]
        for path in entries:
            st = path.lstat()
            assert stat.S_ISREG(st.st_mode) and st.st_nlink == 1
            assert (st.st_uid, st.st_gid) == (owner['uid'], owner['gid'])
            assert st.st_size == self.owned[path.name]['size']
            identities[path.name] = (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns)
        for path in entries:
            fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
            try:
                st = os.fstat(fd)
                assert (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) == identities[path.name]
                data = os.read(fd, st.st_size + 1)
                assert len(data) == st.st_size and digest(data) == self.owned[path.name]['sha256']
            finally:
                os.close(fd)
        for path in entries:
            st = path.lstat()
            assert (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) == identities[path.name]
            path.unlink()
        return [p.name for p in entries]

    def restore(self, *, hooks_terminal):
        assert hooks_terminal, 'All owned hooks must be reaped before restoration'
        self.verify_immutable_inputs()
        removed = self.cleanup_executor(hooks_terminal=True)
        path = self.target(TRACKER)
        st = path.lstat()
        assert stat.S_ISREG(st.st_mode) and st.st_nlink == 1
        assert sorted(p.name for p in path.parent.iterdir()) == ['installed.units']
        fd, temporary = tempfile.mkstemp(prefix='.fx0-commit-', dir=path.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(self.data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.lexists(temporary):
                os.unlink(temporary)
        for name in [TRACKER, EXECUTOR, TRACKER_PARENT]:
            row, path = self.rows[name], self.target(name)
            os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
            path.chmod(row['mode'])
            expected = self.expected_attributes(row)
            for key in self.attributes(path).keys() - expected.keys():
                os.removexattr(path, key, follow_symlinks=False)
            for key, value in expected.items():
                os.setxattr(path, key, bytes.fromhex(value), follow_symlinks=False)
            os.utime(path, ns=(row['mtime_ns'], row['mtime_ns']), follow_symlinks=False)
        self.verify_original()
        fd = os.open(self.target(TRACKER_PARENT), os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
        return removed
