# SPDX-License-Identifier: MIT
"""Bounded synthetic console files, private transport and noncausal summaries."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
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
spec = importlib.util.spec_from_file_location('native_console_under_test', HERE/'native_console.py')
console = importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)
probe, analysis = console.probe, console.analysis
BOOT = '00000000-0000-4000-8000-000000000001'
RETURN = '00000000-0000-4000-8000-000000000002'
NOTES = hashlib.sha256(b'fixture kernel notes').hexdigest()


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.root = self.base/'fixture-root'
        self.root.mkdir()
        self.write('proc/sys/kernel/random/boot_id', BOOT.encode())
        self.write('sys/kernel/notes', b'fixture kernel notes')

    def write(self, name, body):
        path = self.root/name.lstrip('/')
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        path.chmod(0o600)
        return path

    def packet(self, boot=BOOT):
        return probe.capture(boot, NOTES, root=self.root, owner=os.getuid())

    def test_capture_missing_and_regular_files_is_bounded_and_read_only(self):
        body = b'[1.0] fixture console\n'
        path = self.write(probe.PATHS[0], body)
        before = path.read_bytes()
        packet = self.packet()
        self.assertTrue(packet['complete'] and packet['read_only'])
        self.assertEqual(packet['captured_bytes'], len(body))
        self.assertEqual(base64.b64decode(packet['records'][probe.PATHS[0]]['content_base64']), body)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(sum(r['state'] == 'missing' for r in packet['records'].values()), 7)

    def test_wrong_or_changed_native_identity_rejects_capture(self):
        with self.assertRaises(ValueError):
            probe.capture(RETURN, NOTES, root=self.root, owner=os.getuid())
        with mock.patch.object(probe, 'identity', side_effect=[(BOOT, NOTES), (RETURN, NOTES)]):
            with self.assertRaises(ValueError):self.packet()

    def test_final_symlink_and_directory_symlink_are_never_followed(self):
        secret = self.base/'outside-fixture'
        secret.write_bytes(b'private fixture sentinel')
        path = self.root/probe.PATHS[0].lstrip('/')
        path.parent.mkdir(parents=True)
        path.symlink_to(secret)
        packet = self.packet()
        self.assertEqual(packet['records'][probe.PATHS[0]]['state'], 'rejected')
        path.unlink();path.parent.rmdir()
        outside = self.base/'outside-directory';outside.mkdir()
        (outside/path.name).write_bytes(b'private fixture sentinel')
        path.parent.symlink_to(outside, target_is_directory=True)
        packet = self.packet()
        self.assertEqual(packet['records'][probe.PATHS[0]]['state'], 'rejected')
        self.assertNotIn('content_base64', packet['records'][probe.PATHS[0]])

    def test_writable_and_nonregular_files_reject_without_blocking(self):
        path = self.write(probe.PATHS[0], b'fixture')
        path.chmod(0o622)
        self.assertEqual(self.packet()['records'][probe.PATHS[0]]['state'], 'rejected')
        path.unlink();os.mkfifo(path, 0o600)
        self.assertEqual(self.packet()['records'][probe.PATHS[0]]['state'], 'rejected')

    def test_per_file_and_total_limits_reject_excess_without_raw_partial_output(self):
        self.write(probe.PATHS[0], b'x'*17)
        with mock.patch.object(probe, 'PER_FILE', 16), mock.patch.object(probe, 'TOTAL', 20):
            packet = self.packet()
        self.assertEqual(packet['records'][probe.PATHS[0]]['state'], 'rejected')
        self.assertEqual(packet['captured_bytes'], 0)
        self.write(probe.PATHS[0], b'x'*11);self.write(probe.PATHS[1], b'y'*11)
        with mock.patch.object(probe, 'PER_FILE', 16), mock.patch.object(probe, 'TOTAL', 20):
            packet = self.packet()
        self.assertFalse(packet['complete'])
        self.assertEqual(packet['captured_bytes'], 11)
        self.assertNotIn('content_base64', packet['records'][probe.PATHS[1]])

    def test_differing_double_read_is_explicitly_unstable(self):
        self.write(probe.PATHS[0], b'x')
        with mock.patch.object(probe, 'limited_read', side_effect=[b'x', b'y']):
            packet = self.packet()
        self.assertFalse(packet['complete'])
        self.assertEqual(packet['records'][probe.PATHS[0]]['state'], 'changed-during-read')

    def test_all15_exact_compiled_trace_formats_classify_without_raw_lines(self):
        catalog = json.loads(analysis.CATALOG.read_text())
        self.assertEqual(len(catalog['sites']), 15)
        body = ''.join('[6.0] fixture-device: ' + site['format'].replace('%u', '1').replace('%d', '-1')
                       for site in catalog['sites']).encode()
        result = analysis.summarize(body)
        self.assertTrue(all(value == 1 for value in result['known_trace_counts'].values()))
        self.assertEqual(len(result['known_trace_events']), 15)
        self.assertFalse(result['raw_lines_included'] or result['reset_cause_proven'])
        self.assertNotIn('fixture-device', json.dumps(result))

    def test_sensitive_lines_and_out_of_range_values_cannot_become_trace_signals(self):
        body = (b'[1.0] Kernel command line: password=private-fixture fx0-handoff-02: kms-init-enter\n'
                b'[2.0] fx0-handoff-02: legacy-attach-enter type=4294967296\n'
                b'[3.0] fx0-handoff-02: legacy-attach-done ret=2147483648\n'
                b'[4.0] fx0-handoff-02: kms-init-enter-extra\n')
        result = analysis.summarize(body)
        self.assertFalse(any(result['known_trace_counts'].values()))
        self.assertNotIn('private-fixture', json.dumps(result))
        self.assertEqual(result['sensitive_lines_omitted_from_analysis'], 1)

    def test_fault_or_panic_message_and_tail_absence_never_prove_reset_cause(self):
        result = analysis.summarize(b'[6.164901] Unhandled context fault: private-address\n'
                                    b'[7.0] Kernel panic - not syncing: private-message\n', full_record=False)
        self.assertEqual(result['context_fault_messages'], 1)
        self.assertEqual(result['panic_messages'], 1)
        self.assertFalse(result['reset_cause_proven'] or result['full_record'])
        self.assertTrue(result['missing_trace_is_inconclusive'])
        self.assertNotIn('private-', json.dumps(result))

    def test_event_list_is_bounded_while_counts_remain_exact(self):
        result = analysis.summarize(b'[6.0] fx0-handoff-02: kms-init-enter\n'*600)
        self.assertEqual(len(result['known_trace_events']), 512)
        self.assertEqual(result['known_trace_counts']['kms-init-enter'], 600)

    def test_record_comparison_distinguishes_change_missing_and_uncertainty(self):
        self.write(probe.PATHS[0], b'old')
        before = self.packet()
        self.write(probe.PATHS[0], b'new')
        after = self.packet()
        result = analysis.compare(before, after)
        self.assertEqual(result['records'][probe.PATHS[0]]['change'], 'changed')
        self.assertFalse(result['candidate_boot_attribution_proven'] or result['reset_cause_proven'])
        self.assertEqual(analysis.compare(after, after)['records'][probe.PATHS[0]]['change'], 'unchanged')
        after['records'][probe.PATHS[0]]['state'] = 'changed-during-read'
        after['records'][probe.PATHS[0]]['stable'] = False
        self.assertEqual(analysis.compare(before, after)['records'][probe.PATHS[0]]['change'], 'inconclusive')

    def test_packet_wrong_identity_roster_digest_or_completion_rejects(self):
        self.write(probe.PATHS[0], b'fixture')
        valid = self.packet();expected = {'boot_id': BOOT, 'kernel_notes_SHA256': NOTES}
        self.assertTrue(console.validate_packet(json.dumps(valid).encode(), expected)['complete'])
        for kind in ['boot', 'roster', 'digest', 'completion', 'bytes']:
            with self.subTest(kind=kind):
                bad = copy.deepcopy(valid)
                if kind == 'boot':bad['boot_id'] = RETURN
                elif kind == 'roster':bad['records']['/arbitrary/private/path'] = {'state': 'missing'}
                elif kind == 'digest':bad['records'][probe.PATHS[0]]['SHA256'] = '0'*64
                elif kind == 'completion':bad['complete'] = False
                else:bad['captured_bytes'] += 1
                with self.assertRaises(ValueError):console.validate_packet(json.dumps(bad).encode(), expected)

    def host_fixture(self, *, owner=True, after=False):
        base = self.base/'attempt';base.mkdir(mode=0o700)
        before = {'boot_id': BOOT, 'kernel': 'fixture-r1', 'kernel_notes_SHA256': NOTES,
                  'boot_partition_sha256': 'a'*64, 'files_sha256': {'fixture': 'b'*64},
                  'module_tree_digest': 'c'*64, 'modules_FSType': 'ext4', 'trial': False,
                  'taint': 0, 'systemd': 'running', 'Sway': 'fixture', 'gesture': 'fixture'}
        (base/'before.json').write_text(json.dumps(before))
        if after:
            (base/'attempt.claim').write_text('fixture claim')
            (base/'native-return.json').write_text(json.dumps(before | {'boot_id': RETURN}))
        def check_operator():
            if not owner:raise RuntimeError('private-operator-fixture')
        context = types.SimpleNamespace(workspace=base, expected='fixture-plan-hash',
            plan={'credential_client': str(base/'dummy-client.py'), 'device_record': str(base/'dummy-record.json'),
                  'port_lock_path': str(base/'fx0-ram-port-1-7.lock')},
            verify_inputs=lambda: None, check_operator=check_operator)
        return context

    def invoke(self, context, *, phase='before', packet=None, check=False, client_error=False):
        calls = []
        def run(command, **kwargs):
            calls.append('capture')
            self.assertEqual(kwargs, {'root': True, 'timeout': 20})
            self.assertIn('--expected-boot-id', command)
            if client_error:raise RuntimeError('private-client-fixture-sentinel')
            return json.dumps(packet).encode()
        def load(path, name):
            self.assertEqual(name, 'private_console_client')
            calls.append('client')
            return types.SimpleNamespace(run=run)
        lock_hash = console.native.sha(ROOT/'manifests/native-console-capture.json')
        arguments = ['--plan', str(context.workspace/'plan.json'), '--plan-sha256', context.expected,
                     '--source-lock-sha256', lock_hash, '--phase', phase]
        if check:arguments.append('--check-inputs')
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(console.native, 'Context', return_value=context), \
             mock.patch.object(console.native, 'source_module', side_effect=load), \
             contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = console.main(arguments)
        return code, out.getvalue(), err.getvalue(), calls

    def test_host_static_check_needs_no_operator_client_or_output_directory(self):
        context = self.host_fixture(owner=False)
        code, out, err, calls = self.invoke(context, check=True)
        self.assertEqual(code, 0);self.assertEqual(calls, [])
        self.assertFalse((context.workspace/'console-before').exists())
        self.assertFalse(json.loads(out)['device_actions'])

    def test_missing_operator_or_return_gate_prevents_client_load(self):
        context = self.host_fixture(owner=False)
        for phase in ['before', 'after']:
            with self.subTest(phase=phase):
                code, out, err, calls = self.invoke(context, phase=phase)
                self.assertEqual(code, 1);self.assertEqual(calls, [])
                self.assertNotIn('private-operator-fixture', out + err)

    def test_raw_capture_saved_privately_without_stdout_leak_and_no_reuse(self):
        self.write(probe.PATHS[0], b'password=private-capture-fixture\n')
        context = self.host_fixture()
        code, out, err, calls = self.invoke(context, packet=self.packet())
        self.assertEqual(code, 0);self.assertEqual(calls, ['client', 'capture'])
        self.assertNotIn('private-capture-fixture', out + err)
        path = context.workspace/'console-before/capture.private.json'
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(path.parent.stat().st_mode & 0o777, 0o700)
        again = self.invoke(context, packet=self.packet())
        self.assertEqual(again[0], 1);self.assertEqual(again[3], [])

    def test_after_capture_pairs_with_before_without_new_operator_window(self):
        self.write(probe.PATHS[0], b'[1.0] prior console\n')
        context = self.host_fixture(owner=False, after=True)
        before = context.workspace/'console-before';before.mkdir(mode=0o700)
        console.save_private(before, 'capture.private.json', self.packet())
        self.write('proc/sys/kernel/random/boot_id', RETURN.encode())
        self.write(probe.PATHS[0], b'[6.0] fx0-handoff-02: kms-init-enter\n')
        code, out, err, calls = self.invoke(context, phase='after', packet=self.packet(RETURN))
        self.assertEqual(code, 0)
        result = json.loads((context.workspace/'console-after/comparison.json').read_text())
        self.assertEqual(result['records'][probe.PATHS[0]]['change'], 'changed')
        self.assertFalse(result['candidate_boot_attribution_proven'])

    def test_client_error_is_redacted_and_creates_no_capture(self):
        context = self.host_fixture()
        code, out, err, calls = self.invoke(context, client_error=True)
        self.assertEqual(code, 1)
        self.assertNotIn('private-client-fixture-sentinel', out + err)
        self.assertFalse((context.workspace/'console-before').exists())

    def test_capture_source_roles_exclude_private_client_and_device_record(self):
        context = self.host_fixture()
        context.plan['credential_client'] = str(HERE/'native_console_probe.py')
        digest = console.native.sha(ROOT/'manifests/native-console-capture.json')
        with self.assertRaises(ValueError):console.source_lock(context, digest)

    def test_optimized_remote_and_host_entries_fail_before_private_client(self):
        for name, args in [('native_console_probe.py', ['--expected-boot-id', BOOT, '--expected-notes-sha256', NOTES]),
                           ('native_console.py', ['--plan', str(self.base/'missing'), '--plan-sha256', '0'*64,
                            '--source-lock-sha256', '0'*64, '--phase', 'before'])]:
            with self.subTest(name=name):
                result = subprocess.run([sys.executable, '-B', '-O', str(HERE/name), *args],
                                        capture_output=True, timeout=5)
                self.assertEqual(result.returncode, 1)
                self.assertNotIn(b'Traceback', result.stderr)


if __name__ == '__main__':
    unittest.main()
