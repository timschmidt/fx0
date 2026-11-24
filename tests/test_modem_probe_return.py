"""Check artifact acceptance using real mocked-worker output; no phone access."""
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import test_modem_probe as worker_tests

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'modem_probe_return', ROOT / 'diagnostics/modem-control/verify-probe-return.py')
VERIFY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFY)
NOTES = bytes.fromhex(
    '0600000001000000000100004c696e757800000000000000060000000400000001010000'
    '4c696e757800000000000000040000001400000003000000474e5500f6c78534b602f8ec'
    '80f85d37a866e6fd7963b6eb')
RAM_ID = '12345678-1234-1234-1234-123456789abc'
RETURN_ID = '23456789-1234-1234-1234-123456789abc'


class ModemProbeReturnTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # All module commands and sysfs paths are local test doubles.
        with tempfile.TemporaryDirectory() as directory:
            worker = worker_tests.ModemProbeTests()
            result = worker.run_worker(worker.fixture(directory))
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.worker_text = result.stdout

    def fixture(self):
        post = {
            'phase': 'postflight', 'boot_id': RETURN_ID,
            'kernel': '6.18.59-fx0-dmp', 'kernel_taint': 0,
            'raw_boot_sha256': VERIFY.BOOT, 'registers': dict(VERIFY.REGISTERS),
            'files_sha256': {str(i): 'synthetic unchanged digest' for i in range(10)},
            'CPU_policy': {'scaling_governor': 'schedutil'}, 'NFC': {'synthetic': True},
            'remoteprocs': {'adsp': 'running', 'wcnss': 'running'},
            'Sway_PID': 101, 'ModemManager_PID': 102, 'temperatures_mC': [40000, 41000],
            'systemd': 'running', 'pending_jobs': [], 'failed_units': [],
            'native_MSS_disabled_and_unloaded': True, 'ModemManager_objects': [],
            'packages': {'linux-postmarketos-qcom-msm8226': {'version': '6.18.59-r50'}},
            'UPower_samples': [{'PID': 103, 'display': {
                'IsPresent': False, 'State': 0, 'WarningLevel': 1, 'Percentage': 0.0},
                'OnBattery': False} for _ in range(3)]}
        for name in ['upower', 'upower-lang', 'upower-systemd']:
            post['packages'][name] = {'version': '99991.91.0-r5'}
        pre = copy.deepcopy(post)
        pre.update(phase='preflight', boot_id=VERIFY.NATIVE)
        rows = {
            'image-verification.json': {'image_sha256': VERIFY.IMAGE, 'kernel_notes_sha256': VERIFY.NOTES},
            'boot-request.json': {'image_sha256': VERIFY.IMAGE, 'state': 'acknowledged'},
            'transfer/result.json': {'state': 'verified', 'readback_sha256': VERIFY.IMAGE},
            'observation.json': {'RAM_detached_UTC': 'synthetic', 'serial': {'state': 'terminal', 'error': None},
                                 'USB': [{'RAM': True}]},
            'entry-preflight/native.json': pre,
            'postflight-verification/native.json': post,
            'postflight-verification/host-restoration.json': {
                'own_volatile_profile_removed': True,
                'host_routes_resolver_and_protected_index_unchanged': True},
            'native-health-controller.json': {'state': 'terminal', 'returncode': 0}}
        for name in ['transfer', 'observer', 'network']:
            rows[name + '-controller.json'] = {'returncode': 0}
        text = self.worker_text + (
            '__MODEM_PROBE_EXIT__0\n__FX0_CHECK_BEGIN__\n'
            'Linux version 6.18.59-fx0-dmp (synthetic observer)\n__KERNEL_NOTES__\n' +
            ' '.join(f'{value:02x}' for value in NOTES) + '\n__BOOT_HASH__\n' +
            VERIFY.BOOT + '  /dev/mmcblk0p15\n__FX0_CHECK_END__\n__FX0_KMSG_BEGIN__\n'
            '6,0,1500000,-;Fx0 RAM diagnostic init started\n'
            '6,99,181600000,-;Returning to lk2nd for diagnostic retrieval\n')
        return rows, text

    def run_fixture(self, rows, text):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for name, value in rows.items():
                path = base / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps(value))
            (base / 'serial-kmsg.txt').write_text(text)
            return VERIFY.verify(base)

    def test_valid_acknowledged_and_uncertain_boot_evidence(self):
        for state in ['acknowledged', 'uncertain or failed; never retry BOOT']:
            with self.subTest(state=state):
                rows, text = self.fixture()
                rows['boot-request.json']['state'] = state
                result = self.run_fixture(rows, text)
                self.assertEqual(result['RAM_boot_id'], RAM_ID)
                self.assertAlmostEqual(result['timer_seconds_after_init'], 180.1)
                self.assertEqual(result['BOOT_reply_acknowledged'], state == 'acknowledged')
                self.assertFalse(result['physical_display_touch_confirmed_by_this_validator'])
                self.assertIn('firmware start', result['scope'])

    def test_bad_observer_evidence_rejected(self):
        changes = [
            ('no pass', 'MODEM_PROBE_PASS\n', ''),
            ('duplicate pass', 'MODEM_PROBE_PASS\n', 'MODEM_PROBE_PASS\nMODEM_PROBE_PASS\n'),
            ('worker failure', '__MODEM_PROBE_EXIT__0', '__MODEM_PROBE_EXIT__9'),
            ('native boot reused', RAM_ID, VERIFY.NATIVE),
            ('operation failed', '__MODEM_OPERATION__1 load-qcom_pil_info 0', '__MODEM_OPERATION__1 load-qcom_pil_info 9'),
            ('operation order', '__MODEM_OPERATION__2 load-qcom_common', '__MODEM_OPERATION__2 load-mdt_loader'),
            ('not offline', '__MODEM_STATE__offline', '__MODEM_STATE__running'),
            ('notes changed', '06 00 00 00', '07 00 00 00'),
            ('notes abbreviated', '__KERNEL_NOTES__\n', '__KERNEL_NOTES__\n*\n'),
            ('boot hash changed', VERIFY.BOOT, '0' * 64),
            ('wrong kernel', 'Linux version 6.18.59-fx0-dmp ', 'Linux version wrong '),
            ('early return', '181600000', '180000000'),
            ('late return', '181600000', '191500000'),
            ('missing timer', 'Returning to lk2nd for diagnostic retrieval', 'other message'),
            ('IRQ storm', '0: 0 0 0 0 GIC q6v5 wdog', '0: 9 0 0 0 GIC q6v5 wdog'),
            ('missing IRQ', 'q6v5 ready', 'other ready')]
        for case, old, new in changes:
            with self.subTest(case=case):
                rows, text = self.fixture()
                self.assertIn(old, text)
                with self.assertRaises(AssertionError):
                    self.run_fixture(rows, text.replace(old, new))

    def test_bad_handoff_and_native_return_rejected(self):
        cases = [
            ('boot-request.json', ['state'], 'sending once'),
            ('transfer/result.json', ['state'], 'failed'),
            ('transfer/result.json', ['readback_sha256'], 'wrong'),
            ('observer-controller.json', ['returncode'], 1),
            ('network-controller.json', ['returncode'], 1),
            ('observation.json', ['serial', 'error'], 'read failed'),
            ('observation.json', ['RAM_detached_UTC'], None),
            ('entry-preflight/native.json', ['boot_id'], RETURN_ID),
            ('postflight-verification/host-restoration.json', ['own_volatile_profile_removed'], False),
            ('postflight-verification/host-restoration.json', ['host_routes_resolver_and_protected_index_unchanged'], False),
            ('native-health-controller.json', ['state'], 'running')]
        for key, value in [('boot_id', VERIFY.NATIVE), ('boot_id', RAM_ID), ('boot_id', 'malformed'),
                           ('phase', 'preparation'), ('kernel_taint', 1), ('systemd', 'starting'),
                           ('pending_jobs', ['job']), ('failed_units', ['failed']),
                           ('native_MSS_disabled_and_unloaded', False), ('ModemManager_objects', ['modem']),
                           ('Sway_PID', 0), ('temperatures_mC', [60000, 40000]),
                           ('CPU_policy', {}), ('NFC', {}), ('remoteprocs', {}), ('files_sha256', {})]:
            cases.append(('postflight-verification/native.json', [key], value))
        for address in VERIFY.REGISTERS:
            cases.append(('postflight-verification/native.json', ['registers', address], -1))
        for name in ['upower', 'upower-lang', 'upower-systemd']:
            cases.append(('postflight-verification/native.json', ['packages', name, 'version'], 'r4'))
        for key, value in [('IsPresent', True), ('State', 2), ('WarningLevel', 2), ('Percentage', float('nan'))]:
            cases.append(('postflight-verification/native.json', ['UPower_samples', 0, 'display', key], value))
        cases.append(('postflight-verification/native.json', ['UPower_samples', 1, 'PID'], 104))
        for name, keys, value in cases:
            with self.subTest(name=name, keys=keys):
                rows, text = self.fixture()
                target = rows[name]
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(AssertionError):
                    self.run_fixture(rows, text)


if __name__ == '__main__':
    unittest.main()
