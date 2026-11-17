# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,subprocess,os,signal
base=Path(__file__).resolve().parent;root=base.parents[2];source=root/'worktrees/linux-fx0-lts-integration-current-01';out=base/'bindings-01-out';out.mkdir(mode=0o700)
(out/'tmp').mkdir()
controller=base/'bindings-01-controller.json';assert not controller.exists()
site=root/'local/power-managed-port-01/schema-venv/lib64/python3.14/site-packages';venv=root/'local/power-managed-port-01/schema-venv/bin';style=root/'local/camss-msm8226-media-next-01/style-tools/site'
env=os.environ|{'PATH':str(style/'bin')+os.pathsep+str(venv)+os.pathsep+os.environ['PATH'],'PYTHONPATH':str(style)+os.pathsep+str(site),'PYTHONDONTWRITEBYTECODE':'1','TMPDIR':str(out/'tmp')}
names=['opp/opp-v2-kryo-cpu.yaml','opp/opp-v2-qcom-level.yaml','power/avs/qcom,cpr.yaml','regulator/qcom,spmi-regulator.yaml','soc/qcom/qcom,saw2.yaml','regulator/qcom,smd-rpm-regulator.yaml','interrupt-controller/qcom,mpm.yaml','power/qcom,msm8226-system-pm.yaml','soc/qcom/qcom,smd-rpm.yaml'];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();source_hash={n:sha(source/'Documentation/devicetree/bindings'/n) for n in names}
record=dict(started_UTC=datetime.now(timezone.utc).isoformat(),base='8e6fa853a34c0142b9f3e39b55e17ec44089c9fc',binding_SHA256=source_hash,phone_access=False,state='prepared')
command=['make','O='+str(out),'ARCH=arm','LLVM=-21','W=1','-j2','DT_SCHEMA_FILES='+':'.join(names),'dt_binding_check'];record['command']=command
child=None
try:
 with (base/'bindings-01.log').open('xb') as f:
  child=subprocess.Popen(command,cwd=source,env=env,stdout=f,stderr=subprocess.STDOUT,start_new_session=True);record.update(state='running',active_PID=child.pid);controller.write_text(json.dumps(record,indent=2)+'\n');code=child.wait(timeout=1200)
 lines=(base/'bindings-01.log').read_text().splitlines();diags=[s for s in lines if 'warning' in s.lower() or 'error:' in s.lower()]
 record.update(returncode=code,diagnostics=diags);assert code==0 and not diags,(code,diags[:3]);assert {n:sha(source/'Documentation/devicetree/bindings'/n) for n in names}==source_hash
 record.update(passed=True,state='terminal success',full_processed_schema_SHA256=sha(out/'Documentation/devicetree/bindings/processed-schema.json'))
except BaseException as e:
 record.update(passed=False,state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  try:os.killpg(child.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 record.pop('active_PID',None);record.update(owned_child_terminal_and_reaped=child is None or child.returncode is not None,finished_UTC=datetime.now(timezone.utc).isoformat());controller.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({'binding_examples_lint_meta_schema_passed':True}))
