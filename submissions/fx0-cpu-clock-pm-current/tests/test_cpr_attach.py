"""Run the actual CPR attach callback against initialization failures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/pmdomain/qcom/cpr.c'

STUBS = r'''
#include <stddef.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#define EINVAL 22
#define ENOMEM 12
#define GFP_KERNEL 0
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define guard(x) (void)
#define IS_ERR(p) ((intptr_t)(p)<0)
#define PTR_ERR(p) ((intptr_t)(p))
#define dev_dbg(...) ((void)0)
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while(0)
struct device { int id; };
struct generic_pm_domain { struct device dev; };
struct acc_desc { void *config; int num_regs_per_fuse,enable_mask,enable_reg; };
struct cpr_msm8926_data { struct { int bootstrap_mx_uV; } plan; int apc_enabled; };
struct cpr_drv {
 struct generic_pm_domain pd;
 struct device *dev;
 bool initialized;
 const struct acc_desc *acc_desc;
 int lock,num_corners;
 void *cpu_clk,*corners,*corner,*tcsr;
 struct cpr_msm8926_data *msm8926;
 struct { void *apc; } rails;
};
static int calls,fail_at,opp_count,alloc_fail,clk_fail,clock_gets;
static int checkpoint(void) { return ++calls==fail_at ? -5 : 0; }
static void *devm_clk_get(struct device *d,void *name) {
 (void)d;(void)name;clock_gets++;return clk_fail?(void *)(intptr_t)-517:(void *)1;
}
static int dev_err_probe(struct device *d,int error,const char *text) {
 (void)d;(void)text;return error;
}
static int dev_pm_opp_get_opp_count(struct device *d) { (void)d;return opp_count; }
static void *devm_kcalloc(struct device *d,int n,size_t size,int flags) {
 (void)d;(void)n;(void)size;(void)flags;return alloc_fail?NULL:(void *)1;
}
static int cpr_corner_init(struct cpr_drv *d,struct device *cpu) {
 CHECK(cpu && !d->initialized);return checkpoint();
}
static void cpr_set_loop_allowed(struct cpr_drv *d) { (void)d; }
static int cpr_init_parameters(struct cpr_drv *d) { (void)d;return checkpoint(); }
static int cpr_config(struct cpr_drv *d) { (void)d;return checkpoint(); }
static int cpr_find_initial_corner(struct cpr_drv *d) { (void)d;return checkpoint(); }
static int regmap_multi_reg_write(void *map,void *config,int n) {
 (void)map;(void)config;(void)n;return checkpoint();
}
static int regmap_update_bits(void *map,int reg,int mask,int value) {
 (void)map;(void)reg;(void)mask;(void)value;return checkpoint();
}
static int cpr_voltage_bootstrap(void *rails,int floor) {
 (void)rails;CHECK(floor==1287500);return checkpoint();
}
static int regulator_enable(void *reg) { (void)reg;return checkpoint(); }
'''

MAIN = r'''
int main(void) {
 struct device cpu={1},other={2};
 struct acc_desc acc={.config=(void *)1,.enable_mask=1};
 struct cpr_drv drv;
 for(int i=1;i<=6;i++) {
  drv=(struct cpr_drv){.dev=&cpu,.acc_desc=&acc};
  opp_count=4;calls=0;fail_at=i;
  CHECK(cpr_pd_attach_dev(&drv.pd,&cpu)==-5);
  CHECK(!drv.initialized && calls==i);
  calls=0;fail_at=0;
  CHECK(!cpr_pd_attach_dev(&drv.pd,&cpu));
  CHECK(drv.initialized && calls==6);
  CHECK(!cpr_pd_attach_dev(&drv.pd,&other));CHECK(calls==6);
 }
 for(int i=0;i<4;i++) {
  drv=(struct cpr_drv){.dev=&cpu,.acc_desc=&acc};calls=0;
  clk_fail=i==0;opp_count=i==1?-517:i==2?1:4;alloc_fail=i==3;
  CHECK(cpr_pd_attach_dev(&drv.pd,&cpu)==(i<2?-517:i==2?-EINVAL:-ENOMEM));
  CHECK(!drv.initialized && !calls);
  clk_fail=alloc_fail=0;opp_count=4;
  CHECK(!cpr_pd_attach_dev(&drv.pd,&cpu));CHECK(calls==6);
 }
 /* No ACC on MSM8926; activation is the last fallible attachment stage. */
 for(int i=1;i<=6;i++) {
  struct cpr_msm8926_data data={.plan={1287500}};
  drv=(struct cpr_drv){.dev=&cpu,.msm8926=&data,.cpu_clk=(void *)42};
  clock_gets=0;clk_fail=1;calls=0;fail_at=i;
  CHECK(cpr_pd_attach_dev(&drv.pd,&cpu)==-5);
  CHECK(!drv.initialized && !data.apc_enabled && calls==i);
  calls=0;fail_at=0;
  CHECK(!cpr_pd_attach_dev(&drv.pd,&cpu));
  CHECK(drv.initialized && data.apc_enabled && calls==6);
  CHECK(!cpr_pd_attach_dev(&drv.pd,&other));CHECK(calls==6);
  CHECK(!clock_gets && drv.cpu_clk==(void *)42);
  clk_fail=0;
 }
 puts("16 initialization failures retry; completed attachment is idempotent");
 return 0;
}
'''


class CprAttachTests(unittest.TestCase):
    def test_callback_failures_and_retry(self):
        source = SOURCE.read_text()
        start = source.index('static int cpr_pd_attach_dev(')
        end = source.index('\nstatic int cpr_debug_info_show(', start)
        callback = source[start:end]
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            cfile = base / 'test.c'
            exe = base / 'test'
            cfile.write_text(STUBS + callback + MAIN)
            compiled = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                       str(cfile), '-o', str(exe)],
                                      capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(exe)], check=True,
                                    capture_output=True, text=True)
            self.assertIn('16 initialization failures retry', result.stdout)


if __name__ == '__main__':
    unittest.main()
