"""Validate actual compiled provider nodes against the processed DT schema."""
import copy
import os
from pathlib import Path
import unittest
try:
    import dtschema
except ImportError:
    dtschema=None
ROOT=Path(__file__).resolve().parents[1]
BUILD=ROOT/'local/cpu-cpr-build/llvm'
CACHE=Path(os.environ.get('FX0_DT_SCHEMA_CACHE',BUILD/'Documentation/devicetree/bindings/processed-schema.json'))
DTB=BUILD/'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb'

@unittest.skipUnless(dtschema and CACHE.exists() and DTB.exists(),'Built candidate DTB/schema and dtschema required')
class QfpromRawBindingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.validator=dtschema.DTValidator([str(CACHE)])
        cls.soc=cls.validator.decode_dtb(DTB.read_bytes())[0]['soc']
    def raw(self):
        node=copy.deepcopy(self.soc['efuse@fc4b8000']);node['$nodename']=['efuse@fc4b8000'];return node
    def errors(self,node):
        return list(self.validator.iter_errors(node,filter=['nvmem/qcom,qfprom.yaml']))
    def test_compiled_raw_provider_is_valid(self):
        node=self.raw();self.assertFalse(self.errors(node));self.assertEqual(node['reg'],[[0xfc4b8000,4096]])
        self.assertTrue(node['read-only']);self.assertEqual(node['cpu-bin@b0']['reg'],[[0xb0,4]])
        self.assertEqual(node['cpr-primary@450']['reg'],[[0x450,8]])
        self.assertEqual(node['cpr-redundant@458']['reg'],[[0x458,8]])
    def test_read_only_marker_required(self):
        node=self.raw();del node['read-only'];self.assertTrue(self.errors(node))
    def test_extra_regions_rejected(self):
        node=self.raw();node['reg'].append([0xfc4ba000,4096]);self.assertTrue(self.errors(node))
    def test_programming_resources_rejected(self):
        for key,value in [('clocks',[[1]]),('clock-names',['core']),('vcc-supply',[[1]])]:
            with self.subTest(property=key):
                node=self.raw();node[key]=value;self.assertTrue(self.errors(node))
    def test_raw_generic_fallback_rejected(self):
        node=self.raw();node['compatible'].append('qcom,qfprom');self.assertTrue(self.errors(node))
    def test_existing_corrected_provider_remains_valid(self):
        node=copy.deepcopy(self.soc['efuse@fc4bc000']);node['$nodename']=['efuse@fc4bc000'];self.assertFalse(self.errors(node))
    def test_legacy_four_region_schema_remains_valid(self):
        node={'$nodename':['efuse@700000'],'compatible':['qcom,sc7180-qfprom','qcom,qfprom'],
              'reg':[[0x700000,4096],[0x780000,4096],[0x784000,4096],[0x786000,4096]],
              'clocks':[[1]],'clock-names':['core'],'vcc-supply':[[2]]}
        self.assertFalse(self.errors(node))

if __name__=='__main__':unittest.main()
