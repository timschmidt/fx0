# SPDX-License-Identifier: MIT
"""Public plan/operator gates with a synthetic image profile and dummy client."""
import contextlib
import datetime
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'diagnostics/modem-control/passive_owned_adapter.py'
spec = importlib.util.spec_from_file_location('public_passive_adapter', SOURCE)
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)


class PlanTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.image = self.base/'fixture.img'
        self.image.write_bytes(b'offline profile fixture')
        self.profile_hash = hashlib.sha256(self.image.read_bytes()).hexdigest()
        for name, value in [('IMAGE_SHA256', self.profile_hash), ('IMAGE_BYTES', self.image.stat().st_size)]:
            patch = mock.patch.object(adapter, name, value)
            patch.start(); self.addCleanup(patch.stop)
        self.client = self.base/'dummy-client.py'
        self.client.write_text('raise RuntimeError("private-fixture-sentinel")\n')
        self.record = self.base/'dummy-device.json'
        self.record.write_text('{"serial":"fixture-only"}')
        self.index = self.base/'index'; self.index.write_bytes(b'fixture index')
        before = {'boot_id': '00000000-0000-4000-8000-000000000001', 'trial': False,
                  'kernel': '6.18.63-fx0-vibrator-alpine',
                  'kernel_notes_SHA256': '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'}
        (self.base/'before.json').write_text(json.dumps(before))
        (self.base/'preparation.json').write_text(json.dumps({
            'image_path': str(self.image), 'image_SHA256': self.profile_hash,
            'image_bytes': self.image.stat().st_size}))
        audit = self.base/'image-audit.json'
        audit.write_text(json.dumps({'image_SHA256': self.profile_hash,
            'initial_shell_alias_and_all_script_interpreters_present': True,
            'GNU_cpio_independent_extraction_matches_every_entry': True}))
        self.plan = {'format': 1, 'repository_root': str(ROOT), 'workspace': str(self.base),
                     'image_path': str(self.image), 'image_SHA256': self.profile_hash,
                     'image_bytes': self.image.stat().st_size, 'image_audit_path': str(audit),
                     'image_audit_SHA256': adapter.sha(audit), 'baseline_boot_id': before['boot_id'],
                     'workspace_inputs_SHA256': {n: adapter.sha(self.base/n) for n in ['before.json', 'preparation.json']},
                     'source_files_SHA256': {n: adapter.sha(ROOT/n) for n in adapter.SOURCES},
                     'credential_client': str(self.client), 'device_record': str(self.record),
                     'usb_port': '1-7', 'host_index_path': str(self.index),
                     'host_index_SHA256': adapter.sha(self.index),
                     'port_lock_path': str(self.base/'fx0-ram-port-1-7.lock')}
        self.path = self.base/'plan.json'
        self.write_plan()

    def write_plan(self):
        self.path.write_text(json.dumps(self.plan)); self.path.chmod(0o600)
        self.digest = adapter.sha(self.path)

    def context(self): return adapter.Context(self.path, self.digest)

    def owner(self, **changes):
        value = {'answer': adapter.ANSWER, 'boot_id': self.plan['baseline_boot_id'],
                 'image_SHA256': self.profile_hash,
                 'recorded_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        value.update(changes)
        (self.base/'owner-availability.json').write_text(json.dumps(value))

    def call(self, *extra):
        stdout = io.StringIO(); stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = adapter.main(['--plan', str(self.path), '--plan-sha256', self.digest, *extra])
        return status, stdout.getvalue(), stderr.getvalue()

    def test_static_check_needs_no_owner_or_client_import(self):
        with mock.patch.object(adapter, 'source_module', side_effect=AssertionError('client import forbidden')):
            status, output, error = self.call('--check-inputs')
        self.assertEqual(status, 0); self.assertTrue(json.loads(output)['inputs_verified'])
        self.assertFalse((self.base/'attempt.claim').exists()); self.assertEqual(error, '')

    def test_missing_owner_rejects_before_client_load_or_claim(self):
        with mock.patch.object(adapter, 'source_module', side_effect=AssertionError('client import forbidden')):
            status, output, error = self.call()
        self.assertEqual(status, 1); self.assertEqual(json.loads(error)['phase'], 'operator-receipt')
        self.assertFalse((self.base/'attempt.claim').exists())

    def test_stale_wrong_or_future_owner_is_not_authorization(self):
        for change in [
            {'answer': 'Available for another run'}, {'boot_id': 'wrong'}, {'image_SHA256': '0'*64},
            {'recorded_UTC': (datetime.datetime.now(datetime.timezone.utc)-datetime.timedelta(seconds=700)).isoformat()},
            {'recorded_UTC': (datetime.datetime.now(datetime.timezone.utc)+datetime.timedelta(seconds=60)).isoformat()},
        ]:
            with self.subTest(change=change):
                self.owner(**change)
                with self.assertRaises(adapter.PlanRejected): self.context().check_operator()

    def test_approved_current_owner_reaches_dummy_client_without_leaking_error(self):
        self.owner()
        status, output, error = self.call()
        self.assertEqual(status, 1); self.assertEqual(json.loads(error)['phase'], 'client-setup')
        self.assertNotIn('private-fixture-sentinel', output+error)
        self.assertNotIn('Traceback', error); self.assertFalse((self.base/'attempt.claim').exists())

    def test_plan_digest_permissions_and_unknown_roster_reject(self):
        with self.assertRaises(adapter.PlanRejected): adapter.Context(self.path, '0'*64)
        self.path.chmod(0o644)
        with self.assertRaises(adapter.PlanRejected): self.context()
        self.path.chmod(0o600)
        self.plan['source_files_SHA256']['unreviewed.py'] = '0'*64; self.write_plan()
        with self.assertRaises(adapter.PlanRejected): self.context()

    def test_changed_workspace_or_source_fails_closed(self):
        context = self.context()
        (self.base/'before.json').write_text('{}')
        with self.assertRaises(adapter.PlanRejected): context.verify_inputs()
        # Model a changed public source checksum without editing repository files.
        self.setUp_repair_before_for_source_control()
        context = self.context(); real = adapter.sha
        def checksum(path):
            return '0'*64 if Path(path) == ROOT/'scripts/boot_fx0_ram.py' else real(path)
        with mock.patch.object(adapter, 'sha', side_effect=checksum):
            with self.assertRaises(adapter.PlanRejected): context.verify_inputs()

    def setUp_repair_before_for_source_control(self):
        (self.base/'before.json').write_text(json.dumps({'boot_id': self.plan['baseline_boot_id'], 'trial': False,
            'kernel': '6.18.63-fx0-vibrator-alpine',
            'kernel_notes_SHA256': '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'}))
        self.plan['workspace_inputs_SHA256']['before.json'] = adapter.sha(self.base/'before.json'); self.write_plan()

    def test_credential_or_device_record_cannot_be_hashed_as_input(self):
        self.plan['credential_client'] = str(ROOT/'scripts/boot_fx0_ram.py'); self.write_plan()
        real = adapter.sha
        def checksum(path):
            if Path(path) == Path(self.plan['credential_client']): raise AssertionError('excluded body opened')
            return real(path)
        with mock.patch.object(adapter, 'sha', side_effect=checksum):
            with self.assertRaises(adapter.PlanRejected): self.context().verify_inputs()

    def test_optimized_CLI_rejects_before_private_import(self):
        result = subprocess.run([sys.executable, '-B', '-O', str(SOURCE), '--plan', str(self.path),
                                 '--plan-sha256', self.digest], capture_output=True, text=True, timeout=5)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stderr)['phase'], 'plan')
        self.assertNotIn('private-fixture-sentinel', result.stderr)


if __name__ == '__main__': unittest.main()
