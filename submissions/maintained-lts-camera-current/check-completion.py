# SPDX-License-Identifier: GPL-2.0-only
"""Source-extracted saved-completion dispatch with modeled locks/IRQ inputs."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';ap=argparse.ArgumentParser();ap.add_argument('--kernel',type=Path,default=C);ap.add_argument('--templates',type=Path,default=R/'local/camera-vfe-source-regression-03');ap.add_argument('--output',type=Path,default=N/'completion-03');ap.add_argument('--experimental',type=Path);args=ap.parse_args();C=args.kernel;T=args.templates;O=args.output;O.mkdir();prefix='drivers/media/platform/qcom/camss/';sha=lambda b:hashlib.sha256(b).hexdigest();rows=[];bindings={}
def function(t,n):
 m=re.search(r'^(?:static )?(?:void|u32|irqreturn_t|struct camss_buffer \*)\s*'+n+r'\([^;]*?\)\n\{',t,re.M);assert m,n;return t[m.start():t.index('\n}',m.start())+2]
def extract(path,name):
 t=(C/path).read_text();bindings[path]=sha(t.encode());return function(t,name)
for hw in ['4-1','4-7','4-8']:
 old=T/('candidate-'+hw);t=(old/'test.c').read_text();marker=t.index('static void init_vfe');body=t[:marker];tests=t[marker:];gen=prefix+'camss-vfe-gen1.c';core=prefix+'camss-vfe.c';hwpath=prefix+'camss-vfe-'+hw+'.c'
 pattern=r'^(?:static )?(?:void|u32|irqreturn_t|struct camss_buffer \*)\s*(\w+)\([^;]*?\)\n\{'
 matches=list(re.finditer(pattern,body,re.M));updated=[];pos=0;seenreg=0
 for m in matches:
  name=m[1];end=body.index('\n}',m.start())+2
  if name in ['vfe_buf_get_pending','vfe_buf_add_pending','vfe_isr_comp_done','vfe_isr_reset_ack']:path=core
  elif name=='vfe_isr':path=hwpath
  elif name=='vfe_isr_reg_update':path=gen if seenreg==0 else prefix+'camss-vfe-17x.c';seenreg+=1
  else:path=gen
  actual=extract(path,name);assert args.experimental is None or actual==function((args.experimental/path).read_text(),name),(path,name,'completion equivalence')
  scoped = '#pragma clang diagnostic push\n#pragma clang diagnostic ignored \"-Wsign-compare\"\n'+actual+'\n#pragma clang diagnostic pop' if name in ['vfe_isr_wm_done','vfe_isr'] else actual
  updated += [body[pos:m.start()],scoped];pos=end
 updated.append(body[pos:]);base=''.join(updated)+tests
 # Match the used real state types and IRQ macros; service-only structs remain modeled.
 header=(C/(prefix+'camss-vfe.h')).read_text();types=(old/'kernel-types.h').read_text()
 for name in ['vfe_output_state','vfe_line_id','vfe_output','vfe_isr_ops']:
  pat=r'(?:enum|struct) '+name+r' \{.*?\n\};';a=re.search(pat,types,re.S);b=re.search(pat,header,re.S);assert a and b and a[0]==b[0],name
 bindings[prefix+'camss-vfe.h']=sha(header.encode())
 for macro in re.findall(r'^#define (VFE_0_\w+)',body,re.M):
  def readmacro(text):
   ls=text.splitlines();start=next(i for i,l in enumerate(ls) if re.match(r'#define '+macro+r'(?:\(|\s)',l));end=start
   while ls[end].endswith('\\'):end+=1
   return '\n'.join(ls[start:end+1])
  assert readmacro(body)==readmacro((C/hwpath).read_text()),macro
 cases=re.findall(r'!strcmp\(name, "([^"]+)"\)',tests);assert len(cases)==28
 for mutation in ['none','idle-guard','irq-reorder','drop-all-coalesced']:
  text=base
  if mutation=='idle-guard':
   a=function(text,'vfe_isr_reg_update');b=a.replace('return stale_wm;', 'return stale_wm & 0;');assert a!=b;text=text.replace(a,b,1)
   a=function(text,'vfe_isr_wm_done');needle='\toutput = &vfe->line[vfe->wm_output_map[wm]].output;';assert needle in a;b=a.replace(needle,needle+'\n\tif (output->state == VFE_OUTPUT_IDLE)\n\t\tgoto out_unlock;');text=text.replace(a,b,1)
  elif mutation!='none':
   mutant=(T/(mutation+'-'+hw)/'test.c').read_text();a=function((old/'test.c').read_text(),'vfe_isr');b=function(mutant,'vfe_isr');actual=function(text,'vfe_isr');assert a==actual and a!=b;text=text.replace(actual,b,1)
  out=O/(hw+'-'+mutation);out.mkdir();(out/'tmp').mkdir();(out/'test.c').write_text(text)
  for f in ['shim.h','kernel-types.h']:(out/f).write_bytes((old/f).read_bytes())
  cmd=['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(out/'test.c'),'-o',str(out/'model')];r=subprocess.run(cmd,capture_output=True,text=True);(out/'compile.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
  results=[]
  for case in cases:
   r=subprocess.run([str(out/'model'),case],capture_output=True,text=True,env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','TMPDIR':str(out/'tmp')},timeout=10)
   assert r.returncode in [0,2] and (not r.stderr or r.stderr.startswith('FAIL:')),(case,r.stderr)
   results.append(dict(case=case,returncode=r.returncode,stdout=r.stdout,stderr=r.stderr))
  failures=sum(x['returncode']!=0 for x in results);assert (failures==0)==(mutation=='none'),(hw,mutation,failures)
  (out/'results.json').write_text(json.dumps(results,indent=2)+'\n');rows.append(dict(hw=hw,mutation=mutation,cases=len(cases),failures=failures,program_SHA256=sha(text.encode())));(O/'qualification.json').write_text(json.dumps(dict(passed=False,records=rows),indent=2)+'\n')
(O/'qualification.json').write_text(json.dumps(dict(passed=True,records=rows,source_files=bindings,positive_cases=84,negative_variants=9,normal_LSan=True,failfast_UBSAN=True,locks_IRQ_buffers_MMIO_modeled=True,hardware=False,unchanged_wm_done_and_ISR_Wextra_sign_compare_diagnostics_scoped=True),indent=2)+'\n');print(json.dumps(rows))
