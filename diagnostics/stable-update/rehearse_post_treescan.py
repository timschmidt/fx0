"""Exercise the current stable upgrade and exact recovery only in a private root."""
import base64
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tarfile

run = Path(__file__).resolve().parent
assert str(run) == '/var/lib/fx0-rollback/stable-post-treescan-rehearsal-01'
fixture = Path('/var/lib/fx0-rollback/stable-post-treescan-fixture-01')
root = fixture / 'root'
backup = Path('/var/lib/fx0-rollback/post-treescan-userspace-baseline-01')
unit = 'fx0-stable-post-treescan-rehearsal-01.service'
state = dict(status='starting', started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
             live_OS_transaction=False, QEMU_used=False, audio_testing=False, cases=[])
child = None


def save():
    path = run / 'status.partial'
    with path.open('w') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    path.replace(run / 'status.json')


def stage(name):
    state['status'] = name
    save()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def alone():
    line = Path('/proc/self/cgroup').read_text().strip()
    assert line.startswith('0::') and '\n' not in line
    group = line.removeprefix('0::')
    assert group.endswith('/' + unit) or group == '/'
    parent = Path('/sys/fs/cgroup') / group.lstrip('/')
    return {int(pid) for path in parent.rglob('cgroup.procs') for pid in path.read_text().split()} == {os.getpid()}


def stop_owned():
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def interrupted(number, frame):
    raise InterruptedError('Private rehearsal stop requested')


