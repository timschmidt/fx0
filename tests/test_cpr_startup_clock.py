"""Run the actual startup handoff with unlisted clocks and ambiguous I/O."""
import os
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT / 'worktrees/linux-fx0-startup')) / 'drivers/pmdomain/qcom/cpr.c'

HARNESS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#define EINVAL 22
#define EIO 5
#define ERANGE 34
#define BIT(x) (1U << (x))
#define GENMASK(h,l) ((~0U >> (31-(h))) & (~0U << (l)))
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"line %d: %s\n",__LINE__,#x); exit(1); } } while (0)
typedef uint32_t u32;
struct corner { unsigned long freq; int uV; };
struct cpr_voltage { void *apc; bool mx_enabled; };
struct cpr_msm8926_data {
 struct { int bootstrap_mx_uV; } plan;
 bool apc_enabled, applied;
 void *apcs, *aux_clk;
};
struct cpr_drv {
 struct cpr_msm8926_data *msm8926;
 struct corner *corners, *corner;
 unsigned int num_corners;
 struct cpr_voltage rails;
 void *cpu_clk;
 bool initialized;
};
static unsigned long aux_rate, cpu_rate, cached_rate;
static int boot_uV, mx_error, enable_error, clock_error, read_error_at;
static int mx_enables, apc_enables, clock_calls, reads, serial;
static int mx_order, apc_order, clock_order, get_uV_order;
static unsigned int command_bits, config_bits, late_command_bits, late_config_bits;
static bool clock_effect, stale_cache;
static unsigned long clk_get_rate(void *clk) {
 if (clk == (void *)2) return aux_rate;
 CHECK(clk == (void *)1);
 return stale_cache ? cached_rate : cpu_rate;
}
static int regulator_get_voltage(void *reg) {
 CHECK(reg == (void *)3);get_uV_order=++serial;return boot_uV;
}
static int cpr_voltage_bootstrap(struct cpr_voltage *rails, int floor) {
 CHECK(floor == 1287500);mx_order=++serial;
 if (mx_error) return mx_error;
 if (!rails->mx_enabled) mx_enables++;
 rails->mx_enabled=true;return 0;
}
static int regulator_enable(void *reg) {
 CHECK(reg == (void *)3);apc_order=++serial;
 if (enable_error) return enable_error;
 apc_enables++;return 0;
}
static int clk_set_rate(void *clk, unsigned long rate) {
 CHECK(clk == (void *)1 && rate == 300000000);
 CHECK(mx_order > get_uV_order && apc_enables == 1);
 clock_order=++serial;clock_calls++;
 if (clock_effect) { cpu_rate=rate;config_bits=0x403; }
 cached_rate=rate;return clock_error;
}
static int regmap_read(void *map, unsigned int offset, u32 *value) {
 CHECK(map == (void *)4);reads++;
 CHECK(offset == (reads%2 ? 0x50U : 0x54U));
 if (reads == read_error_at) return -EIO;
 if (offset == 0x50) *value=command_bits | (reads == 3 ? late_command_bits : 0);
 else *value=config_bits ^ (reads == 4 ? late_config_bits : 0);
 return 0;
}
static struct corner corners[]={{300000000,1080000},{384000000,1080000}};
static struct cpr_msm8926_data data;
static struct cpr_drv reset(void) {
 aux_rate=600000000;cpu_rate=cached_rate=800000000;boot_uV=1150000;
 mx_error=enable_error=clock_error=read_error_at=0;
 mx_enables=apc_enables=clock_calls=reads=serial=0;
 mx_order=apc_order=clock_order=get_uV_order=0;
 command_bits=late_command_bits=late_config_bits=0;config_bits=0x500;
 clock_effect=true;stale_cache=false;
 data=(struct cpr_msm8926_data){.plan={1287500},.apcs=(void *)4,.aux_clk=(void *)2};
 return (struct cpr_drv){.msm8926=&data,.corners=corners,.num_corners=2,
                       .cpu_clk=(void *)1,.rails={.apc=(void *)3}};
}
static void retained(struct cpr_drv *drv) {
 CHECK(!drv->initialized && !data.applied && !drv->corner);
 CHECK(boot_uV == 1150000 && drv->rails.mx_enabled && data.apc_enabled);
 CHECK(mx_enables == 1 && apc_enables == 1);
}
'''

MAIN = r'''
int main(void) {
 struct cpr_drv drv;
 /* Real 800 MHz handoff: floor, logical reference, clock, hardware readback. */
 drv=reset();CHECK(!cpr_msm8926_bootstrap_clock(&drv));retained(&drv);
 CHECK(cpu_rate==300000000 && mx_order<apc_order && apc_order<clock_order && reads==4);
 reads=0;CHECK(!cpr_msm8926_bootstrap_clock(&drv));retained(&drv);
 CHECK(clock_calls==2); /* No second rail enable on repeated handoff. */
 for (int fault=0;fault<8;fault++) {
  drv=reset();
  if (fault==0) aux_rate=800000000;
  if (fault==1) cpu_rate=0;
  if (fault==2) cpu_rate=19200000;
  if (fault==3) boot_uV=1070000;
  if (fault==4) boot_uV=1290000;
  if (fault==5) boot_uV=-EIO;
  if (fault==6) drv.num_corners=0;
  if (fault==7) drv.msm8926=NULL;
  int ret=cpr_msm8926_bootstrap_clock(&drv);
  CHECK(ret==(fault==5?-EIO:fault>=6?-EINVAL:-ERANGE));
  CHECK(!mx_enables && !apc_enables && !clock_calls);
 }
 drv=reset();mx_error=-EIO;CHECK(cpr_msm8926_bootstrap_clock(&drv)==-EIO);
 CHECK(!drv.rails.mx_enabled && !data.apc_enabled && !clock_calls);
 mx_error=0;CHECK(!cpr_msm8926_bootstrap_clock(&drv));retained(&drv);
 drv=reset();enable_error=-EIO;CHECK(cpr_msm8926_bootstrap_clock(&drv)==-EIO);
 CHECK(drv.rails.mx_enabled && !data.apc_enabled && !clock_calls);
 enable_error=0;CHECK(!cpr_msm8926_bootstrap_clock(&drv));retained(&drv);
 for (int effect=0;effect<2;effect++) {
  drv=reset();clock_effect=effect;clock_error=-EIO;
  CHECK(cpr_msm8926_bootstrap_clock(&drv)==-EIO);retained(&drv);
  CHECK(cpu_rate==(effect?300000000UL:800000000UL));
  clock_error=0;clock_effect=true;CHECK(!cpr_msm8926_bootstrap_clock(&drv));retained(&drv);
 }
 for (int fault=1;fault<=4;fault++) {
  drv=reset();read_error_at=fault;
  CHECK(cpr_msm8926_bootstrap_clock(&drv)==-EIO && reads==fault);retained(&drv);
  reads=0;read_error_at=0;CHECK(!cpr_msm8926_bootstrap_clock(&drv));retained(&drv);
 }
 for (int fault=0;fault<8;fault++) {
  drv=reset();
  if (fault==0) command_bits=BIT(0);
  if (fault==1) command_bits=BIT(4);
  if (fault==2) command_bits=BIT(31);
  if (fault==3) late_command_bits=BIT(0);
  if (fault==4) late_config_bits=1;
  if (fault==5) {clock_effect=false;stale_cache=true;} /* CCF lies: hardware still 800. */
  if (fault==6) {stale_cache=true;cached_rate=300000000;clock_effect=false;config_bits=0x500;}
  if (fault==7) {clock_effect=false;config_bits=0x403;} /* Hardware mux and CCF disagree. */
  CHECK(cpr_msm8926_bootstrap_clock(&drv)==-EIO);retained(&drv);
 }
 puts("startup clock: ordered 800-to-300 handoff, idempotent rails, 24 fault cases, stale-CCF rejection and retries passed");
 return 0;
}
'''


class StartupClockTests(unittest.TestCase):
    def test_provider_reads_and_validates_aux_without_activation(self):
        spec = importlib.util.spec_from_file_location('domain_fixture', ROOT / 'tests/test_msm8926_domain.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        fixture.FIXTURE.VoltagePlanTests.setUpClass()
        try:
            base = Path(fixture.FIXTURE.VoltagePlanTests.tmp.name)
            header = SOURCE.parent / 'cpr-msm8926-corner.h'
            (base / header.name).write_bytes(header.read_bytes())
            stubs = fixture.STUBS.replace('struct regmap *apcs;', 'struct regmap *apcs; struct clk *aux_clk;')
            stubs = stubs.replace('static struct clk provider_clock;',
                                 'static struct clk provider_clock;\n'
                                 'static int aux_failure;static unsigned long aux_rate=600000000;\n'
                                 'static unsigned long clk_get_rate(struct clk *clk) {CHECK(clk);return aux_rate;}')
            stubs = stubs.replace('CHECK(dev && !strcmp(name,"cpu"));clock_gets++;',
                                 'CHECK(dev && (!strcmp(name,"cpu") || !strcmp(name,"aux")));clock_gets++;\n'
                                 ' if (!strcmp(name,"aux") && aux_failure) return (void *)(intptr_t)-EPROBE_DEFER;')
            source = SOURCE.read_text()
            functions = ''.join(fixture.function(source, name) for name in
                                (['cpr_msm8926_check_refclock('] +
                                 (['cpr_msm8926_init_refclock('] if 'static int cpr_msm8926_init_refclock(' in source else []) +
                                 ['cpr_msm8926_init(', 'cpr_msm8926_corner_init(']))
            main = fixture.MAIN.replace('int main(void)', 'static int base_main(void)').replace('clock_gets==1', 'clock_gets==2')
            main += r'''
