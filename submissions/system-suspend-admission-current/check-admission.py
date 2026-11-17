# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact RPM admission/request/callback functions with synthetic RPMsg.

POSIX mutexes/condition variables provide real host thread exclusion. IRQ
state, transport, memory allocation and PM phase ordering are synthetic.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
P=argparse.ArgumentParser();P.add_argument('source',type=Path);P.add_argument('output',type=Path)
a=P.parse_args();a.output.mkdir(parents=True,exist_ok=False)
s=(a.source/'drivers/soc/qcom/smd-rpm.c').read_text()
h=(a.source/'include/linux/soc/qcom/smd-rpm.h').read_text()
def struct(text,name):
 m=re.search(r'struct '+name+r' \{.*?\n\};',text,re.S);assert m,name
 return m.group()+'\n'
def function(text,name):
 m=re.search(r'(?:static\s+)?int\s+'+name+r'\s*\([^;{}]*\)\s*\{',text);assert m,name
 end=m.end();depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[m.start():end]+'\n'
functions=['qcom_rpm_smd_freeze','qcom_rpm_smd_thaw','qcom_rpm_smd_write','qcom_smd_rpm_callback']
bindings={n:hashlib.sha256(function(s,n).encode()).hexdigest() for n in functions}
constants='\n'.join(x for x in s.splitlines() if x.startswith('#define RPM_'))+'\n'
model=(Path(__file__).with_name('admission-services.c').read_text()+struct(h,'qcom_rpm_smd_sleep_token')+
 ''.join(struct(s,n) for n in ['qcom_smd_rpm','qcom_rpm_header','qcom_rpm_request'])+constants+
 ''.join(function(s,n) for n in functions)+Path(__file__).with_name('admission-cases.c').read_text())
(a.output/'model.c').write_text(model)
env=os.environ.copy();env['TMPDIR']=str(a.output.resolve());env['ASAN_OPTIONS']='detect_leaks=1:halt_on_error=1:abort_on_error=1';env['UBSAN_OPTIONS']='halt_on_error=1:print_stacktrace=1'
command=['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread',str(a.output/'model.c'),'-o',str(a.output/'model')]
r=subprocess.run(command,env=env,capture_output=True,text=True)
(a.output/'compile.stdout').write_text(r.stdout);(a.output/'compile.stderr').write_text(r.stderr)
assert r.returncode==0,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],env=env,capture_output=True,text=True,timeout=60)
(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
record=dict(passed=r.returncode==0,returncode=r.returncode,bindings=bindings,actual_functions=len(bindings),
 model_SHA256=hashlib.sha256(model.encode()).hexdigest(),ASAN_OPTIONS=env['ASAN_OPTIONS'],UBSAN_OPTIONS=env['UBSAN_OPTIONS'],
 synthetic=['RPMsg and IRQ delivery','IRQ enable state','allocation failure','PM callback scheduling'],
 real_host_services=['POSIX mutexes','POSIX condition variables','host pthread concurrency'],
 kernel_concurrency_qualified=False,phone_access=False)
try:record.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record));assert r.returncode==0,r.stderr
