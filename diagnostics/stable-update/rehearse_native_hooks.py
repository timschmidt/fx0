"""Run real ARM APK/hooks only inside a private chroot in a bounded unit."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import tarfile

run = Path(__file__).resolve().parent
assert str(run) == '/var/lib/fx0-rollback/stable-native-hooks-01/native-run-01'
inputs = run.parent / 'inputs-01'
root = run / 'root'
boot = '747e87fe-198f-49f8-997a-8e198315968d'
status = dict(started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
              status='starting', live_root_restored=False, native_package_installation=False,
              actual_ARM_kernel=True, QEMU_used=False, private_fixture_removed=False)
child = None

def save():
    temporary = run / 'status.tmp'
    with temporary.open('w') as stream:
        json.dump(status, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(run / 'status.json')

def stage(name):
    status['status'] = name
    save()

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def cgroup_pids():
    line = Path('/proc/self/cgroup').read_text().strip()
    assert line.startswith('0::') and '\n' not in line
    group = line.removeprefix('0::')
    assert group.endswith('/fx0-stable-native-hooks-01.service') or group == '/'
    return {int(value) for value in (Path('/sys/fs/cgroup') / group.lstrip('/') / 'cgroup.procs').read_text().split()}

def hooks_terminal():
    return cgroup_pids() == {os.getpid()}

def stop_owned():
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()

def interrupted(signum, frame):
    raise InterruptedError('Native unit stop requested')

signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
save()
try:
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
    assert os.uname().release == '6.18.59-fx0-dmp'
    assert all(os.statvfs(name).f_flag & os.ST_RDONLY for name in ['/', '/etc', '/usr', '/proc/sys', '/sys/fs/cgroup'])
    assert not os.path.lexists('/dev/mmcblk0p15')
    interfaces = [line.split(':',1)[0].strip() for line in Path('/proc/net/dev').read_text().splitlines()[2:]]
    assert interfaces == ['lo']
    assert hooks_terminal()
    available = next(int(line.split()[1])*1024 for line in Path('/proc/meminfo').read_text().splitlines()
                     if line.startswith('MemAvailable:'))
    assert available >= 640*1024**2 and shutil.disk_usage(run).free >= 768*1024**2
    packet = json.loads((inputs / 'packet-manifest.json').read_text())
    for name, expected in packet['files_sha256'].items():
        assert '..' not in Path(name).parts and not name.startswith('/')
        assert sha(inputs / name) == expected, name
    backup = Path('/var/lib/fx0-rollback/stable-userspace-01')
    reference = json.loads((backup / 'backup-reference.private.json').read_text())
    with tarfile.open(backup / 'delta-files.private.tar.gz', 'r:gz') as archive:
        manifest = json.load(archive.extractfile('.capture-manifest.private.json'))
    assert manifest['boot_id'] == boot and manifest['combined_paths'] == 5784
    spec = importlib.util.spec_from_file_location('restore', inputs / 'file_rollback.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    root.mkdir(mode=0o700)
    restore = helper.FileRollback(root, manifest,
        Path(reference['base_backup_directory']) / 'before-files.private.tar.gz',
        backup / 'delta-files.private.tar.gz', reference['delta_archive_sha256'])
    stage('restoring private native baseline')
    restore.restore()
    restore.verify()
    runtime = json.loads((inputs / 'runtime-manifest.json').read_text())
    with tarfile.open(inputs / 'runtime-libraries.tar.gz', 'r:gz') as archive:
        for name, row in runtime['paths'].items():
            path = restore.target(name)
            if row['kind'] == 'file':
                data = archive.extractfile(name.lstrip('/')).read()
                assert hashlib.sha256(data).hexdigest() == row['sha256']
                if path.exists():
                    assert sha(path) == row['sha256']
                else:
                    path.write_bytes(data)
                    path.chmod(row['mode'])
            elif path.is_symlink():
                assert os.readlink(path) == row['target']
            else:
                assert not path.exists()
                path.symlink_to(row['target'])
    busybox = json.loads((inputs / 'busybox-verification.json').read_text())
    for binary in busybox['binaries']:
        assert sha(restore.target(binary['native_path'])) == binary['native_ELF_sha256']
    plan = json.loads((inputs / 'plan.json').read_text())
    packages = json.loads((inputs / 'packages.json').read_text())
    expected = {row['package']: dict(version=row['version'], checksum=row['index_control_checksum']) for row in packages}
    assert len(expected) == 30
    def database():
        result = {}
        for paragraph in (root / 'usr/lib/apk/db/installed').read_text().split('\n\n'):
            row = {line[:1]:line[2:] for line in paragraph.splitlines() if len(line)>1 and line[1]==':'}
            if row.get('P'):
                result[row['P']] = dict(version=row['V'], checksum=row['C'])
        return result
    original = database()
    assert len(original) == 775
    old_world = (root / 'etc/apk/world').read_bytes()
    assert hashlib.sha256(old_world).hexdigest() == plan['world_sha256']
    assert sha(root / 'usr/lib/apk/db/installed') == plan['native_database_sha256']
    for i in range(4):
        destination = root / ('.fixture-repos/%d/armv7' % i)
        destination.mkdir(parents=True)
        shutil.copyfile(inputs / ('indexes/%d.tar.gz' % i), destination / 'APKINDEX.tar.gz')
    for row in packages:
        source = inputs / ('packages/' + row['filename'])
        shutil.copyfile(source, root / ('.fixture-repos/%d/armv7/' % row['repository']) / row['filename'])
    (root / '.fixture.repositories').write_text(''.join('/.fixture-repos/%d\n' % i for i in range(4)))
    (root / '.fixture-cache').mkdir()
    program = ['/usr/sbin/chroot', str(root), '/usr/sbin/apk']
    def version():
        result = subprocess.run(program + ['--version'], capture_output=True, text=True, timeout=20)
        assert result.returncode == 0
        return result.stdout.strip()
    assert version() == 'apk-tools 3.0.8-r0, compiled for armv7.'
    args = program + ['--arch','armv7','--no-network','--keys-dir','/etc/apk/keys',
                      '--repositories-file','/.fixture.repositories','--cache-dir','/.fixture-cache']
    stage('loading authenticated local indexes with actual native APK3.0.8')
    load = subprocess.run(args + ['update'], capture_output=True, text=True, timeout=120)
    (run / 'index-load.log').write_text(load.stdout + load.stderr)
    assert load.returncode == 0, 'Local index loading failed'
    assert hooks_terminal()
    stage('actual native ARM upgrade with normal package hooks and triggers')
    command = ['/usr/bin/strace','-f','-e','trace=execve,execveat','-s','4096','-o',str(run / 'exec.trace'),
               *args,'--verbose','upgrade']
    assert '--no-scripts' not in command and '--allow-untrusted' not in command
    with (run / 'upgrade.log').open('w') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = child.wait(timeout=300)
        except BaseException:
            stop_owned()
            raise
    status['APK_returncode'] = code
    status['owned_APK_tracer_reaped'] = True
    assert hooks_terminal(), 'Owned unit still contains descendants; do not restore'
    assert code == 0, 'Native private upgrade failed; inspect retained logs'
    text = (run / 'upgrade.log').read_text()
    for name in ['openssh-server', 'libheif']:
        assert 'Executing ' + name + '-' + expected[name]['version'] + '.post-upgrade' in text, name
    assert 'Executing busybox-1.37.0-r31.trigger' in text
    assert not any('script' in line.lower() and ('error' in line.lower() or 'failed' in line.lower()) for line in text.splitlines())
    current = database()
    assert current.keys() == original.keys()
    assert {name for name in original if current[name] != original[name]} == expected.keys()
    assert all(current[name] == row for name,row in expected.items())
    assert (root / 'etc/apk/world').read_bytes() == old_world
    assert version() == 'apk-tools 3.0.9-r0, compiled for armv7.'
    status.update(normal_native_hooks_executed=True, normal_native_BusyBox_trigger_executed=True,
                  selected_packages_upgraded=30, original_package_count=775,
                  upgraded_ARM_APK_version='3.0.9-r0', actual_kernel=os.uname().release)
    stage('restoring after all owned native hooks have reaped')
    assert hooks_terminal()
    restore.restore()
    restore.verify()
    assert database() == original and (root / 'etc/apk/world').read_bytes() == old_world
    assert version() == 'apk-tools 3.0.8-r0, compiled for armv7.'
    assert sha('/lib/apk/db/installed') == plan['native_database_sha256']
    assert sha('/etc/apk/world') == plan['world_sha256']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
    status.update(status='passed', captured_paths_verified=5784, SELinux_labels_verified=939,
                  hardlink_aliases_verified=254, original_775_packages_recovered=True,
                  recovered_ARM_APK_version='3.0.8-r0', live_DB_world_unchanged=True,
                  hooks_terminal_before_restore=True, live_OS_transaction_qualified=False)
except BaseException as error:
    status.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    raise
finally:
    stop_owned()
    if root.exists() and hooks_terminal():
        assert root.parent == run and not root.is_symlink()
        shutil.rmtree(root)
    status['private_fixture_removed'] = not os.path.lexists(root)
    status['finished_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
