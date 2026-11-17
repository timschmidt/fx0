# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent
names=['qcom_cpr_msm8926_suspend_attach','qcom_cpr_msm8926_suspend_detach','qcom_cpr_msm8926_suspend_prepare','qcom_cpr_msm8926_suspend_restore','qcom_cpr_msm8926_suspend_ready','cpr_pm_prepare','cpr_pm_suspend','cpr_pm_resume']
s=(a.source/'drivers/pmdomain/qcom/cpr.c').read_text()
def func(n):
 m=re.search(r'(?:static\s+)?(?:int|bool|void)\s+'+n+r'\s*\([^;{}]*\)\s*\{',s);assert m,n
 i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 return s[m.start():i]+'\n'
headers='\n'.join(re.sub(r'^#include[^\n]*\n','',(a.source/'drivers/pmdomain/qcom'/n).read_text(),flags=re.M) for n in ['cpr-voltage.h','cpr-msm8926-suspend.h'])
model=(B/'cpr-suspend-services.c').read_text()+headers+(B/'cpr-api-services.c').read_text()+''.join(func(n) for n in names)+(B/'cpr-api-cases.c').read_text()
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_API_PM_callbacks=len(names),bindings={n:hashlib.sha256(func(n).encode()).hexdigest() for n in names},source_SHA256=hashlib.sha256(s.encode()).hexdigest(),header_SHA256=hashlib.sha256(headers.encode()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),scope='Actual attach, detach, voltage/clock transaction headers and CPR late/early callbacks; partial driver structures and feedback/config/rate validation services synthetic',physical_voltage_clock_qualification=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
