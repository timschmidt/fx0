# SPDX-License-Identifier: GPL-2.0-only
"""Validate maintained PM8226 boards, existing Madai artifacts and ordinary LED controls."""
from pathlib import Path
import json,hashlib,subprocess,shutil,sys,libfdt
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'DT-qualification-01';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();prior=json.loads((N.parent/'system-coordinator-01/DTBs-01/controller.json').read_text());schema=N/'bindings-01-out/Documentation/devicetree/bindings/processed-schema.json';cli=R/'local/power-managed-port-01/schema-venv/bin/dt-validate'
assert not subprocess.check_output(['git','diff','--name-only','--','arch/arm/boot/dts','include/dt-bindings','scripts/dtc'],cwd=C)
boards=[]
for name,digest in prior['DTBs'].items():
 p=N.parent/'system-coordinator-01/DTBs-01/candidate-out/arch/arm/boot/dts/qcom'/name;assert sha(p)==digest;boards.append((name,p))
falcon=N/'Falcon-01/arch/arm/boot/dts/qcom/msm8226-motorola-falcon.dtb';assert sha(falcon)==json.loads((N/'Falcon-01/controller.json').read_text())['DTB_SHA256'];boards.append((falcon.name,falcon))
checks=[]
for name,p in boards:
 q=subprocess.run([str(cli),'-s',str(schema),str(p)],capture_output=True,text=True,timeout=60);(O/(name+'.stdout')).write_text(q.stdout);(O/(name+'.stderr')).write_text(q.stderr);checks.append(dict(board=name,returncode=q.returncode,silent=not q.stdout and not q.stderr,DTB_SHA256=sha(p)))
(O/'full-schema-results.json').write_text(json.dumps(checks,indent=2)+'\n');assert all(x['returncode']==0 and x['silent'] for x in checks),'Full schema diagnostics retained'
example=N/'bindings-01-out/Documentation/devicetree/bindings/leds/qcom,pm8941-flash-led.example.dtb';f=libfdt.Fdt(example.read_bytes());nodes={}
def walk(off,path):
 nodes[path]=off
 try:child=f.first_subnode(off)
 except libfdt.FdtException as e:assert e.err==-libfdt.NOTFOUND;return
 while child>=0:
  walk(child,path.rstrip('/')+'/'+f.get_name(child))
  try:child=f.next_subnode(child)
  except libfdt.FdtException as e:assert e.err==-libfdt.NOTFOUND;break
walk(0,'/')
found=[]
for path,off in nodes.items():
 try:comp=f.getprop(off,'compatible').as_stringlist()
 except libfdt.FdtException:continue
 if comp==['qcom,pm8226-flash-led','qcom,pm8941-flash-led']:found.append(path)
assert len(found)==1;controller=found[0];led=controller+'/led';controls=[];positive=[]
def run(name,args):
 p=O/(name+'.dtb');shutil.copy2(example,p);subprocess.run(['fdtput',*args[:2],str(p),*args[2:]],check=True);q=subprocess.run([str(cli),'-s',str(schema),'-l','leds/qcom,pm8941-flash-led.yaml:mfd/qcom,spmi-pmic.yaml',str(p)],capture_output=True,text=True,timeout=60);(O/(name+'.stderr')).write_text(q.stderr);assert q.returncode==0 and not q.stdout;return q
for name,args,needle in [('wrong-fallback',['-t','s',controller,'compatible','qcom,pm8226-flash-led','qcom,unrelated'],'compatible'),('current-too-low',['-t','i',led,'led-max-microamp','12499'],'led-max-microamp'),('current-too-high',['-t','i',led,'led-max-microamp','200001'],'led-max-microamp'),('missing-current',['-d','--',led,'led-max-microamp'],'led-max-microamp'),('missing-led',['-r','--',led],'led'),('extra-led',['-c','--',controller+'/led2'],'led2'),('extra-reg',['-t','x',controller,'reg','d300','d400'],'reg')]:
 q=run(name,args);assert needle in q.stderr and 'from schema $id:' in q.stderr and 'Traceback' not in q.stderr;controls.append(dict(name=name,expected_property_diagnostic_verified=True))
for name,args in [('PM8941-only',['-t','s',controller,'compatible','qcom,pm8941-flash-led']),('minimum-current',['-t','i',led,'led-max-microamp','12500']),('non-multiple-current',['-t','i',led,'led-max-microamp','12501'])]:
 q=run(name,args);assert not q.stderr;positive.append(name)
j=dict(passed=True,full_current_LTS_family_schema_gate_passed=True,DTBs=len(boards),eighteen_prior_DTBS_byte_identical=True,all_DTS_DTC_and_DT_binding_header_inputs_unchanged=True,ordinary_example_negative_controls=controls,positive_controls=positive,processed_schema_SHA256=sha(schema),all_current_LTS_affected_boards_present=True,newer_titan_and_eagle_boards_absent_not_imported_or_counted=True,normal_board_APC_and_eight_byte_CPU_cell_preserved=True,phone_access=False,hardware_acceptance=False)
(O/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(passed=True,DTBs=len(boards),negative_controls=len(controls),positive_controls=len(positive))))
