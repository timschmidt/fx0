#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""One-package treescan activation with a fixed, guarded recovery namespace."""
import argparse
import base64
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tarfile
import tempfile
import time

BOOT = '991042aa-9e97-4848-b54c-ad391c06bae0'
RELEASE = '6.18.63-fx0-vibrator-alpine'
BACKUP = Path('/var/lib/fx0-rollback/post-r1-userspace-baseline-01')
MANIFEST_SHA = '17eebbe77e2a19896035b3791d4253cebdc2f659c7c9509e2e9dd660b3d96a06'
ARCHIVE_SHA = '7911243764046e8e8af693932a49ec41a99845fdd80bf4ffcb9e884413a4b3fb'
CANDIDATE_SHA = '24f63c20f7197468a005b08c023242e70c491edb40c965372c540d70736ddf11'
ROLLBACK_SHA = '4a43c233172270107b04f8438b24cb880c38ca006f8bd8ccf49989bbcd56e2fb'
INDEX_SHA = '0a4a578a2e36909a43f29b1b7cd46a4082b6b9a7e4f3161a80381c73b97516e0'
ELF_SHA = '933ebbc4bfe8017a5a6e39bc97d76a499cfaecf5598bacde68744a69206ad4a0'
OLD = dict(version='0.1-r0', checksum='Q1JFbX40hRcXMCTUYRgvA5taFhrbI=')
NEW = dict(version='0.1-r1', checksum='Q1ReYHEKb42riq9D9r5JZ4CWKD8I4=')
DB = '/usr/lib/apk/db/installed'
LOCK = '/usr/lib/apk/db/lock'
ELF = '/usr/bin/treescan'
WORLD = '/etc/apk/world'
INVENTORY = '/var/lib/systemd-apk/installed.units'
EXECUTOR = '/usr/lib/apk/exec'
FILES = frozenset({ELF, DB, '/usr/lib/apk/db/scripts.tar.gz',
                   '/usr/lib/apk/db/triggers', WORLD, INVENTORY})
DIRECTORIES = frozenset({'/usr/bin', '/usr/lib/apk/db', '/etc/apk',
                         '/var/lib/systemd-apk', EXECUTOR})


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def database(data):
    result = {}
    for paragraph in data.decode().split('\n\n'):
        row = {line[:1]: line[2:] for line in paragraph.splitlines()
               if len(line) > 1 and line[1] == ':'}
        if row.get('P'):
            assert row['P'] not in result, 'Duplicate package'
            result[row['P']] = dict(version=row['V'], checksum=row['C'])
    return result


