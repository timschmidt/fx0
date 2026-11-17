# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
B=Path(__file__).resolve().parent;s=(a.source/'drivers/rpmsg/qcom_smd.c').read_text();name='qcom_channel_state_worker_run';m=re.search(r'static void '+name+r'\([^;{}]*\)\s*\{',s);assert m;i=m.end();d=1
while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
function=s[m.start():i]+'\n';model=(B/'smd-state-services.c').read_text()+function+(B/'smd-state-cases.c').read_text();(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=1,bindings={name:hashlib.sha256(function.encode()).hexdigest()},source_SHA256=hashlib.sha256(s.encode()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['fixed channel list and IRQ spinlock','RPMsg registration failure and successful/no-consumer creation','RPMsg removal and endpoint-close state'],kernel_worker_concurrency_qualified=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
