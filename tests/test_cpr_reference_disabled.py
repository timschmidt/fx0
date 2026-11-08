"""Execute disabled-controller XO handoff despite retained measurement BUSY."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-xo-disabled'))


def fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tests'/(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


DOMAIN = fixture('test_msm8926_domain')
EXTRACT = fixture('test_cpr_runtime_clock').function


class DisabledReferenceTests(unittest.TestCase):
    def compile_run(self, base, text, extra_flags=()):
        source, binary = base/'test.c', base/'test'
        source.write_text(text)
        result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                 *extra_flags, '-I', str(base), str(source), '-o', str(binary)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(binary)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_probe_handoff_and_failure_publication(self):
        DOMAIN.FIXTURE.VoltagePlanTests.setUpClass()
        try:
            base = Path(DOMAIN.FIXTURE.VoltagePlanTests.tmp.name)
            directory = KERNEL/'drivers/pmdomain/qcom'
            (base/'cpr-msm8926-corner.h').write_bytes((directory/'cpr-msm8926-corner.h').read_bytes())
            stubs = DOMAIN.STUBS.replace('CHECK(!busy_cycles);', '').replace('struct regmap *apcs;', 'struct regmap *apcs;struct clk *aux_clk,*pll_clk;')
            stubs = stubs.replace('static struct clk provider_clock;',
                                 'static struct clk provider_clock;\n'
                                 'static unsigned long clk_get_rate(struct clk *clk) {CHECK(clk);return 600000000;}')
            stubs = stubs.replace('CHECK(dev && !strcmp(name,"cpu"));clock_gets++;',
                                 'CHECK(dev && (!strcmp(name,"cpu") || !strcmp(name,"aux") || !strcmp(name,"pll")));clock_gets++;')
            source = (directory/'cpr.c').read_text()
            functions = ''.join(EXTRACT(source, name) for name in
                                ['cpr_msm8926_check_refclock(', 'cpr_msm8926_init_refclock(',
                                 'cpr_msm8926_init(', 'cpr_msm8926_corner_init('])
            main = DOMAIN.MAIN.replace('int main(void)', 'static int base_main(void)').replace('clock_gets==1', 'clock_gets==3')
            main += r'''
int main(void) {
 CHECK(!base_main());
 for(int fault=0;fault<10;fault++) {
  struct fuse_corner fuses[3],before[3];struct corner corners[14];
  struct cpr_drv drv=reset(fuses,corners);
  memset(fuses,0x5a,sizeof(fuses));memcpy(before,fuses,sizeof(fuses));ref_source=0xa5;
  if(fault==0)mmio_drop_at=1;
  if(fault==1)mmio_drop_at=2;
  if(fault==2)mmio_bad_at=1;
  if(fault==3)mmio_bad_at=2;
  if(fault==4)mmio_bad_at=3;
  if(fault==5){ref_update_error=-EIO;ref_error_after=0;}
  if(fault==6){ref_update_error=-EIO;ref_error_after=1;}
  if(fault==7)drop_ref_write=1;
  if(fault==8)ref_read_error_at=1;
  if(fault==9){read_error=-EPROBE_DEFER;}
  int expected=fault==7?-EINVAL:fault==9?-EPROBE_DEFER:-EIO;
  CHECK(cpr_msm8926_init(&drv)==expected);
  CHECK(!drv.msm8926 && !drv.rails.mx && !clock_gets);
  CHECK(!memcmp(fuses,before,sizeof(fuses)));
  if(fault<4)CHECK(!ref_updates && ref_source==0xa5);
  if(fault!=0)CHECK(!cpr_regs[REG_RBIF_IRQ_EN(0)/4]);
  if(fault!=1)CHECK(!cpr_regs[REG_RBCPR_CTL/4]);
  free(allocation);
 }
 for(int inherited=0;inherited<2;inherited++) {
  struct fuse_corner fuses[3];struct corner corners[14];
  struct cpr_drv drv=reset(fuses,corners);ref_source=0xa4|inherited;busy_cycles=-1;
  CHECK(!cpr_msm8926_init(&drv));
  CHECK(ref_source==0xa4 && ref_updates==1 && ref_read_calls==1 && busy_cycles==-1);
  CHECK(!cpr_regs[REG_RBCPR_CTL/4] && !cpr_regs[REG_RBIF_IRQ_EN(0)/4]);
  CHECK(drv.msm8926 && !drv.msm8926->applied && !drv.msm8926->apc_enabled);
  CHECK(drv.msm8926->supported_hw==127 && boot_voltage==1150000);
  free(allocation);
 }
 puts("probe: AHB/XO inheritance, unrelated bits, retained BUSY, ten failures and unpublished state passed");
 return 0;
}
'''
            output = self.compile_run(base, DOMAIN.FIXTURE.WRAPPER+stubs+functions+main)
            self.assertIn('ten failures and unpublished state passed', output)
        finally:
            DOMAIN.FIXTURE.VoltagePlanTests.tearDownClass()

    def test_configuration_and_resume_keep_failed_handoff_stopped(self):
        source = (KERNEL/'drivers/pmdomain/qcom/cpr.c').read_text()
        definitions = source[source.index('/* Register Offsets'):source.index('enum voltage_change_dir')]
        # Use the same instrumented MMIO model as the full probe execution.
        model = DOMAIN.STUBS[DOMAIN.STUBS.index('#define REG_RBIF_IRQ_EN'):DOMAIN.STUBS.index('struct clk {')]
        model = model[model.index('static u32 cpr_regs'):].replace('CHECK(!busy_cycles);', '')
        stubs = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define EIO 5
#define EINVAL 22
#define ETIMEDOUT 110
#define BIT(x) (1U<<(x))
#define GENMASK(h,l) ((~0U>>(31-(h)))&(~0U<<(l)))
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define dev_dbg(...) ((void)0)
#define guard(x) (void)
typedef uint32_t u32;
struct regmap {int unused;};static struct regmap apcs;
static unsigned int ref_source;
static int read_error,drop_ref_write;
'''
        structures = r'''
struct cpr_desc {
 unsigned int gcnt_us,timer_delay_us,timer_cons_down,timer_cons_up;
 unsigned int clamp_timer_interval,up_threshold,down_threshold;
};
struct corner {u32 save_ctl,save_irq;};
struct cpr_msm8926_data {struct regmap *apcs;bool applied;};
struct cpr_drv {
 void *base;const struct cpr_desc *desc;struct cpr_msm8926_data *msm8926;
 struct corner *corners;unsigned int num_corners,ref_clk_khz,gcnt,flags;
 bool suspended;int lock;void *dev;
};
struct device {struct cpr_drv *drv;};
static struct cpr_drv *dev_get_drvdata(struct device *dev){return dev->drv;}
static void config_write(u32 value,void *address) {
 unsigned int offset=(char *)address-(char *)cpr_regs;
 if(offset!=REG_RBCPR_CTL && offset!=REG_RBIF_IRQ_EN(0) && offset!=REG_RBIF_IRQ_CLEAR)
  CHECK(!(ref_source&1) && ref_updates && ref_read_calls);
 writel(value,address);
}
#define writel_relaxed config_write
#define readl_relaxed readl
'''
        functions = ''.join(EXTRACT(source, name) for name in
                            ['cpr_write(', 'cpr_read(', 'cpr_irq_set(',
                             'cpr_msm8926_check_refclock(', 'cpr_msm8926_init_refclock(',
                             'cpr_config(', 'cpr_pm_resume('])
        main = r'''
int main(void) {
 struct cpr_desc desc={.gcnt_us=1,.timer_delay_us=5,.timer_cons_up=1,.timer_cons_down=1};
 struct corner corners[2];struct cpr_msm8926_data data={.apcs=&apcs};
 struct cpr_drv drv={.base=cpr_regs,.desc=&desc,.msm8926=&data,.corners=corners,
                    .num_corners=2,.ref_clk_khz=19200};
 struct device dev={.drv=&drv};
 for(int fault=0;fault<8;fault++) {
  reset_refclock();ref_source=0xa5;read_error=0;drv.suspended=true;data.applied=false;
  memset(corners,0x5a,sizeof(corners));struct corner before[2];memcpy(before,corners,sizeof(before));
  if(fault==0)mmio_drop_at=1;
  if(fault==1)mmio_drop_at=2;
  if(fault==2)mmio_bad_at=4;
  if(fault==3)ref_update_error=-EIO;
  if(fault==4){ref_update_error=-EIO;ref_error_after=1;}
  if(fault==5)drop_ref_write=1;
  if(fault==6)ref_read_error_at=1;
  if(fault==7)read_error=-EIO;
  int expected=fault==5?-EINVAL:-EIO;
  CHECK(cpr_pm_resume(&dev)==expected);
  CHECK(drv.suspended && !data.applied && !memcmp(before,corners,sizeof(before)));
  CHECK(!cpr_regs[REG_RBIF_LIMIT/4] && !cpr_regs[REG_RBCPR_TIMER_INTERVAL/4]);
  if(fault!=0)CHECK(!cpr_regs[REG_RBIF_IRQ_EN(0)/4]);
  if(fault!=1)CHECK(!cpr_regs[REG_RBCPR_CTL/4]);
 }
 reset_refclock();ref_source=0xa5;read_error=0;busy_cycles=-1;
 CHECK(!cpr_pm_resume(&dev) && !drv.suspended && !data.applied);
 CHECK(ref_source==0xa4 && ref_updates==1 && ref_read_calls==1 && busy_cycles==-1);
 CHECK(!(cpr_regs[REG_RBCPR_CTL/4]&RBCPR_CTL_LOOP_EN));
 CHECK(cpr_regs[REG_RBCPR_TIMER_INTERVAL/4]==96);
 CHECK(corners[0].save_irq==CPR_INT_DEFAULT && corners[1].save_ctl==corners[0].save_ctl);
 /* A second configuration reestablishes XO; no cached selector assumption. */
 ref_source|=1;CHECK(!cpr_config(&drv));CHECK(ref_source==0xa4 && ref_updates==2);
 /* Legacy QCS404 resume does not touch the new selector or controller. */
 drv.msm8926=NULL;int saved=mmio_writes;
 CHECK(!cpr_pm_resume(&dev) && saved==mmio_writes && ref_updates==2);
 puts("resume: eight failures retain suspension and precede target writes; retry and repeated XO selection passed");
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as temporary:
            # The unchanged cpr_config loop compares int i with unsigned num_corners.
            output = self.compile_run(Path(temporary), stubs+definitions+model+structures+functions+main,
                                      ('-Wno-sign-compare',))
            self.assertIn('eight failures retain suspension', output)


if __name__ == '__main__':
    unittest.main()