def module(name):
    spec = importlib.util.spec_from_file_location(name, run / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def command(name, args, *, expected=0):
    global child
    assert '--no-scripts' not in args and '--allow-untrusted' not in args
    with (run / (name + '.log')).open('x') as stream:
        child = subprocess.Popen(args, stdout=stream, stderr=subprocess.STDOUT,
                                 start_new_session=True, cwd=root)
        try:
            code = child.wait(timeout=600)
        except BaseException:
            stop_owned()
            raise
    assert alone(), 'Owned descendants remain; preserve fixture'
    if expected is not None:
        assert code == expected, (name, code)
    return code, (run / (name + '.log')).read_text()


def database():
    result = {}
    for paragraph in (root / 'usr/lib/apk/db/installed').read_text().split('\n\n'):
        row = {line[:1]: line[2:] for line in paragraph.splitlines() if len(line) > 1 and line[1] == ':'}
        if row.get('P'):
            assert row['P'] not in result
            result[row['P']] = dict(version=row['V'], checksum=row['C'])
    return result


def namespace():
    return {'/' + str((Path(parent) / leaf).relative_to(root))
            for parent, dirs, files in os.walk(root, followlinks=False) for leaf in dirs + files}


def inventory():
    expected = {}
    for stem in ['system', 'user']:
        for parent, directories, files in os.walk(root / ('usr/lib/systemd/' + stem), followlinks=False):
            for leaf in directories + files:
                path = Path(parent) / leaf
                kind = 'symlink' if path.is_symlink() else 'dir' if path.is_dir() else 'file'
                expected['/' + str(path.relative_to(root))] = kind, path.stat().st_mtime_ns // 10**9
    observed = {}
    for line in (root / 'var/lib/systemd-apk/installed.units').read_text().splitlines():
        name, kind, timestamp = line.rsplit(' ', 2)
        assert name not in observed and kind.startswith('type=') and timestamp.startswith('mtime=')
        observed[name] = kind[5:], int(timestamp[6:])
    assert len(expected) == 545 and observed == expected
    return len(expected)


signal.signal(signal.SIGTERM, interrupted)
signal.signal(signal.SIGINT, interrupted)
save()
try:
    plan = json.loads((run / 'rehearsal-plan.json').read_text())
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == plan['boot_id']
    assert os.uname().release == '6.18.63-fx0-vibrator-alpine'
    assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
    assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip() == 'Y'
    assert all(os.statvfs(name).f_flag & os.ST_RDONLY
               for name in ['/', '/etc', '/usr', '/proc/sys', '/sys/fs/cgroup'])
    assert not os.path.lexists('/dev/mmcblk0p15')
    assert 'NoNewPrivs:\t1' in Path('/proc/self/status').read_text()
    assert [s.split(':', 1)[0].strip() for s in Path('/proc/net/dev').read_text().splitlines()[2:]] == ['lo']
    assert alone()
    prepared = json.loads((fixture / 'status.json').read_text())
    assert prepared['status'] == 'prepared' and prepared['native_simulated_upgrades'] == 30
    assert prepared['native_all_30_archive_verifications_passed']
    for name, expected in plan['fixture_files_sha256'].items():
        assert not name.startswith('/') and '..' not in Path(name).parts
        assert sha(fixture / name) == expected
    assert sha(fixture / 'initial-namespace.private.json') == plan['initial_namespace_sha256']
    initial = set(json.loads((fixture / 'initial-namespace.private.json').read_text()))
    assert namespace() == initial
    assert sha(backup / 'manifest.private.json') == '3ae427aff2b8fa640e247afd1389721283d14978ea3ee5f71beaa45dabe71ab8'
    manifest = json.loads((backup / 'manifest.private.json').read_text())
    assert len(manifest['paths']) == 7002
    helper, executor = module('file_rollback_v2'), module('executor_state')
    restore = helper.FileRollback(root, manifest, backup / 'files.private.tar.gz',
        backup / 'empty-delta.private.tar.gz',
        '4f9cfb843c696c9ed32990cf6f8fc1769c125100e1a6008029c9dbd885bedc19')
    stage('checking exact prepared post-treescan baseline')
    restore.verify()
    executor.verify_all_memberships(root, manifest)
    original = database()
    assert len(original) == 775
    old_world = (root / 'etc/apk/world').read_bytes()
    assert sha(root / 'usr/lib/apk/db/installed') == plan['live_sha256']['/lib/apk/db/installed']
    assert sha(root / 'etc/apk/world') == plan['live_sha256']['/etc/apk/world']
    assert inventory() == 545
    packages = json.loads((fixture / 'packages.json').read_text())
    targets = {row['package']: dict(version=row['version'], checksum=row['index_control_checksum']) for row in packages}
    assert len(targets) == 30 and not {'treescan', 'linux-postmarketos-qcom-msm8226'} & targets.keys()
    expected = dict(original, **targets)
    owned = json.loads((run / 'owned-scripts.private.json').read_text())
    known_cache = {}
    for row in packages:
        prefix = base64.b64decode(row['index_control_checksum'][2:], validate=True).hex()[:8]
        known_cache[row['package'] + '-' + row['version'] + '.' + prefix + '.apk'] = row['sha256']
    index_shas = {plan['fixture_files_sha256']['indexes/%d.tar.gz' % i] for i in range(4)}
    args = ['/usr/sbin/chroot', str(root), '/usr/sbin/apk', '--no-interactive', '--arch', 'armv7', '--no-network',
            '--keys-dir', '/etc/apk/keys', '--repositories-file', '/.fixture.repositories',
            '--cache-dir', '/.fixture-cache']
    assert command('version-before', ['/usr/sbin/chroot', str(root), '/usr/sbin/apk', '--version'])[1].strip() == 'apk-tools 3.0.8-r0, compiled for armv7.'
    fault_path = 'lib/apk/exec/openssh-server-10.3_p1-r2.post-upgrade'
    for label, fault in [('success', False), ('hook-exec-failure', True)]:
        stage('actual native stable transaction: ' + label)
        trace = run / (label + '.exec.trace')
        command_args = ['/usr/bin/strace', '-f', '-e', 'trace=execve,execveat', '-s', '4096']
        if fault:
            command_args += ['-P', fault_path, '--inject=execve:error=EIO']
        command_args += ['-o', str(trace), *args, '--verbose', 'upgrade']
        code, text = command(label, command_args, expected=None)
        traced = trace.read_text()
        injected = [line for line in traced.splitlines() if '(INJECTED)' in line]
        if fault:
            assert code != 0 and len(injected) == 1
            assert fault_path in injected[0] and 'EIO' in injected[0]
        else:
            assert code == 0 and not injected
            assert 'postmarketos-base-systemd' in traced and '"pre-commit"' in traced
            assert 'Executing openssh-server-10.3_p1-r2.post-upgrade' in text
            assert 'Executing libheif-1.23.7-r0.post-upgrade' in text
        assert 'Executing busybox-1.37.0-r31.trigger' in text
        assert database() == expected
        assert (root / 'etc/apk/world').read_bytes() == old_world
        assert command(label + '-version-upgraded',
                       ['/usr/sbin/chroot', str(root), '/usr/sbin/apk', '--version'])[1].strip() == 'apk-tools 3.0.9-r0, compiled for armv7.'
        # Refresh the unchanged hook after the completed transaction, including
        # the controlled hook failure whose package database still committed.
        command(label + '-refresh', ['/usr/sbin/chroot', str(root),
                    '/etc/apk/commit_hooks.d/postmarketos-base-systemd', 'pre-commit'])
        assert inventory() == 545
        synthetic = False
        directory = root / 'usr/lib/apk/exec'
        if fault and not list(directory.iterdir()):
            body = base64.b64decode(owned[Path(fault_path).name]['body_base64'], validate=True)
            path = directory / Path(fault_path).name
            path.write_bytes(body)
            path.chmod(0o755)
            synthetic = True
        assert alone()
        removed = executor.cleanup_owned_scripts(root, manifest, owned, hooks_terminal=True)
        stage('file-backed exact private recovery after reaped hooks: ' + label)
        restore.restore()
        restore.verify()
        executor.verify_all_memberships(root, manifest)
        assert database() == original and (root / 'etc/apk/world').read_bytes() == old_world
        assert inventory() == 545
        assert command(label + '-version-restored',
                       ['/usr/sbin/chroot', str(root), '/usr/sbin/apk', '--version'])[1].strip() == 'apk-tools 3.0.8-r0, compiled for armv7.'
        current_namespace = namespace()
        for path in (root / '.fixture-cache').iterdir():
            assert path.is_file() and not path.is_symlink()
            if path.name in known_cache:
                assert sha(path) == known_cache[path.name]
            else:
                assert re.fullmatch(r'APKINDEX\.[0-9a-f]{8}\.tar\.gz', path.name)
                assert sha(path) in index_shas
        extras = current_namespace - initial
        assert all(name.startswith('/.fixture-cache/') for name in extras), ('Unexpected namespace', sorted(extras))
        assert not initial - current_namespace
        state['cases'].append(dict(name=label, package_parent_returncode=code,
            installed_identities_changed=30, unselected_745_identities_preserved=True,
            kernel_and_treescan_and_world_preserved=True,
            hook_exec_failure_injected=fault, injection_before_OpenSSH_hook_body=fault,
            synthetic_retained_executor_injected=synthetic, owned_executor_files_removed=removed,
            recovered_paths=7002, recovered_memberships=701, original_775_identities_recovered=True,
            unit_entries_and_timestamps_verified=545, actual_upgraded_APK='3.0.9-r0',
            actual_restored_APK='3.0.8-r0', exact_private_namespace_restored=True,
            all_owned_processes_reaped_before_recovery=True))
        save()
    for name, expected_sha in plan['live_sha256'].items():
        if not name.startswith('/dev/'):
            assert sha(name) == expected_sha
    assert alone()
    state.update(status='passed', actual_ARM_kernel=True, native_normal_hooks_verified=True,
        current_baseline_recovered_after_success_and_hook_failure=True,
        private_fixture_retained_for_exact_controller_qualification=True,
        fixture_path=str(root), all_owned_processes_terminal=True,
        live_package_or_boot_changes=False, live_transaction_controller_not_qualified=True,
        power_loss_or_stop_signal_matrix_qualified=False)
except BaseException as error:
    state.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    raise
finally:
    stop_owned()
    state['finished_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
