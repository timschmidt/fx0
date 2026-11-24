# SPDX-License-Identifier: MIT
"""Passive profile uses shared cleanup code and complete matching worker receipts."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location('owned_passive_evidence_fixture',Path(__file__).with_name('passive_owned_fixture.py'))
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)


class EvidenceTests(unittest.TestCase):
    def test_ownership_methods_are_actual_qualified_code_without_native_callbacks(self):
        f=fixture.Fixture(self,'borrowed-methods')
        passive=f.Real.__mro__[1]
        owned=fixture.PUBLIC.ownership.adapter_type(f.context,f.services)
        for name in ['_cleanup_child','spawn','close']:
            self.assertIs(getattr(passive,name).__code__,getattr(owned,name).__code__)
        self.assertNotIn('Native',[cls.__name__ for cls in f.Real.__mro__])
        self.assertIs(passive.preflight.__code__,fixture.PUBLIC.common.adapter_type(
            f.context,f.services).preflight.__code__)

    def test_incomplete_or_mismatched_worker_evidence_never_accepts_candidate(self):
        f=fixture.Fixture(self,'receipt-gates');f.execute()
        self.assertTrue(f.candidate())
        path=f.case/'serial-observation.json';original=json.loads(path.read_text());generation=f.ops.state['native_return_USB_generation']
        for fault in ['not-terminal','not-closed','no-native-USB','deadline','wrong-notes',
                      'old-boot','worker-incomplete','nonzero-status','wrong-markers','wrong-native-generation','missing-native-generation']:
            with self.subTest(fault=fault):
                value=copy.deepcopy(original)
                if fault=='not-terminal':value['state']='observing'
                elif fault=='not-closed':value['console_closed']=False
                elif fault=='no-native-USB':value['returned_native_USB']=False
                elif fault=='deadline':value['observation_deadline_reached']=True
                elif fault=='wrong-notes':value['RAM_identity']['notes_SHA256']='0'*64
                elif fault=='old-boot':value['RAM_identity']['boot_id']=f.context.plan['baseline_boot_id']
                elif fault=='worker-incomplete':value['worker_result']['complete']=False
                elif fault=='nonzero-status':value['worker_result']['returncode']=1
                elif fault=='wrong-markers':value['worker_result']['observed_markers']=[]
                elif fault=='wrong-native-generation':value['native_return_USB_generation']='wrong'
                elif fault=='missing-native-generation':
                    value.pop('native_return_USB_generation');f.ops.state.pop('native_return_USB_generation')
                path.write_text(json.dumps(value));self.assertFalse(f.candidate())
                f.ops.state['native_return_USB_generation']=generation
        path.write_text(json.dumps(original))
        self.assertEqual(f.events.count('BOOT'),1)
        self.assertNotIn('reset',f.events)


if __name__=='__main__':unittest.main()
