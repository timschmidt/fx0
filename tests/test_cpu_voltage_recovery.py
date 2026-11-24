"""Run real OPP/genpd/CPR callbacks against before/after-effect SAW errors."""
import os
import importlib.util
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
TREE = KERNEL


def fixture(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tests'/filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SAW = fixture('saw', 'test_saw_fts2.py')

STUBS = r'''
#include <stddef.h>
#include "cpr-voltage.h"
#define EBUSY 16
#define unlikely(x) (x)
#define guard(x) (void)
#define dev_dbg(...) ((void)0)
#define dev_dbg_ratelimited(...) ((void)0)
#define dev_err(dev,...) ((void)(dev))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define list_for_each_entry(p,h,m) for(p=NULL;p;p=NULL)
#define list_for_each_entry_reverse(p,h,m) for(p=NULL;p;p=NULL)
#define list_for_each_entry_continue(p,h,m) for(p=NULL;p;p=NULL)
#define list_for_each_entry_continue_reverse(p,h,m) for(p=NULL;p;p=NULL)
#define OPP_LEVEL_UNSET (~0U)
struct generic_pm_domain {
 unsigned int performance_state;
 int (*set_performance_state)(struct generic_pm_domain *,unsigned int);
};
struct gpd_link {int unused;};
struct generic_pm_domain_data {unsigned int performance_state;};
struct device {struct generic_pm_domain *pd;struct generic_pm_domain_data data;};
struct dev_pm_opp {unsigned long rates[1];unsigned int level;struct dev_pm_opp *required_opps[1];};
struct opp_table {
 struct dev_pm_opp *current_opp;
 bool enabled;
 struct device **required_devs;
 int required_opp_count;
 void **regulators;
 int regulator_count;
 int (*config_clks)(struct device *,struct opp_table *,struct dev_pm_opp *,void *,bool);
 int (*config_regulators)(struct device *,struct dev_pm_opp *,struct dev_pm_opp *,void **,int);
};
struct corner {int uV,last_uV,mx_min_uV;};
struct cpr_msm8926_data {bool applied;};
struct cpr_drv {
 struct generic_pm_domain pd;
 struct device *dev;
 bool initialized;
 struct corner *corner,*corners;
 struct cpr_msm8926_data *msm8926;
 struct cpr_voltage rails;
 unsigned int num_corners;
 int lock;
 bool suspended,loop_disabled;
};
enum voltage_change_dir {NO_CHANGE,DOWN,UP};
static struct spmi_saw_fts2 physical;
static struct regulator apc={0},mx={1};
static int apc_cached,mx_actual,unsafe_clock;
static unsigned long cpu_rate;
int regulator_enable(struct regulator *reg) {(void)reg;return 0;}
int regulator_sync_voltage(struct regulator *reg) {CHECK(reg==&mx);return 0;}
int regulator_set_voltage(struct regulator *reg,int minimum,int maximum) {
 CHECK(minimum<=maximum);
 if(reg==&mx){CHECK(minimum>=(int)p[0x1741]*10000);mx_actual=minimum;return 0;}
 CHECK(reg==&apc && minimum==maximum && minimum<=mx_actual && minimum%10000==0);
 /* Regulator consumer requests are restored on error and skip identical votes. */
 if(apc_cached==minimum)return 0;
 int ret=spmi_saw_fts2_set(&physical,1,minimum/10000);
 if(!ret)apc_cached=minimum;
 return ret;
}
static void cpr_ctl_disable(struct cpr_drv *drv) {(void)drv;}
static void cpr_irq_clr(struct cpr_drv *drv) {(void)drv;}
static void cpr_corner_restore(struct cpr_drv *drv,struct corner *corner) {(void)drv;(void)corner;}
static void cpr_ctl_enable(struct cpr_drv *drv,struct corner *corner) {CHECK(drv->msm8926->applied);(void)corner;}
static int cpr_scale_voltage(struct cpr_drv *drv,struct corner *corner,int voltage,enum voltage_change_dir dir) {
 (void)dir;return cpr_voltage_set(&drv->rails,voltage,corner->mx_min_uV);
}
static struct generic_pm_domain *dev_to_genpd(struct device *dev) {return dev->pd;}
static struct generic_pm_domain_data *dev_gpd_data(struct device *dev) {return &dev->data;}
static unsigned int _genpd_reeval_performance_state(struct generic_pm_domain *pd,unsigned int state) {(void)pd;return state;}
static int _genpd_set_parent_state(struct generic_pm_domain *pd,struct gpd_link *link,unsigned int state,int depth) {
 (void)pd;(void)link;(void)state;(void)depth;CHECK(0);return -EIO;
}
static void _genpd_rollback_parent_state(struct gpd_link *link,int depth) {(void)link;(void)depth;CHECK(0);}
static int genpd_set_performance_state(struct device *,unsigned int);
static int dev_pm_domain_set_performance_state(struct device *dev,unsigned int level) {return genpd_set_performance_state(dev,level);}
static bool lazy_linking_pending(struct opp_table *table) {(void)table;return false;}
static void dev_pm_opp_put(struct dev_pm_opp *opp) {CHECK(opp);}
static struct dev_pm_opp *dev_pm_opp_get(struct dev_pm_opp *opp) {return opp;}
static int _disable_opp_table(struct device *dev,struct opp_table *table) {(void)dev;(void)table;CHECK(0);return -EINVAL;}
static void _find_current_opp(struct device *dev,struct opp_table *table) {(void)dev;(void)table;CHECK(0);}
static int _opp_compare_key(struct opp_table *table,struct dev_pm_opp *a,struct dev_pm_opp *b) {
 (void)table;return a->rates[0]>b->rates[0]?1:a->rates[0]<b->rates[0]?-1:0;
}
static int _set_opp_bw(struct opp_table *table,struct dev_pm_opp *opp,struct device *dev) {(void)table;(void)opp;(void)dev;return 0;}
static int clock_set(struct device *dev,struct opp_table *table,struct dev_pm_opp *opp,void *data,bool down) {
 (void)dev;(void)table;(void)data;(void)down;
 int minimum=opp->rates[0]>384000000?1140000:1080000;
 if((int)p[0x1741]*10000<minimum)unsafe_clock++;
 cpu_rate=opp->rates[0];return 0;
}
'''

MAIN = r'''
int main(void) {
 int total_unsafe=0,cases=0;
#ifdef BROKEN_CONTROL
 const int last_failure=8; /* The old provider has no post-command verification. */
#else
 const int last_failure=10;
#endif
 for(int failure=7;failure<=last_failure;failure++)for(int followup=1;followup<=2;followup++) {
  physical=ready(1,0x80);p[0x1741]=s[0x14]=target=128;
  apc_cached=1280000;mx_actual=1287500;cpu_rate=1190400000;unsafe_clock=0;
  struct corner corners[]={{1080000,1080000,1087500},{1140000,1140000,1287500},{1140000,1280000,1287500}};
  struct cpr_msm8926_data data={.applied=true};
  struct device cpu={0},pddev={0};
  struct cpr_drv drv={.dev=&cpu,.initialized=true,.corners=corners,.corner=&corners[2],
   .msm8926=&data,.num_corners=3,.rails={.apc=&apc,.mx=&mx,.mx_enabled=true,.mx_min_uV=1287500,.mx_max_uV=1337500},
   .pd={.performance_state=3,.set_performance_state=cpr_set_performance_state}};
  pddev.pd=&drv.pd;pddev.data.performance_state=3;
  struct device *required[]={&pddev};
  struct dev_pm_opp pdopps[]={ {.level=1},{.level=2},{.level=3} };
  struct dev_pm_opp opps[]={
   {.rates={300000000},.level=OPP_LEVEL_UNSET,.required_opps={&pdopps[0]}},
   {.rates={998400000},.level=OPP_LEVEL_UNSET,.required_opps={&pdopps[1]}},
   {.rates={1190400000},.level=OPP_LEVEL_UNSET,.required_opps={&pdopps[2]}}};
  struct opp_table table={.current_opp=&opps[2],.enabled=true,.required_devs=required,.required_opp_count=1,.config_clks=clock_set};
  fail_at=failure;commit_error=1;
  CHECK(_set_opp(&cpu,&table,&opps[0],NULL,true)==-EIO);
  CHECK(cpu_rate==300000000 && table.current_opp==&opps[2]);
  CHECK(drv.pd.performance_state==3 && pddev.data.performance_state==3 && drv.corner==&corners[2]);
  CHECK(apc_cached==1280000 && mx_actual==1287500 && data.applied);
#ifdef BROKEN_CONTROL
  CHECK(p[0x1741]==108);
#else
  CHECK(p[0x1741]==128);
#endif
  clear_trace();
  CHECK(!_set_opp(&cpu,&table,&opps[followup],NULL,true));
  CHECK(cpu_rate==opps[followup].rates[0]);
  total_unsafe+=unsafe_clock;cases++;
 }
#ifdef BROKEN_CONTROL
 CHECK(total_unsafe==4);
#else
 CHECK(total_unsafe==0);
#endif
 printf("actual OPP/genpd/CPR/SAW: %d changed-on-error cases, unsafe_clock=%d; contracts passed\n",cases,total_unsafe);
 return 0;
}
'''


def old_header():
    patch = (ROOT/'patches/linux-integration/fx0-pm8226-saw-fixed-range.diff').read_text()
    marker = '+++ b/drivers/regulator/qcom-spmi-saw-fts2.h\n'
    block = patch.split(marker, 1)[1].split('\ndiff --git ', 1)[0]
    return ''.join(line[1:]+'\n' for line in block.splitlines()
                   if line.startswith('+') and not line.startswith('+++')).encode()


def function(source, name):
    pattern = r'static\s+(?:int|void|bool)\s+' + re.escape(name) + r'\s*\([^;{}]*\)\s*\{'
    match = re.search(pattern, source)
    if not match:
        raise AssertionError('Missing actual definition: ' + name)
    end = source.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end] + '\n'


