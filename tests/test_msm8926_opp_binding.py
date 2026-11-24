"""Validate the separate qualification DTB and its CPU/domain relationships."""
import copy
import os
from pathlib import Path
import unittest

try:
    import dtschema
except ImportError:
    dtschema = None

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path(os.environ.get('FX0_CPU_BUILD', ROOT/'build/cpu-calibration-load'))
CACHE = Path(os.environ.get('FX0_DT_SCHEMA_CACHE', BUILD/'processed-schema.json'))
DTBS = BUILD/'arch/arm/boot/dts/qcom'
RATES = [300000000,384000000,600000000,787200000,998400000,1094400000,
         1190400000,1305600000,1344000000,1401600000,1497600000,1593600000,
         1689600000,1785600000]


@unittest.skipUnless(dtschema and CACHE.exists() and
                     (DTBS/'qcom-msm8926-lg-madai-cpr.dtb').exists(),
                     'Compiled DTBs and processed schema required')
class OppBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = dtschema.DTValidator([str(CACHE)])
        cls.candidate = cls.validator.decode_dtb((DTBS/'qcom-msm8926-lg-madai-cpr.dtb').read_bytes())[0]
        cls.baseline = cls.validator.decode_dtb((DTBS/'qcom-msm8926-lg-madai.dtb').read_bytes())[0]
        cls.cpu = copy.deepcopy(cls.candidate['opp-table-cpu'])
        cls.cpu['$nodename'] = ['opp-table-cpu']
        cls.domain = copy.deepcopy(cls.candidate['opp-table-cpr'])
        cls.domain['$nodename'] = ['opp-table-cpr']
        cls.provider = copy.deepcopy(cls.candidate['soc']['power-controller@f9018000'])
        cls.provider['$nodename'] = ['power-controller@f9018000']

    def errors(self, node, binding):
        return list(self.validator.iter_errors(node, filter=[binding]))

    def test_targeted_compiled_schemas(self):
        for node, binding in [(self.cpu,'opp-v2-kryo-cpu.yaml'),
                              (self.domain,'opp-v2-qcom-level.yaml'),
                              (self.provider,'power/avs/qcom,cpr.yaml')]:
            self.assertFalse(self.errors(node,binding))

    def test_required_mask_domain_and_shared_table(self):
        for prop in ['opp-supported-hw','required-opps']:
            node = copy.deepcopy(self.cpu)
            del node['opp-300000000'][prop]
            self.assertTrue(self.errors(node,'opp-v2-kryo-cpu.yaml'),prop)
        node = copy.deepcopy(self.cpu)
        del node['opp-shared']
        self.assertTrue(self.errors(node,'opp-v2-kryo-cpu.yaml'))

    def test_cpu_cannot_bypass_calibration_or_domain_voltage(self):
        for prop,value in [('nvmem-cells',[[1]]),('opp-microvolt',[[1150000]]),
                           ('opp-microvolt-speed0-pvs0',[[1150000]])]:
            node = copy.deepcopy(self.cpu)
            target = node if prop=='nvmem-cells' else node['opp-300000000']
            target[prop] = value
            self.assertTrue(self.errors(node,'opp-v2-kryo-cpu.yaml'),prop)

    def test_each_cpu_rate_requires_matching_filtered_domain_state(self):
        self.assertEqual(len([key for key in self.cpu if key.startswith('opp-') and isinstance(self.cpu[key],dict)]),14)
        self.assertEqual(len([key for key in self.domain if key.startswith('opp') and isinstance(self.domain[key],dict)]),14)
        for index,rate in enumerate(RATES):
            cpu = self.cpu[f'opp-{rate}']
            domain = self.domain[f'opp{index+1}']
            self.assertEqual(cpu['opp-hz'],[[rate]])
            self.assertEqual(cpu['opp-supported-hw'],[[1<<index]])
            self.assertEqual(domain['opp-supported-hw'],cpu['opp-supported-hw'])
            self.assertEqual(cpu['required-opps'],[[domain['phandle']]])
            self.assertEqual(domain['opp-level'],index+1)
            self.assertEqual(domain['qcom,opp-fuse-level'],[1 if index<2 else 2 if index<4 else 3])
        for index in range(4):
            cpu = self.candidate['cpus'][f'cpu@{index}']
            self.assertEqual(cpu['operating-points-v2'],[[self.cpu['phandle']]])
            self.assertEqual(cpu['power-domains'],[[self.provider['phandle']]])
            self.assertEqual(cpu['power-domain-names'],['cpr'])

    def test_provider_wiring_and_full_raw_rows(self):
        phandles = {}

        def walk(node):
            if 'phandle' in node:
                phandles[node['phandle']] = node
            for value in node.values():
                if isinstance(value,dict):
                    walk(value)

        walk(self.candidate)
        provider = self.provider
        self.assertEqual(provider['reg'],[[0xf9018000,0x1000]])
        self.assertEqual(provider['interrupts'],[[0,15,1]])
        self.assertEqual(provider['clock-names'],['ref','cpu'])
        self.assertEqual(phandles[provider['clocks'][0][0]]['clock-frequency'],19200000)
        apcs = provider['clocks'][1][0]
        self.assertEqual(provider['qcom,apcs-syscon'],[[apcs]])
        self.assertEqual(phandles[apcs]['reg'],[[0xf9011000,0x1000]])
        self.assertEqual(provider['operating-points-v2'],[[self.domain['phandle']]])
        for cell,offset in zip(provider['nvmem-cells'],[0xb0,0x450,0x458]):
            self.assertEqual(phandles[cell[0]]['reg'],[[offset,8]])
        self.assertEqual(phandles[provider['vdd-apc-supply'][0][0]]['regulator-name'],['pm8226-apc'])
        mx = self.candidate['remoteproc']['smd-edge']['rpm-requests']['regulators']['l3']
        self.assertEqual(provider['vdd-mx-supply'],[[mx['phandle']]])
        self.assertEqual(mx['regulator-min-microvolt'],[[750000]])
        self.assertEqual(mx['regulator-max-microvolt'],[[1337500]])

    def test_ordinary_board_retains_four_opps_and_no_cpr_consumer(self):
        table = self.baseline['opp-table-cpu']
        self.assertEqual(table['compatible'],['operating-points-v2'])
        self.assertEqual(sorted(int(key[4:]) for key in table if key.startswith('opp-') and isinstance(table[key],dict)),RATES[:4])
        self.assertNotIn('power-controller@f9018000',self.baseline['soc'])
        for index in range(4):
            self.assertNotIn('power-domains',self.baseline['cpus'][f'cpu@{index}'])


if __name__ == '__main__':
    unittest.main()
