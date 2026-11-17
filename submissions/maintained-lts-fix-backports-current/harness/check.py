# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse, hashlib, json, os, re, subprocess
p=argparse.ArgumentParser();p.add_argument('kind',choices=['edge','state','mpm']);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--expect-failure',action='store_true');a=p.parse_args();a.output.mkdir(parents=True,exist_ok=False)
B=Path(__file__).resolve().parent
path='drivers/irqchip/irq-qcom-mpm.c' if a.kind=='mpm' else 'drivers/rpmsg/qcom_smd.c'
source=(a.source/path).read_text();bindings={}
def function(name):
 m=re.search(r'static (?:void|int|bool) '+name+r'\s*\([^;{}]*\)\s*\{',source);assert m,name
 i=m.end();depth=1
 while depth:depth+=(source[i]=='{')-(source[i]=='}');i+=1
 text=source[m.start():i]+'\n';bindings[name]=hashlib.sha256(text.encode()).hexdigest();return text
if a.kind=='edge':model=(B/'edge.c').read_text().replace('/* ACTUAL_FUNCTION */',function('qcom_smd_edge_release'))
elif a.kind=='state':model=(B/'smd-state-services.c').read_text()+function('qcom_channel_state_worker')+(B/'smd-state-cases.c').read_text()
else:
 structs='\n'.join(re.search(r'struct '+name+r' \{.*?\n\};',source,re.S)[0] for name in ['mpm_gic_map','qcom_mpm_priv'])
 adapter='static void qcom_mpm_write(struct qcom_mpm_priv *p,unsigned int reg,unsigned int index,u32 value) {CHECK(p->base==mmio&&reg<5&&index<2&&!value);mmio[2+reg*2+index]=value;}\n'
 model=(B/'mpm-probe-services.c').read_text()+structs+adapter+function('gic_hwirq_is_mapped')+function('qcom_mpm_probe')+(B/'mpm-cases.c').read_text()
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
cmd=['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')]
c=subprocess.run(cmd,env=env,capture_output=True,text=True);(a.output/'compile.stderr').write_text(c.stderr);assert c.returncode==0,c.stderr
r=subprocess.run([str((a.output/'model').resolve())],env=env,capture_output=True,text=True,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
assert not any(x in r.stderr for x in ['Sanitizer','runtime error:']),r.stderr
result=json.loads(r.stdout);assert r.returncode in [0,1]
assert bool(result['failures'])==a.expect_failure and (r.returncode==1)==a.expect_failure,(r.returncode,result)
j=dict(passed=True,expected_failure=a.expect_failure,program_returncode=r.returncode,kind=a.kind,source_path=path,source_SHA256=hashlib.sha256(source.encode()).hexdigest(),bindings=bindings,model_SHA256=hashlib.sha256(model.encode()).hexdigest(),synthetic_kernel_services=True,edge_reference_acquisition_synthetic=a.kind=='edge',kernel_concurrency_qualified=False,phone_access=False,**result)
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
