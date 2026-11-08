"""Check the actual C voltage planner against provider grids and error paths."""
import ctypes as c
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
HEADER=Path(os.environ.get('FX0_CPR_VOLTAGE_PLAN_HEADER',ROOT/'worktrees/linux-cpu-cpr/drivers/pmdomain/qcom/cpr-msm8926-voltage.h'))
spec=importlib.util.spec_from_file_location('calibration_reference',ROOT/'tests/test_msm8926_calibration.py')
REFERENCE=importlib.util.module_from_spec(spec);spec.loader.exec_module(REFERENCE)
WRAPPER=r'''
#include <string.h>
#include "cpr-msm8926-voltage.h"
static int calls,fail_at,error_code;
static struct regulator a,m;
static int fail(void){calls++;return calls==fail_at;}
unsigned int regulator_get_linear_step(struct regulator *r){return r->step;}
int regulator_count_voltages(struct regulator *r){return fail()?error_code:r->count;}
int regulator_list_voltage(struct regulator *r,unsigned int selector){
 if(fail())return error_code;
 int value=r->base+selector*r->step;
 return value<r->minimum||value>r->maximum||value==r->hole?0:value;
}
int run(int step,int bin,int matches,int speed,int uplift_bit,int boot,int mx_max,
        int fault,int error,int apc_hole,int mx_hole,int flags,int *out,int *count){
 struct cpr_msm8926_fuses f={.row22=(unsigned long long)bin<<6|speed|24ULL|(unsigned long long)uplift_bit<<53,
  .row138=700ULL<<24|900ULL<<12|1200,.conditional_matches=matches};
 struct cpr_msm8926_calibration calibration;
 struct cpr_msm8926_voltage_plan plan;
 _Static_assert(sizeof(plan)==13*sizeof(int),"Unexpected wrapper layout");
 int ret=cpr_msm8926_decode(&f,&calibration);
 if(ret)return ret;
 a=(struct regulator){.step=step,.base=step==5000?350000:700000,
  .count=step==5000?186:135,.minimum=900000,.maximum=1350000,.hole=apc_hole};
 m=(struct regulator){.step=12500,.base=750000,.count=64,.minimum=750000,.maximum=1337500,.hole=mx_hole};
 if(flags&1)a.count=0;
 if(flags&2)m.count=0;
 if(flags&4)calibration.floor_uV[0]=0;
 if(flags&8)calibration.floor_uV[0]=calibration.initial_uV[0]+1;
 if(flags&16)calibration.initial_uV[2]=calibration.ceiling_uV[2]+1;
 if(flags&32)calibration.ceiling_uV[2]=1350001;
 if(flags&64)calibration.ceiling_uV[2]=1285000;
 if(flags&256)calibration.ceiling_uV[2]=1270000;
 calls=0;fail_at=fault;error_code=error;
 ret=cpr_msm8926_plan_voltages(flags&512?NULL:&calibration,flags&1024?NULL:&a,flags&2048?NULL:&m,boot,mx_max,flags&4096?NULL:&plan);
 *count=calls;
 if(!ret)memcpy(out,&plan,sizeof(plan));
 return ret;
}
'''


