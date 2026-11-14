# SPDX-License-Identifier: MIT
import importlib.util,json,os,unittest
from pathlib import Path
from unittest import mock

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('qualified_adapter_fixture',HERE/'passive_adapter_fixture.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class AdapterFaults(unittest.TestCase):
    def test_failed_intent_fsync_never_BOOTs_or_retries(self):
        f=fixture.Fixture(self,'fault-intent-fsync')
        original=f.ops.journal.update
        failed=False
        def update(state):
            nonlocal failed
            if state.get('BOOT_attempted') and not failed:
                failed=True
                with mock.patch.object(fixture.RUNTIME.os,'fsync',side_effect=OSError('fixture intent fsync failed')):
                    return original(state)
            return original(state)
        f.ops.journal.update=update
        with self.assertRaises(RuntimeError):f.execute()
        self.assertTrue(failed);self.assertNotIn('BOOT',f.events)
        self.assertNotIn('return',f.events);self.assertNotIn('reset',f.events)
        self.assertTrue(f.ops.boot_sent)
        self.assertIn('waiting for native',f.ops.state['state'])
        f.ops.journal.close()
        with self.assertRaises(FileExistsError):f.Real(device_record=f.case/'fixture-device.json')

    def test_unreaped_transfer_status_forbids_BOOT_and_recovery(self):
        f=fixture.Fixture(self,'fault-unreaped-transfer')
        globals_=f.wait_hook
        def unreaped(child,timeout):raise fixture.RUNTIME.UnreapedChild('fixture uncertain ownership')
        with mock.patch.dict(globals_,{'function':unreaped}):
            with self.assertRaises(fixture.RUNTIME.UnreapedChild):f.execute()
        self.assertNotIn('BOOT',f.events);self.assertNotIn('return',f.events);self.assertNotIn('reset',f.events)
        self.assertNotIn('returncode',f.ops.state['processes']['transfer'])
        self.assertNotIn('owned_child_reaped',f.ops.state['processes']['transfer'])

    def test_wrong_native_module_cohort_cannot_pass_postflight(self):
        f=fixture.Fixture(self,'fault-native-cohort')
        client=f.ops.native.__closure__
        client=next(cell.cell_contents for cell in client if hasattr(cell.cell_contents,'OPTS'))
        original=client.run
        def run(command,**kwargs):
            data=original(command,**kwargs)
            if command.startswith('python3 -c '):
                value=json.loads(data);value['module_tree_digest']='offline wrong module cohort';data=json.dumps(value).encode()
            return data
        client.run=run
        with self.assertRaises(AssertionError):f.execute()
        self.assertEqual(f.events.count('BOOT'),1)
        self.assertNotIn('native_return',f.ops.state)
        self.assertFalse((f.case/'native-return.json').exists())
        self.assertNotIn('return',f.events);self.assertNotIn('reset',f.events)

    def test_directory_fsync_failure_is_failed_even_if_state_visible(self):
        temporary=fixture.tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        directory=Path(temporary.name)
        journal=fixture.RUNTIME.AttemptJournal(directory)
        original=fixture.RUNTIME.os.fsync
        def fsync(descriptor):
            if descriptor==journal.fd:raise OSError('fixture directory fsync failed')
            return original(descriptor)
        with mock.patch.object(fixture.RUNTIME.os,'fsync',side_effect=fsync):
            with self.assertRaises(OSError):journal.update({'BOOT_attempted':True})
        self.assertTrue(json.loads((directory/'controller.json').read_text())['BOOT_attempted'])
        journal.close()
        with self.assertRaises(FileExistsError):fixture.RUNTIME.AttemptJournal(directory)


if __name__=='__main__':unittest.main()
