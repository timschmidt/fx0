"""Actual no-script APK transactions and private file rollback in bounded RAM."""
import datetime
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile

spec = importlib.util.spec_from_file_location('restore', '/file_rollback.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
phase = Path('/capture')
manifest = json.loads((phase / 'capture-manifest.private.json').read_text())
summary = json.loads((phase / 'capture-summary.json').read_text())
plan = json.loads(Path('/preparation/stable-plan.json').read_text())
fetch = json.loads(Path('/preparation/package-fetch.json').read_text())
verified = json.loads(Path('/preparation/verified-packages.json').read_text())
root = Path('/work/root')
root.mkdir()
restore = helper.FileRollback(root, manifest, '/backup/before-files.private.tar.gz',
                              phase / 'delta-files.private.tar.gz', summary['archive_sha256'],
                              skip_selinux_for_host_fixture=True)
restore.restore()
restore.verify()
print('Original 5784-path fixture restored and verified', flush=True)
runtime = json.loads(Path('/runtime/runtime-manifest.json').read_text())
closure = json.loads(Path('/runtime/dependency-closure.json').read_text())
assert closure['complete_signed_payload_match'] and closure['all_NEEDED_and_interpreter_paths_resolved']
assert helper.sha_file('/runtime/runtime-libraries.tar.gz') == closure['runtime_archive_sha256']
with tarfile.open('/runtime/runtime-libraries.tar.gz', 'r:gz') as archive:
    for name, row in runtime['paths'].items():
        path = restore.target(name)
        if row['kind'] == 'file':
            content = archive.extractfile(name.lstrip('/')).read()
            if path.exists():
                assert path.read_bytes() == content
            else:
                path.write_bytes(content)
                path.chmod(row['mode'])
        else:
            if path.is_symlink():
                assert os.readlink(path) == row['target']
            else:
                assert not path.exists()
                path.symlink_to(row['target'])


def target(name):
    # Logical usrmerge aliases are intentionally available to APK inside chroot.
    return root / name.lstrip('/')

def database():
    result = {}
    for paragraph in target('/lib/apk/db/installed').read_text().split('\n\n'):
        row = {line[:1]: line[2:] for line in paragraph.splitlines()
               if len(line) > 1 and line[1] == ':'}
        if row.get('P'):
            result[row['P']] = dict(version=row['V'], checksum=row['C'])
    return result

original = database()
assert len(original) == 775
old_world = target('/etc/apk/world').read_bytes()
assert helper.sha_file(target('/lib/apk/db/installed')) == plan['native_database_sha256']
assert helper.sha_file(target('/etc/apk/world')) == plan['world_sha256']
expected = {row['package']: dict(version=row['version'], checksum=row['index_control_checksum'])
            for row in verified['packages']}
assert len(expected) == 30
assert not set(expected).intersection(row['package'] for row in plan['exact_world_checksum_holds'])
assert not any(name.startswith('sxmo-utils') for name in expected)
assert helper.sha_file('/qemu-arm-static') == closure['emulator_sha256']
shutil.copyfile('/qemu-arm-static', root / '.fixture-qemu')
(root / '.fixture-qemu').chmod(0o700)
(root / '.fixture-cache').mkdir()
repositories = []
for i in range(4):
    destination = root / ('.fixture-repos/%d/armv7' % i)
    destination.mkdir(parents=True)
    shutil.copyfile('/preparation/stable-repositories/%d/armv7/APKINDEX.tar.gz' % i,
                    destination / 'APKINDEX.tar.gz')
    repositories.append('/.fixture-repos/%d' % i)
for row in fetch['packages']:
    source = Path('/preparation') / row['path']
    assert helper.sha_file(source) == row['sha256']
    shutil.copyfile(source, root / ('.fixture-repos/%d/armv7/' % row['repository']) / source.name)
(root / '.fixture.repositories').write_text('\n'.join(repositories) + '\n')
arm_program = ['chroot', str(root), '/.fixture-qemu', '/usr/sbin/apk']
apk = arm_program + ['--arch', 'armv7', '--no-network',
       '--keys-dir', '/etc/apk/keys', '--repositories-file', '/.fixture.repositories',
       '--cache-dir', '/.fixture-cache']
operations = []
versions = []
def version(label, expected):
    child = subprocess.run(arm_program + ['--version'], capture_output=True, text=True, timeout=30)
    assert child.returncode == 0 and expected in child.stdout and 'armv7' in child.stdout, (label, child.stdout, child.stderr)
    versions.append(dict(phase=label, output=child.stdout.strip(), returncode=0))
    return child.stdout.strip()
version('original-native-runtime', '3.0.8-r0')
parked = root / 'usr/lib/libapk.so.3.0.0.fixture-parked'
library = root / 'usr/lib/libapk.so.3.0.0'
library.rename(parked)
try:
    missing = subprocess.run(arm_program + ['--version'], capture_output=True, text=True, timeout=30)
    assert missing.returncode != 0 and 'libapk.so.3.0.0' in missing.stderr
finally:
    parked.rename(library)
controls = []
(root / '.fixture-controls').mkdir()
for kind in ['altered-control', 'altered-payload']:
    path = root / '.fixture-controls' / (kind + '.apk')
    shutil.copyfile('/runtime/runtime-package-verification/' + kind + '.apk', path)
    bad = subprocess.run(apk + ['verify', '/.fixture-controls/' + kind + '.apk'],
                         capture_output=True, text=True, timeout=30)
    assert bad.returncode != 0, (kind, bad.stdout, bad.stderr)
    Path('/receipts/' + kind + '.log').write_text(bad.stdout + bad.stderr)
    controls.append(dict(kind=kind, actual_ARM_apk_3_0_8_rejected=True, returncode=bad.returncode))

def invoke(label, action):
    options = [] if action[0] == 'update' else ['--no-scripts']
    child = subprocess.run(apk + options + action, capture_output=True, text=True, timeout=90)
    Path('/receipts/' + label + '.log').write_text(child.stdout + child.stderr)
    assert child.returncode == 0, (label, child.stdout, child.stderr)
    assert 'Executing ' not in child.stdout + child.stderr
    operations.append(dict(phase=label, returncode=child.returncode, owned_child_reaped=True,
                           native_hooks_disabled=True, network_disabled=True))
    print('Actual APK phase passed:', label, flush=True)

def restored():
    restore.verify()
    assert database() == original
    assert target('/etc/apk/world').read_bytes() == old_world
    version('file-backed-recovery', '3.0.8-r0')

invoke('load-local-signed-indexes', ['update'])
partial = ['/.fixture-repos/%d/armv7/%s' % (row['repository'], Path(row['path']).name)
           for row in fetch['packages'][:5]]
invoke('partial-upgrade', ['add', *partial])
version('after-partial-upgrade', '3.0.9-r0')
changed = {name for name in original if database()[name] != original[name]}
assert 0 < len(changed) < 30 and changed <= expected.keys(), changed
assert database().keys() == original.keys()
partial_count = len(changed)
restore.restore()
restored()
print('Partial transaction recovered exactly', flush=True)
invoke('complete-upgrade', ['upgrade'])
version('after-complete-upgrade', '3.0.9-r0')
current = database()
assert current.keys() == original.keys()
assert {name for name in original if current[name] != original[name]} == expected.keys()
assert all(current[name] == row for name, row in expected.items())
assert all(current[name] == original[name] for name in original if name not in expected)
assert target('/etc/apk/world').read_bytes() == old_world

# Exercise detached hardlinks, incorrect modes, link targets, and unexpected xattrs.
linked = next(name for name, row in manifest['paths'].items()
              if row['kind'] == 'file' and 'hardlink_to' in row)
path = restore.target(linked)
path.unlink()
path.write_bytes(b'fixture-only interrupted package data')
path.chmod(0o600)
os.setxattr(path, 'user.fx0-fixture', b'not-in-backup')
link = next(name for name, row in manifest['paths'].items() if row['kind'] == 'symlink')
restore.target(link).unlink()
restore.target(link).symlink_to('fixture-only-invalid-target')
try:
    restore.restore(stop_after=930)
except InterruptedError:
    interruption_detected = True
else:
    raise AssertionError('Interruption was not injected')
restore.restore()
restored()
print('Complete transaction and interrupted restoration recovered exactly', flush=True)

# A canonical parent escape must be rejected before the first restore operation.
directory = root / 'usr/lib'
parked = root / 'usr/lib.fixture-parked'
directory.rename(parked)
directory.symlink_to('/outside-root')
try:
    try:
        restore.restore()
    except AssertionError as error:
        assert 'Symlink in canonical parent' in str(error)
    else:
        raise AssertionError('Parent symlink escape accepted')
finally:
    directory.unlink()
    parked.rename(directory)

# An absent path must not justify deleting unknown descendants.
absent = next(name for name, row in manifest['paths'].items()
              if row['kind'] == 'absent' and restore.target(name).parent.is_dir())
unexpected = restore.target(absent)
unexpected.mkdir()
(unexpected / 'unrecorded-child').write_bytes(b'preserve')
try:
    try:
        restore.restore()
    except OSError:
        assert (unexpected / 'unrecorded-child').read_bytes() == b'preserve'
    else:
        raise AssertionError('Unknown descendant erased')
finally:
    (unexpected / 'unrecorded-child').unlink()
    unexpected.rmdir()
restore.restore()
restored()

# Check boot rollback semantics on an ordinary RAM file, never a block device.
boot = Path('/work/boot.fixture.img')
source = Path('/backup/boot-partition.private.img')
assert helper.sha_file(source) == manifest['raw_boot_sha256']
shutil.copyfile(source, boot)
prefix = boot.read_bytes()[:512 * 1024]
with boot.open('r+b') as stream:
    stream.seek(8 * 1024**2)
    stream.write(b'fixture-only boot-tail damage')
assert helper.sha_file(boot) != manifest['raw_boot_sha256']
with source.open('rb') as src, boot.open('r+b') as dst:
    src.seek(512 * 1024)
    dst.seek(512 * 1024)
    shutil.copyfileobj(src, dst)
assert boot.read_bytes()[:512 * 1024] == prefix
assert helper.sha_file(boot) == manifest['raw_boot_sha256']

result = dict(recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              scope='Exact signed native ARM APK3.0.8/runtime under QEMU userspace emulation; no phone or ARM kernel execution',
              native_ARM_version_observations=versions, native_ARM_corruption_controls=controls,
              missing_runtime_library_rejected=True, complete_signed_runtime_payload_match=True,
              runtime_archive_sha256=closure['runtime_archive_sha256'],
              emulator_sha256=closure['emulator_sha256'], emulator_version=closure['emulator_version'],
              host_binfmt_registration_changed=False, native_package_hooks_exercised=False,
              native_source_boot_id=manifest['boot_id'], captured_paths_verified=len(manifest['paths']),
              original_packages_restored=len(original), selected_packages_upgraded=30,
              partial_transaction_packages=partial_count, operations=operations,
              partial_full_and_interrupted_restore_passed=True,
              file_bytes_modes_UID_GID_mtime_symlinks_absence_and_hardlinks_verified=True,
              hardlink_aliases_verified=sum('hardlink_to' in row for row in manifest['paths'].values()),
              unexpected_user_xattr_removed=True, canonical_parent_escape_rejected=True,
              unknown_descendant_preserved_and_restore_refused=True,
              raw_boot_recovery_regular_RAM_file_only=True, first_512KiB_preserved=True,
              SELinux_labels_captured=sum('security.selinux' in row.get('xattrs', {}) for row in manifest['paths'].values()),
              SELinux_labels_not_applied_on_host=True, native_hooks_exercised=False,
              native_package_installation=False, native_boot_partition_written=False,
              native_rollback_qualified=False)
Path('/receipts/rehearsal-result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
