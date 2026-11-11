"""Validate the NFC binding plus compiled production wiring and conservative CPUs."""
import copy
import os
from pathlib import Path
import unittest

import dtschema

ROOT = Path(__file__).resolve().parents[1]
CACHE = Path(os.environ.get('FX0_NFC_SCHEMA', ROOT / 'local/nfc-preparation/processed-schema.json'))
DTB = Path(os.environ.get('FX0_NFC_DTB', ROOT / 'build/fx0-nfc-preparation/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb'))
BASELINE = Path(os.environ.get('FX0_NFC_BASELINE_DTB', ROOT / 'build/fx0-r50-reconstruction/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb'))


class NxpNciBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = dtschema.DTValidator([str(CACHE)])
        cls.tree = cls.validator.decode_dtb(DTB.read_bytes())[0]
        cls.baseline = cls.validator.decode_dtb(BASELINE.read_bytes())[0]
        cls.bus = cls.tree['soc']['i2c@f9925000']
        cls.nfc = copy.deepcopy(cls.bus['nfc@28'])
        cls.nfc['$nodename'] = ['nfc@28']

    def errors(self, node, schema='net/nfc/nxp,nci.yaml'):
        return list(self.validator.iter_errors(node, filter=[schema]))

    def test_compiled_NFC_bus_pin_and_clock_bindings(self):
        targets = [(self.nfc, 'net/nfc/nxp,nci.yaml'),
                   (self.bus, 'i2c/qcom,i2c-qup.yaml'),
                   (self.tree['soc']['pinctrl@fd510000'], 'pinctrl/qcom,msm8226-pinctrl.yaml'),
                   (self.tree['remoteproc']['smd-edge']['rpm-requests']['clock-controller'], 'clock/qcom,rpmcc.yaml')]
        for node, schema in targets:
            with self.subTest(schema=schema):
                self.assertFalse(self.errors(node, schema))

    def test_optional_clock_pairing_name_and_count(self):
        for key in ['clocks', 'clock-names']:
            node = copy.deepcopy(self.nfc)
            del node[key]
            self.assertTrue(self.errors(node), key)
        node = copy.deepcopy(self.nfc)
        node['clock-names'] = ['wrong']
        self.assertTrue(self.errors(node))
        for key in ['clocks', 'clock-names']:
            node = copy.deepcopy(self.nfc)
            node[key] *= 2
            self.assertTrue(self.errors(node), key)

    def test_existing_no_clock_and_no_firmware_GPIO_remain_valid(self):
        node = copy.deepcopy(self.nfc)
        del node['clocks'], node['clock-names']
        self.assertFalse(self.errors(node))
        del node['firmware-gpios']
        self.assertFalse(self.errors(node))

    def test_compiled_production_address_GPIO_clock_and_idle_states(self):
        pins = self.tree['soc']['pinctrl@fd510000']
        rpm = self.tree['remoteproc']['smd-edge']['rpm-requests']['clock-controller']
        self.assertEqual(self.bus['status'], ['okay'])
        self.assertEqual(self.bus['clock-frequency'], 100000)
        self.assertEqual(self.nfc['compatible'], ['nxp,pn547', 'nxp,nxp-nci-i2c'])
        self.assertEqual(self.nfc['reg'], [[0x28]])
        self.assertEqual(self.nfc['interrupts'], [[21, 1]])
        self.assertEqual(self.nfc['interrupt-parent'], [[pins['phandle']]])
        self.assertEqual(self.nfc['enable-gpios'], [[pins['phandle'], 20, 0]])
        self.assertEqual(self.nfc['firmware-gpios'], [[pins['phandle'], 22, 0]])
        self.assertEqual(rpm['compatible'], ['qcom,rpmcc-msm8226', 'qcom,rpmcc'])
        self.assertEqual(self.nfc['clocks'], [[rpm['phandle'], 54]])
        self.assertEqual(self.nfc['pinctrl-0'], [[pins[name]['phandle'] for name in [
            'nfc-irq-default-state', 'nfc-enable-default-state', 'nfc-firmware-default-state']]])
        for name, pin in [('nfc-enable-default-state', 'gpio20'), ('nfc-firmware-default-state', 'gpio22')]:
            self.assertEqual(pins[name]['pins'], [pin])
            self.assertTrue(pins[name]['output-low'])
        self.assertTrue(pins['nfc-irq-default-state']['output-disable'])
        self.assertTrue(pins['nfc-irq-default-state']['bias-pull-down'])
        self.assertEqual(pins['blsp1-i2c3-state']['pins'], ['gpio10', 'gpio11'])
        self.assertEqual(pins['blsp1-i2c3-state']['drive-strength'], 8)
        self.assertNotIn('wakeup-source', self.nfc)
        self.assertNotIn('lp5521@32', self.bus)

    def test_CPU_OPPs_and_domain_wiring_retain_r50_semantics(self):
        def without_phandles(value):
            if isinstance(value, dict):
                return {key: without_phandles(item) for key, item in value.items() if key != 'phandle'}
            return value
        self.assertEqual(without_phandles(self.tree['opp-table-cpu']), without_phandles(self.baseline['opp-table-cpu']))
        rates = sorted(node['opp-hz'][0][0] for node in self.tree['opp-table-cpu'].values()
                       if isinstance(node, dict) and 'opp-hz' in node and node.get('status') != ['disabled'])
        self.assertEqual(rates, [300000000, 384000000, 600000000, 787200000])
        for cpu in range(4):
            node, old = self.tree['cpus'][f'cpu@{cpu}'], self.baseline['cpus'][f'cpu@{cpu}']
            self.assertEqual(node.get('power-domains'), old.get('power-domains'))
            self.assertEqual(node['clocks'][0][1:], old['clocks'][0][1:])
        self.assertNotIn('power-controller@f9018000', self.tree['soc'])


if __name__ == '__main__':
    unittest.main()
