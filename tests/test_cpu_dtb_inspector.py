import ctypes.util
import importlib.util
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dtb_inspector', ROOT/'scripts/inspect_fx0_cpu_dtb.py')
module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
DTC = shutil.which('dtc') or str(ROOT/'local/dmp-package-build/llvm/scripts/dtc/dtc')
FIXTURE = '''/dts-v1/;
/ {
 #address-cells=<1>; #size-cells=<1>; model="CPU fixture";
 compatible="test,cpu-fixture"; qcom,msm-id=<200 65537>;
 qcom,clock-a7@f9011050 {
  compatible="qcom,clock-a7-8226"; reg=<0xf9011050 8 0xfc4b80b0 8>;
  reg-names="rcg-base","efuse"; cpu-vdd-supply=<&cpr>;
  qcom,speed0-bin-v0=<0 0 384000000 2 787200000 4 1190400000 7>;
 };
 cpr: regulator@f9018000 {
  compatible="qcom,cpr-regulator"; reg=<0xf9018000 0x1000>;
  vdd-apc-supply=<&s2>; vdd-mx-supply=<&mx>;
  qcom,cpr-fuse-cond-min-volt-sel=<54 42 6 7 1>; qcom,cpr-cond-min-voltage=<1140000>;
 };
 s2: spm-regulator@1700 {reg=<0x1700 0x100>; regulator-name="8226_s2";};
 mx: mx-regulator {regulator-name="mx";};
};
'''

@unittest.skipUnless(Path(DTC).exists() and ctypes.util.find_library('fdt'), 'Host dtc/libfdt required')
class CpuDtbInspectorTests(unittest.TestCase):
    def fixture(self, base):
        source=base/'fixture.dts';source.write_text(FIXTURE);target=base/'fixture.dtb'
        subprocess.run([DTC,'-I','dts','-O','dtb','-o',str(target),str(source)],check=True,capture_output=True)
        return target.read_bytes()

    def test_embedded_fdt_and_supply_links(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);blob=self.fixture(base)
            prefix=b'QCDT'+bytes(20)+struct.pack('>II',0xd00dfeed,0xffffffff)+bytes(32)
            result=module.inspect(prefix+blob,base/'out',Path(DTC))
            self.assertEqual(len(result),1)
            self.assertEqual(result[0]['offset'],len(prefix))
            self.assertEqual(result[0]['root']['qcom,msm-id'],[200,65537])
            clock=result[0]['nodes']['/qcom,clock-a7@f9011050']
            self.assertEqual(clock['reg'],[0xf9011050,8,0xfc4b80b0,8])
            self.assertEqual(clock['qcom,speed0-bin-v0'][-2:],[1190400000,7])
            self.assertEqual({x['provider'] for x in result[0]['resolved_supply_links']},
                             {'/regulator@f9018000','/spm-regulator@1700','/mx-regulator'})
            self.assertEqual(result[0]['nodes']['/regulator@f9018000']['qcom,cpr-fuse-cond-min-volt-sel'],[54,42,6,7,1])
            self.assertEqual(result[0]['dtc_decompile_exit'],0)
            self.assertEqual((base/'out').stat().st_mode & 0o777,0o700)

    def test_corrupt_strings_offset_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);blob=bytearray(self.fixture(base))
            struct.pack_into('>I',blob,12,len(blob)+4)
            with self.assertRaises(ValueError):module.inspect(blob,base/'out')

    def test_truncation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);blob=self.fixture(base)
            with self.assertRaises(ValueError):module.inspect(blob[:-4],base/'out')

    def test_multiple_embedded_dtbs_keep_separate_offsets(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);blob=self.fixture(base)
            result=module.inspect(blob+b'padding'+blob,base/'out')
            self.assertEqual([r['offset'] for r in result],[0,len(blob)+7])
            self.assertEqual(result[0]['sha256'],result[1]['sha256'])

if __name__=='__main__':unittest.main()
