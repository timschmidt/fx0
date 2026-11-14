"""Reconcile PID1 only after independently verified disk and process state."""
STABLE_CLOCK_FIELDS=('Id','ActiveState','SubState','MainPID','InvocationID','ExecMainStartTimestampMonotonic','ExecMainExitTimestampMonotonic','ExecMainStatus','FragmentPath','UnitFileState')

def validate(observed,baseline,kind,*,graph):
    assert kind in {'baseline','candidate'}
    assert observed['boot_id']==baseline['boot_id']
    assert observed['disk_verified'] and observed['package_count']==775
    assert observed['protected_hashes']==baseline['protected_hashes']
    assert observed['original_APK_lock_inode']==baseline['original_APK_lock_inode']==8282
    assert observed['core_processes']==baseline['core_processes']
    assert not observed['marked_units']
    clock=observed['clock_unit'];old=baseline['clock_unit']
    assert all(clock[k]==old[k] for k in STABLE_CLOCK_FIELDS),'Clock invocation or service state changed'
    assert clock['MainPID']=='0' and clock['ActiveState']=='inactive'
    if graph:
        expected_before={'systemd-fsck-root.service','local-fs-pre.target'} if kind=='candidate' else set(old['Before'].split())
        expected_wants={'local-fs-pre.target'} if kind=='candidate' else set(old['Wants'].split())
        assert set(clock['Before'].split())==expected_before
        assert set(clock['Wants'].split())==expected_wants
        for key in ['After','Requires']:assert set(clock[key].split())==set(old[key].split())

def reconcile(backend,baseline,kind):
    evidence=backend.evidence()
    assert evidence['current_boot_PID1_terminal'] and evidence['MainPID']=='0' and evidence['empty_cgroup']
    assert evidence['disk_stage_verified']
    first=backend.observe(kind);validate(first,baseline,kind,graph=False)
    backend.reload_once()
    reloaded=backend.observe(kind);validate(reloaded,baseline,kind,graph=True)
    # The package trigger's enqueue-marked operation is allowed only with no
    # pending markers; validate immediately before it and after completion.
    backend.enqueue_once()
    final=backend.observe(kind);validate(final,baseline,kind,graph=True)
    return final
