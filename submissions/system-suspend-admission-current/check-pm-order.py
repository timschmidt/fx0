# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual platform wrapper dispatch; callback services are synthetic."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False)
s=(a.source/'kernel/power/suspend.c').read_text()
names=['platform_suspend_prepare','platform_suspend_prepare_late','platform_suspend_prepare_noirq','platform_resume_noirq','platform_resume_early','platform_resume_finish','suspend_enter']
def extract(name):
 m=re.search(r'static (?:int|void) '+name+r'\([^;{}]*\)\s*\{',s);assert m,name
 i=m.end();d=1
 while d:
  d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]+'\n'
functions={n:extract(n) for n in names}
text=Path(__file__).with_name('pm-order-services.c').read_text()+''.join(functions.values())+Path(__file__).with_name('pm-order-cases.c').read_text()
(a.output/'model.c').write_text(text)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-g','-O1','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined',str(a.output/'model.c'),'-o',str(a.output/'model')],env=env,capture_output=True,text=True)
(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],env=env,capture_output=True,text=True,timeout=30)
(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},
 actual_functions=7,model_SHA256=hashlib.sha256(text.encode()).hexdigest(),
 scope='Actual suspend_enter and six dispatch wrappers; all device PM, IRQ, syscore, CPU and callback services synthetic',
 production_coordinator_implemented=False,phone_access=False)
if not r.returncode:j.update(json.loads(r.stdout))
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
