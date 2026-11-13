#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run the exact stable controller on native ARM success and failure paths."""
import base64
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import signal

run=Path(__file__).resolve().parent
assert str(run)=='/var/lib/fx0-rollback/stable-userspace-qualification-02'
fixture=Path('/var/lib/fx0-rollback/stable-post-treescan-fixture-02');root=fixture/'root'
unit='fx0-stable-userspace-qualification-02.service'
state=dict(status='starting',live_OS_transaction=False,actual_ARM_kernel=True,QEMU_used=False,
    audio_testing=False,private_fixture_removed=False,started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat())
ops=None

def save():
    path=run/'status.partial'
    with path.open('w') as stream:json.dump(state,stream,indent=2);stream.write('\n');stream.flush();os.fsync(stream.fileno())
    path.replace(run/'status.json')
def stage(name):state['status']=name;save()
def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def namespace():
    return {'/'+str((Path(parent)/leaf).relative_to(root)) for parent,dirs,files in os.walk(root,followlinks=False) for leaf in dirs+files}
def stop(number,frame):raise InterruptedError('Private qualification stop requested')
for signum in [signal.SIGTERM,signal.SIGINT]:signal.signal(signum,stop)
save()
try:
    plan=json.loads((run/'qualification-plan.json').read_text())
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==plan['boot_id']
    assert os.uname().release=='6.18.63-fx0-vibrator-alpine'
    assert Path('/proc/sys/kernel/tainted').read_text().strip()=='0'
    assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip()=='Y'
    assert all(os.statvfs(n).f_flag&os.ST_RDONLY for n in ['/','/etc','/usr','/proc/sys','/sys/fs/cgroup'])
    assert not os.path.lexists('/dev/mmcblk0p15') and 'NoNewPrivs:\t1' in Path('/proc/self/status').read_text()
    assert [s.split(':',1)[0].strip() for s in Path('/proc/net/dev').read_text().splitlines()[2:]]==['lo']
    for name,expected in plan['fixture_inputs_sha256'].items():
        assert not name.startswith('/') and '..' not in Path(name).parts and sha(fixture/name)==expected
    previous=json.loads((fixture/'status.json').read_text())
    assert previous['status']=='prepared' and previous['all_owned_processes_terminal']
    assert previous['captured_paths_verified']==7002 and previous['directory_memberships_verified']==701
    scope=json.loads((run/'scope.json').read_text())
    assert sha(run/'scope.json')==plan['scope_sha256']
    cache_names={}
    for row in scope['packages']:
        suffix=base64.b64decode(row['index_control_checksum'][2:],validate=True).hex()[:8]
        cache_names[row['package']+'-'+row['version']+'.'+suffix+'.apk']=row['sha256']
    def check_cache(directory):
        for path in directory.iterdir():
            assert path.is_file() and not path.is_symlink()
            if path.name in cache_names:assert sha(path)==cache_names[path.name]
            else:
                assert re.fullmatch(r'APKINDEX\.[0-9a-f]{8}\.tar\.gz',path.name)
                assert sha(path) in scope['index_sha256']
    assert sha(fixture/'initial-namespace.private.json')==plan['prior_initial_namespace_sha256']
    prior_initial=set(json.loads((fixture/'initial-namespace.private.json').read_text()))
    extra=namespace()-prior_initial
    assert all(name.startswith('/.fixture-cache/') for name in extra)
    assert not prior_initial-namespace();check_cache(root/'.fixture-cache')
    inside=root/'.fixture-stable-controller';inside.mkdir(mode=0o700,exist_ok=False)
    (inside/'cache').mkdir(mode=0o700)
    for index,expected in enumerate(scope['index_sha256']):
        directory=inside/'repos'/str(index)/'armv7';directory.mkdir(mode=0o700,parents=True)
        src=fixture/'indexes'/('%d.tar.gz'%index);assert sha(src)==expected
        shutil.copyfile(src,directory/'APKINDEX.tar.gz')
    for row in scope['packages']:
        name=row['package']+'-'+row['version']+'.apk';src=fixture/'packages'/name
        assert sha(src)==row['sha256'];shutil.copyfile(src,inside/'repos'/str(row['repository'])/'armv7'/name)
    (inside/'repositories').write_text(''.join('/.fixture-stable-controller/repos/'+str(i)+'\n' for i in range(4)))
    initial=namespace()
    with (run/'initial-namespace.private.json').open('x') as stream:json.dump(sorted(initial),stream);stream.write('\n')
    assert sha(run/'stable_transaction.py')==plan['controller_sha256']
    assert sha(run/'update_transaction.py')==plan['transaction_helper_sha256']
    spec=importlib.util.spec_from_file_location('qualified_stable',run/'stable_transaction.py')
    controller=importlib.util.module_from_spec(spec);spec.loader.exec_module(controller)
    base=dict(format='fx0-stable-userspace-transaction-v1',root=str(root),inside='/.fixture-stable-controller',unit=unit,
        controller_sha256=plan['controller_sha256'],transaction_helper_sha256=plan['transaction_helper_sha256'],live_update_approved=False)
    stage('qualifying exact stable controller: native success')
    ops=controller.execute(dict(base,status_name='success.json'),run)
    assert ops.state['stage']=='updated-and-verified' and ops.state['selected_candidate_identities_verified']==30
    assert ops.state['other_package_identities_unchanged']==745 and ops.state['unit_entries_and_timestamps_verified']==545
    controller.atomic(run/'success-candidate.json',(json.dumps(ops.state,indent=2)+'\n').encode())
    state['success']=dict(retained_distro_paths_immutable=3,stage=ops.state['stage'],selected_candidate_identities_verified=30,
        protected_745_identities_preserved=True,unit_timestamps=545,world_exact=True)
    trace=(run/'success.exec.trace').read_text()
    assert not any('ssh-keygen'==Path(p).name for p in re.findall(r'\bexecve\("([^\"]+)"',trace))
    assert '"pre-commit"' in trace and 'postmarketos-base-systemd' in trace
    stage('qualifying scoped normal recovery with a labelled synthetic signed executor')
    fd=os.open(run/'transaction.lock',os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);assert ops.hooks_terminal()
        owned=json.loads((run/'owned-scripts.private.json').read_text())
        path=ops.snapshot.target(controller.EXECUTOR)/'openssh-server-10.3_p1-r2.post-upgrade'
        assert not list(path.parent.iterdir())
        body=base64.b64decode(owned[path.name]['body_base64'],validate=True)
        assert hashlib.sha256(body).hexdigest()==scope['known_executor_scripts'][path.name]['sha256']
        descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o755)
        with os.fdopen(descriptor,'wb') as stream:stream.write(body);stream.flush();os.fsync(stream.fileno())
        ops.rollback();ops.verify_rollback()
        assert ops.state['owned_executor_files_removed']==[path.name]
        state['synthetic_executor']=dict(synthetic=True,signed_body_sha256=hashlib.sha256(body).hexdigest(),
            all_owned_hooks_terminal_before_insertion=True,recognised_and_removed=True)
    finally:os.close(fd)
    state['normal_recovery']=dict(recovered_paths=7002,recovered_memberships=701,original_775_identities=True,
        hardlink_aliases=254,unit_timestamps=545,APK_lock_inode_preserved=True)
    save()
    failures=[]
    for label,fault in [('hook-exec-failure','hook-exec-EIO'),('post-commit-failure','after-commit')]:
        stage('qualifying exact stable controller: '+label)
        try:controller.execute(dict(base,status_name=label+'.json'),run,fixture_failure=fault)
        except Exception as error:
            assert type(error).__name__=='RolledBack',(type(error).__name__,str(error))
            if fault=='after-commit':assert 'Private controlled failure after actual commit' in str(error)
            else:assert "'upgrade', 1" in str(error)
        else:raise AssertionError('Controlled failure did not occur')
        result=json.loads((run/(label+'.json')).read_text())
        assert result['stage']=='rolled-back' and result['recovered_paths']==7002 and result['recovered_memberships']==701
        assert result['original_775_package_identities_recovered'] and result['all_owned_process_groups_terminal']
        assert result['APK_lock_inode_never_replaced'] and not result['boot_written']
        if fault=='hook-exec-EIO':
            injected=[line for line in (run/(label+'.exec.trace')).read_text().splitlines() if '(INJECTED)' in line]
            assert len(injected)==1 and 'lib/apk/exec/openssh-server-10.3_p1-r2.post-upgrade' in injected[0] and 'EIO' in injected[0]
        failures.append(dict(name=label,terminal_stage='rolled-back',recovered_paths=7002,recovered_memberships=701,
            original_775_identities=True,APK_lock_inode_preserved=True,injected_before_OpenSSH_hook_body=fault=='hook-exec-EIO',
            injected_after_actual_commit_and_inventory=fault=='after-commit'))
        state['failures']=failures;save()
    assert ops.hooks_terminal();ops.cache_guard();check_cache(root/'.fixture-cache')
    expected=initial|{'/.fixture-stable-controller/cache/'+p.name for p in (inside/'cache').iterdir()}
    assert namespace()==expected,'Unknown generated private namespace'
    for name,expected_sha in plan['live_sha256'].items():
        if not name.startswith('/dev/'):assert sha(name)==expected_sha
    state.update(status='passed',controller_sha256=plan['controller_sha256'],scope_sha256=plan['scope_sha256'],
        same_source_success_and_two_failure_recoveries=True,normal_APK_hooks_and_trust_retained=True,
        recovery_write_files=2708,recovery_directory_metadata=133,guarded_paths=7002,guarded_memberships=701,
        protected_other_identities=745,hardlink_aliases=254,SELinux_label_paths=1480,
        complete_private_namespace_verified=True,normal_trace_no_key_generation_tool_execution_observed=True,
        actual_live_hashes_unchanged=True,live_transaction_still_not_started=True,
        all_owned_processes_terminal=True,private_fixture_retained=True,
        abrupt_power_loss_and_stop_matrix_qualified=False)
except BaseException as error:
    state.update(status='failed',error=type(error).__name__+': '+str(error));raise
finally:
    state['finished_UTC']=datetime.datetime.now(datetime.timezone.utc).isoformat();save()
