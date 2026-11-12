#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Guarded native Fx0 kernel update; --check never installs or writes a partition."""
import argparse
import datetime
import fcntl
import gzip
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import signal
import stat
import struct
import subprocess
import tarfile
import tempfile
import time

import update_transaction as transaction
import commit_state

BACKUP_ROOT = Path('/var/lib/fx0-rollback/kernel-6.18.63-01')
DEVICE = Path('/dev/mmcblk0p15')
RELEASE = '6.18.63-fx0-vibrator-alpine'
KERNEL_PACKAGE = 'linux-postmarketos-qcom-msm8226'
SIGNATURE_CONFIG = Path('/etc/kernel-cmdline.d/90-fx0-module-signatures.conf')
SIGNATURE_CONTENT = b'module.sig_enforce=1\n'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def out(*args):
    return subprocess.check_output(args, text=True, timeout=20).strip()


def atomic(path, data, mode=0o644, uid=0, gid=0):
    path = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.' + path.name + '.fx0-', dir=path.parent)
    try:
        os.fchmod(descriptor, mode)
        os.fchown(descriptor, uid, gid)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    finally:
        if os.path.lexists(temporary):
            os.unlink(temporary)


def database(data):
    result = {}
    for paragraph in data.decode().split('\n\n'):
        fields = {}
        for line in paragraph.splitlines():
            if len(line) > 1 and line[1] == ':':
                fields.setdefault(line[0], []).append(line[2:])
        if fields.get('P'):
            result[fields['P'][0]] = {key: fields.get(key, []) for key in ['V', 'C']}
    return result


def cpio_index(compressed):
    data = gzip.decompress(compressed)
    entries = {}
    at = 0
    trailers = 0
    while at < len(data):
        while at < len(data) and data[at] == 0:
            at += 1
        if at == len(data):
            break
        assert at % 4 == 0 and data[at:at + 6] == b'070701'
        header = data[at:at + 110]
        assert len(header) == 110
        fields = [int(header[n:n + 8], 16) for n in range(6, 110, 8)]
        size, length = fields[6], fields[11]
        name = data[at + 110:at + 110 + length]
        assert name.endswith(b'\0')
        name = str(PurePosixPath(name[:-1].decode()))
        start = (at + 110 + length + 3) & ~3
        end = start + size
        assert end <= len(data)
        payload = data[start:end]
        at = (end + 3) & ~3
        if name == 'TRAILER!!!':
            assert size == 0
            trailers += 1
            continue
        assert not name.startswith('/') and '..' not in PurePosixPath(name).parts
        assert name not in entries
        entries[name] = dict(mode=fields[1], uid=fields[2], gid=fields[3],
                             sha256=hashlib.sha256(payload).hexdigest())
    assert trailers == 1
    return entries