int main(void) {
 CHECK(!base_main());
 struct fuse_corner fuses[3];struct corner corners[14];
 struct cpr_drv drv=reset(fuses,corners);
 aux_failure=1;CHECK(cpr_msm8926_init(&drv)==-EPROBE_DEFER);
 CHECK(!drv.msm8926 && !drv.rails.mx);free(allocation);aux_failure=0;
 drv=reset(fuses,corners);aux_rate=800000000;
 CHECK(cpr_msm8926_init(&drv)==-ERANGE && !drv.msm8926 && !drv.rails.mx);free(allocation);
 puts("aux reference ownership, defer and unsupported safe-clock rejection passed without activation APIs");
 return 0;
}
'''
            (base / 'startup-init.c').write_text(fixture.FIXTURE.WRAPPER + stubs + functions + main)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-I', str(base),
                                     str(base / 'startup-init.c'), '-o', str(base / 'startup-init')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(base / 'startup-init')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('without activation APIs', result.stdout)
        finally:
            fixture.FIXTURE.VoltagePlanTests.tearDownClass()

    def test_actual_attachment_orders_handoff_before_corner_lookup(self):
        spec = importlib.util.spec_from_file_location('attach_fixture', ROOT / 'tests/test_cpr_attach.py')
        fixture = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fixture)
        stubs = fixture.STUBS.replace(
            'static int cpr_find_initial_corner(struct cpr_drv *d) { (void)d;return checkpoint(); }',
            'static int cpr_find_initial_corner(struct cpr_drv *d) {\n'
            ' if(d->msm8926) { CHECK(d->msm8926->apc_enabled); }\n return checkpoint();\n}')
        stubs += r'''
