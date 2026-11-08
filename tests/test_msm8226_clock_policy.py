"""Execute real provider probes to check CPU-only failure and cache policies."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT / 'worktrees/linux-fx0-runtime'))
spec = importlib.util.spec_from_file_location('runtime', ROOT / 'tests/test_cpr_runtime_clock.py')
RUNTIME = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RUNTIME)

HARNESS = r'''
#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define GFP_KERNEL 0
#define ENOMEM 12
#define ENODEV 19
#define EPROBE_DEFER 517
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define __iomem
#define CLK_GET_RATE_NOCACHE 1UL
#define CLK_IS_CRITICAL 2UL
#define CLK_SET_RATE_PARENT 4UL
#define dev_err(...) ((void)0)
#define CHECK(x) do {if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
typedef uint32_t u32;
struct clk_parent_data {const char *fw_name,*name;};
struct clk_ops {int unused;};
struct clk_init_data {const char *name;const struct clk_parent_data *parent_data;int num_parents;const struct clk_ops *ops;unsigned long flags;};
struct clk_hw {const struct clk_init_data *init;};
struct regmap {int unused;};
struct clk_regmap {struct clk_hw hw;struct regmap *regmap;};
struct pll_freq_tbl {int unused;};
struct clk_pll {int l_reg,m_reg,n_reg,config_reg,mode_reg,status_reg,status_bit;bool critical_rate;const struct pll_freq_tbl *freq_tbl;struct clk_regmap clkr;};
struct notifier_block {int (*notifier_call)(struct notifier_block *,unsigned long,void *);};
struct clk_regmap_mux_div {
 int reg_offset,hid_width,hid_shift,src_width,src_shift;
 const u32 *parent_map;struct clk_regmap clkr;void *pclk;
 struct notifier_block clk_nb;bool critical_rate;
};
struct device_node {const char *full_name;bool msm8226;};
struct device {struct device *parent;struct device_node *of_node;};
struct platform_device {struct device dev;void *data;};
static const struct clk_ops clk_pll_sr2_ops,clk_regmap_mux_div_ops,clk_pll_ops;
static const struct pll_freq_tbl a53pll_freq[1];
static const u32 gpll0_a53cc_map[]={4,5};
static const struct clk_parent_data pdata[2];
static int a53pll_regmap_config;
static struct regmap map;
static void *allocated;
static unsigned long flags;
static const struct clk_ops *ops;
static bool parent_deferred;
static int of_clk_hw_simple_get;
static void *devm_kzalloc(struct device *dev,size_t size,int gfp) {(void)dev;(void)gfp;return allocated=calloc(1,size);}
static const char *devm_kasprintf(struct device *dev,int gfp,const char *fmt,const char *name) {(void)dev;(void)gfp;(void)fmt;(void)name;return "clock@unit";}
static bool of_device_is_compatible(struct device_node *node,const char *name) {CHECK(strstr(name,"msm8226"));return node->msm8226;}
static void *devm_platform_ioremap_resource(struct platform_device *pdev,int n) {(void)pdev;CHECK(!n);return &map;}
static struct regmap *devm_regmap_init_mmio(struct device *dev,void *base,const int *cfg) {(void)dev;CHECK(base==&map && cfg==&a53pll_regmap_config);return &map;}
static const struct pll_freq_tbl *qcom_a53pll_get_freq_tbl(struct device *dev) {(void)dev;return NULL;}
static int devm_clk_register_regmap(struct device *dev,struct clk_regmap *clkr) {(void)dev;flags=clkr->hw.init->flags;ops=clkr->hw.init->ops;return 0;}
static int devm_of_clk_add_hw_provider(struct device *dev,int get,struct clk_hw *hw) {(void)dev;(void)get;CHECK(hw);return 0;}
static struct regmap *dev_get_regmap(struct device *dev,const char *name) {(void)dev;(void)name;return &map;}
static void *devm_clk_get(struct device *dev,const char *name) {(void)dev;CHECK(!name);return parent_deferred?(void *)(intptr_t)-EPROBE_DEFER:(void *)1;}
static int a53cc_notifier_cb(struct notifier_block *nb,unsigned long event,void *data) {(void)nb;(void)event;(void)data;return 0;}
static int clk_notifier_register(void *clk,struct notifier_block *nb) {CHECK(clk==(void *)1 && nb->notifier_call==a53cc_notifier_cb);return 0;}
static void clk_notifier_unregister(void *clk,struct notifier_block *nb) {(void)clk;(void)nb;}
static void platform_set_drvdata(struct platform_device *pdev,void *data) {pdev->data=data;}
static struct {void *freq_tbl;} ce1_clk_src,gp1_clk_src,gp2_clk_src,gp3_clk_src;
static int ftbl_gcc_ce1_clk_msm8226[1],ftbl_gcc_gp_clk_msm8226[1];
'''

MAIN = r'''
int main(void) {
 for(int msm=0;msm<2;msm++) {
  struct device_node node={"/soc/clock@123",msm};
  struct device parent={.of_node=&node};
  struct platform_device pdev={.dev={.of_node=&node,.parent=&parent}};
  CHECK(!qcom_a53pll_probe(&pdev));
  struct clk_pll *pll=allocated;
  CHECK(pll->critical_rate==msm && flags==(msm?CLK_GET_RATE_NOCACHE:0));
  CHECK(ops==&clk_pll_sr2_ops);free(allocated);
  CHECK(!qcom_apcs_msm8916_clk_probe(&pdev));
  struct clk_regmap_mux_div *md=pdev.data;
  CHECK(md==allocated && md->critical_rate==msm);
  CHECK(flags==(CLK_IS_CRITICAL|CLK_SET_RATE_PARENT|(msm?CLK_GET_RATE_NOCACHE:0)));
  CHECK(ops==&clk_regmap_mux_div_ops);free(allocated);
  parent_deferred=true;
  CHECK(qcom_apcs_msm8916_clk_probe(&pdev)==-EPROBE_DEFER);free(allocated);parent_deferred=false;
 }
 CHECK(!gpll0_init.flags);msm8226_clock_override();CHECK(gpll0_init.flags==CLK_GET_RATE_NOCACHE);
 puts("actual PLL/APCS probes select CPU fail-stop and uncached reads only on MSM8226; aux PLL override enables fresh reads; parent defer passed");
 return 0;
}
'''


class ClockPolicyTests(unittest.TestCase):
    def test_supplier_owns_pll_handle_and_defers_without_activation(self):
        spec = importlib.util.spec_from_file_location('domain', ROOT / 'tests/test_msm8926_domain.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        fixture.FIXTURE.VoltagePlanTests.setUpClass()
        try:
            base = Path(fixture.FIXTURE.VoltagePlanTests.tmp.name)
            directory = KERNEL / 'drivers/pmdomain/qcom'
            (base / 'cpr-msm8926-corner.h').write_bytes((directory / 'cpr-msm8926-corner.h').read_bytes())
            stubs = fixture.STUBS.replace('struct regmap *apcs;', 'struct regmap *apcs;struct clk *aux_clk,*pll_clk;')
            stubs = stubs.replace('static struct clk provider_clock;',
                                 'static struct clk provider_clock;\nstatic int pll_deferred;\n'
                                 'static unsigned long clk_get_rate(struct clk *clk) {CHECK(clk);return 600000000;}')
            stubs = stubs.replace('CHECK(dev && !strcmp(name,"cpu"));clock_gets++;',
                                 'CHECK(dev && (!strcmp(name,"cpu") || !strcmp(name,"aux") || !strcmp(name,"pll")));clock_gets++;\n'
                                 ' if (!strcmp(name,"pll") && pll_deferred) return (void *)(intptr_t)-EPROBE_DEFER;')
            text = (directory / 'cpr.c').read_text()
            functions = ''.join(RUNTIME.function(text, name) for name in
                                (['cpr_msm8926_check_refclock('] +
                                 (['cpr_msm8926_init_refclock('] if 'static int cpr_msm8926_init_refclock(' in text else []) +
                                 ['cpr_msm8926_init(', 'cpr_msm8926_corner_init(']))
            main = fixture.MAIN.replace('int main(void)', 'static int base_main(void)').replace('clock_gets==1', 'clock_gets==3')
            main += r'''
int main(void) {
 CHECK(!base_main());
 struct fuse_corner fuses[3];struct corner corners[14];
 struct cpr_drv drv=reset(fuses,corners);
 pll_deferred=1;CHECK(cpr_msm8926_init(&drv)==-EPROBE_DEFER);
 CHECK(clock_gets==3 && !drv.msm8926 && !drv.rails.mx);free(allocation);pll_deferred=0;
 drv=reset(fuses,corners);CHECK(!cpr_msm8926_init(&drv));
 CHECK(drv.msm8926->pll_clk==&provider_clock && drv.msm8926->aux_clk==&provider_clock);
 free(allocation);
 puts("provider owns both parents; PLL defer publishes no partial plan and performs no activation");
 return 0;
}
'''
            (base / 'init.c').write_text(fixture.FIXTURE.WRAPPER + stubs + functions + main)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(base),
                                     str(base / 'init.c'), '-o', str(base / 'init')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(base / 'init')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('no activation', result.stdout)
        finally:
            fixture.FIXTURE.VoltagePlanTests.tearDownClass()

    def test_actual_provider_flags_and_legacy_scope(self):
        directory = KERNEL / 'drivers/clk/qcom'
        pll = (directory / 'a53-pll.c').read_text()
        apcs = (directory / 'apcs-msm8916.c').read_text()
        gcc = (directory / 'gcc-msm8974.c').read_text()
        start = gcc.index('static struct clk_init_data gpll0_init =')
        init = gcc[start:gcc.index('\n};', start) + 3]
        source = (HARNESS + init + RUNTIME.function(pll, 'qcom_a53pll_probe(') +
                  RUNTIME.function(apcs, 'qcom_apcs_msm8916_clk_probe(') +
                  RUNTIME.function(gcc, 'msm8226_clock_override(') + MAIN)
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'policy.c').write_text(source)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     str(base / 'policy.c'), '-o', str(base / 'policy')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(base / 'policy')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('only on MSM8226', result.stdout)


if __name__ == '__main__':
    unittest.main()
