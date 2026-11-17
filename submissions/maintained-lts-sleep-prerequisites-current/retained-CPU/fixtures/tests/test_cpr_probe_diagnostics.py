"""Execute real CPR initialization to distinguish equal errors by stage."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-probe'))


def fixture(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tests'/(name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


DOMAIN = fixture('test_msm8926_domain')
RUNTIME = fixture('test_cpr_runtime_clock')
FUSES = fixture('test_msm8926_fuses')
LOG = r'''
static const char *last_diagnostic;
#undef dev_err_probe
#define dev_err_probe(dev, err, fmt, ...) ((void)(dev), last_diagnostic=(fmt), (err))
'''


class ProbeDiagnosticsTests(unittest.TestCase):
    def compile_run(self, base, text):
        source, binary = base/'test.c', base/'test'
        source.write_text(text)
        result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                 '-I', str(base), str(source), '-o', str(binary)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = subprocess.run([str(binary)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_initialization_stage_and_exact_error_are_preserved(self):
        DOMAIN.FIXTURE.VoltagePlanTests.setUpClass()
        try:
            base = Path(DOMAIN.FIXTURE.VoltagePlanTests.tmp.name)
            directory = KERNEL/'drivers/pmdomain/qcom'
            (base/'cpr-msm8926-corner.h').write_bytes((directory/'cpr-msm8926-corner.h').read_bytes())
            stubs = DOMAIN.STUBS.replace('struct regmap *apcs;', 'struct regmap *apcs;struct clk *aux_clk,*pll_clk;')
            stubs = stubs.replace('static struct clk provider_clock;',
                                 'static struct clk provider_clock;\nstatic int pll_deferred,aux_bad;\n'
                                 'static unsigned long clk_get_rate(struct clk *clk) {CHECK(clk);return aux_bad?500000000:600000000;}')
            stubs = stubs.replace('CHECK(dev && !strcmp(name,"cpu"));clock_gets++;',
                                 'CHECK(dev && (!strcmp(name,"cpu") || !strcmp(name,"aux") || !strcmp(name,"pll")));clock_gets++;\n'
                                 'if (!strcmp(name,"pll") && pll_deferred) return (void *)(intptr_t)-EPROBE_DEFER;')
            source = (directory/'cpr.c').read_text()
            functions = ''.join(RUNTIME.function(source, name) for name in
                                (['cpr_msm8926_check_refclock('] +
                                 (['cpr_msm8926_init_refclock('] if 'static int cpr_msm8926_init_refclock(' in source else []) +
                                 ['cpr_msm8926_init(', 'cpr_msm8926_corner_init(']))
            main = DOMAIN.MAIN.replace('int main(void)', 'static int base_main(void)').replace('clock_gets==1', 'clock_gets==3')
            main += r'''
int main(void) {
 CHECK(!base_main());
 const char *expected[]={"register map","reference source","MX supply",
  "voltage plan","rate rounding","A7 PLL","auxiliary clock","acquisition"};
 const int errors[]={-EINVAL,-EINVAL,-EPROBE_DEFER,-EINVAL,-EINVAL,
  -EPROBE_DEFER,-ERANGE,-EPROBE_DEFER};
 for(int fault=0;fault<8;fault++) {
  struct fuse_corner fuses[3];struct corner corners[14];
  struct cpr_drv drv=reset(fuses,corners);
  last_diagnostic=NULL;pll_deferred=aux_bad=0;
  if(fault==0)syscon_error=-EINVAL;
  if(fault==1){ref_source=1;drop_ref_write=1;}
  if(fault==2)fail_stage=3;
  if(fault==3)boot_voltage=0;
  if(fault==4)round_error=-EINVAL;
  if(fault==5)pll_deferred=1;
  if(fault==6)aux_bad=1;
  if(fault==7)fail_stage=2;
  CHECK(cpr_msm8926_init(&drv)==errors[fault]);
  CHECK(last_diagnostic && strstr(last_diagnostic,expected[fault]));
  CHECK(!drv.msm8926 && !drv.rails.mx);
  free(allocation);
 }
 puts("eight stages retain errno and unpublished state while identifying the failure");
 return 0;
}
'''
            output = self.compile_run(base, DOMAIN.FIXTURE.WRAPPER+stubs+LOG+functions+main)
            self.assertIn('eight stages retain errno', output)
        finally:
            DOMAIN.FIXTURE.VoltagePlanTests.tearDownClass()

    def test_equal_fuse_errors_retain_cleanup_and_distinct_diagnostics(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base/'linux/firmware/qcom').mkdir(parents=True)
            for header in ['device.h', 'err.h', 'errno.h', 'types.h', 'minmax.h',
                           'nvmem-consumer.h', 'slab.h', 'unaligned.h',
                           'firmware/qcom/qcom_scm.h']:
                (base/'linux'/header).write_text('')
            (base/'stubs.h').write_text(FUSES.STUBS+LOG)
            for name in ['cpr-msm8926.h', 'cpr-msm8926-fuses.h']:
                (base/name).write_bytes((KERNEL/'drivers/pmdomain/qcom'/name).read_bytes())
            main = FUSES.HARNESS.replace('int main(void)', 'static int base_main(void)')
            main += r'''
int main(void) {
 CHECK(!base_main());
 const char *expected[]={"SCM read","cell has","cell lookup","cell read"};
 for(int fault=0;fault<4;fault++) {
  reset();last_diagnostic=NULL;error_code=-EINVAL;
  if(fault==0)secure_error=-EINVAL;
  if(fault==1){length_fault=1;bad_length=4;}
  if(fault==2)get_fault=2;
  if(fault==3)read_fault=3;
  CHECK(run()==-EINVAL && last_diagnostic && strstr(last_diagnostic,expected[fault]));
  CHECK(!live_cell && !live_buffer);
 }
 puts("equal fuse errors identify their stage without leaking cells or buffers");
 return 0;
}
'''
            self.assertIn('equal fuse errors identify their stage', self.compile_run(base, main))


if __name__ == '__main__':
    unittest.main()
