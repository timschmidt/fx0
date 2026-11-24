"""Regression checks for attributing SDHC2 and card-detect IRQ counts."""
import importlib.util
from pathlib import Path
import unittest

SOURCE = Path(__file__).resolve().parents[1]/'diagnostics/microsd/observe-sdhc2.py'
SPEC = importlib.util.spec_from_file_location('observe_sdhc2', SOURCE)
OBS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(OBS)

TABLE = '''                 CPU0       CPU1       CPU2       CPU3
 57:            200          0          0          0 GIC-0 156 Level mmc0
 81:            412          0          0          0 GIC-0 157 Level mmc1
 82:              1          0          0          0 GIC-0 253 Level f98a4900.mmc
 99:              0          0          0          0 msmgpio 37 Edge f98a4900.mmc cd
IPI0:             1          2          3          4 Rescheduling interrupts
'''


class ObserverIRQTests(unittest.TestCase):
    def test_roles_are_independent_of_linux_irq_number_and_cpu_affinity(self):
        old = OBS.interrupt_rows(TABLE)
        new_table = TABLE.replace('412          0', '412         18')
        new_table = new_table.replace('0          0          0          0 msmgpio',
                                      '0          0          0          2 msmgpio')
        new = OBS.interrupt_rows(new_table)
        self.assertEqual(old['controller']['irq'], 81)
        self.assertEqual(old['card_detect']['irq'], 99)
        self.assertEqual(OBS.counter_delta(old, new), {'controller': 18, 'power': 0, 'card_detect': 2})

    def test_missing_or_wrong_controller_is_not_reported_as_zero(self):
        for change in [TABLE.replace('157 Level mmc1', '156 Level mmc1'),
                       TABLE.replace('157 Level mmc1', '157 Level mmc0')]:
            with self.subTest(change=change), self.assertRaisesRegex(RuntimeError, 'Missing expected'):
                OBS.interrupt_rows(change)

    def test_duplicate_card_detect_is_rejected(self):
        card_row = next(line for line in TABLE.splitlines() if 'msmgpio' in line)
        with self.assertRaisesRegex(RuntimeError, 'Ambiguous or invalid card_detect'):
            OBS.interrupt_rows(TABLE + card_row.replace('99:', '100:') + '\n')

    def test_identity_changes_and_counter_resets_cannot_form_deltas(self):
        old = OBS.interrupt_rows(TABLE)
        variants = [(TABLE.replace('81:', '84:'), 'IRQ identity changed'),
                    (TABLE.replace('412          0', '411         20'), 'counters decreased'),
                    (TABLE.replace('CPU3', 'CPU4'), 'CPU columns changed')]
        for text, error in variants:
            with self.subTest(error=error), self.assertRaisesRegex(RuntimeError, error):
                OBS.counter_delta(old, OBS.interrupt_rows(text))

    def test_disk_reinsert_does_not_form_a_continuous_sample(self):
        old = {'diskseq': 7, 'device_number': '179:32'}
        new = {'diskseq': 8, 'device_number': '179:32'}
        with self.assertRaisesRegex(RuntimeError, 'SD block device changed'):
            OBS.compare(old, new)


if __name__ == '__main__':
    unittest.main()