static int cpr_msm8926_bootstrap_clock(struct cpr_drv *d) {
 int ret=cpr_voltage_bootstrap(&d->rails,d->msm8926->plan.bootstrap_mx_uV);
 if(ret)return ret;
 if(!d->msm8926->apc_enabled) {
  ret=regulator_enable(d->rails.apc);if(ret)return ret;
  d->msm8926->apc_enabled=true;
 }
 return checkpoint();
}
'''
        main = r'''
int main(void) {
 struct device cpu={1},other={2};
 for(int fault=1;fault<=7;fault++) {
  struct cpr_msm8926_data data={.plan={1287500}};
  struct cpr_drv drv={.dev=&cpu,.msm8926=&data,.cpu_clk=(void *)42};
  calls=0;fail_at=fault;opp_count=4;
  CHECK(cpr_pd_attach_dev(&drv.pd,&cpu)==-5 && calls==fault && !drv.initialized);
  CHECK(data.apc_enabled==(fault>=6));
  int retained=data.apc_enabled;
  calls=0;fail_at=0;
  CHECK(!cpr_pd_attach_dev(&drv.pd,&cpu));
  CHECK(drv.initialized && data.apc_enabled && calls==7-retained);
  CHECK(!cpr_pd_attach_dev(&drv.pd,&other) && calls==7-retained);
 }
 puts("attachment preserves partial rail activation, retries, and looks up the corner after normalization");
 return 0;
}
'''
        source = SOURCE.read_text()
        start = source.index('static int cpr_pd_attach_dev(')
        end = source.index('\nstatic int cpr_debug_info_show(', start)
        self.compile_and_run(stubs + source[start:end] + main, 'after normalization')

    def test_actual_handoff(self):
        source = SOURCE.read_text()
        start = source.index('static int cpr_msm8926_bootstrap_clock(')
        end = source.index('\n}', start) + 2
        self.compile_and_run(HARNESS + source[start:end] + MAIN, 'stale-CCF rejection')

    def compile_and_run(self, source, expected):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            (base / 'test.c').write_text(source)
            result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                     str(base / 'test.c'), '-o', str(base / 'test')],
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(base / 'test')], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)


if __name__ == '__main__':
    unittest.main()
