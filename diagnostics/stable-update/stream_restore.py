"""Replay a captured private namespace with bounded memory and validated inputs.

This helper refuses the live root. The caller must prove exclusive ownership
of the private root and keep both source archives read-only throughout replay.
"""
import hashlib
import gzip
import os
from pathlib import Path, PurePosixPath
import stat
import tarfile

from file_rollback_v2 import FileRollback


class StreamRollback(FileRollback):
    def __init__(self, root, manifest, base_archive, delta_archive, delta_sha256,
                 *, skip_selinux_for_host_fixture=False):
        root = Path(root)
        assert root.is_absolute() and root != Path('/') and root.resolve(strict=True) == root
        assert stat.S_ISDIR(root.lstat().st_mode)
        self.root, self.rows = root, manifest['paths']
        self.skip_selinux = skip_selinux_for_host_fixture
        self.membership = manifest['directory_membership']
        self.archives = {}
        self.refs = {}
        self._validate_manifest(manifest)
        self._check_mounts()
        self.preflight()
        try:
            for kind, path, digest in [('base_archive_member', base_archive, manifest['base_archive_sha256']),
                                       ('delta_archive_member', delta_archive, delta_sha256)]:
                path = Path(path)
                assert not path.resolve().is_relative_to(root)
                fd = os.open(path, os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW)
                stream = os.fdopen(fd, 'rb')
                self.archives[kind] = dict(stream=stream, sha256=digest)
                assert stat.S_ISREG(os.fstat(fd).st_mode)
                assert hashlib.file_digest(stream, 'sha256').hexdigest() == digest
                stream.seek(0)
                self.archives[kind]['identity'] = self._source_identity(stream)
            self._scan()
        except BaseException:
            self.close()
            raise

    @staticmethod
    def _name(name):
        assert isinstance(name, str) and '\x00' not in name
        path = PurePosixPath(name)
        assert path.is_absolute() and name != '/' and '..' not in path.parts and str(path) == name
        return name

    def _validate_manifest(self, manifest):
        assert manifest['format'] == 'fx0-stable-file-delta-v2'
        assert isinstance(self.rows, dict) and self.rows
        groups = {}
        known_children = {}
        for name, row in self.rows.items():
            self._name(name)
            assert row['kind'] in {'absent','directory','symlink','file'}
            if row['kind'] == 'absent':
                assert row == {'kind':'absent'}
                continue
            assert type(row['mode']) is int and 0 <= row['mode'] <= 0o7777
            assert all(type(row[k]) is int and row[k] >= 0 for k in ['uid','gid'])
            assert type(row['mtime_ns']) is int and isinstance(row['xattrs'], dict)
            for key, value in row['xattrs'].items():
                assert '\x00' not in key and bytes.fromhex(value).hex() == value
            parent = str(PurePosixPath(name).parent)
            assert parent == '/' or self.rows.get(parent, {}).get('kind') == 'directory'
            known_children.setdefault(parent, set()).add(PurePosixPath(name).name)
            if row['kind'] == 'symlink':
                assert isinstance(row['target'], str) and '\x00' not in row['target']
            if row['kind'] != 'file':
                assert 'data_source' not in row and 'hardlink_to' not in row
                continue
            assert type(row['size']) is int and row['size'] >= 0
            assert len(bytes.fromhex(row['sha256'])) == 32
            assert type(row['nlink']) is int and row['nlink'] >= 1
            leader = row.get('hardlink_to', name)
            groups.setdefault(leader, []).append(name)
            if leader != name:
                assert leader in self.rows and 'hardlink_to' not in self.rows[leader]
                for key in ['kind','mode','uid','gid','mtime_ns','xattrs','size','sha256','nlink']:
                    assert row[key] == self.rows[leader][key]
                assert 'data_source' not in row
            else:
                source = row['data_source']
                assert len(source) == 1
                kind, member = next(iter(source.items()))
                assert kind in {'base_archive_member','delta_archive_member'}
                assert member == name.lstrip('/')
                assert (kind, member) not in self.refs
                self.refs[kind, member] = name
        for leader, names in groups.items():
            assert self.rows[leader]['nlink'] == len(names), ('Open captured hardlink group', leader)
        self.expected_groups = groups
        for name, children in self.membership.items():
            self._name(name)
            assert self.rows[name]['kind'] == 'directory'
            assert children == sorted(set(children))
            assert all(isinstance(n,str) and n not in {'','.', '..'} and '/' not in n and '\x00' not in n for n in children)
            assert known_children.get(name, set()) <= set(children)

    @staticmethod
    def _source_identity(stream):
        value = os.fstat(stream.fileno())
        return value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns

    def _check_sources(self):
        for source in self.archives.values():
            assert self._source_identity(source['stream']) == source['identity'], 'Source archive changed'

    def _check_mounts(self):
        for line in Path('/proc/self/mountinfo').read_text().splitlines():
            point = line.split()[4]
            for escaped, literal in [('\\040',' '),('\\011','\t'),('\\012','\n'),('\\134','\\')]:
                point = point.replace(escaped,literal)
            assert not point.startswith(str(self.root)+'/'), 'Nested mount in private restore root'

    def _scan(self, install=None):
        self._check_sources()
        seen_refs = set()
        for kind, source in self.archives.items():
            source['stream'].seek(0)
            seen = set()
            # gzip.GzipFile bounds decompression output to each requested read;
            # tarfile's built-in streaming gzip decoder can inflate an entire
            # compressed block at once for highly compressible file bodies.
            with gzip.GzipFile(fileobj=source['stream'], mode='rb') as decoded, tarfile.open(fileobj=decoded, mode='r|') as archive:
                for member in archive:
                    name = member.name.rstrip('/')
                    self._name('/' + name)
                    assert not member.name.startswith('/') and name not in seen
                    assert member.isfile() or member.isdir() or member.issym() or member.islnk()
                    seen.add(name)
                    key = kind, member.name
                    if key not in self.refs:
                        continue
                    target = self.refs[key]
                    row = self.rows[target]
                    assert member.isfile() and member.size == row['size']
                    with archive.extractfile(member) as body:
                        if install is None:
                            digest = hashlib.sha256()
                            partial = self._open_partial(target, readonly=True)
                            if partial is not None:
                                with partial:
                                    self._matching_prefix(partial, body, digest)
                            while block := body.read(1024**2):
                                digest.update(block)
                            digest = digest.hexdigest()
                        else:
                            digest = install(target, body)
                    assert digest == row['sha256'], ('Archived body differs', target)
                    seen_refs.add(key)
                while decoded.read(1024**2):
                    pass  # Finish the gzip footer and CRC validation.
            self._check_sources()
        assert seen_refs == set(self.refs), 'Missing referenced archive body'

    def close(self):
        for value in self.archives.values():
            value['stream'].close()
        self.archives.clear()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _closed_existing_links(self):
        observed = {}
        for name in self.rows:
            path = self.target(name)
            try:
                value = path.lstat()
            except FileNotFoundError:
                continue
            if stat.S_ISREG(value.st_mode):
                observed.setdefault((value.st_dev,value.st_ino), []).append((name,value.st_nlink))
        for names in observed.values():
            assert all(nlink == len(names) for _,nlink in names), 'Existing hardlink crosses captured scope'

    def _captured_links_match(self, name, path):
        value = path.lstat()
        peers = self.expected_groups[name]
        if value.st_nlink != len(peers):
            return False
        for peer in peers:
            try:
                other = self.target(peer).lstat()
            except FileNotFoundError:
                return False
            if not stat.S_ISREG(other.st_mode) or (other.st_dev,other.st_ino) != (value.st_dev,value.st_ino):
                return False
        return True

    def partial_path(self, name):
        key = hashlib.sha256((name+'\x00'+self.rows[name]['sha256']).encode()).hexdigest()
        return self.target(name).with_name('.fx0-stream-restore-'+key)

    def _open_partial(self, name, *, readonly):
        path = self.partial_path(name)
        try:
            fd = os.open(path, (os.O_RDONLY if readonly else os.O_RDWR) | os.O_CLOEXEC | os.O_NOFOLLOW)
        except FileNotFoundError:
            return None
        except OSError as error:
            raise AssertionError('Unrecognised private restore partial; preserve it') from error
        try:
            value = os.fstat(fd)
            visible = path.lstat()
            assert stat.S_ISREG(value.st_mode) and value.st_nlink == 1
            assert (value.st_dev,value.st_ino) == (visible.st_dev,visible.st_ino)
            assert (value.st_uid,value.st_gid,stat.S_IMODE(value.st_mode)) == (os.geteuid(),os.getegid(),0o600)
            assert value.st_size <= self.rows[name]['size']
            assert set(os.listxattr(path,follow_symlinks=False)) <= {'security.selinux'}
        except BaseException:
            os.close(fd)
            raise
        return os.fdopen(fd, 'rb' if readonly else 'r+b')

    @staticmethod
    def _matching_prefix(partial, source, digest):
        count = 0
        while block := partial.read(1024**2):
            assert source.read(len(block)) == block, 'Private restore partial is not an authenticated body prefix'
            digest.update(block)
            count += len(block)
        assert count == os.fstat(partial.fileno()).st_size
        return count

    def restore(self, *, stop_after=None):
        self._check_mounts()
        self.preflight()
        self._check_sources()
        self._closed_existing_links()
        changes = 0
        parents = set()
        def changed(path):
            nonlocal changes
            changes += 1
            parents.add(path.parent)
            if stop_after is not None and changes >= stop_after:
                raise InterruptedError('Private restore interrupted after %d changes' % changes)
        ordered = sorted(self.rows, key=lambda n:(len(PurePosixPath(n).parts),n))
        for name in reversed(ordered):
            path = self.target(name)
            if self.rows[name]['kind'] == 'absent' and os.path.lexists(path):
                self.remove(path)
                changed(path)
        for name in ordered:
            if self.rows[name]['kind'] != 'directory':
                continue
            path = self.target(name)
            if path.is_symlink() or (path.exists() and not path.is_dir()):
                self.remove(path)
            if not path.exists():
                path.mkdir()
                changed(path)

        def install(name, source):
            row, path = self.rows[name], self.target(name)
            # Every reused body is rehashed; metadata is restored separately.
            same = False
            if path.is_file() and not path.is_symlink() and path.stat().st_size == row['size'] and self._captured_links_match(name, path):
                with path.open('rb') as current:
                    same = hashlib.file_digest(current, 'sha256').hexdigest() == row['sha256']
            partial_path = self.partial_path(name)
            output = self._open_partial(name, readonly=False)
            digest = hashlib.sha256()
            if same:
                if output is not None:
                    with output:
                        self._matching_prefix(output, source, digest)
                while block := source.read(1024**2):
                    digest.update(block)
                assert digest.hexdigest() == row['sha256']
                if output is not None:
                    partial_path.unlink()
                    changed(partial_path)
                return digest.hexdigest()
            if path.is_dir() and not path.is_symlink():
                self.remove(path)
            if output is None:
                fd = os.open(partial_path,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600)
                os.fchown(fd,os.geteuid(),os.getegid())
                os.fchmod(fd,0o600)
                for key in os.listxattr(fd):
                    if key != 'security.selinux':
                        os.removexattr(fd,key)
                output = os.fdopen(fd,'r+b')
            total = 0
            with output:
                total = self._matching_prefix(output, source, digest)
                while block := source.read(1024**2):
                    digest.update(block)
                    total += len(block)
                    output.write(block)
                output.flush()
                os.fsync(output.fileno())
                value = os.fstat(output.fileno())
                visible = partial_path.lstat()
                assert (value.st_dev,value.st_ino) == (visible.st_dev,visible.st_ino)
            assert total == row['size'] and digest.hexdigest() == row['sha256']
            os.replace(partial_path, path)
            changed(path)
            return digest.hexdigest()
        self._scan(install)
        for name in ordered:
            row, path = self.rows[name], self.target(name)
            if row['kind'] == 'symlink':
                if not path.is_symlink() or os.readlink(path) != row['target']:
                    self.remove(path)
                    path.symlink_to(row['target'])
                    changed(path)
            elif 'hardlink_to' in row:
                peer = self.target(row['hardlink_to'])
                if path.is_symlink() or not path.exists() or (path.stat().st_dev,path.stat().st_ino) != (peer.stat().st_dev,peer.stat().st_ino):
                    self.remove(path)
                    os.link(peer, path, follow_symlinks=False)
                    changed(path)
        ignored = {'security.selinux'} if self.skip_selinux else set()
        for name in reversed(ordered):
            row, path = self.rows[name], self.target(name)
            if row['kind'] == 'absent':
                continue
            value = path.lstat()
            attrs = {k:os.getxattr(path,k,follow_symlinks=False).hex() for k in os.listxattr(path,follow_symlinks=False) if k not in ignored}
            expected = {k:v for k,v in row['xattrs'].items() if k not in ignored}
            if (stat.S_IMODE(value.st_mode),value.st_uid,value.st_gid,value.st_mtime_ns,attrs) == (row['mode'],row['uid'],row['gid'],row['mtime_ns'],expected):
                continue
            os.chown(path,row['uid'],row['gid'],follow_symlinks=False)
            if row['kind'] != 'symlink':
                os.chmod(path,row['mode'],follow_symlinks=False)
            for key in attrs.keys() - expected.keys():
                os.removexattr(path,key,follow_symlinks=False)
            for key,val in expected.items():
                if attrs.get(key) != val:
                    os.setxattr(path,key,bytes.fromhex(val),follow_symlinks=False)
            os.utime(path,ns=(row['mtime_ns'],row['mtime_ns']),follow_symlinks=False)
            if row['kind'] == 'file' and 'hardlink_to' not in row:
                fd = os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
                try:
                    os.fsync(fd)
                finally:
                    os.close(fd)
            changed(path)
            if row['kind'] == 'directory':
                parents.add(path)
        for parent in sorted(parents, key=str):
            if not parent.exists():
                continue  # A captured absent directory may have been removed.
            fd = os.open(parent,os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        self._check_sources()
        return dict(changes=changes, memory_file_body_buffer_bytes=1024**2)

    def verify(self):
        super().verify()
        for name, children in self.membership.items():
            assert sorted(p.name for p in self.target(name).iterdir()) == children, ('Directory membership differs',name)
        self._check_sources()
