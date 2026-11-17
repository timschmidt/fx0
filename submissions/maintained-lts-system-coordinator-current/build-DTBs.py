# SPDX-License-Identifier: GPL-2.0-only
"""Build all maintained family DTBs, preserving the seventeen earlier targets."""
from pathlib import Path
from datetime import datetime,timezone
from collections import Counter
import hashlib,json,os,signal,subprocess
B=Path(__file__).resolve().parent;R=B.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';P=B.parent/'sleep-prerequisites-01';O=B/'DTBs-01';O.mkdir();out=O/'candidate-out';out.mkdir();(out/'tmp').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();old=json.loads((P/'DTBs-current.json').read_text());assert old['passed'];new='qcom-msm8926-lg-madai-suspend.dtb'
names=sorted({p.with_suffix('.dtb').name for prefix in ['qcom-msm8226','qcom-msm8926','qcom-msm8928','qcom-apq8026','qcom-apq8028'] for p in (C/'arch/arm/boot/dts/qcom').glob(prefix+'*.dts')});assert len(names)==18 and set(names)-set(old['DTBs']['candidate'])=={new}
for name,digest in old['DTBs']['candidate'].items():assert sha(P/'DTBs-01/candidate-out/arch/arm/boot/dts/qcom'/name)==digest
(out/'.config').write_bytes((B/'native-01/arm-normal-CPU-enabled-system-on-out/.config').read_bytes())
j=dict(passed=False,state='prepared',stages=[],phone_access=False,physical_acceptance=False,full_global_schema_gate=False,started_UTC=datetime.now(timezone.utc).isoformat());child=None
save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 make=['make','O='+str(out),'ARCH=arm','LLVM=-21','W=1','-j2'];env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'}
 for label,args in [('config',['olddefconfig']),('DTBs',['qcom/'+n for n in names])]:
  with (O/(label+'.log')).open('xb') as log:
   child=subprocess.Popen(make+args,cwd=C,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=300)
  j.pop('active_PID',None);j['stages'].append(dict(label=label,returncode=code,log_SHA256=sha(O/(label+'.log'))));save();assert code==0,label
 candidate={name:sha(out/'arch/arm/boot/dts/qcom'/name) for name in names};unchanged=sorted(old['DTBs']['candidate']);assert all(candidate[n]==old['DTBs']['candidate'][n] for n in unchanged)
 warnings=[line.replace(str(C),'<source>').replace(str(out),'<out>') for line in (O/'DTBs.log').read_text().splitlines() if 'warning' in line.lower() or 'error:' in line.lower()]
 before=old['warnings']['candidate'];extra=Counter(warnings)-Counter(before);missing=Counter(before)-Counter(warnings)
 # The additional target inherits the base DTS warnings. Keep exact deltas for audit.
 j.update(DTBs=candidate,seventeen_prior_DTBS_byte_identical=unchanged,baseline_warning_lines=len(before),candidate_warning_lines=len(warnings),extra_warning_lines=dict(extra),missing_warning_lines=dict(missing));save()
 schema=B/'bindings-01-out/Documentation/devicetree/bindings/processed-schema.json';validator=R/'local/power-managed-port-01/schema-venv/bin/dt-validate'
 filters=['opp/opp-v2-kryo-cpu.yaml','opp/opp-v2-qcom-level.yaml','power/avs/qcom,cpr.yaml','regulator/qcom,spmi-regulator.yaml','soc/qcom/qcom,saw2.yaml','nvmem/qcom,qfprom.yaml','regulator/qcom,smd-rpm-regulator.yaml','interrupt-controller/qcom,mpm.yaml','power/qcom,msm8226-system-pm.yaml','soc/qcom/qcom,smd-rpm.yaml'];checks=[]
 for name in names:
  for index,selected in enumerate(filters):
   log=O/(name+'.schema-'+str(index)+'.log');r=subprocess.run([str(validator),'-s',str(schema),'-l',selected,str(out/'arch/arm/boot/dts/qcom'/name)],capture_output=True,timeout=60);log.write_bytes(r.stdout+r.stderr);checks.append(dict(board=name,schema=selected,returncode=r.returncode,silent=not r.stdout and not r.stderr,log_SHA256=sha(log)))
 j.update(schema_checks=checks,processed_schema_SHA256=sha(schema));save();assert all(x['returncode']==0 and x['silent'] for x in checks),'Selected schema diagnostics retained'
 j.update(passed=True,state='terminal success')
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,DTBs=18,prior_unchanged=17,selected_schema_checks=len(checks))))
