"""Check the fixed-range opt-in against compiled DT and processed schema."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    import dtschema
except ImportError:
    dtschema = None

ROOT = Path(__file__).resolve().parents[1]
BUILD = Path(os.environ.get('FX0_CPU_BUILD', ROOT/'local/cpu-cpr-build/llvm'))
CACHE = Path(os.environ.get('FX0_DT_SCHEMA_CACHE', BUILD/'Documentation/devicetree/bindings/processed-schema.json'))
DTC = BUILD/'scripts/dtc/dtc'
FIXTURE = '''/dts-v1/;
/ {
 #address-cells=<1>; #size-cells=<1>;
 saw: power-manager@f9012000 { compatible="test,saw", "syscon"; reg=<0xf9012000 0x1000>; };
 regulators {
  compatible="qcom,pm8226-regulators"; qcom,saw-reg=<&saw>;
  s2 { regulator-name="test-s2"; qcom,saw-leader; qcom,saw-fixed-range; regulator-always-on; };
 };
};
'''


@unittest.skipUnless(dtschema and CACHE.exists() and DTC.exists(), 'Built schema, dtc and dtschema required')
class SawFts2BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator = dtschema.DTValidator([str(CACHE)])
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base/'test.dts').write_text(FIXTURE)
            subprocess.run([str(DTC),'-I','dts','-O','dtb','-o',str(base/'test.dtb'),str(base/'test.dts')],check=True,capture_output=True)
            cls.fixture = cls.validator.decode_dtb((base/'test.dtb').read_bytes())[0]['regulators']
            cls.fixture['$nodename'] = ['regulators']

    def node(self):
        return copy.deepcopy(self.fixture)

    def errors(self, node):
        return list(self.validator.iter_errors(node, filter=['regulator/qcom,spmi-regulator.yaml']))

    def test_fixed_pm8226_s2_valid(self):
        self.assertFalse(self.errors(self.node()))

    def test_missing_saw_controller_rejected(self):
        node=self.node();del node['qcom,saw-reg']
        self.assertTrue(self.errors(node))

    def test_missing_leader_rejected(self):
        node=self.node();del node['s2']['qcom,saw-leader']
        self.assertTrue(self.errors(node))

    def test_missing_always_on_rejected(self):
        node=self.node();del node['s2']['regulator-always-on']
        self.assertTrue(self.errors(node))

    def test_slave_rejected(self):
        node=self.node();node['s2']['qcom,saw-slave']=True
        self.assertTrue(self.errors(node))

    def test_other_rails_rejected(self):
        for name in ['s1','s3','l2','lvs1']:
            node=self.node();node[name]=node.pop('s2')
            with self.subTest(name=name):
                self.assertTrue(self.errors(node))

    def test_other_pmic_rejected(self):
        node=self.node();node['compatible']=['qcom,pm8941-regulators']
        self.assertTrue(self.errors(node))

    def test_legacy_saw_remains_valid(self):
        node=self.node();del node['s2']['qcom,saw-fixed-range']
        self.assertFalse(self.errors(node))

    def test_ordinary_spmi_remains_valid(self):
        node=self.node();del node['qcom,saw-reg']
        del node['s2']['qcom,saw-fixed-range'];del node['s2']['qcom,saw-leader']
        self.assertFalse(self.errors(node))


if __name__ == '__main__':
    unittest.main()
