# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
from datetime import datetime,timezone
import copy,hashlib,json,os,signal,subprocess,sys
N=Path(__file__).resolve().parent;Q=N.parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'DT-01';O.mkdir();site=R/'local/power-managed-port-01/schema-venv/lib64/python3.14/site-packages';style=R/'local/camss-msm8226-media-next-01/style-tools/site';venv=R/'local/power-managed-port-01/schema-venv/bin';sys.path[:0]=[str(style),str(site)];import dtschema
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();old=json.loads((Q/'bindings-torch-01/DT-qualification-01/full-schema-results.json').read_text());names=[r['board'] for r in old];assert len(names)==19;out=O/'out';out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((Q/'system-coordinator-01/native-01/arm-normal-CPU-enabled-system-on-out/.config').read_bytes());env=os.environ|{'PATH':str(style/'bin')+os.pathsep+str(venv)+os.pathsep+os.environ['PATH'],'PYTHONPATH':str(style)+os.pathsep+str(site),'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'}
selected=['net/nfc/nxp,nci.yaml','remoteproc/qcom,wcnss-pil.yaml','soc/qcom/qcom,wcnss.yaml'];binding_hashes={f:sha(C/'Documentation/devicetree/bindings'/f) for f in selected};j=dict(passed=False,state='prepared',stages=[],phone_access=False,source_bindings=binding_hashes);child=None;save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 make=['make','O='+str(out),'ARCH=arm','LLVM=-21','W=1','-j2']
 for label,args in [('config',['olddefconfig']),('bindings',['DT_SCHEMA_FILES='+':'.join(selected),'dt_binding_check']),('DTBs',['qcom/'+name for name in names])]:
  log=O/(label+'.log')
  with log.open('xb') as stream:
   child=subprocess.Popen(make+args,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=1200)
  diagnostics=[l for l in log.read_text().splitlines() if 'warning' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(label=label,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0
  if label!='DTBs':assert not diagnostics,diagnostics
 schema=out/'Documentation/devicetree/bindings/processed-schema.json';validator=dtschema.DTValidator([str(schema)]);rows=[];trees={};baseline_trees={}
 for row in old:
  name=row['board'];dtb=out/'arch/arm/boot/dts/qcom'/name;previous=(Q/'bindings-torch-01/Falcon-01/arch/arm/boot/dts/qcom'/name if name=='msm8226-motorola-falcon.dtb' else Q/'system-coordinator-01/DTBs-01/candidate-out/arch/arm/boot/dts/qcom'/name);assert sha(previous)==row['DTB_SHA256'];r=subprocess.run([str(venv/'dt-validate'),'-s',str(schema),str(dtb)],env=env,capture_output=True,text=True,timeout=60);(O/(name+'.schema.stdout')).write_text(r.stdout);(O/(name+'.schema.stderr')).write_text(r.stderr);assert r.returncode==0 and not r.stdout and not r.stderr,(name,r.stderr[:1500]);same=sha(dtb)==row['DTB_SHA256'];expected_same=name not in ['qcom-msm8926-lg-madai.dtb','qcom-msm8926-lg-madai-suspend.dtb'];assert same==expected_same,name;rows.append(dict(board=name,DTB_SHA256=sha(dtb),previous_SHA256=row['DTB_SHA256'],byte_identical=same,full_schema_silent=True));trees[name]=validator.decode_dtb(dtb.read_bytes())[0];baseline_trees[name]=validator.decode_dtb(previous.read_bytes())[0]
 def flatten(tree):
  nodes={}
  def walk(node,path):
   nodes[path]={k:v for k,v in node.items() if not isinstance(v,dict)}
   for k,v in node.items():
    if isinstance(v,dict):walk(v,path.rstrip('/')+'/'+k)
  walk(tree,'/');return nodes
 def normalize(tree):
  nodes=flatten(tree);ph={n['phandle']:path for path,n in nodes.items() if 'phandle' in n};out=copy.deepcopy(nodes)
  for path,node in out.items():
   node.pop('phandle',None)
   for prop,value in node.items():
    if validator.property_get_type(prop) in [{'phandle'},{'phandle-array'}]:
     for row in value:
      if row[0]:assert row[0] in ph,(path,prop,row);row[0]=ph[row[0]]
  return out
 diffs={}
 for name in ['qcom-msm8926-lg-madai.dtb','qcom-msm8926-lg-madai-suspend.dtb']:
  a=normalize(baseline_trees[name]);b=normalize(trees[name]);added=set(b)-set(a);assert not set(a)-set(b);assert len(added)==4 and sum(p.endswith('/nfc@28') for p in added)==1 and all('/nfc-' in p or p.endswith('/nfc@28') for p in added),added
  changed={p:{k:dict(before=a[p].get(k),after=b[p].get(k)) for k in set(a[p])|set(b[p]) if a[p].get(k)!=b[p].get(k)} for p in a if a[p]!=b[p]};assert len(changed)==2,changed
  assert sorted([sorted(v) for v in changed.values()])==[['clock-frequency','status'],['drive-strength']],changed;diffs[name]=dict(added_nodes=sorted(added),changed_existing=changed)
  nfc=next(b[p] for p in added if p.endswith('/nfc@28'));assert nfc['compatible']==['nxp,pn547','nxp,nxp-nci-i2c'] and nfc['reg']==[[0x28]] and nfc['clock-names']==['ref'];assert nfc['interrupts']==[[21,1]] and nfc['enable-gpios'][0][1:]==[20,0] and nfc['firmware-gpios'][0][1:]==[22,0]
 node=next(n for p,n in flatten(trees['qcom-msm8926-lg-madai.dtb']).items() if p.endswith('/nfc@28'));controls=[]
 def check(label,node,valid,prop=None):
  errors=list(validator.iter_errors(node,filter=['net/nfc/nxp,nci.yaml']));assert (not errors) if valid else bool(errors) and any(prop in str(e.path) or prop in str(e.schema_path) or prop in e.message or e.schema is False for e in errors),(label,[e.message for e in errors]);controls.append(dict(label=label,expected_valid=valid,diagnostics=len(errors),property=prop))
 check('production-ref-clock',copy.deepcopy(node),True);legacy=copy.deepcopy(node);legacy.pop('clocks');legacy.pop('clock-names');check('legacy-clockless',legacy,True)
 for prop in ['clocks','clock-names']:
  bad=copy.deepcopy(node);bad.pop(prop);check('missing-'+prop,bad,False,prop)
 for label,prop,value in [('wrong-name','clock-names',['wrong']),('two-names','clock-names',['ref','ref']),('two-clocks','clocks',node['clocks']*2),('unknown-property','nxp,unexpected',True)]:
  bad=copy.deepcopy(node);bad[prop]=value;check(label,bad,False,prop)
 assert all(sha(C/'Documentation/devicetree/bindings'/f)==h for f,h in binding_hashes.items());j.update(passed=True,state='terminal success',DTBs=rows,full_current_19_board_schema_passed=True,seventeen_other_DTBS_byte_identical=True,normal_and_suspend_changes_only_NFC_and_bus_pin=diffs,binding_controls=controls,processed_schema_SHA256=sha(schema),selected_binding_examples=3)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,DTBs=19,unchanged=17,binding_controls=len(controls))))
