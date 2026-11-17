# SPDX-License-Identifier: GPL-2.0-only
"""Check real current USB/charger schemas using complete compiled board nodes."""
from pathlib import Path
import copy,hashlib,json,os,subprocess,sys
N=Path(__file__).resolve().parent;R=N.parents[2];site=R/'local/power-managed-port-01/schema-venv/lib64/python3.14/site-packages';style=R/'local/camss-msm8226-media-next-01/style-tools/site';sys.path[:0]=[str(style),str(site)];import dtschema
O=N/'schema-controls-01';O.mkdir();schema=N/'bindings-01-out/Documentation/devicetree/bindings/processed-schema.json';dtb=N.parent/'system-coordinator-01/DTBs-01/candidate-out/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();validator=dtschema.DTValidator([str(schema)]);tree=validator.decode_dtb(dtb.read_bytes())[0];charger=tree['soc']['spmi@fc4cf000']['pm8226@0']['charger@1000'];rows=[]
def check(label,node,valid,property=None,filter='qcom,pm8941-charger'):
 errors=list(validator.iter_errors(node,filter=[filter]))
 if valid:assert not errors,(label,[e.message for e in errors])
 else:assert errors and any(property in str(e.path) or property in str(e.schema_path) or property in e.message or (e.schema is False and e.instance==node.get(property)) for e in errors),(label,[e.message for e in errors])
 rows.append(dict(label=label,expected_valid=valid,errors=len(errors),property_diagnostic_verified=True))
check('normal-current-charger',copy.deepcopy(charger),True)
runtime=copy.deepcopy(charger);runtime['qcom,boot-charge-inhibited']=True;runtime['lg,battery-charge-profile']=['tocad-madai'];runtime['monitored-battery']=[[1]];check('simulated-runtime-profile',runtime,True)
for label,prop,value in [('managed-manual-limit','usb-charge-current-limit',500000),('wrong-variant','compatible',['qcom,pm8941-charger']),('unknown-profile','lg,battery-charge-profile',['unknown']),('nonboolean-opt-in','qcom,software-charge-control',['enabled']),('nonboolean-runtime-marker','qcom,boot-charge-inhibited',[[1]]),('two-batteries','monitored-battery',[[1],[2]])]:
 node=copy.deepcopy(runtime);node[prop]=value;check(label,node,False,prop)
node=copy.deepcopy(runtime);node.pop('qcom,software-charge-control');check('runtime-without-opt-in',node,False,'qcom,software-charge-control')
child=copy.deepcopy(charger['charge-policy']);check('normal-policy',child,True,filter='lg,madai-charge-policy')
for label,prop,value in [('reversed-channel-names','io-channel-names',['voltage','thermistor']),('extra-channel','io-channels',child['io-channels']+child['io-channels'][:1]),('unknown-child-property','lg,unexpected-control',[[1]])]:
 node=copy.deepcopy(child);node[prop]=value;check(label,node,False,prop,filter='lg,madai-charge-policy')
script=N/'harness/diagnostics/smbb-charging-policy/check-usb-binding-contract.py';env=os.environ|{'PYTHONPATH':str(style)+os.pathsep+str(site),'PYTHONDONTWRITEBYTECODE':'1'};run=subprocess.run([sys.executable,'-B',str(script),'--schema',str(schema),'--dtb',str(dtb),'--output',str(O/'USB')],capture_output=True,text=True,env=env,timeout=60);(O/'USB.stdout').write_text(run.stdout);(O/'USB.stderr').write_text(run.stderr);assert run.returncode==0 and not run.stderr,(run.returncode,run.stderr)
usb=json.loads((O/'USB/verified.json').read_text());assert usb['cases']==14
(O/'qualification.json').write_text(json.dumps(dict(passed=True,charger_policy_cases=len(rows),charger_policy_results=rows,USB_cases=14,DTB_SHA256=sha(dtb),schema_SHA256=sha(schema),runtime_firmware_handoff_simulated=True,phone_access=False,physical_acceptance=False),indent=2)+'\n');print(json.dumps(dict(passed=True,charger_policy_cases=len(rows),USB_cases=14)))
