"""Execute the CPR driver's MSM8926 calibration and OPP construction paths."""
import os
import importlib.util
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/pmdomain/qcom/cpr.c'
spec = importlib.util.spec_from_file_location('voltage', ROOT/'tests/test_msm8926_voltage_plan.py')
FIXTURE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FIXTURE)

STUBS = r'''
#include <stdlib.h>
#include <stdio.h>
#include <stdint.h>
#include "cpr-msm8926-corner.h"
#define __maybe_unused
#define GFP_KERNEL 0
#define BIT(x) (1U << (x))
#define ENOMEM 12
#define EPROBE_DEFER 517
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define dev_err_probe(dev, err, ...) ((void)(dev), (err))
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct device { int id; void *of_node; };
struct regmap {int unused;};
static struct regmap apcs;
static int syscon_error,read_error,drop_ref_write;
static unsigned int ref_source;
static struct regmap *syscon_regmap_lookup_by_phandle(void *node,const char *name) {
 (void)node;CHECK(!strcmp(name,"qcom,apcs-syscon"));
 return syscon_error?(void *)(intptr_t)syscon_error:&apcs;
}


#define REG_RBIF_IRQ_EN(n) (0x100+4*(n))
#define REG_RBCPR_CTL 0x90
#define REG_RBCPR_RESULT_0 0xa0
#define REG_RBIF_IRQ_CLEAR 0x110
#define RBCPR_RESULT0_BUSY_MASK BIT(19)
#define CPR_INT_ALL 0x7f
#define ETIMEDOUT 110
static u32 cpr_regs[0x120/4];
static int mmio_reads,mmio_writes,mmio_bad_at,mmio_drop_at,busy_cycles;
static int ref_updates,ref_update_error,ref_error_after,ref_read_calls,ref_read_error_at;
static u32 __attribute__((unused)) readl(void *address) {
 unsigned int index=((u32 *)address-cpr_regs);
 CHECK(index<sizeof(cpr_regs)/sizeof(*cpr_regs));mmio_reads++;
 if(mmio_reads==mmio_bad_at)return 1;
 if(index==REG_RBCPR_RESULT_0/4 && busy_cycles) {
  if(busy_cycles>0)busy_cycles--;
  return RBCPR_RESULT0_BUSY_MASK;
 }
 return cpr_regs[index];
}
static void __attribute__((unused)) writel(u32 value,void *address) {
 unsigned int index=((u32 *)address-cpr_regs);
 CHECK(index<sizeof(cpr_regs)/sizeof(*cpr_regs));mmio_writes++;
 if(mmio_writes!=mmio_drop_at)cpr_regs[index]=value;
}
#define readl_poll_timeout(address,value,condition,delay,timeout) ({ \
 CHECK((delay)==1 && (timeout)==1000);int poll_result=-ETIMEDOUT; \
 for(int poll=0;poll<=1000;poll++){(value)=readl(address);if(condition){poll_result=0;break;}} \
 poll_result; })
static int __attribute__((unused)) regmap_update_bits(struct regmap *map,unsigned int offset,u32 mask,u32 value) {
 CHECK(map==&apcs && offset==0x64 && mask==1 && value==0);
 CHECK(!cpr_regs[REG_RBIF_IRQ_EN(0)/4] && !cpr_regs[REG_RBCPR_CTL/4]);
 CHECK(!busy_cycles);ref_updates++;
 if(read_error)return read_error;
 if(ref_update_error && !ref_error_after)return ref_update_error;
 if(!drop_ref_write)ref_source=(ref_source&~mask)|(value&mask);
 return ref_update_error;
}
static void reset_refclock(void) {
 memset(cpr_regs,0,sizeof(cpr_regs));
 cpr_regs[REG_RBIF_IRQ_EN(0)/4]=CPR_INT_ALL;
 cpr_regs[REG_RBCPR_CTL/4]=1|8|32|64;
 mmio_reads=mmio_writes=mmio_bad_at=mmio_drop_at=busy_cycles=0;
 ref_updates=ref_update_error=ref_error_after=ref_read_calls=ref_read_error_at=drop_ref_write=0;
}

static int regmap_read(struct regmap *map,unsigned int offset,unsigned int *value) {
 CHECK(map==&apcs && offset==0x64);ref_read_calls++;if(read_error || ref_read_calls==ref_read_error_at)return read_error?read_error:-EIO;*value=ref_source;return 0;
}
struct clk { int unused; };
struct generic_pm_domain { struct device dev; };
struct fuse_corner {
 int mx_min_uV,min_uV,max_uV,uV,quot,step_quot;
 unsigned long max_freq;
 unsigned char ring_osc_idx;
};
struct corner {
 int min_uV,max_uV,uV,last_uV,quot_adjust;
 unsigned long freq;
 struct fuse_corner *fuse_corner;
};
struct cpr_msm8926_data {
 struct cpr_msm8926_calibration calibration;
 struct cpr_msm8926_voltage_plan plan;
 bool apc_enabled,applied;
 u32 supported_hw; int opp_token; struct regmap *apcs;
};
struct cpr_drv {
 void *base;
 struct device *dev;
 struct generic_pm_domain pd;
 struct { struct regulator *apc,*mx;int mx_max_uV; } rails;
 struct cpr_msm8926_data *msm8926;
 struct fuse_corner *fuse_corners;
 struct corner *corners;
 struct clk *cpu_clk;
 unsigned int num_corners;
};
struct dev_pm_opp { unsigned int fuse;unsigned long freq; };
static struct dev_pm_opp opps[14];
static int stage,fail_stage,boot_voltage,opp_gets,opp_puts,opp_fail,round_error;
static unsigned long round_mismatch;
static int clk_failure,clock_gets,disable_feedback;
static struct clk provider_clock;
static struct clk *devm_clk_get(struct device *dev,const char *name) {
 CHECK(dev && !strcmp(name,"cpu"));clock_gets++;
 return clk_failure?(void *)(intptr_t)-EPROBE_DEFER:&provider_clock;
}
static void *allocation;
static int checkpoint(void) { return ++stage==fail_stage; }
static void *devm_kzalloc(struct device *dev,size_t size,int flags) {
 (void)dev;(void)flags;
 if(checkpoint())return NULL;
 return allocation=calloc(1,size);
}
static int cpr_msm8926_read_calibration(struct device *dev,struct cpr_msm8926_calibration *cal) {
 (void)dev;if(checkpoint())return -EPROBE_DEFER;
 struct cpr_msm8926_fuses f={.row22=8|16|(21ULL<<6),.row138=(700ULL<<24)|(900ULL<<12)|1200,
 .conditional_matches=1};
 int ret=cpr_msm8926_decode(&f,cal);
 if(disable_feedback){cal->fuse_allows_loop=false;cal->quotient[0]=4096;cal->ring_osc[0]=255;}
 return ret;
}
static struct regulator *devm_regulator_get(struct device *dev,const char *name) {
 (void)dev;CHECK(!strcmp(name,"vdd-mx"));
 return checkpoint()?(void *)(intptr_t)-EPROBE_DEFER:&m;
}
static int regulator_get_voltage(struct regulator *reg) {
 CHECK(reg==&a);return checkpoint()?-EIO:boot_voltage;
}
static struct dev_pm_opp *dev_pm_opp_find_level_exact(struct device *dev,unsigned int level) {
 (void)dev;CHECK(level>=1 && level<=14);opp_gets++;
 return level==(unsigned int)opp_fail?(void *)(intptr_t)-EPROBE_DEFER:&opps[level-1];
}
static unsigned int cpr_get_fuse_corner(struct dev_pm_opp *opp) {return opp->fuse;}
static unsigned long cpr_get_opp_hz_for_req(struct dev_pm_opp *opp,struct device *dev) {
 (void)dev;return opp->freq;
}
static void dev_pm_opp_put(struct dev_pm_opp *opp) {CHECK(opp>=opps && opp<opps+14);opp_puts++;}
static long clk_round_rate(struct clk *clk,unsigned long rate) {
 CHECK(clk);return round_error?round_error:rate==round_mismatch?(long)rate-1:(long)rate;
}
'''

