"""Exercise the real context-probe fault-clear block with mocked PM/MMIO."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-6.18.63-r50'))
SOURCE = Path(os.environ.get('FX0_IOMMU_SOURCE', KERNEL/'drivers/iommu/arm/arm-smmu/qcom_iommu.c'))
SHIM = r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#define ARM_SMMU_CB_FSR 0x58
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"check failed at %d: %s\n",__LINE__,#x); exit(1); } } while (0)
struct device { struct device *parent; };
struct context { bool secured_ctx; };
struct iommu { void *cfg; };
static int events[8], count, power_error;
static bool powered;
static struct device parent_device;
static void event(int value) { CHECK(count<8); events[count++]=value; }
static int pm_runtime_resume_and_get(struct device *device) {
 CHECK(device==&parent_device); event(1);
 if (power_error) return power_error;
 CHECK(!powered); powered=true; return 0;
}
static unsigned iommu_readl(struct context *ctx, unsigned reg) {
 CHECK(ctx && reg==ARM_SMMU_CB_FSR && powered); event(2); return 0x1024;
}
static void iommu_writel(struct context *ctx, unsigned reg, unsigned value) {
 CHECK(ctx && reg==ARM_SMMU_CB_FSR && powered && value==0x1024); event(3);
}
static void pm_runtime_put_sync(struct device *device) {
 CHECK(device==&parent_device && powered); event(4); powered=false;
}
static int probe(bool secured, bool configured) {
 struct context context={.secured_ctx=secured}; struct context *ctx=&context;
 struct iommu iommu={.cfg=configured?&context:NULL}; struct iommu *qcom_iommu=&iommu;
 struct device device={.parent=&parent_device}; struct device *dev=&device;
 int ret=0;
 (void)qcom_iommu; (void)dev;
 (void)pm_runtime_resume_and_get; (void)pm_runtime_put_sync;
'''
MAIN = r'''
 return ret;
}
int main(int argc,char **argv) {
 CHECK(argc==2); int which=atoi(argv[1]); int result;
 if (which==0) {
  result=probe(false,false); CHECK(result==0 && count==4 && !powered);
  for(int i=0;i<4;i++) CHECK(events[i]==i+1);
 } else if (which==1) {
  power_error=-5; result=probe(false,false);
  CHECK(result==-5 && count==1 && events[0]==1 && !powered);
 } else if (which==2) {
  result=probe(true,false); CHECK(result==0 && count==0 && !powered);
 } else if (which==3) {
  result=probe(false,true); CHECK(result==0 && count==0 && !powered);
 } else if (which==4) {
  power_error=-5; result=probe(true,true); CHECK(result==0 && count==0 && !powered);
 } else CHECK(false);
 return 0;
}
'''


class ContextProbePowerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SOURCE.read_text()
        start = source.index('\t/* clear IRQs before registering fault handler')
        end = source.index('\n\tret = devm_request_irq', start)
        cls.directory = tempfile.TemporaryDirectory(prefix='fx0-iommu-probe-')
        base = Path(cls.directory.name)
        c_file = base/'probe.c'
        cls.executable = base/'probe'
        c_file.write_text(SHIM + source[start:end] + MAIN)
        result = subprocess.run(['/usr/bin/clang','-std=c11','-O1','-g',
                                 '-fsanitize=address,undefined','-Wall','-Wextra','-Werror',
                                 str(c_file),'-o',str(cls.executable)],
                                capture_output=True,text=True)
        if result.returncode:
            raise RuntimeError(result.stdout + result.stderr)

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def run_case(self, number):
        result = subprocess.run([str(self.executable),str(number)],
                                capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stdout+result.stderr)

    def test_legacy_fault_clear_is_powered_and_balanced(self):
        self.run_case(0)

    def test_failed_resume_returns_before_MMIO_or_put(self):
        self.run_case(1)

    def test_secured_legacy_context_is_untouched(self):
        self.run_case(2)

    def test_OS_managed_context_retains_r50_deferred_clear(self):
        self.run_case(3)

    def test_secured_OS_managed_context_is_untouched(self):
        self.run_case(4)


if __name__=='__main__':
    unittest.main()