class CpuRecoveryTests(unittest.TestCase):
    run_harness = SAW.SawFts2Tests.run_harness

    def test_real_callers_with_fixed_and_broken_provider(self):
        cpr = (TREE/'drivers/pmdomain/qcom/cpr.c').read_text()
        genpd = (TREE/'drivers/pmdomain/core.c').read_text()
        opp = (TREE/'drivers/opp/core.c').read_text()
        functions = ''.join(function(source, name) for source, name in [
            (cpr, 'cpr_is_allowed'), (cpr, 'cpr_set_performance_state'),
            (genpd, '_genpd_set_performance_state'), (genpd, 'genpd_set_performance_state'),
            (opp, '_set_opp_level'), (opp, '_set_required_opps'), (opp, '_set_opp')])
        # The kernel permits unused parameters in these unmodified definitions.
        functions = ('#pragma GCC diagnostic push\n'
                     '#pragma GCC diagnostic ignored "-Wunused-parameter"\n'
                     + functions + '#pragma GCC diagnostic pop\n')
        program = SAW.HARNESS.split('int main(void)')[0] + STUBS + functions + MAIN
        headers = {'cpr-voltage.h': (TREE/'drivers/pmdomain/qcom/cpr-voltage.h').read_text(),
                   'linux/regulator/consumer.h': SAW_CONSUMER}
        fixed = self.run_harness(program, extra_headers=headers)
        self.assertIn('8 changed-on-error cases, unsafe_clock=0', fixed)
        broken = self.run_harness('#define BROKEN_CONTROL\n' + program,
                                  extra_headers=headers, header=old_header())
        self.assertIn('4 changed-on-error cases, unsafe_clock=4', broken)


SAW_CONSUMER = '''#include <stdbool.h>
struct regulator {int id;};
int regulator_set_voltage(struct regulator *,int,int);
int regulator_enable(struct regulator *);
int regulator_sync_voltage(struct regulator *);
'''

if __name__ == '__main__':
    unittest.main()
