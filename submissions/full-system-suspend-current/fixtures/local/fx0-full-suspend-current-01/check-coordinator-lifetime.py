# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent;s=(a.source/'drivers/soc/qcom/msm8226-pm.c').read_text();names=['msm8226_pm_supplier','msm8226_pm_get_cpus','msm8226_pm_install','msm8226_pm_probe','msm8226_pm_remove']
def func(n):
 m=re.search(r'static (?:struct platform_device \*|int |void )'+n+r'\s*\([^;{}]*\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]+'\n'
structure=re.search(r'struct msm8226_pm \{.*?\n\};',s,re.S)[0]
model=(B/'coordinator-lifetime-services.c').read_text()+structure+(B/'coordinator-lifetime-adapters.c').read_text()+''.join(func(n) for n in names)+(B/'coordinator-lifetime-cases.c').read_text()
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=len(names),bindings={n:hashlib.sha256(func(n).encode()).hexdigest() for n in names},source_SHA256=hashlib.sha256(s.encode()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['device graph, devres and driver-core cleanup','supplier ownership and hardware resource mappings','CPU-hotplug writer and online masks','async work scheduling and system sleep ops mutex'],actual_driver_core_concurrency_qualified=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
