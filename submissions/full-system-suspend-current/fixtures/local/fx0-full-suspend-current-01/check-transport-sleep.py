# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent
files={n:(a.source/n).read_text() for n in ['drivers/soc/qcom/smd-rpm.c','drivers/rpmsg/qcom_smd.c','include/linux/soc/qcom/smd-rpm.h']}
rpm=['qcom_rpm_smd_freeze','qcom_rpm_smd_thaw','qcom_rpm_smd_register_sleep','qcom_rpm_smd_unregister_sleep','qcom_rpm_smd_prepare_sleep','qcom_rpm_smd_finish_sleep','qcom_rpm_smd_sleep_ready']
smd=['qcom_smd_rpm_get_irq','qcom_channel_scan_worker','qcom_channel_state_worker','qcom_smd_sleep_notify']
def func(t,n):
 m=re.search(r'(?:static\s+)?(?:int|void|bool)\s+'+n+r'\s*\([^;{}]*\)\s*\{',t);assert m,n
 i=m.end();d=1
 while d:d+=(t[i]=='{')-(t[i]=='}');i+=1
 return t[m.start():i]+'\n'
def structure(t,n):return re.search(r'struct '+n+r' \{.*?\n\};',t,re.S)[0]+'\n'
functions={n:func(files['drivers/rpmsg/qcom_smd.c' if n in smd else 'drivers/soc/qcom/smd-rpm.c'],n) for n in smd+rpm}
model=(B/'transport-sleep-services.c').read_text()+structure(files['include/linux/soc/qcom/smd-rpm.h'],'qcom_rpm_smd_sleep_token')+structure(files['drivers/soc/qcom/smd-rpm.c'],'qcom_smd_rpm')+(B/'transport-sleep-adapters.c').read_text()+''.join(functions.values())+(B/'transport-sleep-cases.c').read_text()
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=45);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=len(functions),bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},source_SHA256={n:hashlib.sha256(t.encode()).hexdigest() for n,t in files.items()},model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['channel state, endpoint fields and receive IRQ','work scheduling and child removal','system PM callback scheduling'],real_host_services=['POSIX mutexes, condition variables and concurrent worker'],actual_SMD_parse_probe_remove_included=False,kernel_concurrency_qualified=False,physical_transport_qualification=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
