# SPDX-License-Identifier: MIT
"""Public callback-ordering tests; no USB, SSH, phone or ignored local imports."""
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'passive_trial', ROOT / 'diagnostics/modem-control/passive_trial.py')
flow = importlib.util.module_from_spec(spec)
spec.loader.exec_module(flow)


class Operations:
    def __init__(self, *, transfer=None, readback=True, live=True, faults=None):
        self.transfer = transfer if transfer is not None else {
            'terminal': True, 'returncode': 0, 'timeout': False}
        self.readback = readback
        self.live = live
        self.faults = faults or {}
        self.calls = []

    def call(self, name):
        self.calls.append(name)
        if name in self.faults:
            raise self.faults[name]

    def preflight(self): self.call('preflight')
    def enter(self): self.call('enter')
    def stage(self):
        self.call('stage')
        return self.transfer
    def readback_matches(self):
        self.call('readback')
        return self.readback
    def start_observers(self): self.call('start')
    def observers_live(self):
        self.call('live')
        return self.live
    def stop_observers(self): self.call('stop')
    def mark_boot_attempt(self): self.call('intent')
    def boot(self): self.call('BOOT')
    def uncertain_boot(self, error): self.call('uncertain')
    def finish_observers(self): self.call('finish')
    def return_native(self, reset): self.call(('return', reset))
    def native(self): self.call('native')


class PassiveTrialFlow(unittest.TestCase):
    def test_owner_barrier_precedes_device_actions(self):
        ops = Operations(faults={'preflight': RuntimeError('owner required')})
        with self.assertRaises(RuntimeError):
            flow.Trial(ops).execute()
        self.assertEqual(ops.calls, ['preflight'])

    def test_live_or_unknown_transfer_forbids_BOOT_and_recovery(self):
        for result in [
            {'terminal': False, 'returncode': 0},
            {'terminal': True, 'returncode': None},
            {'terminal': True},
            {'terminal': True, 'returncode': False},
            {'terminal': 1, 'returncode': 0},
            {'terminal': True, 'returncode': 0, 'timeout': 'yes'},
        ]:
            with self.subTest(result=result):
                ops = Operations(transfer=result)
                with self.assertRaises(RuntimeError):
                    flow.Trial(ops).execute()
                self.assertEqual(ops.calls, ['preflight', 'enter', 'stage'])

    def test_readback_mismatch_never_BOOTs_or_resets(self):
        ops = Operations(readback=False, transfer={
            'terminal': True, 'returncode': 0, 'timeout': True})
        flow.Trial(ops).execute()
        self.assertNotIn('BOOT', ops.calls)
        self.assertEqual(ops.calls[-2:], [('return', False), 'native'])

    def test_only_known_terminal_timeout_allows_pre_BOOT_reset(self):
        for timeout in [False, True]:
            with self.subTest(timeout=timeout):
                ops = Operations(transfer={
                    'terminal': True, 'returncode': 1, 'timeout': timeout})
                flow.Trial(ops).execute()
                self.assertNotIn('readback', ops.calls)
                self.assertEqual(ops.calls[-2:], [('return', timeout), 'native'])

    def test_dead_observer_stops_before_pre_BOOT_recovery(self):
        ops = Operations(live=False)
        with self.assertRaises(RuntimeError):
            flow.Trial(ops).execute()
        self.assertEqual(ops.calls[-3:], ['stop', ('return', False), 'native'])
        self.assertNotIn('intent', ops.calls)

    def test_failed_observer_stop_forbids_speculative_recovery(self):
        ops = Operations(live=False, faults={'stop': OSError('still owned')})
        with self.assertRaises(OSError):
            flow.Trial(ops).execute()
        self.assertEqual(ops.calls[-1], 'stop')
        self.assertFalse(any(isinstance(call, tuple) for call in ops.calls))

    def test_uncertain_BOOT_is_observed_without_retry(self):
        ops = Operations(faults={'BOOT': OSError('ack missing')})
        flow.Trial(ops).execute()
        self.assertEqual(ops.calls[-3:], ['uncertain', 'finish', 'native'])
        self.assertEqual(ops.calls.count('BOOT'), 1)
        self.assertFalse(any(isinstance(call, tuple) for call in ops.calls))

    def test_failed_intent_record_still_observes_and_verifies(self):
        ops = Operations(faults={'intent': OSError('marker write failed')})
        trial = flow.Trial(ops)
        with self.assertRaises(OSError):
            trial.execute()
        self.assertTrue(trial.boot_attempted)
        self.assertEqual(ops.calls[-3:], ['intent', 'finish', 'native'])
        self.assertNotIn('BOOT', ops.calls)
        self.assertFalse(any(isinstance(call, tuple) for call in ops.calls))

    def test_failed_uncertainty_report_still_observes_and_verifies(self):
        ops = Operations(faults={
            'BOOT': OSError('ack missing'), 'uncertain': RuntimeError('report failed')})
        with self.assertRaises(RuntimeError):
            flow.Trial(ops).execute()
        self.assertEqual(ops.calls[-3:], ['uncertain', 'finish', 'native'])

    def test_failed_post_BOOT_observation_still_verifies_native(self):
        ops = Operations(faults={'finish': RuntimeError('observer failed')})
        with self.assertRaises(RuntimeError):
            flow.Trial(ops).execute()
        self.assertEqual(ops.calls[-2:], ['finish', 'native'])
        self.assertEqual(ops.calls.count('BOOT'), 1)

    def test_interrupt_after_intent_runs_postflight_and_propagates(self):
        for point in ['intent', 'BOOT', 'finish']:
            with self.subTest(point=point):
                ops = Operations(faults={point: KeyboardInterrupt()})
                with self.assertRaises(KeyboardInterrupt):
                    flow.Trial(ops).execute()
                self.assertEqual(ops.calls[-2:], ['finish', 'native'])
                self.assertLessEqual(ops.calls.count('BOOT'), 1)
                self.assertFalse(any(isinstance(call, tuple) for call in ops.calls))

    def test_failed_native_verification_cannot_return_success(self):
        ops = Operations(faults={'native': RuntimeError('wrong native image')})
        with self.assertRaises(RuntimeError):
            flow.Trial(ops).execute()

    def test_success_records_intent_before_single_BOOT(self):
        ops = Operations()
        result = flow.Trial(ops).execute()
        self.assertEqual(result, 'BOOT attempted once; native return observed')
        self.assertEqual(ops.calls, [
            'preflight', 'enter', 'stage', 'readback', 'start', 'live',
            'intent', 'BOOT', 'finish', 'native'])

    def test_instance_cannot_repeat_even_after_failure(self):
        for faults in [{}, {'preflight': RuntimeError('owner required')},
                       {'finish': RuntimeError('observer failed')}]:
            with self.subTest(faults=faults):
                ops = Operations(faults=faults)
                trial = flow.Trial(ops)
                try:
                    trial.execute()
                except RuntimeError:
                    pass
                before = list(ops.calls)
                with self.assertRaisesRegex(RuntimeError, 'already used'):
                    trial.execute()
                self.assertEqual(ops.calls, before)


if __name__ == '__main__':
    unittest.main()