def boot_parts(data, kernel_bytes):
    assert data.startswith(b'ANDROID!') and len(data) >= 2048
    size, address, rsize, raddress, second, saddress, tags, page, version, unused = struct.unpack_from('<10I', data, 8)
    assert (address, raddress, second, saddress, tags, page, version, unused) == (
        0x8000, 0x02000000, 0, 0x00f00000, 0x01e00000, 2048, 0, 0)
    assert kernel_bytes < size
    rstart = page + ((size + page - 1) // page) * page
    assert len(data) == rstart + ((rsize + page - 1) // page) * page
    assert not any(data[page + size:rstart]) and not any(data[rstart + rsize:])
    kernel = data[page:page + size]
    ramdisk = data[rstart:rstart + rsize]
    digest = hashlib.sha1()
    for part in [kernel, ramdisk, b'']:
        digest.update(part)
        digest.update(struct.pack('<I', len(part)))
    assert digest.digest() == data[576:596]
    assert data[596:608] == b'\0' * 12 and not any(data[608:1632])
    assert raddress + len(ramdisk) < 0x03200000
    cmdline = data[64:576].split(b'\0', 1)[0].decode('ascii').split()
    return kernel[:kernel_bytes], kernel[kernel_bytes:], ramdisk, cmdline


def snapshot(roots):
    result = {}
    def visit(path):
        metadata = path.lstat()
        row = dict(mode=stat.S_IMODE(metadata.st_mode), uid=metadata.st_uid, gid=metadata.st_gid)
        if stat.S_ISDIR(metadata.st_mode):
            row['kind'] = 'directory'
            for child in sorted(path.iterdir()):
                visit(child)
        elif stat.S_ISLNK(metadata.st_mode):
            row.update(kind='symlink', target=os.readlink(path))
        else:
            assert stat.S_ISREG(metadata.st_mode), str(path)
            row.update(kind='file', size=metadata.st_size, sha256=sha(path))
        result[str(path)] = row
    for name in roots:
        visit(Path('/') / name)
    return dict(sorted(result.items()))


class NativeUpdate:
    def __init__(self, plan, require_owner):
        self.plan = plan
        self.require_owner = require_owner
        self.root = BACKUP_ROOT
        assert sha(self.root / 'backup.private.json') == plan['backup_metadata_sha256']
        self.backup = json.loads((self.root / 'backup.private.json').read_text())
        assert sha(self.root / 'before-files.private.tar.gz') == self.backup['archive_sha256']
        self.status = self.root / 'kernel-update-status.json'
        self.state = dict(started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                          PID=os.getpid(), native_installation_started=False,
                          rollback_attempted=False, automatic_reboot=False)
        self.children = []
        self.scope = None
        self.baseline_db = database(self.archive_bytes('lib/apk/db/installed'))
        self.old_world = self.archive_bytes('etc/apk/world')
        held = [line for line in self.old_world.decode().splitlines(keepends=True)
                if line.startswith(KERNEL_PACKAGE + '><Q1')]
        assert len(held) == 1
        self.new_world = self.old_world.decode().replace(
            held[0], KERNEL_PACKAGE + '><' + plan['candidate_control_checksum'] + '\n').encode()
        self.old_boot_image = self.archive_bytes('boot/boot.img')
        assert sha(Path(commit_state.__file__)) == plan['commit_state_helper_sha256']
        capture_path = self.root / 'commit-state.private.json'
        assert sha(capture_path) == plan['commit_state_capture_sha256']
        self.commit = commit_state.CommitState('/', json.loads(capture_path.read_text()))
        self.generated_inventory = None

    def archive_bytes(self, name):
        with tarfile.open(self.root / 'before-files.private.tar.gz', 'r:gz') as archive:
            return archive.extractfile(name).read()

    def record(self, stage, **fields):
        self.state.update(stage=stage, **fields)
        atomic(self.status, (json.dumps(self.state, indent=2) + '\n').encode(), 0o600)

    def verify_identity(self):
        assert os.geteuid() == 0
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == self.backup['boot_id']
        assert Path('/proc/sys/kernel/osrelease').read_text().strip() == '6.18.59-fx0-dmp'
        assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
        assert out('systemctl', 'is-active', 'tinydm', 'upower', 'iio-sensor-proxy').splitlines() == ['active'] * 3
        assert len(out('pgrep', '-x', 'sway').splitlines()) == 1
        assert len(out('pgrep', '-x', 'lisgd').splitlines()) == 1

    def verify_device(self):
        assert stat.S_ISBLK(DEVICE.stat().st_mode)
        assert Path(out('findfs', 'PARTLABEL=boot')).resolve() == DEVICE
        assert int(out('blockdev', '--getsize64', str(DEVICE))) == self.backup['raw_boot_bytes']
        with DEVICE.open('rb') as stream:
            prefix = stream.read(self.plan['boot_offset'])
        assert hashlib.sha256(prefix).hexdigest() == self.plan['bootloader_prefix_sha256']

    def verify_runtime_inputs(self):
        assert sorted(p.name for p in Path('/etc/apk/keys').iterdir() if p.is_file()) == self.plan['public_APK_key_names']
        for name, expected in self.plan['runtime_input_sha256'].items():
            assert sha(name) == expected, name

    def verify_labels(self):
        for name, expected in self.plan['original_xattrs'].items():
            assert {key: os.getxattr(name, key, follow_symlinks=False).hex()
                    for key in os.listxattr(name, follow_symlinks=False)} == expected, name

    def verify_signature_parent(self):
        expected = self.plan['signature_config_parent_metadata']
        path = SIGNATURE_CONFIG.parent
        assert path.is_dir() and not path.is_symlink()
        metadata = path.stat()
        assert (stat.S_IMODE(metadata.st_mode), metadata.st_uid, metadata.st_gid) == (expected['mode'], expected['uid'], expected['gid'])
        assert {key: os.getxattr(path, key).hex() for key in os.listxattr(path)} == expected['xattrs_hex']

    def apply_labels(self):
        for name, attributes in self.plan['original_xattrs'].items():
            for key, value in attributes.items():
                os.setxattr(name, key, bytes.fromhex(value), follow_symlinks=False)

    def preflight(self):
        assert not self.status.exists()
        assert self.plan['boot_offset'] == 524288 and self.plan['candidate_release'] == RELEASE
        assert self.plan['candidate_control_checksum'] == 'Q1zTO1mlgs1wilduzQdkNU/kbwGNI='
        assert self.root.is_dir() and not self.root.is_symlink()
        assert self.root.stat().st_uid == 0 and stat.S_IMODE(self.root.stat().st_mode) == 0o700
        assert self.backup['boot_id'] == self.plan['boot_id']
        assert sha(self.root / 'backup.private.json') == self.plan['backup_metadata_sha256']
        assert sha(self.root / 'before-files.private.tar.gz') == self.backup['archive_sha256']
        assert sha(self.root / 'boot-partition.private.img') == self.backup['raw_boot_sha256']
        assert self.backup['snapshot_paths'] == 2595
        assert self.backup['backup_roots'] == ['boot', 'usr/lib/modules', 'usr/share/kernel', 'lib/apk/db', 'etc/apk/world']
        self.verify_identity()
        self.verify_device()
        self.verify_runtime_inputs()
        self.commit.verify_original()
        inventories = []
        for directory in ['/usr/lib/systemd/system', '/usr/lib/systemd/user']:
            result = subprocess.run(['/usr/bin/treescan', directory], capture_output=True, check=True, timeout=30)
            assert not result.stderr, 'Unit scan reported an error'
            inventories.append(result.stdout)
        self.generated_inventory = b''.join(inventories)
        assert self.generated_inventory
        assert sha(DEVICE) == self.backup['raw_boot_sha256']
        assert snapshot(self.backup['backup_roots']) == self.backup['snapshot']
        self.verify_labels()
        self.verify_signature_parent()
        assert not SIGNATURE_CONFIG.exists() and not SIGNATURE_CONFIG.is_symlink()
        assert sorted(p.name for p in SIGNATURE_CONFIG.parent.iterdir()) == self.plan['original_cmdline_directory_entries']
        assert not (Path('/usr/lib/modules') / RELEASE).exists()
        assert not Path('/run/systemd/system/fx0-native-return.timer').exists()
        assert shutil.disk_usage('/').free > 1500000000
        for name, key in [('candidate.apk', 'candidate_APK_sha256'), ('rollback.apk', 'rollback_APK_sha256')]:
            assert sha(self.root / name) == self.backup[key]
        assert out('systemctl', 'is-system-running') == 'running'
        assert not out('systemctl', '--failed', '--no-legend') and not out('systemctl', 'list-jobs', '--no-legend')
        if self.require_owner:
            ui = self.plan['owner_display_touch']
            assert ui['status'] == 'confirmed' and ui['display_confirmed'] and ui['touch_confirmed']
            assert ui.get('native_boot_id', ui.get('boot_id')) == self.backup['boot_id']

    def set_install_scope(self):
        expected = '/system.slice/fx0-kernel-6.18.63-install-01.service'
        rows = Path('/proc/self/cgroup').read_text().splitlines()
        assert rows == ['0::' + expected], 'Installation requires the dedicated systemd service'
        self.scope = Path('/sys/fs/cgroup') / expected.lstrip('/')
        assert self.scope.is_dir()

    def hooks_terminal(self):
        for child in self.children:
            if child.poll() is None:
                return False
            try:
                os.killpg(child.pid, 0)
            except ProcessLookupError:
                continue
            return False
        if self.scope is not None:
            for file in self.scope.rglob('cgroup.procs'):
                if any(int(pid) != os.getpid() for pid in file.read_text().split()):
                    return False
        return True

    def apk_command(self, package):
        return ['/sbin/apk', '--no-interactive', 'add', '--no-network', str(self.root / package)]

    def run_apk(self, phase, package):
        with (self.root / (phase + '.log')).open('xb') as log:
            child = subprocess.Popen(self.apk_command(package), stdout=log,
                                     stderr=subprocess.STDOUT, start_new_session=True)
            self.children.append(child)
            self.record(phase + '-hooks-running', package_process_PID=child.pid)
            code = child.wait()
            # Never kill or race a surviving descendant with restoration writes.
            while not self.hooks_terminal():
                self.record(phase + '-waiting-for-descendants', package_parent_returncode=code)
                time.sleep(2)
        self.record(phase + '-hooks-terminal', package_parent_returncode=code,
                    all_owned_process_groups_terminal=True)
        assert code == 0, 'Native APK transaction failed: ' + phase

    def install(self):
        self.record('installing', native_installation_started=True)
        original = self.backup['snapshot']['/etc/apk/world']
        atomic('/etc/apk/world', self.new_world, original['mode'], original['uid'], original['gid'])
        atomic(SIGNATURE_CONFIG, SIGNATURE_CONTENT)
        self.run_apk('candidate', 'candidate.apk')
        self.apply_labels()
        os.sync()

    def verify_package_state(self, candidate):
        current = database(Path('/lib/apk/db/installed').read_bytes())
        assert current.keys() == self.baseline_db.keys()
        assert {k: v for k, v in current.items() if k != KERNEL_PACKAGE} == {
            k: v for k, v in self.baseline_db.items() if k != KERNEL_PACKAGE}
        if candidate:
            assert current[KERNEL_PACKAGE] == dict(V=['6.18.63-r1'], C=[self.plan['candidate_control_checksum']])
        else:
            assert current == self.baseline_db

    def verify_candidate(self):
        self.verify_identity()
        self.verify_device()
        self.verify_runtime_inputs()
        self.verify_package_state(True)
        assert Path('/etc/apk/world').read_bytes() == self.new_world
        assert SIGNATURE_CONFIG.read_bytes() == SIGNATURE_CONTENT
        assert not SIGNATURE_CONFIG.is_symlink() and stat.S_IMODE(SIGNATURE_CONFIG.stat().st_mode) == 0o644
        self.verify_labels()
        self.verify_signature_parent()
        assert sorted(p.name for p in SIGNATURE_CONFIG.parent.iterdir()) == sorted(self.plan['original_cmdline_directory_entries'] + [SIGNATURE_CONFIG.name])
        for name, digest in self.plan['candidate_payload_sha256'].items():
            assert sha('/' + name) == digest, name
        assert Path('/usr/share/kernel/postmarketos-qcom-msm8226/kernel.release').read_text().strip() == RELEASE
        image = Path('/boot/boot.img').read_bytes()
        kernel, dtb, ramdisk, cmdline = boot_parts(image, self.plan['kernel_bytes'])
        assert hashlib.sha256(kernel).hexdigest() == self.plan['kernel_sha256']
        assert hashlib.sha256(dtb).hexdigest() == self.plan['DTB_sha256']
        assert ramdisk == Path('/boot/initramfs').read_bytes()
        assert cpio_index(ramdisk) == self.plan['expected_initramfs_payloads']
        before_cmdline = self.old_boot_image[64:576].split(b'\0', 1)[0].decode('ascii').split()
        assert not any(word.startswith('module.sig_enforce=') for word in before_cmdline)
        assert cmdline.count('module.sig_enforce=1') == 1
        assert [word for word in cmdline if word != 'module.sig_enforce=1'] == before_cmdline
        assert not any(word.startswith('fx0.native_trial=') for word in cmdline)
        with DEVICE.open('rb') as stream:
            stream.seek(self.plan['boot_offset'])
            assert stream.read(len(image)) == image
        assert self.plan['boot_offset'] + len(image) < self.backup['raw_boot_bytes']
        # Verify retained kernels and local known-good boot artifacts separately.
        owned = {str((Path('/') / name).resolve()) for name in self.plan['rollback_payload_paths']}
        mutable = owned | {'/boot/initramfs', '/boot/boot.img', '/boot/qcom-msm8926-lg-madai.dtb'}
        for name, row in self.backup['snapshot'].items():
            if row['kind'] == 'file' and name not in mutable and not name.startswith('/lib/apk/db/') and name != '/etc/apk/world':
                assert sha(name) == row['sha256'], name
        self.commit.verify_generated(self.generated_inventory)
        self.record('candidate-files-and-boot-verified', candidate_boot_image_sha256=hashlib.sha256(image).hexdigest(),
                    candidate_initramfs_sha256=hashlib.sha256(ramdisk).hexdigest(),
                    candidate_payload_files_verified=len(self.plan['candidate_payload_sha256']),
                    initramfs_payloads_verified=len(self.plan['expected_initramfs_payloads']),
                    other_774_package_identities_unchanged=True, bootloader_prefix_preserved=True,
                    module_signature_force_in_persistent_cmdline=True, reboot_required=True)

    def rollback(self):
        assert self.hooks_terminal()
        self.verify_identity()
        self.verify_device()
        self.verify_runtime_inputs()
        current = database(Path('/lib/apk/db/installed').read_bytes())
        assert {k: v for k, v in current.items() if k != KERNEL_PACKAGE} == {
            k: v for k, v in self.baseline_db.items() if k != KERNEL_PACKAGE}, 'Unrelated package state changed'
        assert Path('/etc/apk/world').read_bytes() in [self.old_world, self.new_world]
        if SIGNATURE_CONFIG.exists():
            assert not SIGNATURE_CONFIG.is_symlink() and SIGNATURE_CONFIG.read_bytes() == SIGNATURE_CONTENT
            SIGNATURE_CONFIG.unlink()
        self.commit.cleanup_executor(hooks_terminal=self.hooks_terminal())
        self.record('rollback-started', rollback_attempted=True)
        row = self.backup['snapshot']['/etc/apk/world']
        atomic('/etc/apk/world', self.old_world, row['mode'], row['uid'], row['gid'])
        # A partial failed installation can still be repaired from the complete
        # snapshot even if the normal signed-APK rollback itself returns failure.
        try:
            self.run_apk('rollback', 'rollback.apk')
        except Exception:
            assert self.hooks_terminal()
            self.record('rollback-APK-failed-restoring-complete-snapshot')
        candidate = Path('/usr/lib/modules') / RELEASE
        if candidate.exists():
            assert candidate.is_dir() and not candidate.is_symlink()
            shutil.rmtree(candidate)
        with tarfile.open(self.root / 'before-files.private.tar.gz', 'r:gz') as archive:
            members = {('/' + m.name): m for m in archive.getmembers()}
            assert set(members) == set(self.backup['snapshot'])
            for name, member in sorted(members.items(), key=lambda item: (len(PurePosixPath(item[0]).parts), item[0])):
                path = Path(name)
                if member.isdir():
                    assert not path.is_symlink()
                    path.mkdir(parents=True, exist_ok=True)
                    os.chown(path, member.uid, member.gid)
                    path.chmod(member.mode)
                else:
                    assert member.isfile() and not path.is_symlink()
                    atomic(path, archive.extractfile(member).read(), member.mode, member.uid, member.gid)
        self.apply_labels()
        self.commit.restore(hooks_terminal=self.hooks_terminal())
        metadata = self.plan['signature_config_parent_metadata']
        os.chown(SIGNATURE_CONFIG.parent, metadata['uid'], metadata['gid'])
        SIGNATURE_CONFIG.parent.chmod(metadata['mode'])
        for key, value in metadata['xattrs_hex'].items():
            os.setxattr(SIGNATURE_CONFIG.parent, key, bytes.fromhex(value))
        self.verify_device()
        result = transaction.restore_boot_tail(self.root / 'boot-partition.private.img', DEVICE,
                                               self.plan['boot_offset'], self.backup['raw_boot_sha256'])
        os.sync()
        self.record('rollback-restored', raw_boot_restore=result)

    def verify_rollback(self):
        self.verify_identity()
        self.verify_device()
        self.verify_runtime_inputs()
        self.verify_package_state(False)
        assert snapshot(self.backup['backup_roots']) == self.backup['snapshot']
        assert not SIGNATURE_CONFIG.exists() and not SIGNATURE_CONFIG.is_symlink()
        self.verify_labels()
        self.verify_signature_parent()
        assert sorted(p.name for p in SIGNATURE_CONFIG.parent.iterdir()) == self.plan['original_cmdline_directory_entries']
        assert sha(DEVICE) == self.backup['raw_boot_sha256']
        self.commit.verify_original()
        self.record('rollback-verified', original_snapshot_paths_verified=2595,
                    original_raw_boot_and_APK_state_verified=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('plan', type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--install', action='store_true')
    args = parser.parse_args()
    assert args.plan.resolve().parent == BACKUP_ROOT
    assert args.plan.stat().st_uid == 0 and stat.S_IMODE(args.plan.stat().st_mode) == 0o600
    plan = json.loads(args.plan.read_text())
    assert sha(Path(transaction.__file__)) == plan['transaction_helper_sha256']
    assert sha(Path(__file__)) == plan['controller_sha256']
    with (BACKUP_ROOT / 'kernel-update.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        ops = NativeUpdate(plan, require_owner=args.install)
        if args.check:
            ops.preflight()
            print(json.dumps(dict(read_only_preflight_passed=True, boot_id=plan['boot_id'],
                                  owner_UI_status=plan['owner_display_touch']['status'],
                                  native_installation=False, boot_partition_written=False)))
            return
        ops.set_install_scope()
        def interrupted(signum, frame):
            raise InterruptedError('Native update interrupted by signal ' + str(signum))
        signal.signal(signal.SIGTERM, interrupted)
        signal.signal(signal.SIGINT, interrupted)
        try:
            transaction.execute(ops)
        except BaseException:
            # Keep the service alive while owned hooks finish. Exiting a default
            # systemd service could kill an in-flight boot writer in its cgroup.
            had_active_hooks = not ops.hooks_terminal()
            while not ops.hooks_terminal():
                time.sleep(2)
            if had_active_hooks:
                ops.record('stopped-hooks-terminal-inspection-required')
            raise
        print(json.dumps(ops.state))


if __name__ == '__main__':
    main()