MAIN = r'''
static struct cpr_drv reset(struct fuse_corner *fuses,struct corner *corners) {
 static struct device dev;
 static struct clk clk;
 a=(struct regulator){.step=10000,.base=700000,.count=135,.minimum=900000,.maximum=1350000};
 m=(struct regulator){.step=12500,.base=750000,.count=64,.minimum=750000,.maximum=1337500};
 stage=fail_stage=calls=fail_at=opp_gets=opp_puts=opp_fail=round_error=0;
 reset_refclock();syscon_error=read_error=0;ref_source=0;clk_failure=clock_gets=disable_feedback=0;error_code=-EIO;boot_voltage=1150000;allocation=NULL;round_mismatch=0;
 memset(fuses,0,3*sizeof(*fuses));memset(corners,0,14*sizeof(*corners));
 unsigned long rates[]={300000000,384000000,600000000,787200000,998400000,1094400000,1190400000};
 for(unsigned int i=0;i<7;i++)opps[i]=(struct dev_pm_opp){.freq=rates[i],.fuse=i<2?1:i<4?2:3};
 return (struct cpr_drv){.base=cpr_regs,.dev=&dev,.rails={.apc=&a},.fuse_corners=fuses,.corners=corners,.cpu_clk=&clk,.num_corners=7};
}
int main(void) {
 struct fuse_corner fuses[3],before[3];struct corner corners[14];
 struct cpr_drv drv;
 for(int fault=1;fault<=5;fault++) {
  drv=reset(fuses,corners);memset(fuses,0x5a,sizeof(fuses));memcpy(before,fuses,sizeof(fuses));
  if(fault<5)fail_stage=fault;else fail_at=1;
  int ret=cpr_msm8926_init(&drv);
  CHECK(ret==(fault==1?-ENOMEM:fault==4||fault==5?-EIO:-EPROBE_DEFER));
  CHECK(!drv.msm8926 && !drv.rails.mx && !memcmp(fuses,before,sizeof(fuses)));
  free(allocation);
 }
 for(int fault=0;fault<3;fault++) {
  drv=reset(fuses,corners);memset(fuses,0x5a,sizeof(fuses));memcpy(before,fuses,sizeof(fuses));
  if(fault==0)syscon_error=-EPROBE_DEFER;
  if(fault==1)read_error=-EIO;
  if(fault==2){ref_source=1;drop_ref_write=1;}
  CHECK(cpr_msm8926_init(&drv)==(fault==0?-EPROBE_DEFER:fault==1?-EIO:-EINVAL));
  CHECK(!drv.msm8926 && !drv.rails.mx && !memcmp(fuses,before,sizeof(fuses)));
  free(allocation);
 }
 for(int fault=0;fault<3;fault++) {
  drv=reset(fuses,corners);memset(fuses,0x5a,sizeof(fuses));memcpy(before,fuses,sizeof(fuses));
  clk_failure=fault==0;round_error=fault==1?-EPROBE_DEFER:0;
  round_mismatch=fault==2?600000000:0;
  CHECK(cpr_msm8926_init(&drv)==(fault==2?-ERANGE:-EPROBE_DEFER));
  CHECK(!drv.msm8926 && !drv.rails.mx && !memcmp(fuses,before,sizeof(fuses)));
  free(allocation);
 }
 drv=reset(fuses,corners);CHECK(!cpr_msm8926_init(&drv));
 CHECK(drv.msm8926 && drv.rails.mx==&m && drv.rails.mx_max_uV==1337500);
 CHECK(drv.msm8926->plan.bootstrap_mx_uV==1287500);
 CHECK(drv.msm8926->supported_hw==127 && drv.cpu_clk==&provider_clock && clock_gets==1);
 CHECK(!drv.msm8926->apc_enabled && !drv.msm8926->applied);
 for(int i=0;i<3;i++) {
  CHECK(fuses[i].step_quot==30);
  CHECK((fuses[i].mx_min_uV==(int[]){1087500,1187500,1287500}[i]));
 }
 CHECK(!cpr_msm8926_corner_init(&drv,drv.dev));CHECK(opp_gets==7 && opp_puts==7);
 for(int i=0;i<7;i++) {
  CHECK(corners[i].freq==opps[i].freq && corners[i].fuse_corner==&fuses[opps[i].fuse-1]);
  CHECK(corners[i].min_uV<=corners[i].uV && corners[i].uV<=corners[i].max_uV);
  CHECK(corners[i].last_uV==corners[i].uV);
 }
 /* Required OPP references must be released on every malformed description. */
 for(int fault=0;fault<10;fault++) {
  opp_gets=opp_puts=0;
  struct dev_pm_opp save=opps[4];
  if(fault==0)opps[4].freq=0;
  if(fault==1)opps[4].freq=opps[3].freq;
  if(fault==2)opps[4].fuse=0;
  if(fault==3)opps[4].fuse=4;
  if(fault==4)opps[4].fuse=2;
  if(fault==5)round_mismatch=opps[4].freq;
  if(fault==6)round_error=-EPROBE_DEFER;
  if(fault==7)drv.msm8926->calibration.clock_bin_valid=false;
  if(fault==8)drv.msm8926->calibration.fuse_allows_loop=false;
  if(fault==9)opps[4].freq=1190400001;
  int ret=cpr_msm8926_corner_init(&drv,drv.dev);
  CHECK(ret==(fault<=4||fault==9?-EINVAL:fault==6?-EPROBE_DEFER:-ERANGE));
  CHECK(opp_gets==opp_puts);
  opps[4]=save;round_mismatch=0;round_error=0;
  drv.msm8926->calibration.clock_bin_valid=true;drv.msm8926->calibration.fuse_allows_loop=true;
 }
 for(int level=1;level<=7;level++) {
  opp_gets=opp_puts=0;opp_fail=level;
  CHECK(cpr_msm8926_corner_init(&drv,drv.dev)==-EPROBE_DEFER);
  CHECK(opp_gets==level && opp_puts==level-1);
 }
 opp_fail=0;drv.num_corners=15;CHECK(cpr_msm8926_corner_init(&drv,drv.dev)==-EINVAL);
 drv.num_corners=4;drv.msm8926->supported_hw=15;drv.msm8926->calibration.clock_bin_valid=false;
 drv.msm8926->calibration.fuse_allows_loop=false;
 CHECK(!cpr_msm8926_corner_init(&drv,drv.dev));
 free(allocation);
 drv=reset(fuses,corners);disable_feedback=1;
 CHECK(!cpr_msm8926_init(&drv) && drv.msm8926->supported_hw==15);
 for(int i=0;i<3;i++)CHECK(!fuses[i].quot && !fuses[i].ring_osc_idx);
 drv.num_corners=4;CHECK(!cpr_msm8926_corner_init(&drv,drv.dev));
 free(allocation);
 puts("MSM8926 actual init and corner paths: calibration faults, 7 OPPs and rejection/ownership cases passed");
 return 0;
}
'''


