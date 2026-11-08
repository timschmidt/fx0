"""Validate the L2 owner opt-in and reject incompatible controller shapes."""
import copy
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

try:
    import dtschema
except ImportError:
    dtschema=None

ROOT=Path(__file__).resolve().parents[1]
BUILD=Path(os.environ.get('FX0_CPU_BUILD', ROOT/'local/cpu-cpr-build/llvm'))
CACHE=Path(os.environ.get('FX0_DT_SCHEMA_CACHE',BUILD/'Documentation/devicetree/bindings/processed-schema.json'))
DTC=BUILD/'scripts/dtc/dtc'
FIXTURE='''/dts-v1/;
/ {
 #address-cells=<1>; #size-cells=<1>;
 power-manager@f9012000 {
  compatible="qcom,msm8226-saw2-v2.1-l2", "qcom,saw2";
  reg=<0xf9012000 0x1000>; qcom,pmic-arbiter-master;
 };
};
'''


@unittest.skipUnless(dtschema and CACHE.exists() and DTC.exists(),'Built schema/dtc and dtschema required')
class SpmL2BindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator=dtschema.DTValidator([str(CACHE)])
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);(base/'test.dts').write_text(FIXTURE)
            subprocess.run([str(DTC),'-I','dts','-O','dtb','-o',str(base/'test.dtb'),str(base/'test.dts')],check=True,capture_output=True)
            cls.fixture=cls.validator.decode_dtb((base/'test.dtb').read_bytes())[0]['power-manager@f9012000']
            cls.fixture['$nodename']=['power-manager@f9012000']

    def node(self):
        return copy.deepcopy(self.fixture)

    def errors(self,node):
        return list(self.validator.iter_errors(node,filter=['soc/qcom/qcom,saw2.yaml']))

    def test_master_valid(self):
        self.assertFalse(self.errors(self.node()))

    def test_cpu_controller_rejected(self):
        node=self.node();node['compatible'][0]='qcom,msm8226-saw2-v2.1-cpu'
        self.assertTrue(self.errors(node))

    def test_other_soc_rejected(self):
        node=self.node();node['compatible'][0]='qcom,msm8974-saw2-v2.1-l2'
        self.assertTrue(self.errors(node))

    def test_alias_region_rejected(self):
        node=self.node();node['reg'].append([0xf9013000,4096])
        self.assertTrue(self.errors(node))

    def test_embedded_regulator_rejected(self):
        node=self.node();node['regulator']={'regulator-name':['wrong-owner']}
        self.assertTrue(self.errors(node))

    def test_generic_syscon_fallback_rejected(self):
        node=self.node();node['compatible'].append('syscon')
        self.assertTrue(self.errors(node))

    def test_ordinary_l2_remains_valid(self):
        node=self.node();del node['qcom,pmic-arbiter-master']
        self.assertFalse(self.errors(node))

    def test_ordinary_cpu_remains_valid(self):
        node=self.node();del node['qcom,pmic-arbiter-master'];node['compatible'][0]='qcom,msm8226-saw2-v2.1-cpu'
        self.assertFalse(self.errors(node))


if __name__=='__main__':
    unittest.main()
