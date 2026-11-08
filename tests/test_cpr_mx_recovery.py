"""Execute CPR MX recovery through the real regulator sync and RPM callbacks."""
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
TREE = KERNEL
spec = importlib.util.spec_from_file_location('rpm_fixture', ROOT/'tests/test_smd_rpm_ack.py')
FIXTURE = importlib.util.module_from_spec(spec)
spec.loader.exec_module(FIXTURE)

PREFIX = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <stddef.h>
#include <string.h>
#include <setjmp.h>
typedef uint32_t u32;
typedef uint32_t __le32;
#define EINVAL 22
#define EIO 5
#define ETIMEDOUT 110
#define PM_SUSPEND_ON 0
#define REGULATOR_CHANGE_VOLTAGE 1
#define QCOM_SMD_RPM_ACTIVE_STATE 0
#define cpu_to_le32(v) (v)
#define RPM_KEY_SWEN 0x6e657773
#define RPM_KEY_UV 0x00007675
#define RPM_KEY_MA 0x0000616d
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct regulator_dev;
struct regulator_ops {
 int (*set_voltage)(struct regulator_dev *,int,int,unsigned int *);
 int (*set_voltage_sel)(struct regulator_dev *,unsigned int);
};
struct regulator_desc {const struct regulator_ops *ops;};
struct qcom_rpm_reg {
 u32 type,id,load;
 int is_enabled,uV;
 bool enabled_updated,uv_updated,load_updated;
};
struct rpm_regulator_req {__le32 key,nbytes,value;};
struct regulator_dev {struct qcom_rpm_reg *data;const struct regulator_desc *desc;struct {int n_coupled;} coupling_desc;bool held;};
struct regulator_voltage {int min_uV,max_uV;};
struct regulator {struct regulator_dev *rdev;struct regulator_voltage voltage[1];};
static int physical_mx,physical_apc,writes,syncs,apc_calls,first_fault,second_fault,committed,persistent,panics,expect_panic;
static void *smd_vreg_rpm;
static struct regulator apc,mx;
static struct regulator_dev mxdev;
static struct qcom_rpm_reg vreg;
static jmp_buf panic_jump;
void panic(const char *format,...){(void)format;panics++;if(expect_panic)longjmp(panic_jump,1);exit(99);}
static void regulator_lock(struct regulator_dev *rdev){CHECK(!rdev->held);rdev->held=true;}
static void regulator_unlock(struct regulator_dev *rdev){CHECK(rdev->held);rdev->held=false;}
static bool regulator_ops_is_valid(struct regulator_dev *rdev,int mask){(void)rdev;CHECK(mask==REGULATOR_CHANGE_VOLTAGE);return true;}
static int regulator_check_voltage(struct regulator_dev *rdev,int *min,int *max){(void)rdev;CHECK(*min>0 && *min<=*max);return 0;}
static int regulator_check_consumers(struct regulator_dev *rdev,int *min,int *max,int state){(void)rdev;(void)min;(void)max;CHECK(state==PM_SUSPEND_ON);return 0;}
static int regulator_balance_voltage(struct regulator_dev *rdev,int state){(void)rdev;(void)state;CHECK(0);return -EINVAL;}
static int _regulator_do_set_voltage(struct regulator_dev *rdev,int min,int max){unsigned int selector;CHECK(rdev->held);syncs++;return rdev->desc->ops->set_voltage(rdev,min,max,&selector);}
#define rdev_get_drvdata(rdev) ((rdev)->data)
static int qcom_rpm_smd_write(void *rpm,int state,u32 type,u32 id,void *data,size_t count) {
 (void)rpm;(void)type;(void)id;CHECK(state==QCOM_SMD_RPM_ACTIVE_STATE && mxdev.held);
 CHECK(count==sizeof(struct rpm_regulator_req));
 struct rpm_regulator_req *req=data;CHECK(req->key==RPM_KEY_UV && req->nbytes==4);
 CHECK((int)req->value>=physical_apc);writes++;
 int fail=writes==first_fault||writes==second_fault||(persistent&&writes>=2);
 if(fail&&!committed)return -ETIMEDOUT;
 physical_mx=req->value;
 return fail?-ETIMEDOUT:0;
}
'''

ADAPTER = r'''
static const struct regulator_ops ops={.set_voltage=rpm_reg_set_voltage};
static const struct regulator_desc desc={.ops=&ops};
int regulator_enable(struct regulator *reg){(void)reg;return 0;}
int regulator_set_voltage(struct regulator *reg,int min,int max) {
 if(reg==&apc){CHECK(min==max && min<=physical_mx);physical_apc=min;apc_calls++;return 0;}
 CHECK(reg==&mx);
 /* Model consumer caching; sync below is the actual kernel implementation. */
 struct regulator_voltage before=reg->voltage[0];
 if(before.min_uV==min && before.max_uV==max)return 0;
 regulator_lock(reg->rdev);reg->voltage[0]=(struct regulator_voltage){min,max};
 unsigned int selector;int ret=rpm_reg_set_voltage(reg->rdev,min,max,&selector);
 if(ret)reg->voltage[0]=before;
 regulator_unlock(reg->rdev);return ret;
}
'''

MAIN = r'''
static struct cpr_voltage reset(int high) {
 physical_apc=high?1250000:1080000;physical_mx=high?1287500:1087500;
 writes=syncs=apc_calls=first_fault=second_fault=committed=persistent=panics=expect_panic=0;
 vreg=(struct qcom_rpm_reg){.is_enabled=1,.uV=physical_mx};
 mxdev=(struct regulator_dev){.data=&vreg,.desc=&desc,.coupling_desc={1}};
 mx=(struct regulator){.rdev=&mxdev,.voltage={{physical_mx,1337500}}};
 return (struct cpr_voltage){.apc=&apc,.mx=&mx,.mx_enabled=true,.mx_min_uV=physical_mx,.mx_max_uV=1337500};
}
static struct cpr_voltage fatal_rails;
static void fatal_case(int after_effect) {
 fatal_rails=reset(1);first_fault=1;committed=after_effect;persistent=1;expect_panic=1;
 if(!setjmp(panic_jump)) {
  (void)cpr_voltage_set(&fatal_rails,1080000,1087500);
  CHECK(0);
 }
 CHECK(panics==1 && writes==3 && syncs==2 && apc_calls==1 && !mxdev.held);
}
int main(void) {
 struct cpr_voltage rails;
 for(int after_effect=0;after_effect<2;after_effect++) {
  rails=reset(1);first_fault=1;committed=after_effect;
  CHECK(!cpr_voltage_set(&rails,1080000,1087500));
  CHECK(rails.mx_lower_error==-ETIMEDOUT && rails.mx_min_uV==1287500);
  CHECK(physical_apc==1080000 && physical_mx==1287500 && vreg.uV==1287500);
  CHECK(writes==2 && syncs==1 && !panics);
  first_fault=0;CHECK(!cpr_voltage_set(&rails,1250000,1287500));
  CHECK(physical_apc==1250000 && physical_mx>=physical_apc);
  rails=reset(0);first_fault=1;committed=after_effect;
  CHECK(cpr_voltage_set(&rails,1250000,1287500)==-ETIMEDOUT);
  CHECK(!apc_calls && physical_apc==1080000 && physical_mx==1087500 && rails.mx_min_uV==1087500);
  CHECK(writes==2 && syncs==1 && !panics);
  rails=reset(1);first_fault=1;second_fault=2;committed=after_effect;
  CHECK(!cpr_voltage_set(&rails,1080000,1087500));
  CHECK(physical_mx==1287500 && writes==3 && syncs==2 && !panics);
  fatal_case(after_effect);
 }
 puts("MX before/after-effect failures, forced old-vote sync, retry and persistent fail-stop contracts passed");
 return 0;
}
'''


class MxRecoveryTests(unittest.TestCase):
    def test_actual_sync_and_rpm_callbacks(self):
        rpm = (TREE/'drivers/regulator/qcom_smd-regulator.c').read_text()
        core = (TREE/'drivers/regulator/core.c').read_text()
        functions = (FIXTURE.definition(rpm, 'rpm_reg_write_active')
                     + FIXTURE.definition(rpm, 'rpm_reg_set_voltage')
                     + FIXTURE.definition(core, 'regulator_sync_voltage'))
        functions = ('#pragma GCC diagnostic push\n'
                     '#pragma GCC diagnostic ignored "-Wunused-parameter"\n'
                     + functions + '#pragma GCC diagnostic pop\n')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base/'linux/regulator').mkdir(parents=True)
            (base/'linux/regulator/consumer.h').write_text(
                'int regulator_set_voltage(struct regulator *,int,int);\n'
                'int regulator_enable(struct regulator *);\n'
                'int regulator_sync_voltage(struct regulator *);\n')
            (base/'linux/errno.h').write_text('')
            (base/'linux/panic.h').write_text('void panic(const char *,...) __attribute__((noreturn));\n')
            (base/'cpr-voltage.h').write_bytes((TREE/'drivers/pmdomain/qcom/cpr-voltage.h').read_bytes())
            source, executable = base/'test.c', base/'test'
            source.write_text(PREFIX + functions + ADAPTER + '\n#include "cpr-voltage.h"\n' + MAIN)
            compiled = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                       '-I', str(base), str(source), '-o', str(executable)], capture_output=True, text=True)
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            result = subprocess.run([str(executable)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('forced old-vote sync, retry and persistent fail-stop contracts passed', result.stdout)


if __name__ == '__main__':
    unittest.main()