def function(source, name):
    start = source.index(name)
    start = source.rfind('\nstatic ', 0, start) + 1
    brace = source.index('{', start)
    end, depth = brace + 1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end] + '\n'


class DomainTests(unittest.TestCase):
    def test_actual_driver_init_and_corners(self):
        FIXTURE.VoltagePlanTests.setUpClass()
        try:
            base = Path(FIXTURE.VoltagePlanTests.tmp.name)
            header = KERNEL/'drivers/pmdomain/qcom/cpr-msm8926-corner.h'
            (base/header.name).write_bytes(header.read_bytes())
            text = SOURCE.read_text()
            functions = ''.join(function(text, name) for name in
                                (['cpr_msm8926_check_refclock('] +
                                 (['cpr_msm8926_init_refclock('] if 'static int cpr_msm8926_init_refclock(' in text else []) +
                                 ['cpr_msm8926_init(', 'cpr_msm8926_corner_init(']))
            source, executable = base/'domain.c', base/'domain'
            source.write_text(FIXTURE.WRAPPER + STUBS + functions + MAIN)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     '-I', str(base), str(source), '-o', str(executable)],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('7 OPPs and rejection/ownership cases passed', result.stdout)
        finally:
            FIXTURE.VoltagePlanTests.tearDownClass()


if __name__ == '__main__':
    unittest.main()
