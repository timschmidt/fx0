# SPDX-License-Identifier: MIT
import datetime,importlib.util,json,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('public_adapter_fixture',Path(__file__).with_name('passive_adapter_fixture.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
Fixture=fixture.Fixture
class AdapterTests(unittest.TestCase):
    def test_success_records_intent_and_reaps_actual_fixture_children(self):
        f=Fixture(self,'success');f.execute()
        self.assertEqual(f.events.count('BOOT'),1);self.assertNotIn('return',f.events);self.assertTrue(f.candidate())
        self.assertIn('native_return',f.ops.state)
        for name in ['transfer','observer']:self.assertTrue(f.ops.state['processes'][name]['owned_child_reaped'])
        f.ops.journal.close()
        with self.assertRaises(FileExistsError):f.Real(device_record=f.case/'fixture-device.json')

    def test_known_transfer_failures_return_without_BOOT(self):
        for mode,reset in [('usb-timeout',True),('other-transfer-error',False),('bad-readback',False),('parent-deadline',False)]:
            with self.subTest(mode=mode):
                f=Fixture(self,mode,mode);f.execute()
                self.assertNotIn('BOOT',f.events);self.assertEqual(f.events.count('return'),1)
                self.assertEqual('reset' in f.events,reset);self.assertFalse(f.candidate());self.assertIn('native_return',f.ops.state)
                if mode=='parent-deadline':
                    self.assertTrue(f.ops.state['processes']['transfer']['process_deadline_expired'])
                    self.assertFalse(f.ops.state['transfer_timeout'])

    def test_uncertain_BOOT_never_retries_or_resets(self):
        f=Fixture(self,'uncertain-BOOT','uncertain-BOOT');f.execute()
        self.assertEqual(f.events.count('BOOT'),1);self.assertNotIn('return',f.events);self.assertNotIn('reset',f.events)
        self.assertIn('native_return',f.ops.state)

    def test_observer_failure_forbids_acceptance_but_verifies_native(self):
        f=Fixture(self,'observer-error','observer-error')
        with self.assertRaisesRegex(RuntimeError,'observer failed'):f.execute()
        self.assertEqual(f.events.count('BOOT'),1);self.assertIn('native_return',f.ops.state)
        self.assertEqual(f.ops.state['observer_returncode'],7)

    def test_dead_observer_never_reaches_BOOT_intent(self):
        f=Fixture(self,'dead-observer','dead-observer')
        with self.assertRaisesRegex(RuntimeError,'not live'):f.execute()
        self.assertNotIn('BOOT',f.events);self.assertEqual(f.events.count('return'),1)
        self.assertFalse(f.ops.boot_sent)

    def test_native_return_does_not_imply_worker_pass(self):
        f=Fixture(self,'worker-failed','worker-failed');f.execute()
        self.assertIn('native_return',f.ops.state);self.assertFalse(f.candidate())

    def test_preflight_requires_current_correct_owner_and_baseline(self):
        for mode in ['wrong-answer','expired','future','wrong-image','wrong-boot','baseline-mismatch']:
            with self.subTest(mode=mode):
                f=Fixture(self,mode,mode);owner=dict(f.owner)
                if mode=='wrong-answer':owner['answer']='Available for another run'
                elif mode=='expired':owner['recorded_UTC']=(datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=700)).isoformat()
                elif mode=='future':owner['recorded_UTC']=(datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=60)).isoformat()
                elif mode=='wrong-image':owner['image_SHA256']='0'*64
                elif mode=='wrong-boot':owner['boot_id']='00000000-0000-4000-8000-000000000003'
                (f.case/'owner-availability.json').write_text(json.dumps(owner))
                with self.assertRaises((AssertionError,fixture.PUBLIC.PlanRejected)):f.execute()
                self.assertNotIn('enter',f.events);self.assertNotIn('BOOT',f.events)


if __name__=='__main__':unittest.main()
