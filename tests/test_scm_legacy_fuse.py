"""Compile the actual SCM fuse reader with a captured, fault-injected transport."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
SOURCE=Path(os.environ.get('FX0_SCM_SOURCE',KERNEL/'drivers/firmware/qcom/qcom_scm.c'))
INTERNAL=SOURCE.with_name('qcom_scm.h')
STUBS=r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
typedef uint32_t u32;typedef uint64_t u64;
#define EINVAL 22
#define EPROBE_DEFER 517
#define EOPNOTSUPP 95
#define EIO 5
#define ETIMEDOUT 110
#define QCOM_SCM_ARGS(n) (n)
#define ARM_SMCCC_OWNER_SIP 2
#define CHECK(x) do { if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);} } while(0)
struct device {int dummy;};
struct qcom_scm_desc {u32 svc,cmd,arginfo;u64 args[2];u32 owner;};
struct qcom_scm_res {u64 result[3];};
static struct device device;
static struct {struct device *dev;} scm={&device};
static __typeof__(scm) *__scm=&scm;
static bool available;
static enum qcom_scm_convention convention;
static int calls,availability_checks,convention_checks,transport_rc;
static struct qcom_scm_desc captured;
static struct qcom_scm_res reply;
static bool qcom_scm_is_available(void) {availability_checks++;return available;}
static enum qcom_scm_convention __get_convention(void) {convention_checks++;return convention;}
static int qcom_scm_call(struct device *dev,const struct qcom_scm_desc *desc,struct qcom_scm_res *res) {
 CHECK(dev==&device);calls++;captured=*desc;*res=reply;return transport_rc;
}
'''
CASES=r'''
static void reset(void) {
 available=true;convention=SMC_CONVENTION_LEGACY;calls=availability_checks=convention_checks=transport_rc=0;
 reply=(struct qcom_scm_res){.result={0x76543210,0xfedcba98,0}};
}
int main(void) {
 const u32 address=0xfc4b81b0;const u64 sentinel=0x1122334455667788ULL;u64 value;
 reset();CHECK(qcom_scm_legacy_fuse_read(address,NULL)==-EINVAL);CHECK(!calls && !availability_checks && !convention_checks);
 reset();value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address+4,&value)==-EINVAL);CHECK(value==sentinel && !calls && !availability_checks);
 reset();available=false;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EPROBE_DEFER);CHECK(value==sentinel && !calls && !convention_checks);
 reset();convention=SMC_CONVENTION_ARM_32;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EOPNOTSUPP);CHECK(value==sentinel && !calls);
 reset();convention=SMC_CONVENTION_ARM_64;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EOPNOTSUPP);CHECK(value==sentinel && !calls);
 reset();convention=SMC_CONVENTION_UNKNOWN;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EOPNOTSUPP);CHECK(value==sentinel && !calls);
 reset();CHECK(!qcom_scm_legacy_fuse_read(address,&value));CHECK(calls==1 && value==0xfedcba9876543210ULL);CHECK(captured.svc==8 && captured.cmd==7 && captured.arginfo==2 && captured.owner==2);CHECK(captured.args[0]==address && captured.args[1]==0);
 reset();transport_rc=-ETIMEDOUT;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-ETIMEDOUT);CHECK(value==sentinel && calls==1);
 reset();transport_rc=3;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EIO);CHECK(value==sentinel && calls==1);
 reset();reply.result[2]=7;value=sentinel;CHECK(qcom_scm_legacy_fuse_read(address,&value)==-EIO);CHECK(value==sentinel && calls==1);
 reset();reply.result[0]|=0xfeedface00000000ULL;reply.result[1]|=0xdeadbeef00000000ULL;CHECK(!qcom_scm_legacy_fuse_read(address,&value));CHECK(value==0xfedcba9876543210ULL);
 reset();reply.result[0]=reply.result[1]=0;CHECK(!qcom_scm_legacy_fuse_read(address,&value));CHECK(value==0);
 reset();CHECK(!qcom_scm_legacy_fuse_read(0xfffffff8,&value));CHECK(captured.args[0]==0xfffffff8ULL);
 puts("13 actual-API contracts passed");return 0;
}
'''

@unittest.skipUnless(SOURCE.exists(),'Candidate SCM source required')
class ScmLegacyFuseTests(unittest.TestCase):
    def test_descriptor_convention_status_and_output_contracts(self):
        source=SOURCE.read_text();header=INTERNAL.read_text();enum=re.search(r'enum qcom_scm_convention\s*\{.*?\};',header,re.S).group(0)
        constants='\n'.join(line for line in header.splitlines() if line.startswith(('#define QCOM_SCM_SVC_FUSE\t','#define QCOM_SCM_FUSE_READ_LEGACY\t')))
        self.assertEqual(len(constants.splitlines()),2)
        start=source.index('int qcom_scm_legacy_fuse_read(');body=source.index('{',start);depth=1;end=body+1
        while depth:
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);c=base/'test.c';exe=base/'test';c.write_text(enum+'\n'+constants+'\n'+STUBS+'\n'+source[start:end]+'\n'+CASES)
            subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(c),'-o',str(exe)],check=True,capture_output=True,text=True)
            result=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
            self.assertIn('13 actual-API contracts passed',result.stdout)
if __name__=='__main__':unittest.main()
