import copy,unittest
import manager_policy as policy

def baseline():
    clock=dict(Id='swclock-offset-boot.service',ActiveState='inactive',SubState='dead',MainPID='0',InvocationID='existing',ExecMainStartTimestampMonotonic='11000000',ExecMainExitTimestampMonotonic='12000000',ExecMainStatus='0',FragmentPath='/usr/lib/systemd/system/swclock-offset-boot.service',UnitFileState='enabled',Before='systemd-fsck-root.service systemd-fsck@swclock-offset-boot.service',Wants='',After='systemd-journald.socket system.slice',Requires='system.slice')
    return dict(boot_id='same',clock_unit=clock,disk_verified=True,package_count=775,protected_hashes={'offset':'unchanged','boot':'unchanged'},original_APK_lock_inode=8282,core_processes={'sway':'12','lisgd':'13'},marked_units=[])

class Backend:
    def __init__(self,kind='candidate',fault=None):self.kind=kind;self.fault=fault;self.calls=[];self.state=baseline()
    def evidence(self):return dict(current_boot_PID1_terminal=self.fault!='active',MainPID='1' if self.fault=='active' else '0',empty_cgroup=self.fault!='active',disk_stage_verified=self.fault!='disk-stage')
    def observe(self,kind):
        result=copy.deepcopy(self.state)
        if self.fault=='offset':result['protected_hashes']['offset']='changed'
        if self.fault=='marker':result['marked_units']=['unrelated.service']
        if self.fault=='disk':result['disk_verified']=False
        if self.fault=='PID':result['core_processes']['sway']='99'
        if self.fault=='invocation':result['clock_unit']['InvocationID']='new'
        if self.fault=='late-marker' and self.calls:result['marked_units']=['unrelated.service']
        return result
    def reload_once(self):
        self.calls.append('reload')
        if self.fault=='reload-error':raise RuntimeError('Reload failed or acknowledgement uncertain')
        if self.kind=='candidate' and self.fault!='bad-graph':self.state['clock_unit'].update(Before='local-fs-pre.target systemd-fsck-root.service',Wants='local-fs-pre.target')
    def enqueue_once(self):self.calls.append('enqueue')

class ManagerPolicyTests(unittest.TestCase):
    def test_candidate_and_baseline_graphs(self):
        for kind in ['candidate','baseline']:
            b=Backend(kind);policy.reconcile(b,baseline(),kind);self.assertEqual(b.calls,['reload','enqueue'])
    def test_preconditions_prevent_all_manager_commands(self):
        for fault in ['active','disk-stage','disk','offset','marker','PID','invocation']:
            b=Backend(fault=fault)
            with self.subTest(fault=fault),self.assertRaises(AssertionError):policy.reconcile(b,baseline(),'candidate')
            self.assertEqual(b.calls,[])
    def test_failed_or_uncertain_reload_is_not_retried_or_enqueued(self):
        b=Backend(fault='reload-error')
        with self.assertRaises(RuntimeError):policy.reconcile(b,baseline(),'candidate')
        self.assertEqual(b.calls,['reload'])
    def test_bad_graph_or_new_markers_prevent_enqueue(self):
        for fault in ['bad-graph','late-marker']:
            b=Backend(fault=fault)
            with self.subTest(fault=fault),self.assertRaises(AssertionError):policy.reconcile(b,baseline(),'candidate')
            self.assertEqual(b.calls,['reload'])
if __name__=='__main__':unittest.main()
