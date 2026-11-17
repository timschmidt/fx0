# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent
names={
 'drivers/soc/qcom/msm8226-pm.c':['qcom_msm8226_pm_active','msm8226_core_finisher','qcom_msm8226_cpu_collapse','qcom_msm8226_cpu_kill','msm8226_secondaries_collapsed','msm8226_system_finisher','msm8226_suspend_enter','msm8226_platform_prepare_late','msm8226_platform_wake','msm8226_pm_suspend_late','msm8226_pm_resume_early'],
 'arch/arm/mach-qcom/platsmp.c':['msm8226_cpu_disable','msm8226_cpu_die','msm8226_boot_secondary'],
 'drivers/irqchip/irq-gic.c':['gic_cpu_quiesce_ppis'],
 'kernel/power/suspend.c':['platform_suspend_prepare','platform_suspend_prepare_late','platform_suspend_prepare_noirq','platform_resume_noirq','platform_resume_early','platform_resume_finish','suspend_enter']}
texts={n:(a.source/n).read_text() for n in names}
def func(t,n):
 m=re.search(r'(?:static\s+)?(?:int|void|bool)\s+'+n+r'\s*\([^;{}]*\)\s*\{',t);assert m,n
 i=m.end();d=1
 while d:d+=(t[i]=='{')-(t[i]=='}');i+=1
 return t[m.start():i]+'\n'
functions={n:func(texts[f],n) for f,ns in names.items() for n in ns}
# Build actual GIC and ARM hooks before the synthetic driver-core service adapters.
structure=re.search(r'struct msm8226_pm \{.*?\n\};',texts['drivers/soc/qcom/msm8226-pm.c'],re.S)[0]
ops=re.search(r'static const struct platform_suspend_ops msm8226_suspend_ops = \{.*?\n\};',texts['drivers/soc/qcom/msm8226-pm.c'],re.S)[0]
model=((B/'coordinator-services.c').read_text()+structure+(B/'coordinator-adapters.c').read_text()+functions['gic_cpu_quiesce_ppis']+''.join(functions[n] for n in names['drivers/soc/qcom/msm8226-pm.c'])+ops+''.join(functions[n] for n in names['arch/arm/mach-qcom/platsmp.c'])+(B/'coordinator-pm-services.c').read_text()+''.join(functions[n] for n in names['kernel/power/suspend.c'])+(B/'coordinator-cases.c').read_text())
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=50);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=len(functions),bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},actual_suspend_ops_SHA256=hashlib.sha256(ops.encode()).hexdigest(),source_SHA256={n:hashlib.sha256(t.encode()).hexdigest() for n,t in texts.items()},model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['SPM and CPR/RPM/MPM provider responses','SCM collapse, warm reset and banked GIC/ACC registers','driver PM traversal, IRQ/syscore callbacks, wakeup and test levels'],real_host_services=['three concurrent secondary CPU threads','POSIX condition variables, atomic flags and mutexes'],actual_probe_remove_included=False,physical_collapse_qualification=False,kernel_concurrency_qualified=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
