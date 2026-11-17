# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent
source=a.source/'drivers/irqchip/irq-qcom-mpm.c';t=source.read_text()
names=['qcom_mpm_read','qcom_mpm_write','get_mpm_gic_map','qcom_mpm_handler','qcom_mpm_register_sleep','qcom_mpm_unregister_sleep','qcom_mpm_prepare_sleep','qcom_mpm_put_node','qcom_mpm_init_wake_domains','qcom_mpm_pin_enabled','qcom_mpm_irq_covered','qcom_mpm_wake_covered','qcom_mpm_sleep_ready','qcom_mpm_finish_sleep','mpm_pd_power_off']
def func(name):
 m=re.search(r'(?:static\s+)?(?:int|bool|void|u32|irqreturn_t|struct mpm_gic_map \*)\s*'+name+r'\s*\([^;{}]*\)\s*\{',t);assert m,name
 i=m.end();d=1
 while d:d+=(t[i]=='{')-(t[i]=='}');i+=1
 return t[m.start():i]+'\n'
structs='\n'.join(re.search(r'struct '+n+r' \{.*?\n\};',t,re.S)[0] for n in ['mpm_gic_map','qcom_mpm_wake_domain','qcom_mpm_priv'])
model=(B/'mpm-sleep-services.c').read_text()+structs+(B/'mpm-sleep-adapters.c').read_text()+''.join(func(n) for n in names)+(B/'mpm-sleep-cases.c').read_text()
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=len(names),bindings={n:hashlib.sha256(func(n).encode()).hexdigest() for n in names},source_SHA256=hashlib.sha256(source.read_bytes()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['IRQ descriptors, actions and domains','DT node enumeration and references','devres and fault injection','register IO and mailbox delivery'],actual_provider_probe_included=False,physical_wake_qualification=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
