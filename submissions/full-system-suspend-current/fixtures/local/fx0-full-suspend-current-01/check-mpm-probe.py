# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir(exist_ok=False)
B=Path(__file__).resolve().parent;s=(a.source/'drivers/irqchip/irq-qcom-mpm.c').read_text();names=['gic_hwirq_is_mapped','qcom_mpm_probe'];functions={}
for name in names:
 m=re.search(r'static (?:bool|int) '+name+r'\([^;{}]*\)\s*\{',s);assert m;i=m.end();d=1
 while d:d+=(s[i]=='{')-(s[i]=='}');i+=1
 functions[name]=s[m.start():i]+'\n'
structs='\n'.join(re.search(r'struct '+name+r' \{.*?\n\};',s,re.S)[0] for name in ['mpm_gic_map','qcom_mpm_wake_domain','qcom_mpm_priv'])
model=(B/'mpm-probe-services.c').read_text()+structs+(B/'mpm-probe-adapters.c').read_text()+''.join(functions.values())+(B/'mpm-probe-cases.c').read_text();(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env);(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,actual_functions=2,bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},source_SHA256=hashlib.sha256(s.encode()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),services_synthetic=['fixed DT public routing data, resource maps and devres','genpd/provider/mailbox/domain/IRQ registration and failure','wake-domain cache initialization'],actual_kernel_resource_concurrency_qualified=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert not r.returncode,r.stderr
