"""Exercise actual CPR state/PM callbacks before enabling an Fx0 CPU domain."""
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE = KERNEL/'drivers/pmdomain/qcom/cpr.c'
spec = importlib.util.spec_from_file_location('domain_fixture', ROOT/'tests/test_msm8926_domain.py')
FIXTURE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FIXTURE)

STUBS = r'''
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EINVAL 22
#define EBUSY 16
#define EIO 5
#define EOPNOTSUPP 95
#define EPROBE_DEFER 517
#define PM_SUSPEND_TO_IDLE 1
#define guard(x) (void)
#define dev_dbg(...) ((void)0)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct cpr_drv;
struct device { struct cpr_drv *drv; };
struct generic_pm_domain { int unused; };
struct corner { int uV,last_uV; };
struct cpr_msm8926_data { bool applied,apc_enabled; };
struct cpr_drv {
 struct generic_pm_domain pd;
 struct device *dev;
 bool initialized;
 struct corner *corner,*corners;
 struct cpr_msm8926_data *msm8926;
 int lock;
 unsigned int num_corners;
 bool loop_disabled,suspended;
 struct {void *apc;bool mx_enabled;} rails;
};
enum voltage_change_dir {NO_CHANGE,DOWN,UP};
static int n,fail_voltage,new_voltage,configured,loop_enabled,apc_enables,apc_disables,config_error;
static int pm_suspend_target_state;
static char calls[64];
static void call(char op) {CHECK(n<63);calls[n++]=op;}
static struct cpr_drv *dev_get_drvdata(struct device *dev) {return dev->drv;}
static void mutex_lock(int *lock) {(void)lock;}
static void mutex_unlock(int *lock) {(void)lock;}
static int regulator_enable(void *reg) {(void)reg;apc_enables++;return 0;}
static int regulator_disable(void *reg) {(void)reg;apc_disables++;return 0;}
static void cpr_irq_clr(struct cpr_drv *drv) {(void)drv;call('I');}
static void cpr_ctl_disable(struct cpr_drv *drv) {(void)drv;call('D');loop_enabled=0;}
static void cpr_corner_save(struct cpr_drv *drv,struct corner *corner) {(void)drv;(void)corner;call('S');}
static void cpr_corner_restore(struct cpr_drv *drv,struct corner *corner) {(void)drv;(void)corner;call('R');}
static void cpr_ctl_enable(struct cpr_drv *drv,struct corner *corner) {
 CHECK(drv->msm8926->applied && !drv->suspended);(void)corner;call('E');loop_enabled=1;
}
static int cpr_scale_voltage(struct cpr_drv *drv,struct corner *corner,int voltage,enum voltage_change_dir dir) {
 (void)drv;(void)corner;(void)dir;call('V');new_voltage=voltage;return fail_voltage?-EIO:0;
}
static int cpr_config(struct cpr_drv *drv) {(void)drv;configured++;loop_enabled=0;return config_error;}
'''

MAIN = r'''
int main(void) {
 struct corner corners[]={{1080000,1100000},{1140000,1160000}};
 struct cpr_msm8926_data data={0};
 struct device dev;
 struct cpr_drv drv={.dev=&dev,.initialized=true,.corners=corners,.corner=&corners[0],.num_corners=2,.msm8926=&data};
 dev.drv=&drv;
 CHECK(!cpr_is_allowed(&drv));
 CHECK(cpr_enable(&drv)==-EPROBE_DEFER && !apc_enables);
 drv.rails.mx_enabled=true;
 CHECK(!cpr_enable(&drv) && data.apc_enabled && apc_enables==1 && !loop_enabled);
 CHECK(!cpr_enable(&drv) && apc_enables==1 && !loop_enabled);
 n=0;CHECK(!cpr_set_performance_state(&drv.pd,2));
 CHECK(new_voltage==1140000 && data.applied && drv.corner==&corners[1]);
 CHECK(n==4 && !memcmp(calls,"VIRE",4));
 CHECK(corners[1].last_uV==1140000 && loop_enabled);
 n=0;CHECK(!cpr_set_performance_state(&drv.pd,1));
 CHECK(new_voltage==1100000 && n==5 && !memcmp(calls,"DVIRE",5));
 fail_voltage=1;n=0;CHECK(cpr_set_performance_state(&drv.pd,2)==-EIO);
 CHECK(data.applied && loop_enabled && drv.corner==&corners[0]);
 CHECK(n==5 && !memcmp(calls,"DVIRE",5));
 fail_voltage=0;n=0;CHECK(!cpr_set_performance_state(&drv.pd,2));
 CHECK(new_voltage==1140000 && data.applied && loop_enabled);
 CHECK(!cpr_set_performance_state(&drv.pd,0));
 CHECK(cpr_set_performance_state(&drv.pd,3)==-EINVAL);
 pm_suspend_target_state=1;CHECK(!cpr_pm_prepare(&dev));
 pm_suspend_target_state=3;CHECK(cpr_pm_prepare(&dev)==-EOPNOTSUPP);
 n=0;CHECK(!cpr_pm_suspend(&dev));
 CHECK(drv.suspended && !data.applied && !loop_enabled && !cpr_is_allowed(&drv));
 CHECK(cpr_set_performance_state(&drv.pd,1)==-EBUSY);
 config_error=-EINVAL;CHECK(cpr_pm_resume(&dev)==-EINVAL && drv.suspended && !data.applied && !loop_enabled);
 CHECK(cpr_set_performance_state(&drv.pd,1)==-EBUSY);
 config_error=0;CHECK(!cpr_pm_resume(&dev) && !drv.suspended && configured==2);
 CHECK(!data.applied && !loop_enabled);
 CHECK(!cpr_set_performance_state(&drv.pd,1) && new_voltage==1080000 && data.applied);
 CHECK(!cpr_disable(&drv) && !apc_disables && data.apc_enabled && drv.rails.mx_enabled);
 data.applied=false;fail_voltage=1;n=0;
 CHECK(cpr_set_performance_state(&drv.pd,2)==-EIO);
 CHECK(!data.applied && !loop_enabled && n==1 && calls[0]=='V');
 fail_voltage=0;
 /* QCS404 remains a no-op for the new PM callbacks. */
 drv.msm8926=NULL;configured=0;pm_suspend_target_state=3;
 CHECK(!cpr_pm_prepare(&dev) && !cpr_pm_suspend(&dev) && !cpr_pm_resume(&dev) && !configured);
 CHECK(cpr_set_performance_state(&drv.pd,0)==-EINVAL);
 CHECK(!cpr_disable(&drv) && apc_disables==1);
 puts("initial, failed, recovery and suspend callback ordering passed; retained MX/APC and legacy PM behavior passed");
 return 0;
}
'''


class DomainStateTests(unittest.TestCase):
    def test_state_and_pm_ordering(self):
        text = SOURCE.read_text()
        functions = ''.join(FIXTURE.function(text, name) for name in
                            ['cpr_is_allowed(', 'cpr_enable(', 'cpr_disable(',
                             'cpr_set_performance_state(', 'cpr_pm_prepare(',
                             'cpr_pm_suspend(', 'cpr_pm_resume('])
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            source, executable = base/'test.c', base/'test'
            source.write_text(STUBS + functions + MAIN)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     str(source), '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('initial, failed, recovery and suspend callback ordering passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
