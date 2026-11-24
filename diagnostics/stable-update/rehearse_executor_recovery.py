"""Run real ARM APK/hooks only inside a private chroot in a bounded unit."""
import datetime
import base64
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
assert str(run) == '/var/lib/fx0-rollback/stable-executor-recovery-03/native-failure-03'
inputs = Path('/var/lib/fx0-rollback/stable-native-hooks-01/inputs-01')
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
    assert group.endswith('/fx0-stable-executor-failure-03.service') or group == '/'
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
    manifest_path=run.parent/'manifest.private.json'
    assert sha(manifest_path)=='6f0bee055d3df428816c05639adbed879d22851a0234772e1145d2866a2e58bc'
    manifest=json.loads(manifest_path.read_text())
    assert manifest['boot_id']==boot and manifest['combined_paths']==6351
    spec = importlib.util.spec_from_file_location('restore', run / 'file_rollback_v2.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    extra=importlib.util.spec_from_file_location('executor',run/'executor_state.py')
    executor=importlib.util.module_from_spec(extra);extra.loader.exec_module(executor)
    owned=json.loads((run/'owned-scripts.private.json').read_text())
    scan_spec=importlib.util.spec_from_file_location('commit_state',run/'commit_state.py')
    scan=importlib.util.module_from_spec(scan_spec);scan_spec.loader.exec_module(scan)
    root.mkdir(mode=0o700)
    restore = helper.FileRollback(root, manifest,
        Path(reference['base_backup_directory']) / 'before-files.private.tar.gz',
        backup / 'delta-files.private.tar.gz', reference['delta_archive_sha256'])
    stage('restoring private native baseline')
    restore.restore()
    restore.verify()
    executor.verify_all_memberships(root,manifest)
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
    addon_manifests=[]
    for stem, expected_sha in [('runtime','811fa938f764124ad22e24b940d8a546789a446535e9c4624143a70210e794c1'),
                                ('utmps','5011eca3486c1a36723ab21f6020885480977730d92ec4632933c72ea4719059')]:
        addon=json.loads((run/(stem+'-manifest.json')).read_text())
        archive_path=run/(stem+'-libraries.tar.gz')
        assert sha(archive_path)==expected_sha
        with tarfile.open(archive_path,'r:gz') as archive:
            for name,row in addon['paths'].items():
                path=restore.target(name)
                assert not os.path.lexists(path),name
                if row['kind']=='file':
                    content=archive.extractfile(name.lstrip('/')).read()
                    assert hashlib.sha256(content).hexdigest()==row['sha256']
                    path.write_bytes(content);path.chmod(row['mode'])
                else:path.symlink_to(row['target'])
        addon_manifests.append(addon)
    def verify_addon_runtime():
        for addon in addon_manifests:
            for name,row in addon['paths'].items():
                path=restore.target(name)
                if row['kind']=='file':assert sha(path)==row['sha256'],name
                else:assert path.is_symlink() and os.readlink(path)==row['target'],name
    verify_addon_runtime()
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
    args = program + ['--no-interactive','--arch','armv7','--no-network','--keys-dir','/etc/apk/keys',
                      '--repositories-file','/.fixture.repositories','--cache-dir','/.fixture-cache']
    stage('loading authenticated local indexes with actual native APK3.0.8')
    load = subprocess.run(args + ['update'], capture_output=True, text=True, timeout=120)
    (run / 'index-load.log').write_text(load.stdout + load.stderr)
    assert load.returncode == 0, 'Local index loading failed'
    assert hooks_terminal()
    def namespace():
        result=set()
        for directory,dirs,files in os.walk(root,followlinks=False):
            for leaf in dirs+files:result.add('/'+str((Path(directory)/leaf).relative_to(root)))
        return result
    def harness(name):
        return any(name==p or name.startswith(p+'/') for p in ['/.fixture-repos','/.fixture-cache','/.fixture.repositories'])
    initial_namespace=namespace()
    (run/'initial-namespace.private.json').write_text(json.dumps(sorted(initial_namespace))+'\n')
    stage('preflighting actual global pre-commit hook in the matched private root')
    preflight_command=['/usr/bin/strace','-f','-e','trace=execve,execveat','-s','4096','-o',str(run/'precommit.exec.trace'),
        '/usr/sbin/chroot',str(root),'/etc/apk/commit_hooks.d/postmarketos-base-systemd','pre-commit']
    with (run/'precommit.log').open('w') as log:
        child=subprocess.Popen(preflight_command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:preflight_code=child.wait(timeout=120)
        except BaseException:stop_owned();raise
    assert hooks_terminal()
    assert preflight_code==0,'Global commit-hook preflight failed'
    messages=(run/'precommit.log').read_text()
    assert not any(word in messages.lower() for word in ['not found','no such file','error:','permission denied']),messages
    tracker=root/'var/lib/systemd-apk/installed.units'
    preflight_inventory=tracker.read_bytes()
    (run/'preflight-inventory.private').write_bytes(preflight_inventory)
    preflight_identity=scan.inventory_identity(preflight_inventory)
    tracker_name='/var/lib/systemd-apk/installed.units'
    tracker_row=manifest['paths'][tracker_name]
    tracker.write_bytes(restore.data[tracker_name])
    os.chown(tracker,tracker_row['uid'],tracker_row['gid']);tracker.chmod(tracker_row['mode'])
    for key,value in tracker_row['xattrs'].items():os.setxattr(tracker,key,bytes.fromhex(value))
    os.utime(tracker,ns=(tracker_row['mtime_ns'],tracker_row['mtime_ns']))
    assert sha(tracker)==tracker_row['sha256']
    stage('controlled OpenSSH post-upgrade execve EIO in actual native APK upgrade')
    fault_path='lib/apk/exec/openssh-server-10.3_p1-r2.post-upgrade'
    command=['/usr/bin/strace','-f','-e','trace=execve,execveat','-s','4096','-P',fault_path,
        '--inject=execve:error=EIO','-o',str(run/'exec.trace'),*args,'--verbose','upgrade']
    assert '--no-scripts' not in command and '--allow-untrusted' not in command
    with (run / 'upgrade.log').open('w') as log:
        child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True, cwd=root)
        try:
            code = child.wait(timeout=300)
        except BaseException:
            stop_owned()
            raise
    status['APK_returncode'] = code
    status['owned_APK_tracer_reaped'] = True
    assert hooks_terminal(), 'Owned unit still contains descendants; do not restore'
    status['APK_parent_reported_failure']=code!=0  # A failed hook must not be hidden by a zero parent status.
    fault_trace=(run/'exec.trace').read_text()
    injected=[line for line in fault_trace.splitlines() if '(INJECTED)' in line]
    assert len(injected)==1 and fault_path in injected[0] and 'EIO' in injected[0],fault_trace
    text=(run/'upgrade.log').read_text()
    assert 'Executing openssh-server-10.3_p1-r2.post-upgrade' in text
    assert 'openssh-server' in text and ('127' in text or 'error' in text.lower())
    generated_tracker_sha256=sha(tracker)
    assert scan.inventory_identity(tracker.read_bytes())==preflight_identity
    assert tracker.stat().st_mtime_ns!=tracker_row['mtime_ns']
    changed=[];failed_database_parse=None
    try:
        current=database()
        changed=[name for name in original if current.get(name)!=original[name]]
    except Exception as error:failed_database_parse=type(error).__name__
    APK_binary_changed=sha(root/'usr/sbin/apk')!=runtime['paths']['/usr/sbin/apk']['sha256']
    after_failure=namespace()
    # Exercise a known retained executor artifact without pretending APK left it.
    injected_stale=False
    executable_dir=root/'usr/lib/apk/exec'
    if not list(executable_dir.iterdir()):
        body=base64.b64decode(owned[Path(fault_path).name]['body_base64'],validate=True)
        path=executable_dir/Path(fault_path).name;path.write_bytes(body);path.chmod(0o755)
        injected_stale=True
    assert hooks_terminal()
    removed=executor.cleanup_owned_scripts(root,manifest,owned,hooks_terminal=True)
    inventory=dict(initial_paths=sorted(initial_namespace),after_failure_paths=sorted(after_failure),
        known_stale_executor_file_injected=injected_stale,owned_executor_paths_removed=removed)
    (run/'namespace-inventory.private.json').write_text(json.dumps(inventory,indent=2)+'\n')
    status.update(actual_controlled_hook_exec_failure=True,hook_failure_kind='execve EIO before OpenSSH post-upgrade body',
        global_commit_hook_preflight_returncode=preflight_code,global_commit_inventory_generated_before_failure=True,
        treescan_unit_identities_verified=True,treescan_mtime_values_unreliable=True,
        generated_tracker_sha256=generated_tracker_sha256,changed_package_identities=len(changed),
        failure_database_parse=failed_database_parse,APK_binary_changed_after_failure=APK_binary_changed,
        known_stale_executor_file_injected=injected_stale,owned_executor_paths_removed=len(removed))
    stage('restoring after all owned native hooks have reaped')
    assert hooks_terminal()
    restore.restore()
    restore.verify()
    executor.verify_all_memberships(root,manifest)
    final_namespace=namespace()
    missing=sorted(n for n in initial_namespace-final_namespace if not harness(n))
    unexpected=sorted(n for n in final_namespace-initial_namespace if not harness(n))
    inventory.update(final_paths=sorted(final_namespace),unrestored_missing_paths=missing,unrestored_generated_paths=unexpected)
    (run/'namespace-inventory.private.json').write_text(json.dumps(inventory,indent=2)+'\n')
    assert missing==[] and unexpected==[],'Generated namespace not fully restored; inspect private inventory'
    assert APK_binary_changed,'No installed payload changed before the controlled failure'
    assert database() == original and (root / 'etc/apk/world').read_bytes() == old_world
    assert version() == 'apk-tools 3.0.8-r0, compiled for armv7.'
    verify_addon_runtime()
    assert sha('/lib/apk/db/installed') == plan['native_database_sha256']
    assert sha('/etc/apk/world') == plan['world_sha256']
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
    status.update(status='passed', captured_paths_verified=6351, SELinux_labels_verified=1479,
                  directory_memberships_verified=40,generated_state_namespace_restored=True,
                  hardlink_aliases_verified=254, original_775_packages_recovered=True,
                  recovered_ARM_APK_version='3.0.8-r0', live_DB_world_unchanged=True,
                  hooks_terminal_before_restore=True, exact_signed_coreutils_runtime_verified=True, live_OS_transaction_qualified=False)
except BaseException as error:
    status.update(status='failed', error=type(error).__name__ + ': ' + str(error))
    raise
finally:
    stop_owned()
    if root.exists() and hooks_terminal() and status['status']=='passed':
        assert root.parent == run and not root.is_symlink()
        shutil.rmtree(root)
    status['private_fixture_removed'] = not os.path.lexists(root)
    status['finished_UTC'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save()
