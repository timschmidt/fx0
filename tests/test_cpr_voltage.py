"""Compile the actual regulator-sequencing helper with fault-injected rails."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
HEADER=Path(os.environ.get('FX0_CPR_VOLTAGE_HEADER',KERNEL/'drivers/pmdomain/qcom/cpr-voltage.h'))
CONSUMER='''#include <stdbool.h>
struct regulator { int id; };
int regulator_set_voltage(struct regulator *, int, int);
int regulator_enable(struct regulator *);
int regulator_sync_voltage(struct regulator *);
'''
HARNESS=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "cpr-voltage.h"
#define EIO 5
#define CHECK(x) do { if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
struct call { int id,min,max; } calls[20];
static struct regulator apc={0},mx={1};
static int n,fail_at,apc_actual,mx_actual,check_mx,enable_calls,enable_error,mx_active,mx_requested;
void panic(const char *format, ...) { (void)format; fprintf(stderr,"unexpected MX recovery failure\n"); exit(99); }
int regulator_sync_voltage(struct regulator *reg) { CHECK(reg==&mx); mx_actual=mx_requested;return 0; }
int regulator_enable(struct regulator *reg) { CHECK(reg==&mx); enable_calls++; if(enable_error)return enable_error; CHECK(mx_requested>=apc_actual); mx_actual=mx_requested; mx_active=1; return 0; }
int regulator_set_voltage(struct regulator *reg,int min,int max) {
 CHECK(n<20 && min<=max);calls[n++]=(struct call){reg->id,min,max};
 if(n==fail_at)return -EIO;
 if(reg->id==0) { if(check_mx)CHECK(min<=mx_actual);apc_actual=min; }
 else { CHECK(min>=apc_actual);mx_requested=min;if(mx_active)mx_actual=min; }
 return 0;
}
static struct cpr_voltage reset(int coupled) {
 enable_calls=enable_error=0;n=fail_at=0;memset(calls,0,sizeof(calls));apc_actual=1150000;mx_requested=mx_actual=1175000;mx_active=1;check_mx=coupled;
 return (struct cpr_voltage){.apc=&apc,.mx=coupled?&mx:NULL,.mx_enabled=coupled,.mx_max_uV=1337500,.mx_min_uV=coupled?1175000:0};
}
static void high(struct cpr_voltage *r) { r->mx_min_uV=mx_actual=mx_requested=1280000;apc_actual=1250000; }
int main(void) {
 struct cpr_voltage r;
 r=reset(0);CHECK(!cpr_voltage_set(&r,1100000,0));CHECK(n==1 && calls[0].id==0 && calls[0].min==calls[0].max);CHECK(!cpr_voltage_bootstrap(&r,0));
 r=reset(1);r.mx_min_uV=0;CHECK(!cpr_voltage_bootstrap(&r,1280000));CHECK(n==1 && calls[0].id==1 && calls[0].max==1337500 && r.mx_min_uV==1280000);
 apc_actual=1250000;CHECK(!cpr_voltage_bootstrap(&r,1175000));CHECK(n==1 && r.mx_min_uV==1280000);
 r=reset(1);CHECK(!cpr_voltage_set(&r,1250000,1280000));CHECK(n==2 && calls[0].id==1 && calls[1].id==0 && r.mx_min_uV==1280000);
 r=reset(1);high(&r);CHECK(!cpr_voltage_set(&r,1100000,1175000));CHECK(n==2 && calls[0].id==0 && calls[1].id==1 && r.mx_min_uV==1175000);
 r=reset(1);fail_at=1;CHECK(cpr_voltage_set(&r,1250000,1280000)==-EIO);CHECK(n==1 && calls[0].id==1 && apc_actual==1150000 && r.mx_min_uV==1175000);
 r=reset(1);fail_at=2;CHECK(cpr_voltage_set(&r,1250000,1280000)==-EIO);CHECK(n==2 && mx_actual==1280000 && r.mx_min_uV==1280000 && apc_actual==1150000);
 r=reset(1);high(&r);fail_at=1;CHECK(cpr_voltage_set(&r,1100000,1175000)==-EIO);CHECK(n==1 && mx_actual==1280000 && r.mx_min_uV==1280000);
 r=reset(1);high(&r);fail_at=2;CHECK(!cpr_voltage_set(&r,1100000,1175000));CHECK(r.mx_lower_error==-EIO && apc_actual==1100000 && mx_actual==1280000 && r.mx_min_uV==1280000);
 fail_at=0;n=0;CHECK(!cpr_voltage_set(&r,1100000,1175000));CHECK(n==2 && !r.mx_lower_error && r.mx_min_uV==1175000);
 r=reset(1);r.mx_min_uV=0;CHECK(cpr_voltage_set(&r,1250000,1280000)==-EINVAL);CHECK(!n);
 r=reset(1);CHECK(cpr_voltage_set(&r,0,1280000)==-EINVAL);CHECK(!n);
 CHECK(cpr_voltage_set(&r,1200000,1175000)==-EINVAL);CHECK(!n);
 CHECK(cpr_voltage_set(&r,1100000,1400000)==-EINVAL);CHECK(!n);
 CHECK(cpr_voltage_bootstrap(&r,1400000)==-EINVAL);CHECK(!n);
 r=reset(1);r.mx_min_uV=0;fail_at=1;CHECK(cpr_voltage_bootstrap(&r,1280000)==-EIO);CHECK(r.mx_min_uV==0 && n==1);
 r=reset(1);r.mx_min_uV=1400000;CHECK(cpr_voltage_bootstrap(&r,1280000)==-EINVAL);CHECK(!n);
 r=reset(1);CHECK(!cpr_voltage_set(&r,1100000,1175000));CHECK(n==1 && calls[0].id==0);
 r=reset(1);r.mx_enabled=0;r.mx_min_uV=0;mx_active=0;
 CHECK(cpr_voltage_set(&r,1100000,1175000)==-EINVAL);CHECK(!n && !enable_calls);
 enable_error=-EIO;CHECK(cpr_voltage_bootstrap(&r,1280000)==-EIO);
 CHECK(n==1 && enable_calls==1 && !r.mx_enabled && r.mx_min_uV==1280000);
 CHECK(!mx_active && mx_actual==1175000 && mx_requested==1280000);
 CHECK(cpr_voltage_set(&r,1100000,1175000)==-EINVAL);CHECK(n==1);
 enable_error=0;CHECK(!cpr_voltage_bootstrap(&r,1175000));
 CHECK(n==1 && enable_calls==2 && r.mx_enabled && r.mx_min_uV==1280000);
 CHECK(mx_active && mx_actual==1280000);
 CHECK(!cpr_voltage_bootstrap(&r,1175000));CHECK(n==1 && enable_calls==2);
 CHECK(!cpr_voltage_set(&r,1100000,1175000));CHECK(n==3 && enable_calls==2);
 r=reset(1);r.mx_enabled=0;r.mx_min_uV=0;mx_active=0;fail_at=1;
 CHECK(cpr_voltage_bootstrap(&r,1280000)==-EIO);CHECK(!enable_calls && !r.mx_enabled);
 puts("18 sequencing/failure contracts passed; MX activation contracts passed");return 0;
}
'''

@unittest.skipUnless(HEADER.exists(),'Candidate CPR voltage helper required')
class CprVoltageTests(unittest.TestCase):
    def test_sequencing_and_failures(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);(base/'linux/regulator').mkdir(parents=True)
            (base/'linux/regulator/consumer.h').write_text(CONSUMER)
            (base/'linux/errno.h').write_text('#define EINVAL 22\n')
            (base/'linux/panic.h').write_text('void panic(const char *,...) __attribute__((noreturn));\n')
            (base/'cpr-voltage.h').write_bytes(HEADER.read_bytes());source=base/'test.c';source.write_text(HARNESS);exe=base/'test'
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I',str(base),str(source),'-o',str(exe)],check=True,capture_output=True,text=True)
            result=subprocess.run([str(exe)],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('18 sequencing/failure contracts passed',result.stdout)
if __name__=='__main__':unittest.main()
