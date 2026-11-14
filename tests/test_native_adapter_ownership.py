# SPDX-License-Identifier: MIT
"""Owned-child cleanup when persistence fails after an actual Popen."""
import importlib.util
import contextlib
import fcntl
import io
import os
import types
from pathlib import Path
import unittest
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('ownership_native_fixture',HERE/'native_adapter_fixture.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

class OwnershipTests(unittest.TestCase):
    def call_main_with_owned_child(self, *, fail_cleanup=False, successful_candidate=False):
        f=fixture.Fixture(self,'main-cleanup','success' if successful_candidate else 'spawn-persistence-fault')
        held=[]
        original=f.ops.close
        def close():
            descriptor=os.open(f.context.plan['port_lock_path'],os.O_RDWR)
            try:
                try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
                except BlockingIOError:held.append(True)
                else:held.append(False)
            finally:os.close(descriptor)
            original()
            if fail_cleanup:raise RuntimeError('private-cleanup-fixture-sentinel')
        f.ops.close=close
        def execute():
            f.ops.spawn('transfer',[fixture.sys.executable,'transfer_fx0_ram.py'])
            raise RuntimeError('private-operation-fixture-sentinel')
        flow=types.SimpleNamespace(Trial=lambda ops:types.SimpleNamespace(execute=execute))
        if successful_candidate:flow=fixture.FLOW
        def module(path,name):
            if name=='qualified_runtime':return fixture.RUNTIME
            if name=='qualified_flow':return flow
            if name in ['private_native_client','qualified_boot_helper']:return types.SimpleNamespace()
            raise AssertionError('Forbidden client/module load')
        output,error=io.StringIO(),io.StringIO()
        with mock.patch.object(fixture.PUBLIC,'Context',return_value=f.context), \
             mock.patch.object(fixture.PUBLIC,'source_module',side_effect=module), \
             mock.patch.object(fixture.PUBLIC,'adapter_type',return_value=lambda:f.ops), \
             contextlib.redirect_stdout(output),contextlib.redirect_stderr(error):
            status=fixture.PUBLIC.main(['--plan',str(f.plan_path),'--plan-sha256',f.context.expected])
        self.assertEqual(status,1)
        self.assertEqual(held,[True],'Shared port lock released before owned-child cleanup')
        self.assertIsNotNone(f.ops.children['transfer'].poll())
        self.assertIsNone(f.ops.journal.fd)
        self.assertNotIn('private-operation-fixture-sentinel',output.getvalue()+error.getvalue())
        self.assertNotIn('private-cleanup-fixture-sentinel',output.getvalue()+error.getvalue())
        if fail_cleanup:self.assertNotIn('"state": "terminal"',output.getvalue())
        descriptor=os.open(f.context.plan['port_lock_path'],os.O_RDWR)
        try:fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        finally:os.close(descriptor)
        return error.getvalue()

    def test_main_holds_shared_port_lock_until_child_cleanup_finishes(self):
        self.call_main_with_owned_child()

    def test_main_cleanup_error_is_failed_and_redacted(self):
        self.assertIn('owned-child-cleanup',self.call_main_with_owned_child(fail_cleanup=True))

    def test_successful_candidate_is_not_reported_terminal_if_cleanup_fails(self):
        self.assertIn('owned-child-cleanup',self.call_main_with_owned_child(
            fail_cleanup=True,successful_candidate=True))

    def test_spawn_journal_failure_reaps_every_actual_child_role(self):
        for role in ['transfer','observer','normal-reboot']:
            with self.subTest(role=role):
                f=fixture.Fixture(self,role,'spawn-persistence-fault')
                command={'transfer':[fixture.sys.executable,'transfer_fx0_ram.py'],
                         'observer':[fixture.sys.executable,'native_trial_observer.py'],
                         'normal-reboot':['fastboot','-s',f.serial,'reboot']}[role]
                with mock.patch.object(f.ops.journal,'update',side_effect=OSError('fixture journal unavailable')):
                    with self.assertRaises(OSError):f.ops.spawn(role,command)
                self.assertIn(role,f.ops.children)
                self.assertIsNotNone(f.ops.children[role].poll(),'Child remains live after failed spawn persistence')
                self.assertTrue(f.ops.state['processes'][role]['cleanup']['owned_child_reaped'])
                self.assertNotIn('BOOT',f.events);self.assertNotIn('reset',f.events)

    def test_close_reaps_child_even_when_journal_stays_unwritable(self):
        f=fixture.Fixture(self,'close-journal-error','spawn-persistence-fault')
        f.ops.spawn('transfer',[fixture.sys.executable,'transfer_fx0_ram.py'])
        with mock.patch.object(f.ops.journal,'update',side_effect=OSError('fixture journal unavailable')):
            with self.assertRaises(OSError):f.ops.close()
        self.assertIsNotNone(f.ops.children['transfer'].poll())
        self.assertTrue(f.ops.state['processes']['transfer']['cleanup']['owned_child_reaped'])
        self.assertIsNone(f.ops.journal.fd)
        self.assertNotIn('BOOT',f.events);self.assertNotIn('reset',f.events)

    def test_cleanup_keeps_original_observer_deadline_failure(self):
        f=fixture.Fixture(self,'close-deadline','observer-parent-deadline')
        with self.assertRaisesRegex(RuntimeError,'observer failed'):f.execute()
        self.assertTrue(f.ops.state['processes']['observer']['process_deadline_expired'])
        f.ops.close()
        record=f.ops.state['processes']['observer']
        self.assertTrue(record['process_deadline_expired'])
        self.assertFalse(record['cleanup']['process_deadline_expired'])
        self.assertFalse(f.candidate())

    def test_duplicate_role_cannot_replace_owned_handle(self):
        f=fixture.Fixture(self,'duplicate-role','spawn-persistence-fault')
        f.ops.spawn('transfer',[fixture.sys.executable,'transfer_fx0_ram.py'])
        original=f.ops.children['transfer']
        with self.assertRaisesRegex(RuntimeError,'cannot be replaced'):
            f.ops.spawn('transfer',[fixture.sys.executable,'transfer_fx0_ram.py'])
        self.assertIs(f.ops.children['transfer'],original)
        self.assertEqual(len(f.children),1)
        f.ops.close();self.assertIsNotNone(original.poll())

    def test_uncertain_child_cleanup_does_not_skip_other_owned_children(self):
        f=fixture.Fixture(self,'uncertain-cleanup','spawn-persistence-fault')
        f.ops.spawn('transfer',[fixture.sys.executable,'transfer_fx0_ram.py'])
        f.ops.spawn('observer',[fixture.sys.executable,'native_trial_observer.py'])
        original=f.wait_hook['function']
        def wait(child,timeout):
            if child is f.ops.children['transfer']:
                raise fixture.RUNTIME.UnreapedChild('fixture uncertain cleanup')
            return original(child,timeout)
        with mock.patch.dict(f.wait_hook,{'function':wait}):
            with self.assertRaises(fixture.RUNTIME.UnreapedChild):f.ops.close()
        self.assertIsNotNone(f.ops.children['observer'].poll())
        self.assertTrue(f.ops.state['processes']['observer']['cleanup']['owned_child_reaped'])
        self.assertNotIn('cleanup',f.ops.state['processes']['transfer'])
        self.assertFalse(f.ops.state['owned_child_cleanup_complete'])
        self.assertIsNone(f.ops.journal.fd)

if __name__=='__main__':unittest.main()
