"""Qualification must reject plausible-looking records without causal evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

path = Path(__file__).resolve().parents[1] / 'diagnostics/imu-dmp-native/run_wake_cycles.py'
spec = importlib.util.spec_from_file_location('wake_verifier', path)
verifier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verifier)


class WakeEvidence(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fx0-wake-evidence-')
        self.root = Path(self.temp.name)
        self.m = {'boot_id': 'boot', 'armed_after_resume': '0', 'disabled_after': '0',
                  'events': [{'code': '0x5021e1300000000', 'timestamp_ns': 1}],
                  'rtc_alarm_after': '200', 'rtc_epoch_after': 150,
                  'registers_before': {'0x23': 0, '0x38': 2, '0x6a': 128, '0x72': 0, '0x73': 0}}
        self.save()
        (self.root / 'power-irq.trace').write_text('1.000000: suspend_resume: machine_suspend[1] begin\n6.000000: suspend_resume: machine_suspend[1] end\n')
        (self.root / 'interrupts-before.txt').write_text('82: 7 0 0 0 msmgpio 69 Edge inv_mpu\n33: 3 0 0 0 pmic rtc_alarm\n')
        (self.root / 'interrupts-after.txt').write_text('82: 8 0 0 0 msmgpio 69 Edge inv_mpu\n33: 3 0 0 0 pmic rtc_alarm\n')
        (self.root / 'kernel.log').write_text('DMP resume status 0x4, event 1\n')
        (self.root / 'quaternion-after-resume.csv').write_text('timestamp_ns,w,x,y,z\n2,1,0,0,0\n3,1,0,0,0\n')

    def tearDown(self):
        self.temp.cleanup()

    def save(self):
        (self.root / 'manifest.json').write_text(json.dumps(self.m))

    def test_complete_causal_record(self):
        self.assertEqual(verifier.verify_cycle(self.root, 'boot')['sleep_seconds'], 5)

    def test_rtc_wrong_event_or_mixed_producer_is_rejected(self):
        for key, value in [('rtc_alarm_after', ''), ('boot_id', 'reboot'), ('events', []),
                           ('registers_before', {'0x6a': 192})]:
            original = self.m[key]
            self.m[key] = value
            self.save()
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                verifier.verify_cycle(self.root, 'boot')
            self.m[key] = original
        self.save()

    def test_irq_and_suspend_proof_cannot_be_replaced_by_event_alone(self):
        (self.root / 'interrupts-after.txt').write_text('82: 8 0 0 0 msmgpio 69 Edge inv_mpu\n33: 4 0 0 0 pmic rtc_alarm\n')
        with self.assertRaises(RuntimeError):
            verifier.verify_cycle(self.root, 'boot')
        (self.root / 'interrupts-after.txt').write_text((self.root / 'interrupts-before.txt').read_text())
        with self.assertRaises(RuntimeError):
            verifier.verify_cycle(self.root, 'boot')
        (self.root / 'interrupts-after.txt').write_text('82: 8 0 0 0 msmgpio 69 Edge inv_mpu\n33: 3 0 0 0 pmic rtc_alarm\n')
        (self.root / 'power-irq.trace').write_text('no actual suspend\n')
        with self.assertRaises(RuntimeError):
            verifier.verify_cycle(self.root, 'boot')

    def test_retained_status_and_recovered_scan_required(self):
        (self.root / 'kernel.log').write_text('awake event only\n')
        with self.assertRaises(RuntimeError):
            verifier.verify_cycle(self.root, 'boot')
        (self.root / 'kernel.log').write_text('DMP resume status 0x4, event 1\n')
        (self.root / 'quaternion-after-resume.csv').write_text('timestamp_ns,w,x,y,z\n2,nan,0,0,0\n')
        with self.assertRaises(RuntimeError):
            verifier.verify_cycle(self.root, 'boot')


if __name__ == '__main__':
    unittest.main()
