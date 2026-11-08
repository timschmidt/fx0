"""Check the C mapper against the pinned vendor clock-plan manifest."""
import ctypes as c
import importlib.util
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('voltage_fixture', ROOT/'tests/test_msm8926_voltage_plan.py')
FIXTURE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FIXTURE)
WRAPPER = r'''
#include "cpr-msm8926-corner.h"
int map_corner(unsigned int bin,unsigned int version,unsigned long rate,int flags,int *out) {
 struct cpr_msm8926_calibration cal={.clock_speed_bin=bin,.pvs_version=version,
 .quotient={700,900,1200},.ring_osc={2,3,4}};
 struct cpr_msm8926_voltage_plan plan={.floor_uV={1080000,1080000,1130000},
 .ceiling_uV={1080000,1180000,1280000},.initial_uV={1080000,1080000,1140000},
 .mx_min_uV={1087500,1187500,1287500}};
 struct cpr_msm8926_corner result;
 for(int i=0;i<14;i++)cal.quotient_adjust[i]=i*3;
 if(flags&1)cal.quotient[2]=4096;
 if(flags&2)cal.ring_osc[2]=8;
 if(flags&4)cal.quotient_adjust[6]=1200;
 if(flags&8)plan.floor_uV[2]=0;
 if(flags&16)plan.initial_uV[2]=1120000;
 if(flags&32)plan.initial_uV[2]=1290000;
 if(flags&64)plan.mx_min_uV[2]=1270000;
 int ret=cpr_msm8926_map_corner(flags&128?NULL:&cal,flags&256?NULL:&plan,
 rate,flags&512?NULL:&result);
 _Static_assert(sizeof(result)==8*sizeof(int),"wrapper layout");
 if(!ret)memcpy(out,&result,sizeof(result));
 return ret;
}
'''

class CornerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        FIXTURE.VoltagePlanTests.setUpClass()
        cls.base = Path(FIXTURE.VoltagePlanTests.tmp.name)
        header = ROOT/'worktrees/linux-cpu-cpr/drivers/pmdomain/qcom/cpr-msm8926-corner.h'
        (cls.base/header.name).write_bytes(header.read_bytes())
        source = cls.base/'corners.c'
        source.write_text(FIXTURE.WRAPPER+WRAPPER)
        result = subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(cls.base),str(source),'-o',str(cls.base/'corner.so')],capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.lib = c.CDLL(str(cls.base/'corner.so'))
        cls.lib.map_corner.argtypes = [c.c_uint,c.c_uint,c.c_ulong,c.c_int,c.POINTER(c.c_int)]
        cls.lib.map_corner.restype = c.c_int
        cls.plans = json.loads((ROOT/'manifests/msm8926-cpu-corner-plans.json').read_text())['plans']

    @classmethod
    def tearDownClass(cls):
        FIXTURE.VoltagePlanTests.tearDownClass()

    def run_corner(self,bin=0,version=1,rate=1190400000,flags=0):
        out = (c.c_int*8)(*([0x5a5a5a5a]*8))
        ret = self.lib.map_corner(bin,version,rate,flags,out)
        if ret:
            self.assertEqual(list(out),[0x5a5a5a5a]*8)
        return ret,list(out)

    def test_all_clock_bins_versions_and_boundaries(self):
        rates = {1,300000000,600000000}
        for plan in self.plans.values():
            for hz,_ in plan[1:]:
                rates.update([hz-1,hz,hz+1])
        for bin in range(8):
            for version in range(4):
                plan = self.plans.get(f'qcom,speed{bin}-bin-v{version}',self.plans['qcom,speed0-bin-v0'])[1:]
                for rate in sorted(rates):
                    selected = next((corner for hz,corner in plan if hz>=rate),None)
                    ret,out = self.run_corner(bin,version,rate)
                    if selected is None:
                        self.assertEqual(ret,-34,(bin,version,rate))
                        continue
                    self.assertEqual(ret,0,(bin,version,rate))
                    fuse = 0 if selected<=2 else 1 if selected<=4 else 2
                    self.assertEqual(out,[selected,fuse+1,[700,900,1200][fuse]-(selected-1)*3,[2,3,4][fuse],
                        [1080000,1080000,1130000][fuse],[1080000,1180000,1280000][fuse],
                        [1080000,1080000,1140000][fuse],[1087500,1187500,1287500][fuse]])

    def test_invalid_metadata_leaves_output_unchanged(self):
        for flags in [1,2,4,8,16,32,64,128,256,512]:
            self.assertEqual(self.run_corner(flags=flags)[0],-22,flags)
        for kwargs in [dict(rate=0),dict(bin=8),dict(version=4)]:
            self.assertEqual(self.run_corner(**kwargs)[0],-22)

if __name__ == '__main__':
    unittest.main()
