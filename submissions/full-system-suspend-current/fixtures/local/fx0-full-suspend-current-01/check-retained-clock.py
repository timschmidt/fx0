# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
B=Path(__file__).resolve().parent;R=B.parents[1];fixture=R/'local/fx0-cpu-clock-pm-current-01/fixtures/tests/test_cpr_runtime_clock.py';spec=importlib.util.spec_from_file_location('retained_clock',fixture);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
groups={
 'drivers/clk/qcom/clk-pll.c':['clk_pll_rate_error(','clk_pll_disable_checked(','clk_pll_disable(','clk_pll_recalc_rate(','find_freq(','wait_for_pll(','clk_pll_sr2_enable(','clk_pll_sr2_set_rate('],
 'drivers/clk/qcom/clk-regmap-mux-div.c':['mux_div_rate_error(','mux_div_set_src_div(','mux_div_get_src_div(','mux_div_get_parent(','mux_div_recalc_rate('],
 'drivers/pmdomain/qcom/cpr.c':['cpr_msm8926_check_cpu_rate(','cpr_scale_voltage(','cpr_msm8926_bootstrap_clock(']}
functions={name:m.function((a.source/file).read_text(),name) for file,names in groups.items() for name in names}
h=m.HARNESS.replace('#define EINVAL 22','#define EOPNOTSUPP 95\n#define EINVAL 22').replace('bool critical_rate;\n const struct pll_freq_tbl *freq_tbl;', 'bool critical_rate,suspend_valid,suspend_armed;\n u32 suspend_config,suspend_l,suspend_m,suspend_n;\n const struct pll_freq_tbl *freq_tbl;')
h=h.replace('static int pre_calls,', 'static bool drop_first_l_write;\nstatic int pre_calls,').replace('if(io_calls==drop_write_at)return 0;', 'if(io_calls==drop_write_at || (drop_first_l_write && map==&pll_map && offset==cpu_pll.l_reg)){drop_first_l_write=false;return 0;}')
model_cases=m.MODEL.replace('panics=io_calls=fail_at=', 'drop_first_l_write=false;panics=io_calls=fail_at=').replace('drop_write_at=4; /* Lost L write', 'drop_first_l_write=true; /* Lost L write')
model=h+''.join(functions.values())+model_cases
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
runs=[]
for scope in ['pll','mux','cpr','startup']:
 r=subprocess.run([str((a.output/'model').resolve()),scope],capture_output=True,text=True,env=env,timeout=30);(a.output/(scope+'.stdout')).write_text(r.stdout);(a.output/(scope+'.stderr')).write_text(r.stderr);runs.append(dict(scope=scope,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
j=dict(passed=all(not r['returncode'] for r in runs),actual_functions=len(functions),bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},fixture_SHA256=hashlib.sha256(fixture.read_bytes()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),service_adaptations=['new private clk_pll context fields, zero by default','EOPNOTSUPP numeric model constant','drop-L fault targets its register instead of old operation index 4, now shifted by mandatory disable readback'],old_model_also_run_with_failfast_ASAN_UBSAN_and_normal_LSan=True,services_synthetic=True,phone_access=False,runs=runs)
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(passed=j['passed'],runs=runs)));assert j['passed']
