"""Validate MSM8926 and legacy QCS404 CPR provider shapes."""
import copy
import os
from pathlib import Path
import unittest

try:
    import dtschema
except ImportError:
    dtschema = None

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path(os.environ.get('FX0_CPU_BUILD', ROOT/'local/cpu-cpr-build/llvm'))
CACHE = Path(os.environ.get('FX0_DT_SCHEMA_CACHE', BUILD/'Documentation/devicetree/bindings/processed-schema.json'))


@unittest.skipUnless(dtschema and CACHE.exists(), 'Processed schema and dtschema required')
class CprBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = dtschema.DTValidator([str(CACHE)])
        cls.msm = {'$nodename': ['power-controller@f9018000'],
                   'compatible': ['qcom,msm8926-cpr', 'qcom,cpr'],
                   'reg': [[0xf9018000, 0x1000]], 'interrupts': [[0, 13, 1]],
                   'clocks': [[1], [9]], 'clock-names': ['ref', 'cpu'],
                   'vdd-apc-supply': [[2]], 'vdd-mx-supply': [[3]],
                   'qcom,apcs-syscon': [[9]],
                   '#power-domain-cells': 0, 'operating-points-v2': [[4]],
                   'nvmem-cells': [[5], [6], [7]],
                   'nvmem-cell-names': ['cpu_calibration', 'cpr_primary', 'cpr_redundant']}
        cls.legacy = copy.deepcopy(cls.msm)
        cls.legacy['compatible'] = ['qcom,qcs404-cpr', 'qcom,cpr']
        del cls.legacy['vdd-mx-supply']
        del cls.legacy['qcom,apcs-syscon']
        cls.legacy['clocks'] = [[1]]
        cls.legacy['clock-names'] = ['ref']
        cls.legacy['acc-syscon'] = [[8]]
        cls.legacy['nvmem-cells'] = [[i] for i in range(10, 23)]
        cls.legacy['nvmem-cell-names'] = [
            'cpr_quotient_offset1', 'cpr_quotient_offset2', 'cpr_quotient_offset3',
            'cpr_init_voltage1', 'cpr_init_voltage2', 'cpr_init_voltage3',
            'cpr_quotient1', 'cpr_quotient2', 'cpr_quotient3',
            'cpr_ring_osc1', 'cpr_ring_osc2', 'cpr_ring_osc3', 'cpr_fuse_revision']

    def errors(self, node):
        return list(self.validator.iter_errors(node, filter=['power/avs/qcom,cpr.yaml']))

    def test_msm8926_valid(self):
        self.assertFalse(self.errors(self.msm))

    def test_exact_provider_owned_cpu_clock(self):
        for key in ['clocks', 'clock-names']:
            for count in [1,3]:
                node = copy.deepcopy(self.msm)
                node[key] = (node[key]*2)[:count]
                self.assertTrue(self.errors(node),(key,count))
        node = copy.deepcopy(self.msm)
        node['clock-names'].reverse()
        self.assertTrue(self.errors(node))
        node = copy.deepcopy(self.legacy)
        node['clocks'] = self.msm['clocks']
        node['clock-names'] = self.msm['clock-names']
        self.assertTrue(self.errors(node))

    def test_mx_required_and_acc_rejected(self):
        for key in ['vdd-mx-supply', 'qcom,apcs-syscon']:
            node = copy.deepcopy(self.msm)
            del node[key]
            self.assertTrue(self.errors(node))
        node = copy.deepcopy(self.msm)
        node['acc-syscon'] = [[8]]
        self.assertTrue(self.errors(node))

    def test_exact_three_cell_order(self):
        for key in ['nvmem-cells', 'nvmem-cell-names']:
            for count in [2, 4, 13]:
                node = copy.deepcopy(self.msm)
                node[key] = (node[key] * 5)[:count]
                self.assertTrue(self.errors(node), (key, count))
        node = copy.deepcopy(self.msm)
        node['nvmem-cell-names'].reverse()
        self.assertTrue(self.errors(node))

    def test_legacy_qcs404_remains_valid(self):
        self.assertFalse(self.errors(self.legacy))

    def test_mixed_layout_rejected(self):
        node = copy.deepcopy(self.legacy)
        node['compatible'] = self.msm['compatible']
        node['vdd-mx-supply'] = [[3]]
        self.assertTrue(self.errors(node))
        node = copy.deepcopy(self.msm)
        node['compatible'] = self.legacy['compatible']
        del node['vdd-mx-supply']
        self.assertTrue(self.errors(node))

    def test_legacy_mx_and_generic_only_rejected(self):
        node = copy.deepcopy(self.legacy)
        node['vdd-mx-supply'] = [[3]]
        self.assertTrue(self.errors(node))
        for compatible in [['qcom,cpr'], ['qcom,msm8926-cpr']]:
            node = copy.deepcopy(self.msm)
            node['compatible'] = compatible
            self.assertTrue(self.errors(node))


if __name__ == '__main__':
    unittest.main()
