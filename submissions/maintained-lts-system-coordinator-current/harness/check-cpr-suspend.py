# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent
names=['cpr_voltage_vote_mx','cpr_voltage_bootstrap','cpr_voltage_set','cpr_suspend_check_parents','cpr_suspend_check_clock','cpr_suspend_sync','cpr_suspend_cover','cpr_suspend_restore','cpr_suspend_prepare']
texts=[(a.source/'drivers/pmdomain/qcom'/n).read_text() for n in ['cpr-voltage.h','cpr-msm8926-suspend.h']]
def func(text,name):
 m=re.search(r'(?:static\s+)?(?:inline\s+)?(?:int|bool|void|u32)\s+'+name+r'\s*\([^;{}]*\)\s*\{',text);assert m,name
 i=m.end();d=1
 while d:d+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[m.start():i]+'\n'
bindings={n:hashlib.sha256(func(texts[0] if n.startswith('cpr_voltage') else texts[1],n).encode()).hexdigest() for n in names}
headers='\n'.join(re.sub(r'^#include[^\n]*\n','',t,flags=re.M) for t in texts)
model=(B/'cpr-suspend-services.c').read_text()+headers+(B/'cpr-suspend-cases.c').read_text();(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=len(bindings),bindings=bindings,model_SHA256=hashlib.sha256(model.encode()).hexdigest(),
 services_synthetic=['regulator core caching and provider ACK semantics','clock prepare/enable references and physical mux','register reads and failures','quiescent CPR/IRQ preconditions'],
 actual_CPR_device_PM_callbacks_included=False,physical_regulator_clock_firmware_qualification=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
