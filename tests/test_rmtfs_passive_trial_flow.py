#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise device-action ordering without opening USB or connecting to a phone."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('prepared_trial_flow',ROOT/'local/rmtfs-passive-r1-trial-01/flow.py')
flow=importlib.util.module_from_spec(spec);spec.loader.exec_module(flow)


class Operations:
    def __init__(self,**options):self.options=options;self.calls=[]
    def preflight(self):
        self.calls.append('preflight')
        if self.options.get('missing_owner'):raise RuntimeError('availability required')
    def enter(self):self.calls.append('enter')
    def stage(self):
        self.calls.append('stage')
        return {'terminal':not self.options.get('transfer_live'),'returncode':int(bool(self.options.get('transfer_failed'))),'timeout':bool(self.options.get('transfer_timeout'))}
    def readback_matches(self):return not self.options.get('wrong_readback')
    def start_observers(self):self.calls.append('start_observer')
    def observers_live(self):return not self.options.get('observer_dead')
    def stop_observers(self):self.calls.append('stop_observer')
    def mark_boot_attempt(self):self.calls.append('mark_BOOT')
    def boot(self):
        self.calls.append('BOOT')
        if self.options.get('uncertain_BOOT'):raise OSError('acknowledgement missing')
    def uncertain_boot(self,error):self.calls.append('uncertain_BOOT')
    def finish_observers(self):self.calls.append('finish_observer')
    def return_native(self,reset):self.calls.append(('return_before_BOOT',reset))
    def native(self):self.calls.append('verify_native')


class PassiveFlowTest(unittest.TestCase):
    def test_owner_barrier_precedes_every_device_action(self):
        ops=Operations(missing_owner=True)
        with self.assertRaises(RuntimeError):flow.Trial(ops).execute()
        self.assertEqual(ops.calls,['preflight'])

    def test_live_transfer_prevents_BOOT_or_recovery(self):
        ops=Operations(transfer_live=True)
        with self.assertRaises(RuntimeError):flow.Trial(ops).execute()
        self.assertEqual(ops.calls,['preflight','enter','stage'])

    def test_wrong_readback_returns_without_BOOT(self):
        ops=Operations(wrong_readback=True);flow.Trial(ops).execute()
        self.assertNotIn('BOOT',ops.calls)
        self.assertEqual(ops.calls[-2:],[('return_before_BOOT',False),'verify_native'])

    def test_terminal_timeout_recovers_only_before_BOOT(self):
        ops=Operations(transfer_failed=True,transfer_timeout=True);flow.Trial(ops).execute()
        self.assertNotIn('BOOT',ops.calls)
        self.assertEqual(ops.calls[-2:],[('return_before_BOOT',True),'verify_native'])

    def test_dead_observer_prevents_BOOT(self):
        ops=Operations(observer_dead=True)
        with self.assertRaises(RuntimeError):flow.Trial(ops).execute()
        self.assertNotIn('BOOT',ops.calls)
        self.assertEqual(ops.calls[-3:],['stop_observer',('return_before_BOOT',False),'verify_native'])

    def test_uncertain_BOOT_is_observed_without_retry_or_reset(self):
        ops=Operations(uncertain_BOOT=True);flow.Trial(ops).execute()
        self.assertEqual(ops.calls.count('BOOT'),1)
        self.assertEqual(ops.calls[-3:],['uncertain_BOOT','finish_observer','verify_native'])
        self.assertFalse(any(isinstance(call,tuple) for call in ops.calls))

    def test_success_marks_intent_before_single_BOOT(self):
        ops=Operations();flow.Trial(ops).execute()
        self.assertEqual(ops.calls,['preflight','enter','stage','start_observer','mark_BOOT','BOOT','finish_observer','verify_native'])


if __name__=='__main__':unittest.main()