def oracle(step,bin,matches,speed,uplift_bit,boot=1150000,mx_max=1337500):
    row22=bin<<6|speed|24|uplift_bit<<53
    values=REFERENCE.reference(row22,700<<24|900<<12|1200,0,matches)
    floor=[values[4+i*5] for i in range(3)]
    ceiling=[values[5+i*5] for i in range(3)]
    initial=[values[6+i*5] for i in range(3)]
    maximum=max(ceiling)
    def ceil(value,unit):return ((value+unit-1)//unit)*unit
    floor=[ceil(v,step) for v in floor]
    initial=[ceil(v,step) for v in initial]
    ceiling=[ceil(v,step) for v in ceiling]
    mx=[ceil(v,12500) for v in ceiling]
    bootstrap=ceil(max([boot]+ceiling),12500)
    apc_points={v for v in range(350000 if step==5000 else 700000,(1275000 if step==5000 else 2040000)+1,step) if 900000<=v<=1350000}
    mx_points={v for v in range(750000,1537500+1,12500) if v<=mx_max}
    if boot not in apc_points or max(ceiling)>maximum or any(v not in apc_points for v in floor+ceiling+initial) or any(v not in mx_points for v in mx+[bootstrap]):
        return -34,None
    return 0,floor+ceiling+initial+mx+[bootstrap]


@unittest.skipUnless(HEADER.exists(),'Candidate voltage planner required')
class VoltagePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();base=Path(cls.tmp.name);(base/'linux/regulator').mkdir(parents=True)
        (base/'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint64_t u64;typedef uint32_t u32;\n')
        (base/'linux/errno.h').write_text('#define EINVAL 22\n#define EIO 5\n#define ENODEV 19\n#define ERANGE 34\n#define EOPNOTSUPP 95\n')
        (base/'linux/minmax.h').write_text('#define min(a,b) ((a)<(b)?(a):(b))\n#define max(a,b) ((a)>(b)?(a):(b))\n#define clamp(x,l,h) min(max(x,l),h)\n')
        (base/'linux/kernel.h').write_text('#include <stddef.h>\n#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))\n')
        # No activation or voltage-write API is provided by this read-only fixture.
        (base/'linux/regulator/consumer.h').write_text('struct regulator {int step,base,count,minimum,maximum,hole;};\nunsigned int regulator_get_linear_step(struct regulator*);\nint regulator_count_voltages(struct regulator*);\nint regulator_list_voltage(struct regulator*,unsigned int);\n')
        for header in [HEADER,HEADER.parent/'cpr-msm8926.h']:(base/header.name).write_bytes(header.read_bytes())
        (base/'wrapper.c').write_text(WRAPPER)
        result=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-shared','-fPIC','-I',str(base),str(base/'wrapper.c'),'-o',str(base/'plan.so')],capture_output=True,text=True)
        if result.returncode:raise RuntimeError(result.stderr)
        cls.lib=c.CDLL(str(base/'plan.so'));cls.lib.run.argtypes=[c.c_int]*12+[c.POINTER(c.c_int)]*2;cls.lib.run.restype=c.c_int

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def run_plan(self,step=10000,bin=21,matches=1,speed=0,uplift_bit=1,boot=1150000,mx_max=1337500,fault=0,error=-5,apc_hole=0,mx_hole=0,flags=0):
        out=(c.c_int*13)(*([0x5a5a5a5a]*13));count=c.c_int()
        result=self.lib.run(step,bin,matches,speed,uplift_bit,boot,mx_max,fault,error,apc_hole,mx_hole,flags,out,c.byref(count))
        if result:self.assertEqual(list(out),[0x5a5a5a5a]*13)
        return result,list(out),count.value

    def test_all_nominal_bins_and_rule_combinations(self):
        for step in [5000,10000]:
            for bin in range(32):
                for matches in range(2):
                    for speed in range(2):
                        for uplift_bit in range(2):
                            expected,values=oracle(step,bin,matches,speed,uplift_bit)
                            actual,out,_=self.run_plan(step,bin,matches,speed,uplift_bit)
                            self.assertEqual(actual,expected,(step,bin,matches,speed,uplift_bit))
                            if not actual:self.assertEqual(out,values)

    def test_unit_range1_and_higher_boot_voltage(self):
        ret,out,_=self.run_plan();self.assertEqual(ret,0)
        self.assertEqual(out,[1080000,1080000,1130000,1080000,1180000,1280000,1080000,1080000,1140000,1087500,1187500,1287500,1287500])
        ret,out,_=self.run_plan(boot=1310000);self.assertEqual(ret,0);self.assertEqual(out[-1],1312500)

    def test_provider_metadata_failures_leave_output_unchanged(self):
        ret,_,calls=self.run_plan();self.assertEqual(ret,0)
        for fault in range(1,calls+1):
            self.assertEqual(self.run_plan(fault=fault)[0],-5,fault)
        self.assertEqual(self.run_plan(fault=calls,error=-517)[0],-517)

    def test_missing_points_do_not_choose_higher_substitutes(self):
        for hole in [1080000,1130000,1140000,1180000,1280000,1150000]:
            self.assertEqual(self.run_plan(apc_hole=hole)[0],-34,hole)
        for hole in [1087500,1187500,1287500]:
            self.assertEqual(self.run_plan(mx_hole=hole)[0],-34,hole)

    def test_bounds_and_invalid_metadata(self):
        for step in [0,7500]:self.assertEqual(self.run_plan(step=step)[0],-95)
        for flags in [1,2]:self.assertEqual(self.run_plan(flags=flags)[0],-19)
        for flags in [4,8,16,32,512,1024,2048,4096]:self.assertEqual(self.run_plan(flags=flags)[0],-22)
        self.assertEqual(self.run_plan(flags=64)[0],-34)
        for boot in [0,1350001]:self.assertEqual(self.run_plan(boot=boot)[0],-22)
        self.assertEqual(self.run_plan(boot=-5)[0],-5)
        for boot in [1155000,1340000]:self.assertEqual(self.run_plan(boot=boot)[0],-34)
        for mx in [0,1400000]:self.assertEqual(self.run_plan(mx_max=mx)[0],-22)
        self.assertEqual(self.run_plan(mx_max=1280000)[0],-34)

    def test_range0_only_when_entire_plan_is_representable(self):
        self.assertEqual(self.run_plan(step=5000)[0],-34)
        ret,out,_=self.run_plan(step=5000,flags=256);self.assertEqual(ret,0)
        self.assertEqual(out,[1075000,1075000,1125000,1075000,1175000,1270000,1075000,1075000,1140000,1075000,1175000,1275000,1275000])


if __name__=='__main__':unittest.main()
