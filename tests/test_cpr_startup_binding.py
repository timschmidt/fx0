"""Validate the startup candidate's aux dependency and its compiled DTB."""
import copy
import importlib.util
import os
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tests' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BINDING = fixture('test_msm8926_cpr_binding')
OPP = fixture('test_msm8926_opp_binding')
BUILD = Path(os.environ.get('FX0_CPU_BUILD', ROOT / 'build/fx0-cpr-startup'))
CACHE = Path(os.environ.get('FX0_DT_SCHEMA_CACHE', BUILD / 'processed-schema.json'))
BINDING.CACHE = OPP.CACHE = CACHE
OPP.BUILD = BUILD
OPP.DTBS = BUILD / 'arch/arm/boot/dts/qcom'


class StartupCprBindingTests(BINDING.CprBindingTests):
    __unittest_skip__ = not (BINDING.dtschema and CACHE.exists())
    __unittest_skip_why__ = 'Startup processed schema and dtschema required'

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.msm['clocks'] = [[1], [9], [10, 0]]
        cls.msm['clock-names'] = ['ref', 'cpu', 'aux']

    def test_exact_provider_owned_cpu_clock(self):
        for key in ['clocks', 'clock-names']:
            for count in [1, 2, 4]:
                node = copy.deepcopy(self.msm)
                node[key] = (node[key] * 2)[:count]
                self.assertTrue(self.errors(node), (key, count))
        node = copy.deepcopy(self.msm)
        node['clock-names'].reverse()
        self.assertTrue(self.errors(node))
        node = copy.deepcopy(self.legacy)
        node['clocks'] = self.msm['clocks']
        node['clock-names'] = self.msm['clock-names']
        self.assertTrue(self.errors(node))


class StartupOppBindingTests(OPP.OppBindingTests):
    __unittest_skip__ = not (OPP.dtschema and CACHE.exists() and
                            (OPP.DTBS / 'qcom-msm8926-lg-madai-cpr.dtb').exists())
    __unittest_skip_why__ = 'Startup DTBs, processed schema and dtschema required'

    def test_provider_wiring_and_full_raw_rows(self):
        phandles = {}

        def walk(node):
            if 'phandle' in node:
                phandles[node['phandle']] = node
            for value in node.values():
                if isinstance(value, dict):
                    walk(value)

        walk(self.candidate)
        provider = self.provider
        self.assertEqual(provider['reg'], [[0xf9018000, 0x1000]])
        self.assertEqual(provider['interrupts'], [[0, 15, 1]])
        self.assertEqual(provider['clock-names'], ['ref', 'cpu', 'aux'])
        self.assertEqual(phandles[provider['clocks'][0][0]]['clock-frequency'], 19200000)
        apcs = provider['clocks'][1][0]
        self.assertEqual(provider['qcom,apcs-syscon'], [[apcs]])
        self.assertEqual(phandles[apcs]['reg'], [[0xf9011000, 0x1000]])
        self.assertEqual(provider['clocks'][2], phandles[apcs]['clocks'][1])
        self.assertEqual(provider['operating-points-v2'], [[self.domain['phandle']]])
        for cell, offset in zip(provider['nvmem-cells'], [0xb0, 0x450, 0x458]):
            self.assertEqual(phandles[cell[0]]['reg'], [[offset, 8]])
        self.assertEqual(phandles[provider['vdd-apc-supply'][0][0]]['regulator-name'], ['pm8226-apc'])
        mx = self.candidate['remoteproc']['smd-edge']['rpm-requests']['regulators']['l3']
        self.assertEqual(provider['vdd-mx-supply'], [[mx['phandle']]])
        self.assertEqual(mx['regulator-min-microvolt'], [[750000]])
        self.assertEqual(mx['regulator-max-microvolt'], [[1337500]])


if __name__ == '__main__':
    unittest.main()