def atomic(path, data, mode=0o600):
    descriptor, temporary = tempfile.mkstemp(prefix='.fx0-treescan-', dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


class Snapshot:
    """Read the complete baseline; write only the six fixed transaction files."""

    def __init__(self, root, manifest, payloads):
        self.root = Path(root).resolve(strict=True)
        self.manifest = manifest
        self.rows = manifest['paths']
        self.payloads = payloads
        self.lock_fd = None
        self.lock_inode = None
        assert FILES <= self.rows.keys() and DIRECTORIES <= self.rows.keys()
        assert set(payloads) == FILES
        for name in FILES:
            row = self.rows[name]
            assert row['kind'] == 'file' and row['nlink'] == 1
            assert 'hardlink_to' not in row
            assert digest(payloads[name]) == row['sha256']
        assert self.rows[LOCK]['kind'] == 'file' and self.rows[LOCK]['size'] == 0
        assert self.rows[LOCK]['nlink'] == 1 and self.rows[LOCK]['mode'] == 0o600
        assert manifest['directory_membership'][EXECUTOR] == []

    def target(self, name):
        assert name.startswith('/') and name != '/' and '..' not in Path(name).parts
        path = self.root
        for part in Path(name).parts[1:-1]:
            path /= part
            assert not path.is_symlink(), ('Symlink ancestor', name)
            if path.exists():
                assert path.is_dir(), ('Non-directory ancestor', name)
        return path / Path(name).name

    @staticmethod
    def attributes(path):
        return {key: os.getxattr(path, key, follow_symlinks=False).hex()
                for key in os.listxattr(path, follow_symlinks=False)}

    def locks(self):
        held = os.fstat(self.lock_fd)
        found = set()
        for line in Path('/proc/locks').read_text().splitlines():
            fields = line.split()
            if len(fields) < 8 or fields[1] not in {'FLOCK', 'POSIX'} or fields[4] != str(os.getpid()):
                continue
            major, minor, inode = fields[5].split(':')
            if (int(major, 16), int(minor, 16), int(inode)) == (
                    os.major(held.st_dev), os.minor(held.st_dev), held.st_ino):
                assert fields[3] == 'WRITE'
                found.add(fields[1])
        assert found == {'FLOCK', 'POSIX'}, 'Both real APK lock types must remain held'

    @contextlib.contextmanager
    def locked(self):
        assert self.lock_fd is None
        fd = os.open(self.target(LOCK), os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.lockf(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            st = os.fstat(fd)
            identity = st.st_dev, st.st_ino
            assert self.lock_inode is None or self.lock_inode == identity, 'APK lock inode replaced'
            self.lock_inode = identity
            self.lock_fd = fd
            self.locks()
            try:
                yield
            finally:
                self.locks()
        finally:
            self.lock_fd = None
            os.close(fd)

    def row(self, name):
        path = self.target(name)
        try:
            st = path.lstat()
        except FileNotFoundError:
            return dict(kind='absent')
        row = dict(mode=stat.S_IMODE(st.st_mode), uid=st.st_uid, gid=st.st_gid,
                   mtime_ns=st.st_mtime_ns, xattrs=self.attributes(path))
        if stat.S_ISDIR(st.st_mode):
            row['kind'] = 'directory'
        elif stat.S_ISLNK(st.st_mode):
            row.update(kind='symlink', target=os.readlink(path))
        else:
            assert stat.S_ISREG(st.st_mode), ('Unexpected special file', name)
            if name == LOCK:
                assert self.lock_fd is not None
                content_sha = digest(os.pread(self.lock_fd, st.st_size, 0))
            else:
                content_sha = sha(path)
            row.update(kind='file', size=st.st_size, nlink=st.st_nlink, sha256=content_sha)
        return row

    def verify(self, *, transaction_state=False, executor_may_contain_owned_script=False):
        assert self.lock_fd is not None
        changes = {}
        groups = {}
        for name, recorded in self.rows.items():
            wanted = {key: value for key, value in recorded.items()
                      if key not in {'data_source', 'hardlink_to'}}
            actual = self.row(name)
            ignored = set()
            if transaction_state and name in FILES:
                ignored = {'sha256', 'size', 'mtime_ns'}
                if name == ELF:
                    # Atomic APK replacement may have a default SELinux label.
                    # The controller explicitly reapplies the captured label.
                    ignored.add('xattrs')
            elif transaction_state and name in DIRECTORIES:
                ignored = {'mtime_ns'}
            assert {k: v for k, v in actual.items() if k not in ignored} == {
                k: v for k, v in wanted.items() if k not in ignored}, ('Unowned state changed', name, actual, wanted)
            if actual != wanted:
                changes[name] = sorted(k for k in actual.keys() | wanted.keys() if actual.get(k) != wanted.get(k))
            if actual['kind'] == 'file' and name not in FILES:
                st = self.target(name).lstat()
                leader = recorded.get('hardlink_to', name)
                identity = st.st_dev, st.st_ino
                assert leader not in groups or groups[leader] == identity, ('Hardlink identity', name)
                groups[leader] = identity
        for name, children in self.manifest['directory_membership'].items():
            if name == EXECUTOR and executor_may_contain_owned_script:
                continue
            assert sorted(p.name for p in self.target(name).iterdir()) == children, ('Directory membership', name)
        self.locks()
        return changes

    def metadata(self, name):
        assert name in FILES | DIRECTORIES
        path, row = self.target(name), self.rows[name]
        os.chown(path, row['uid'], row['gid'], follow_symlinks=False)
        path.chmod(row['mode'])
        for key in self.attributes(path).keys() - row['xattrs'].keys():
            os.removexattr(path, key, follow_symlinks=False)
        for key, value in row['xattrs'].items():
            if self.attributes(path).get(key) != value:
                os.setxattr(path, key, bytes.fromhex(value), follow_symlinks=False)
        os.utime(path, ns=(row['mtime_ns'], row['mtime_ns']), follow_symlinks=False)

    def restore(self, *, hooks_terminal):
        assert hooks_terminal and self.lock_fd is not None
        # Refuse every unowned modification before the first recovery write.
        self.verify(transaction_state=True)
        for name in sorted(FILES):
            atomic(self.target(name), self.payloads[name], self.rows[name]['mode'])
            self.metadata(name)
        for name in sorted(DIRECTORIES, key=lambda n: len(Path(n).parts), reverse=True):
            self.metadata(name)
        self.verify()


def load_snapshot(root):
    assert sha(BACKUP / 'manifest.private.json') == MANIFEST_SHA
    assert sha(BACKUP / 'files.private.tar.gz') == ARCHIVE_SHA
    manifest = json.loads((BACKUP / 'manifest.private.json').read_text())
    assert manifest['boot_id'] == BOOT and manifest['kernel'] == RELEASE
    assert manifest['combined_paths'] == len(manifest['paths']) == 7002
    assert len(manifest['directory_membership']) == 701
    payloads = {}
    with tarfile.open(BACKUP / 'files.private.tar.gz', 'r|gz') as archive:
        for member in archive:
            name = '/' + member.name
            if name in FILES:
                assert member.isfile() and name not in payloads
                assert member.size == manifest['paths'][name]['size']
                payloads[name] = archive.extractfile(member).read()
    return Snapshot(root, manifest, payloads)


class TreescanUpdate:
    def __init__(self, plan, work, *, fixture_failure=False):
        self.plan = plan
        self.work = Path(work).resolve(strict=True)
        self.root = Path(plan['root']).resolve(strict=True)
        self.live = self.root == Path('/')
        assert plan['format'] == 'fx0-treescan-transaction-v1'
        assert plan['unit'].startswith('fx0-treescan-') and plan['unit'].endswith('.service')
        assert plan['status_name'] == Path(plan['status_name']).name
        assert plan['status_name'].endswith('.json')
        assert sha(Path(__file__)) == plan['controller_sha256']
        assert not fixture_failure or not self.live, 'Failure injection is private-fixture only'
        if self.live:
            assert self.work == Path('/var/lib/fx0-rollback/treescan-live-r1-01')
            assert plan['live_update_approved'] and plan['qualified_controller_sha256'] == plan['controller_sha256']
            assert plan['inside'] == str(self.work)
        else:
            assert self.root == Path('/var/lib/fx0-rollback/treescan-controller-fixture-01/root')
            assert plan['inside'] == '/.fixture-controller'
        self.state = dict(stage='created', live_OS_transaction=self.live, automatic_reboot=False,
                          started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(), history=[])
        self.status = self.work / plan['status_name']
        self.snapshot = load_snapshot(self.root)
        self.original_db = database(self.snapshot.payloads[DB])
        assert len(self.original_db) == 775 and self.original_db['treescan'] == OLD
        assert self.original_db['linux-postmarketos-qcom-msm8226'] == dict(
            version='6.18.63-r1', checksum='Q1zTO1mlgs1wilduzQdkNU/kbwGNI=')
        self.children = []
        self.stopping = False
        self.recovering = False
        self.fixture_failure = fixture_failure
        self.number = 0
        self.initial_bin_names = None
        self.prefix = [] if self.live else ['/usr/sbin/chroot', str(self.root)]
        inside = plan['inside']
        assert inside.startswith('/') and '..' not in Path(inside).parts
        self.inside = inside
        self.apk = self.prefix + ['/usr/sbin/apk', '--no-interactive', '--arch', 'armv7', '--no-network',
                                  '--keys-dir', '/etc/apk/keys', '--repositories-file', inside + '/repositories',
                                  '--cache-dir', inside + '/cache']
        self.owned_scripts = {}
        with tarfile.open(fileobj=io.BytesIO(self.snapshot.payloads['/usr/lib/apk/db/scripts.tar.gz']), mode='r:gz') as archive:
            selected = [m for m in archive if m.name.startswith('busybox-1.37.0-r31.') and m.name.endswith('.trigger')]
            assert len(selected) == 1 and selected[0].isfile() and selected[0].size <= 65536
            self.owned_scripts['busybox-1.37.0-r31.trigger'] = archive.extractfile(selected[0]).read()

    def record(self, stage, **fields):
        self.state.update(stage=stage, **fields)
        self.state['history'].append(dict(stage=stage, UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        atomic(self.status, (json.dumps(self.state, indent=2) + '\n').encode())

    def hooks_terminal(self):
        if any(child.poll() is None for child in self.children):
            return False
        line = Path('/proc/self/cgroup').read_text().strip()
        assert line.startswith('0::') and '\n' not in line
        group = line.removeprefix('0::')
        assert group.endswith('/' + self.plan['unit']) or group == '/'
        parent = Path('/sys/fs/cgroup') / group.lstrip('/')
        pids = {int(pid) for path in parent.rglob('cgroup.procs') for pid in path.read_text().split()}
        return pids == {os.getpid()}

    def command(self, phase, args):
        assert '--no-scripts' not in args and '--allow-untrusted' not in args
        assert self.snapshot.lock_fd is None or phase == 'refresh-inventory'
        if self.stopping and not self.recovering:
            raise RuntimeError('Stop requested before next forward command')
        self.number += 1
        log = self.work / (self.status.stem + '-%02d-%s.log' % (self.number, phase))
        with log.open('xb') as stream:
            child = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
            self.children.append(child)
            code = child.wait()
            while not self.hooks_terminal():
                self.record(phase + '-waiting-for-owned-descendants', package_parent_returncode=code)
                time.sleep(2)
        self.record(phase + '-terminal', package_parent_returncode=code,
                    all_owned_process_groups_terminal=True)
        assert code == 0, ('Command failed', phase, code)
        if self.stopping and not self.recovering:
            raise RuntimeError('Stop requested after owned command reaped')
        return log.read_text()

    def identity(self):
        assert os.geteuid() == 0
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == BOOT
        assert os.uname().release == RELEASE
        assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
        assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip() == 'Y'
        if self.live:
            assert sha('/dev/mmcblk0p15') == self.snapshot.manifest['raw_boot_sha256']

    def package_state(self, *, candidate=None):
        current = database(self.snapshot.target(DB).read_bytes())
        assert {k: v for k, v in current.items() if k != 'treescan'} == {
            k: v for k, v in self.original_db.items() if k != 'treescan'}, 'Unrelated package identity changed'
        if candidate is not None:
            assert set(current) == set(self.original_db)
            assert current['treescan'] == (NEW if candidate else OLD)
        else:
            assert current.get('treescan') in [None, OLD, NEW]
        return current

    def world_guard(self, *, exact):
        before = self.snapshot.payloads[WORLD].decode().splitlines()
        current = self.snapshot.target(WORLD).read_text().splitlines()
        if exact:
            assert self.snapshot.target(WORLD).read_bytes() == self.snapshot.payloads[WORLD]
            return
        allowed = {'treescan', 'treescan=0.1-r0', 'treescan><' + OLD['checksum']}
        tree_lines = [line for line in current if re.match(r'^treescan(?:$|[<>=~@])', line)]
        old_tree_lines = [line for line in before if re.match(r'^treescan(?:$|[<>=~@])', line)]
        assert len(tree_lines) <= 1 and all(line in allowed for line in tree_lines)
        assert sorted(line for line in current if line not in tree_lines) == sorted(
            line for line in before if line not in old_tree_lines), 'Unrelated world entry changed'

    def bin_namespace(self):
        names = sorted(p.name for p in self.snapshot.target('/usr/bin').iterdir())
        if self.initial_bin_names is None:
            self.initial_bin_names = names
        else:
            assert names == self.initial_bin_names, 'Unexpected executable namespace'

    def cache_guard(self):
        directory = self.snapshot.target(self.inside + '/cache')
        assert directory.is_dir() and not directory.is_symlink()
        allowed = {}
        for identity, expected in [(OLD, ROLLBACK_SHA), (NEW, CANDIDATE_SHA)]:
            prefix = base64.b64decode(identity['checksum'][2:], validate=True).hex()[:8]
            allowed['treescan-' + identity['version'] + '.' + prefix + '.apk'] = expected
        for path in directory.iterdir():
            st = path.lstat()
            assert stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and (st.st_uid, st.st_gid) == (0, 0)
            expected = allowed.get(path.name)
            if expected is None:
                assert re.fullmatch(r'APKINDEX\.[0-9a-f]{8}\.tar\.gz', path.name), 'Unknown controller cache file'
                expected = INDEX_SHA
            assert sha(path) == expected, 'Controller cache payload differs from its signed input'

    def preflight(self):
        assert not self.status.exists()
        assert self.work.stat().st_uid == 0 and stat.S_IMODE(self.work.stat().st_mode) == 0o700
        self.identity()
        if self.live:
            assert subprocess.check_output(['systemctl', 'is-system-running'], text=True).strip() == 'running'
            assert subprocess.check_output(['systemctl', 'is-active', 'tinydm', 'upower',
                                            'iio-sensor-proxy'], text=True).splitlines() == ['active'] * 3
        assert self.hooks_terminal()
        inside = self.snapshot.target(self.inside)
        assert not inside.is_symlink() and inside.is_dir()
        for relative, expected in [('repo/armv7/APKINDEX.tar.gz', INDEX_SHA),
                                   ('repo/armv7/treescan-0.1-r1.apk', CANDIDATE_SHA),
                                   ('rollback.apk', ROLLBACK_SHA)]:
            path = self.snapshot.target(self.inside + '/' + relative)
            assert not path.is_symlink() and sha(path) == expected
        assert (inside / 'repositories').read_text() == self.inside + '/repo\n'
        self.cache_guard()
        with self.snapshot.locked():
            self.snapshot.verify()
            self.package_state(candidate=False)
            self.world_guard(exact=True)
            self.bin_namespace()
        assert self.command('version', self.prefix + ['/usr/sbin/apk', '--version']).strip() == 'apk-tools 3.0.8-r0, compiled for armv7.'
        for name, relative in [('verify-candidate', '/repo/armv7/treescan-0.1-r1.apk'),
                               ('verify-rollback', '/rollback.apk')]:
            self.command(name, self.prefix + ['/usr/sbin/apk', '--no-network', '--keys-dir',
                                               '/etc/apk/keys', 'verify', self.inside + relative])
        text = self.command('simulate', self.apk + ['upgrade', '--simulate', 'treescan'])
        actions = re.findall(r'^\([ 0-9]+/[ 0-9]+\) (?:Upgrading|Installing|Downgrading|Reinstalling) (\S+)', text, re.M)
        assert actions == ['treescan'] and '(0.1-r0 -> 0.1-r1)' in text
        with self.snapshot.locked():
            self.snapshot.verify()
        self.record('preflight-verified', baseline_paths=7002, memberships=701,
                    candidate_and_rollback_signature_verified=True, simulated_actions=actions)

    def inventory(self):
        expected = {}
        for stem in ['system', 'user']:
            start = self.snapshot.target('/usr/lib/systemd/' + stem)
            for parent, directories, files in os.walk(start, followlinks=False):
                for leaf in directories + files:
                    path = Path(parent) / leaf
                    name = '/' + str(path.relative_to(self.root))
                    kind = 'symlink' if path.is_symlink() else 'dir' if path.is_dir() else 'file'
                    expected[name] = kind, path.stat().st_mtime_ns // 10**9
        observed = {}
        for line in self.snapshot.target(INVENTORY).read_text().splitlines():
            name, kind, timestamp = line.rsplit(' ', 2)
            assert name not in observed and kind.startswith('type=') and timestamp.startswith('mtime=')
            observed[name] = kind[5:], int(timestamp[6:])
        assert len(expected) == 545 and observed == expected, 'Unit inventory differs from independent metadata'
        return len(expected)

    def install(self):
        self.record('installing', native_installation_started=True)
        self.command('upgrade', self.apk + ['--verbose', 'upgrade', 'treescan'])
        assert self.hooks_terminal()
        with self.snapshot.locked():
            self.package_state(candidate=True)
            self.world_guard(exact=True)
            self.snapshot.verify(transaction_state=True)
            self.bin_namespace()
            assert sha(self.snapshot.target(ELF)) == ELF_SHA
            # Preserve the original executable's policy label after APK's
            # atomic replacement, without replacing signed payload bytes.
            path = self.snapshot.target(ELF)
            attrs = self.snapshot.rows[ELF]['xattrs']
            for key in self.snapshot.attributes(path).keys() - attrs.keys():
                os.removexattr(path, key, follow_symlinks=False)
            for key, value in attrs.items():
                os.setxattr(path, key, bytes.fromhex(value), follow_symlinks=False)
            self.command('refresh-inventory', self.prefix + [
                '/etc/apk/commit_hooks.d/postmarketos-base-systemd', 'pre-commit'])
            self.inventory()
        if self.fixture_failure:
            raise RuntimeError('Qualified private failure after actual APK commit and inventory refresh')

    def verify_candidate(self):
        assert self.hooks_terminal()
        self.identity()
        self.cache_guard()
        with self.snapshot.locked():
            changes = self.snapshot.verify(transaction_state=True)
            self.package_state(candidate=True)
            self.world_guard(exact=True)
            self.bin_namespace()
            path = self.snapshot.target(ELF)
            assert sha(path) == ELF_SHA
            assert path.stat().st_mtime_ns == self.plan['candidate_mtime_ns']
            assert self.snapshot.attributes(path) == self.snapshot.rows[ELF]['xattrs']
            count = self.inventory()
        self.record('candidate-verified', baseline_paths_guarded=7002, memberships_guarded=701,
                    other_package_identities_unchanged=774, world_exact=True,
                    unit_entries_and_timestamps_verified=count, changed_captured_paths=changes,
                    database_sha256=sha(self.snapshot.target(DB)),
                    treescan_ELF_sha256=ELF_SHA, boot_written=False)

    def cleanup_executor(self):
        assert self.hooks_terminal() and self.snapshot.lock_fd is not None
        directory = self.snapshot.target(EXECUTOR)
        entries = sorted(directory.iterdir())
        checked = []
        for path in entries:
            assert path.name in self.owned_scripts, 'Unknown executor entry; preserve all'
            st = path.lstat()
            assert stat.S_ISREG(st.st_mode) and st.st_nlink == 1
            assert (st.st_uid, st.st_gid, st.st_size) == (0, 0, len(self.owned_scripts[path.name]))
            assert path.read_bytes() == self.owned_scripts[path.name]
            checked.append((path, st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns))
        for path, device, inode, size, mtime in checked:
            st = path.lstat()
            assert (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns) == (device, inode, size, mtime)
            path.unlink()
        assert not list(directory.iterdir())
        return [path.name for path, *_ in checked]

    def rollback(self):
        assert self.hooks_terminal(), 'Never restore while owned hooks remain'
        self.recovering = True
        self.identity()
        with self.snapshot.locked():
            self.snapshot.verify(transaction_state=True, executor_may_contain_owned_script=True)
            current = self.package_state()
            self.world_guard(exact=False)
            self.bin_namespace()
            removed = self.cleanup_executor()
            self.cache_guard()
        self.record('rollback-started', rollback_attempted=True, owned_executor_files_removed=removed)
        if current.get('treescan') != OLD or sha(self.snapshot.target(ELF)) != self.snapshot.rows[ELF]['sha256']:
            try:
                self.command('rollback-apk', self.apk + ['--verbose', 'add', self.inside + '/rollback.apk'])
            except Exception as error:
                assert self.hooks_terminal(), 'Do not restore while rollback hooks remain'
                self.record('rollback-APK-failed-rechecking-before-file-recovery', error=str(error))
        with self.snapshot.locked():
            self.package_state()
            self.world_guard(exact=False)
            self.snapshot.verify(transaction_state=True, executor_may_contain_owned_script=True)
            self.cleanup_executor()
            self.bin_namespace()
            self.cache_guard()
            self.snapshot.restore(hooks_terminal=self.hooks_terminal())
        self.record('rollback-files-restored', restored_files=sorted(FILES),
                    restored_directory_metadata=sorted(DIRECTORIES), APK_lock_inode_never_replaced=True)

    def verify_rollback(self):
        assert self.hooks_terminal()
        self.identity()
        with self.snapshot.locked():
            self.snapshot.verify()
            self.package_state(candidate=False)
            self.world_guard(exact=True)
            self.bin_namespace()
        self.record('rollback-verified', recovered_paths=7002, recovered_memberships=701,
                    original_775_package_identities_recovered=True, original_world_exact=True,
                    hardlink_aliases=254, SELinux_label_paths=1480, boot_written=False)


def transaction_module(plan):
    here = Path(__file__).resolve().parent
    path = here / 'update_transaction.py'
    if not path.exists():
        path = here.parent / 'kernel-maintenance/update_transaction.py'
    assert sha(path) == plan['transaction_helper_sha256']
    spec = importlib.util.spec_from_file_location('treescan_update_protocol', path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def execute(plan, work, *, fixture_failure=False, check=False):
    protocol = transaction_module(plan)
    work = Path(work).resolve(strict=True)
    assert work.stat().st_uid == 0 and stat.S_IMODE(work.stat().st_mode) == 0o700
    descriptor = os.open(work / 'transaction.lock', os.O_RDWR | os.O_CREAT | os.O_CLOEXEC | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ops = TreescanUpdate(plan, work, fixture_failure=fixture_failure)
        previous = {}
        for signum in [signal.SIGTERM, signal.SIGINT]:
            previous[signum] = signal.signal(signum, lambda number, frame: setattr(ops, 'stopping', True))
        try:
            if check:
                ops.preflight()
            else:
                protocol.execute(ops)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)
        return ops
    finally:
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--install-live', action='store_true')
    modes.add_argument('--fixture', action='store_true')
    parser.add_argument('--fixture-fail-after-commit', action='store_true')
    args = parser.parse_args()
    assert args.plan.stat().st_uid == 0 and stat.S_IMODE(args.plan.stat().st_mode) == 0o600
    plan = json.loads(args.plan.read_text())
    live = Path(plan['root']).resolve(strict=True) == Path('/')
    assert not live or (args.install_live or args.check)
    assert not args.install_live or live
    assert not args.fixture or not live
    assert not args.fixture_fail_after_commit or (args.fixture and not live)
    execute(plan, args.plan.resolve().parent, fixture_failure=args.fixture_fail_after_commit, check=args.check)


if __name__ == '__main__':
    main()
