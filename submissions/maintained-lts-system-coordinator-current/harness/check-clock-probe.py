# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
B=Path(__file__).resolve().parent;R=B.parents[1];fixture=B/'retained-clock-fixtures/tests/test_msm8226_clock_policy.py';spec=importlib.util.spec_from_file_location('retained_policy',fixture);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
groups={'a53-pll.c':'qcom_a53pll_probe(','apcs-msm8916.c':'qcom_apcs_msm8916_clk_probe(','gcc-msm8974.c':'msm8226_clock_override('};functions={name:m.RUNTIME.function((a.source/'drivers/clk/qcom'/file).read_text(),name) for file,name in groups.items()};gcc=(a.source/'drivers/clk/qcom/gcc-msm8974.c').read_text();start=gcc.index('static struct clk_init_data gpll0_init =');init=gcc[start:gcc.index('\n};',start)+3]
h=m.HARNESS.replace('#define GFP_KERNEL 0','#define GFP_KERNEL 0\nstatic int checks;\n#define devm_kzalloc_obj(d,o) devm_kzalloc(d,sizeof(o),GFP_KERNEL)').replace('#define ENOMEM 12','#define ENOMEM 12\n#define EIO 5\nstatic bool full_pm;\n#define IS_ENABLED(x) full_pm').replace('struct regmap {int unused;};','struct regmap {u32 words[8];};').replace('bool critical_rate;const struct pll_freq_tbl', 'bool critical_rate,suspend_valid,suspend_armed;u32 suspend_config,suspend_l,suspend_m,suspend_n;const struct pll_freq_tbl')
h=h.replace('#define CHECK(x) do {if(!(x))', '#define CHECK(x) do {checks++;if(!(x))')
h+='''
static int reads,fail_read,registrations;
static int regmap_read(struct regmap *r,unsigned int off,u32 *value) {CHECK(r==&map&&off<32);reads++;if(reads==fail_read)return -EIO;*value=r->words[off/4];return 0;}
'''
h=h.replace('flags=clkr->hw.init->flags;', 'registrations++;flags=clkr->hw.init->flags;')
# Declare the counter before its earlier registration service.
h=h.replace('static int reads,fail_read,registrations;', 'static int reads,fail_read;').replace('static unsigned long flags;', 'static int registrations;\nstatic unsigned long flags;')
model=h+init+''.join(functions.values())+(B/'clock-probe-cases.c').read_text();(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=len(functions),bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},retained_fixture_SHA256=hashlib.sha256(fixture.read_bytes()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['clock registration and devres allocation','public synthetic register values and read failures','DT compatibility and parent readiness'],real_clock_provider_qualification=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
