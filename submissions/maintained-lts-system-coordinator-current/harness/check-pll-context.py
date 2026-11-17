# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--expect-failure',action='store_true');a=p.parse_args()
a.output.mkdir(parents=True,exist_ok=False);B=Path(__file__).resolve().parent
s=(a.source/'drivers/clk/qcom/clk-pll.c').read_text();h=(a.source/'drivers/clk/qcom/clk-pll.h').read_text();new=(a.source/'drivers/clk/qcom/clk-pll-suspend.h').read_text()
def function(text,name):
 m=re.search(r'\b'+re.escape(name)+r'\s*\([^;{}]*\)\s*\{',text);assert m,name
 start=text.rfind('\n\n',0,m.start())+2;i=m.end();depth=1
 while depth:depth+=(text[i]=='{')-(text[i]=='}');i+=1
 return text[start:i]+'\n'
def struct(text,name):
 m=re.search(r'struct '+name+r' \{.*?\n\};',text,re.S);assert m,name
 return m.group()+'\n'
names=['clk_pll_rate_error','clk_pll_disable_checked','clk_pll_disable','clk_pll_suspend_prepare','clk_pll_suspend_unprepare','clk_pll_recalc_rate','find_freq','clk_pll_determine_rate','wait_for_pll','clk_pll_sr2_enable','clk_pll_sr2_set_rate']
functions={n:function(new if n.startswith('clk_pll_suspend_') else s,n) for n in names}
constants='\n'.join(l for l in s.splitlines() if l.startswith('#define PLL_'))+'\n'
common=(a.source/'drivers/clk/qcom/common.h').read_text();m=re.search(r'^#define PLL_VOTE_FSM_ENA\s+.*$',common,re.M);assert m;constants+=m.group()+'\n'
ops=re.search(r'const struct clk_ops clk_pll_sr2_ops = \{.*?\n\};',s,re.S).group()+'\n'
model=(B/'pll-context-services.c').read_text()+struct(h,'pll_freq_tbl')+struct(h,'clk_pll')+constants+''.join(functions.values())+ops+(B/'pll-context-cases.c').read_text()
(a.output/'model.c').write_text(model)
env=os.environ|{'TMPDIR':str(a.output.resolve()),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-sign-compare','-Werror=incompatible-function-pointer-types','-fsanitize=address,undefined','-fno-omit-frame-pointer',str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,env=env)
(a.output/'compile.stderr').write_text(r.stderr);assert not r.returncode,r.stderr
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,env=env,timeout=30)
(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(passed=r.returncode==0,returncode=r.returncode,bindings={n:hashlib.sha256(t.encode()).hexdigest() for n,t in functions.items()},actual_functions=len(functions),ops_SHA256=hashlib.sha256(ops.encode()).hexdigest(),model_SHA256=hashlib.sha256(model.encode()).hexdigest(),expected_draft_failure=a.expect_failure,services_synthetic=True,physical_PLL_or_firmware_qualified=False,phone_access=False)
try:j.update(json.loads(r.stdout))
except ValueError:pass
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
if a.expect_failure:assert r.returncode==1 and j['failures']>0 and not any(x in r.stderr for x in ['AddressSanitizer','runtime error:','LeakSanitizer'])
else:assert not r.returncode,r.stderr
