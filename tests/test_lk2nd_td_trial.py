"""Regression checks for the matched Fastboot trial's command and recovery boundaries."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'lk2nd_td_trial', ROOT / 'diagnostics/ram-transfer/run-lk2nd-td-trial.py')
trial = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = trial
SPEC.loader.exec_module(trial)


class TrialChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.out = Path(self.temp.name)
        self.port = self.out / '1-14'
        self.image = self.out / 'loader.img'
        self.payload = self.out / 'payload.img'
        self.payload.write_bytes(b'shared fixture')
        self.stock = trial.UsbDevice(1, 9, '18d1', 'd00d', '480', 'fixture')
        self.loader = trial.UsbDevice(1, 10, '18d1', 'd00d', '480', 'fixture')
        self.native = trial.UsbDevice(1, 11, '18d1', 'd001', '480', 'fixture')
        self.run = trial.Trial('control', self.port, self.out, self.image, self.payload)

    def test_stock_probe_reads_exact_product_and_protocol(self):
        outputs = [subprocess.CompletedProcess([], 0, '', 'product: MADAI\n'),
                   subprocess.CompletedProcess([], 0, '', '(bootloader) version: 0.5\n')]
        with patch.object(trial, 'unique_device') as unique, patch.object(
                trial.subprocess, 'run', side_effect=outputs) as process:
            trial.stock_identity(self.port, self.stock)
        self.assertEqual(unique.call_count, 3)
        self.assertEqual([row.args[0] for row in process.call_args_list], [
            ['fastboot', '-s', 'fixture', 'getvar', 'product'],
            ['fastboot', '-s', 'fixture', 'getvar', 'version'],
        ])

    def test_installed_lk2nd_is_refused_before_launch(self):
        with patch.object(trial, 'usb_at', return_value=self.loader), patch.object(
                trial, 'stock_query', return_value='lk2nd-msm8226'), patch.object(self.run, 'run') as process:
            with self.assertRaisesRegex(ValueError, 'Expected stock MADAI'):
                self.run.execute()
            process.assert_not_called()

    def test_duplicate_serial_is_refused(self):
        self.port.mkdir()
        other = self.out / '2-1'
        other.mkdir()
        for path in [self.port, other]:
            (path / 'serial').write_text('fixture')
        with patch.object(trial, 'PORTS', self.out), patch.object(trial, 'usb_at', return_value=self.stock):
            with self.assertRaisesRegex(ValueError, 'does not uniquely select'):
                trial.unique_device(self.port, self.stock)

    def test_installed_lk2nd_version_is_refused_as_pair(self):
        with patch.object(trial, 'unique_device'), patch.object(
                trial.boot, 'query', return_value={'product': [trial.PAIR_PRODUCT],
                                                    'lk2nd_version': ['OKAYfx0-pon-reboot']}):
            with self.assertRaisesRegex(ValueError, 'Expected the temporary'):
                trial.pair_identity(self.port, self.loader)

    def test_only_fresh_loader_generation_enters_transfer(self):
        def wait(port, predicate):
            self.assertEqual(port, self.port)
            self.assertFalse(predicate(self.stock))
            self.assertTrue(predicate(self.loader))
            return self.loader

        with patch.object(trial, 'usb_at', return_value=self.stock), patch.object(trial, 'stock_identity'), \
                patch.object(trial, 'pair_identity') as identify, patch.object(trial, 'wait_port', side_effect=wait), \
                patch.object(self.run, 'run', return_value=0) as process, patch.object(
                    self.run, 'stage', return_value='verified') as stage, patch.object(self.run, 'return_native') as recover:
            self.run.execute()
        process.assert_called_once_with('stock-boot', ['fastboot', '-s', 'fixture', 'boot', str(self.image)])
        identify.assert_called_once_with(self.port, self.loader)
        stage.assert_called_once_with(self.loader)
        recover.assert_called_once_with(self.loader, 'verified')

    def test_ambiguous_launch_with_verified_loader_returns_without_transfer(self):
        with patch.object(trial, 'usb_at', side_effect=[self.stock, self.loader]), \
                patch.object(trial, 'stock_identity'), patch.object(trial, 'pair_identity'), \
                patch.object(trial, 'wait_port', return_value=self.loader), \
                patch.object(self.run, 'run', return_value=1), patch.object(self.run, 'stage') as stage, \
                patch.object(self.run, 'return_native') as recover:
            with self.assertRaisesRegex(ValueError, 'uncertain launch'):
                self.run.execute()
        stage.assert_not_called()
        recover.assert_called_once_with(self.loader, 'uncertain launch acknowledgement')

    def test_rejected_stock_launch_reboots_stock_once(self):
        with patch.object(trial, 'usb_at', return_value=self.stock), patch.object(trial, 'stock_identity'), \
                patch.object(trial, 'wait_port', side_effect=[RuntimeError('no loader'), self.native]), patch.object(
                    self.run, 'run', side_effect=[1, 0]) as process, patch.object(self.run, 'stage') as stage:
            with self.assertRaisesRegex(RuntimeError, 'Temporary loader did not appear'):
                self.run.execute()
        stage.assert_not_called()
        self.assertEqual(process.call_args_list, [
            call('stock-boot', ['fastboot', '-s', 'fixture', 'boot', str(self.image)]),
            call('reboot', ['fastboot', '-s', 'fixture', 'reboot']),
        ])

    def write_transfer(self, result, readback=None):
        directory = self.out / 'transfer'
        directory.mkdir()
        row = {'sha256': trial.PAYLOAD_SHA256, 'chunk_bytes': 16384, 'pace_ms': 5} | result
        (directory / 'result.json').write_text(json.dumps(row))
        if readback is not None:
            (directory / 'readback.bin').write_bytes(readback)

    def test_data_only_transfer_verifies_exact_payload(self):
        self.write_transfer({'state': 'verified', 'readback_sha256': trial.PAYLOAD_SHA256},
                            self.payload.read_bytes())
        with patch.object(trial, 'pair_identity'), patch.object(self.run, 'run', return_value=0) as process:
            self.assertEqual(self.run.stage(self.loader), 'verified')
        self.assertEqual(process.call_args.args[0], 'transfer')
        self.assertEqual(process.call_args.args[1][-2:], ['--pace-ms', '5'])
        self.assertNotIn('boot', process.call_args.args[1])
        self.assertFalse(self.run.report['linux_BOOT_sent'])

    def test_readback_mismatch_is_refused(self):
        self.write_transfer({'state': 'verified', 'readback_sha256': trial.PAYLOAD_SHA256}, b'different')
        with patch.object(trial, 'pair_identity'), patch.object(self.run, 'run', return_value=0):
            with self.assertRaisesRegex(ValueError, 'exact transfer readback'):
                self.run.stage(self.loader)

    def test_timeout_preserves_unknown_count_and_phase(self):
        failed = {'event': 'failed', 'errno': 110, 'actual_bytes': None, 'offset': 524288}
        self.write_transfer({'state': 'failed', 'phase': 'download', 'bytes': 524288, 'last_IO': failed})
        with patch.object(trial, 'pair_identity'), patch.object(self.run, 'run', return_value=1):
            self.assertEqual(self.run.stage(self.loader), 'timeout')
        self.assertEqual(self.run.report['first_unconfirmed_request'], failed)
        self.assertEqual(self.run.report['download_confirmed_bytes'], 524288)
        self.assertEqual(self.run.report['readback_confirmed_bytes'], 0)

    def test_timeout_before_first_progress_is_eligible_for_terminal_recovery(self):
        failed = {'event': 'failed', 'errno': 110, 'actual_bytes': None, 'phase': 'download-command'}
        self.write_transfer({'state': 'failed', 'bytes': 0, 'last_IO': failed})
        with patch.object(trial, 'pair_identity'), patch.object(self.run, 'run', return_value=1):
            self.assertEqual(self.run.stage(self.loader), 'timeout')
        self.assertEqual(self.run.report['download_confirmed_bytes'], 0)
        self.assertEqual(self.run.report['readback_confirmed_bytes'], 0)

    def test_recovery_never_touches_a_live_transfer(self):
        self.run.report['processes']['transfer'] = {'PID': os.getpid()}
        with patch.object(trial, 'unique_device') as identify, patch.object(trial, 'usb_reset') as reset, \
                patch.object(self.run, 'run') as process:
            with self.assertRaisesRegex(ValueError, 'not confirmed terminal'):
                self.run.return_native(self.loader, 'timeout')
        identify.assert_not_called()
        reset.assert_not_called()
        process.assert_not_called()

    def test_receipt_returncode_does_not_override_live_pid(self):
        self.run.report['processes']['transfer'] = {'PID': os.getpid(), 'returncode': 1}
        with patch.object(trial, 'usb_reset') as reset:
            with self.assertRaisesRegex(ValueError, 'not confirmed terminal'):
                self.run.return_native(self.loader, 'timeout')
        reset.assert_not_called()

    def test_timeout_recovery_checks_identity_and_reboots_once(self):
        events = []
        self.run.report['processes']['transfer'] = {'PID': 2**31-1, 'returncode': 1}
        with patch.object(trial, 'unique_device'), patch.object(
                trial, 'usb_reset', side_effect=lambda *_: events.append('reset')), patch.object(
                trial, 'pair_identity', side_effect=lambda *_: events.append('identity')), patch.object(
                trial, 'wait_port', side_effect=[self.loader, self.native]), patch.object(
                self.run, 'run', side_effect=lambda *args: events.append(args) or 0):
            self.run.return_native(self.loader, 'timeout')
        self.assertEqual(events, ['reset', 'identity', ('reboot', ['fastboot', '-s', 'fixture', 'reboot'])])
        self.assertEqual(self.run.report['native_USB'], self.native.public())

    def test_success_returns_without_transport_reset(self):
        with patch.object(trial, 'unique_device'), patch.object(trial, 'pair_identity'), patch.object(
                trial, 'usb_reset') as reset, patch.object(trial, 'wait_port', return_value=self.native), patch.object(
                self.run, 'run', return_value=0) as process:
            self.run.return_native(self.loader, 'verified')
        reset.assert_not_called()
        process.assert_called_once_with('reboot', ['fastboot', '-s', 'fixture', 'reboot'])

    def test_real_process_receipt_records_terminal_child(self):
        self.assertEqual(self.run.run('fixture', [sys.executable, '-c', 'print("terminal fixture")']), 0)
        record = json.loads((self.out / 'trial.json').read_text())['processes']['fixture']
        self.assertTrue(trial.terminal(record))
        self.assertEqual((self.out / 'fixture.log').read_text(), 'terminal fixture\n')


class PairChecks(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        out = Path(temp.name)
        self.payload = b'fixture payload'
        self.sha = hashlib.sha256(self.payload).hexdigest()
        self.directories = [out / arm for arm in trial.FASTBOOT_PAIR]
        self.receipts = []
        for index, (directory, (arm, (loader_sha, limit))) in enumerate(
                zip(self.directories, trial.FASTBOOT_PAIR.items(), strict=True)):
            transfer = directory / 'transfer'
            transfer.mkdir(parents=True)
            failed = {'event': 'failed', 'errno': 110, 'actual_bytes': None, 'offset': 4}
            common = {'sha256': self.sha, 'chunk_bytes': 16384, 'pace_ms': 5}
            if index:
                result = common | {'state': 'verified', 'phase': 'readback', 'bytes': len(self.payload)}
                (transfer / 'readback.bin').write_bytes(self.payload)
            else:
                result = common | {'state': 'failed', 'phase': 'download', 'bytes': 4, 'last_IO': failed}
            (transfer / 'result.json').write_text(json.dumps(result))
            receipt = {
                'arm': arm, 'state': 'terminal', 'linux_BOOT_sent': False, 'USB_port': '1-14',
                'loader_sha256': loader_sha, 'loader_request_bytes': limit,
                'payload_sha256': self.sha, 'payload_bytes': len(self.payload),
                'host_request_bytes': 16384, 'pace_ms': 5,
                'started_UTC': f'2026-11-11T00:0{2 * index}:00+00:00',
                'finished_UTC': f'2026-11-11T00:0{2 * index + 1}:00+00:00',
                'stock': {'bus': 1, 'number': 10 + index * 3, 'protocol': '0.5', 'product_name': 'MADAI'},
                'temporary_lk2nd': {'bus': 1, 'number': 11 + index * 3,
                                    'version': 'fx0-usb-td-pair', 'speed': '480'},
                'native_USB': {'bus': 1, 'number': 12 + index * 3, 'vendor': '18d1', 'product': 'd001'},
                'processes': {name: {'returncode': 0} for name in ['stock-boot', 'reboot', 'transfer']},
                'transfer_outcome': 'verified' if index else 'timeout', 'first_unconfirmed_request': failed,
            }
            if not index:
                receipt['processes']['transfer']['returncode'] = 1
            self.receipts.append(receipt)

    def compare(self):
        for directory, receipt in zip(self.directories, self.receipts, strict=True):
            (directory / 'trial.json').write_text(json.dumps(receipt))
        with patch.object(trial, 'PAYLOAD_SHA256', self.sha), patch.object(trial, 'PAYLOAD_BYTES', len(self.payload)):
            return trial.compare_trials(self.directories)

    def test_compare_preserves_distinct_timeout_and_readback_outcomes(self):
        report = self.compare()
        self.assertEqual(report['speed_Mbps'], '480')
        self.assertEqual(report['outcomes']['control']['download_confirmed_bytes'], 4)
        self.assertEqual(report['outcomes']['single_td'], {'outcome': 'exact readback', 'bytes': len(self.payload)})

    def test_compare_rejects_unmatched_speed(self):
        self.receipts[1]['temporary_lk2nd']['speed'] = '12'
        with self.assertRaisesRegex(ValueError, 'speed differs'):
            self.compare()

    def test_compare_rejects_overlapping_sessions(self):
        self.receipts[0]['finished_UTC'] = '2026-11-11T00:02:30+00:00'
        with self.assertRaisesRegex(ValueError, 'sessions overlapped'):
            self.compare()

    def test_compare_rejects_changed_readback(self):
        (self.directories[1] / 'transfer/readback.bin').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Readback does not match'):
            self.compare()


if __name__ == '__main__':
    unittest.main()
