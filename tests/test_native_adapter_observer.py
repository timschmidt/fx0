# SPDX-License-Identifier: MIT
"""Actual native observer with forbidden-by-default, read-only remote fixtures."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
HERE = ROOT/'diagnostics/kernel-maintenance'
spec = importlib.util.spec_from_file_location('native_observer_under_test', HERE/'native_trial_observer.py')
observer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(observer)


class ObserverTests(unittest.TestCase):
    def fixture(self, observations, health=None, client_error=False):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name)
        before = {'boot_id': '00000000-0000-4000-8000-000000000001',
                  'kernel_notes_SHA256': 'r1-fixture-notes',
                  'files_sha256': {'/lib/apk/db/installed': 'a'*64, '/etc/apk/world': 'b'*64},
                  'boot_partition_sha256': 'c'*64}
        (base/'before.json').write_text(json.dumps(before))
        (base/'attempt.claim').write_text('fixture parent claim')
        calls = []
        context = types.SimpleNamespace(root=ROOT, workspace=base,
            plan={'baseline_boot_id': before['boot_id']},
            verify_inputs=lambda: calls.append('inputs'), check_operator=lambda: calls.append('operator'))
        result = {'boot_id': '00000000-0000-4000-8000-000000000003', 'systemd': 'running',
                  'taint': 0, 'serious_kernel_pattern_counts': {'BUG:': 0}}
        for name in ['exact_r2_notes_verified', 'all478_new_module_metadata_files_verified',
                     'early_static_helper_alive_and_exact_binary', 'primary_return_timer_active',
                     'four_cpus_schedutil_787200_max', 'touch_device_open',
                     'package_DB_world_and_raw_boot_unchanged', 'read_only']:
            result[name] = True
        if health:
            result.update(health)

        def run(command, **kwargs):
            self.assertEqual(command[0], 'fixture-ssh')
            self.assertEqual(kwargs, {'capture_output': True, 'timeout': 10})
            calls.append('probe')
            if not observations:
                raise AssertionError('Unexpected further probe in fixture')
            value = observations.pop(0)
            if isinstance(value, Exception):
                raise value
            return subprocess.CompletedProcess(command, 0, json.dumps(value).encode(), b'')

        def health_run(command, **kwargs):
            self.assertTrue(command.startswith('python3 -B -c '))
            self.assertIn(' --baseline-boot-id ', command)
            self.assertEqual(kwargs, {'root': True, 'timeout': 45})
            calls.append('health')
            if client_error:
                raise RuntimeError('private-client-fixture-sentinel')
            return json.dumps(result).encode()
        phone = types.SimpleNamespace(OPTS=['fixture-ssh'], run=health_run)
        tick = [0]

        def pause(seconds):
            tick[0] += 200

        def execute():
            return observer.observe(context, phone, run=run, clock=lambda: tick[0], pause=pause)
        return context, calls, execute

    def current(self, boot='candidate', notes=None, trial=True, **changes):
        value = {'boot_id': '00000000-0000-4000-8000-00000000000' + {'before': '1', 'return': '2', 'candidate': '3', 'other': '4'}[boot],
                 'notes': notes or observer.adapter.NOTES,
                 'trial': trial, 'any_trial': trial, 'uptime': 20, 'Sway': 'fixture'}
        value.update(changes)
        return value

    def returned(self):
        return self.current('return', 'r1-fixture-notes', False)

    def test_candidate_health_then_native_return_are_distinct_proofs(self):
        context, calls, execute = self.fixture([self.current('before'), self.current(), self.returned()])
        report = execute()
        self.assertTrue(report['candidate_seen'] and report['candidate_health_passed'] and report['returned'])
        self.assertEqual(calls.count('health'), 1)
        state = {'BOOT_attempted': True, 'observer_returncode': 0, 'native_return': {'boot_id': self.returned()['boot_id']},'processes':{'observer':{'owned_child_reaped':True,'process_deadline_expired':False}}}
        self.assertTrue(observer.adapter.candidate_accepted(context, state))
        self.assertFalse(observer.adapter.candidate_accepted(context, state | {'observer_returncode': 7}))
        self.assertFalse(observer.adapter.candidate_accepted(context, state | {'native_return': {'boot_id': 'wrong'}}))
        self.assertEqual((context.workspace/'native-observation.json').stat().st_mode & 0o777, 0o600)

    def test_native_return_without_candidate_cannot_pass_candidate(self):
        context, calls, execute = self.fixture([self.returned()])
        report = execute()
        self.assertTrue(report['returned'])
        self.assertFalse(report['candidate_seen'] or report['candidate_health_passed'])
        self.assertNotIn('health', calls)
        self.assertFalse(observer.adapter.candidate_accepted(context, {'BOOT_attempted': True, 'observer_returncode': 0}))

    def test_wrong_or_incomplete_health_never_creates_ready_receipt(self):
        for bad in [{'boot_id': 'wrong'}, {'primary_return_timer_active': False},
                    {'serious_kernel_pattern_counts': {'IOMMU.*fault': 1}}]:
            with self.subTest(bad=bad):
                context, calls, execute = self.fixture([self.current(), self.returned()], health=bad)
                report = execute()
                self.assertFalse(report['candidate_health_passed'])
                self.assertFalse((context.workspace/'candidate-ready.json').exists())

    def test_candidate_boot_change_fails_without_accepting_return(self):
        context, calls, execute = self.fixture([self.current(), self.current('other')])
        with self.assertRaisesRegex(RuntimeError, 'Candidate boot changed'):
            execute()
        report = json.loads((context.workspace/'native-observation.json').read_text())
        self.assertFalse(report['returned'])
        self.assertEqual(calls.count('health'), 1)

    def test_unknown_identity_reaches_bounded_failure_without_health(self):
        context, calls, execute = self.fixture([self.current(notes='wrong') for _ in range(5)])
        with self.assertRaisesRegex(RuntimeError, 'bounded window'):
            execute()
        self.assertNotIn('health', calls)
        report = json.loads((context.workspace/'native-observation.json').read_text())
        self.assertTrue(report['observation_deadline'])
        self.assertFalse(report['returned'] or report['candidate_health_passed'])

    def test_client_exception_text_is_never_copied_to_observations(self):
        context, calls, execute = self.fixture([self.current(), self.returned()], client_error=True)
        report = execute()
        self.assertFalse(report['candidate_health_passed'])
        self.assertNotIn('private-client-fixture-sentinel', (context.workspace/'native-observation.json').read_text())
        self.assertEqual(report['errors'][0]['health_error_type'], 'RuntimeError')

    def test_stale_artifact_or_observer_claim_prevents_another_probe(self):
        for name in ['native-observation.json', 'observer.claim']:
            with self.subTest(name=name):
                context, calls, execute = self.fixture([self.returned()])
                (context.workspace/name).write_text('retained fixture state')
                with self.assertRaises(FileExistsError):
                    execute()
                self.assertNotIn('probe', calls)
                self.assertEqual((context.workspace/name).read_text(), 'retained fixture state')

    def test_directory_fsync_failure_is_not_success_even_if_file_visible(self):
        context, calls, execute = self.fixture([self.returned()])
        real = observer.os.fsync
        def fsync(fd):
            if Path('/proc/self/fd/' + str(fd)).resolve() == context.workspace:
                raise OSError('fixture directory fsync failure')
            return real(fd)
        with mock.patch.object(observer.os, 'fsync', side_effect=fsync):
            with self.assertRaises(OSError):
                execute()
        self.assertNotIn('probe', calls)
        self.assertTrue((context.workspace/'native-observation.json').exists())
        self.assertTrue((context.workspace/'observer.claim').exists())

    def test_remote_probes_are_inert_on_import_and_reject_optimized_execution(self):
        for name in ['native_trial_stage_probe.py', 'native_trial_health_probe.py']:
            with self.subTest(name=name):
                spec = importlib.util.spec_from_file_location('read_only_probe_fixture', HERE/name)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                result = subprocess.run([sys.executable, '-B', '-O', str(HERE/name),
                                         '--baseline-boot-id', 'fixture'], capture_output=True, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b'Optimized Python is forbidden', result.stderr)


if __name__ == '__main__':
    unittest.main()
