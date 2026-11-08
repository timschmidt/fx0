"""Run the actual CPR attach callback against initialization failures."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'worktrees/linux-cpu-cpr/drivers/pmdomain/qcom/cpr.c'

STUBS = r'''
#include <stddef.h>
#include <stdint.h>
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
struct cpr_drv {
 struct generic_pm_domain pd;
 struct device *dev,*attached_cpu_dev;
 const struct acc_desc *acc_desc;
 int lock,num_corners;
 void *cpu_clk,*corners,*tcsr;
};
static int calls,fail_at,opp_count,alloc_fail,clk_fail;
static int checkpoint(void) { return ++calls==fail_at ? -5 : 0; }
static void *devm_clk_get(struct device *d,void *name) {
 (void)d;(void)name;return clk_fail?(void *)(intptr_t)-517:(void *)1;
}
static int dev_err_probe(struct device *d,int error,const char *text) {
 (void)d;(void)text;return error;
}
static int dev_pm_opp_get_opp_count(struct device *d) { (void)d;return opp_count; }
static void *devm_kcalloc(struct device *d,int n,size_t size,int flags) {
 (void)d;(void)n;(void)size;(void)flags;return alloc_fail?NULL:(void *)1;
}
static int cpr_corner_init(struct cpr_drv *d,struct device *cpu) {
 CHECK(cpu && !d->attached_cpu_dev);return checkpoint();
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
  CHECK(!drv.attached_cpu_dev && calls==i);
  calls=0;fail_at=0;
  CHECK(!cpr_pd_attach_dev(&drv.pd,&cpu));
  CHECK(drv.attached_cpu_dev==&cpu && calls==6);
  CHECK(!cpr_pd_attach_dev(&drv.pd,&other));CHECK(calls==6);
 }
 for(int i=0;i<4;i++) {
  drv=(struct cpr_drv){.dev=&cpu,.acc_desc=&acc};calls=0;
  clk_fail=i==0;opp_count=i==1?-517:i==2?1:4;alloc_fail=i==3;
  CHECK(cpr_pd_attach_dev(&drv.pd,&cpu)==(i<2?-517:i==2?-EINVAL:-ENOMEM));
  CHECK(!drv.attached_cpu_dev && !calls);
  clk_fail=alloc_fail=0;opp_count=4;
  CHECK(!cpr_pd_attach_dev(&drv.pd,&cpu));CHECK(calls==6);
 }
 puts("10 initialization failures retry; completed attachment is idempotent");
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
            subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            str(cfile), '-o', str(exe)], check=True,
                           capture_output=True, text=True)
            result = subprocess.run([str(exe)], check=True,
                                    capture_output=True, text=True)
            self.assertIn('10 initialization failures retry', result.stdout)


if __name__ == '__main__':
    unittest.main()
