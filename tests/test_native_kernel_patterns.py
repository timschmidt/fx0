# SPDX-License-Identifier: MIT
"""Regression coverage for unchanged-r2 kernel-log acceptance tokens."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    'native_kernel_pattern_probe',
    ROOT / 'diagnostics/kernel-maintenance/native_trial_health_probe.py')
PROBE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROBE)


class NativeKernelPatterns(unittest.TestCase):
    def test_normal_boot_labels_are_not_errors(self):
        text = '\n'.join([
            '[0.000000] debug: normal boot announcement',
            '[0.088922] ramoops: using a reserved region',
            '[0.147605] iommu: Default domain type: Translated',
            '[1.000000] loops: calibration complete',
        ])
        self.assertFalse(any(PROBE.kernel_pattern_counts(text).values()))

    def test_each_real_error_category_is_retained(self):
        for category, line in [
            ('BUG:', 'BUG: unable to handle kernel request'),
            ('Oops:', 'Internal error: Oops: 5 [#1] SMP ARM'),
            ('Kernel panic', 'Kernel panic - not syncing: test'),
            ('CFI failure', 'CFI failure at a kernel callsite'),
            ('soft lockup', 'watchdog: soft lockup detected'),
            ('rcu.*stall', 'rcu: detected stalls on CPUs/tasks'),
            ('mdp5.*underrun', 'mdp5: underrun detected'),
            ('IOMMU.*fault', 'qcom_iommu device: Unhandled context fault: test'),
        ]:
            with self.subTest(category=category):
                counts = PROBE.kernel_pattern_counts('[12.5] ' + line)
                self.assertEqual(counts[category], 1)
                self.assertEqual(sum(counts.values()), 1)

    def test_case_insensitivity_and_repeated_events(self):
        counts = PROBE.kernel_pattern_counts('bug: first\nBUG: second\noOPS: third')
        self.assertEqual(counts['BUG:'], 2)
        self.assertEqual(counts['Oops:'], 1)

    def test_errors_are_not_hidden_by_normal_labels_on_same_line(self):
        text = 'debug: BUG: test\nramoops: Oops: test\niommu: Default domain type: test; fault detected'
        counts = PROBE.kernel_pattern_counts(text)
        self.assertEqual(counts['BUG:'], 1)
        self.assertEqual(counts['Oops:'], 1)
        self.assertEqual(counts['IOMMU.*fault'], 1)

    def test_fault_substrings_and_stack_symbol_are_not_fault_messages(self):
        text = 'iommu: default configuration\nqcom_iommu_fault+0x0/0x20'
        self.assertEqual(PROBE.kernel_pattern_counts(text)['IOMMU.*fault'], 0)

    def test_iommu_fault_does_not_span_separate_lines(self):
        self.assertEqual(PROBE.kernel_pattern_counts('iommu: normal\nfault elsewhere')['IOMMU.*fault'], 0)


if __name__ == '__main__':
    unittest.main()
