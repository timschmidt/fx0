# SPDX-License-Identifier: GPL-2.0-only
"""Validate complete maintained DTBs and focused malformed binding controls."""
from pathlib import Path
import copy,hashlib,json,os,subprocess,sys
N=Path(__file__).resolve().parent;R=N.parents[2];site=R/'local/power-managed-port-01/schema-venv/lib64/python3.14/site-packages';style=R/'local/camss-msm8226-media-next-01/style-tools/site';sys.path[:0]=[str(style),str(site)];import dtschema
O=N/'DT-qualification-01';O.mkdir();schema=N/'bindings-01-out/Documentation/devicetree/bindings/processed-schema.json';validator=dtschema.DTValidator([str(schema)]);sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();env=os.environ|{'PYTHONPATH':str(style)+os.pathsep+str(site),'PYTHONDONTWRITEBYTECODE':'1'};validate=R/'local/power-managed-port-01/schema-venv/bin/dt-validate';rows=[]
for old in json.loads((N.parent/'bindings-torch-01/DT-qualification-01/full-schema-results.json').read_text()):
 board=old['board'];dtb=(N.parent/'bindings-torch-01/Falcon-01/arch/arm/boot/dts/qcom'/board if board=='msm8226-motorola-falcon.dtb' else N.parent/'system-coordinator-01/DTBs-01/candidate-out/arch/arm/boot/dts/qcom'/board);assert sha(dtb)==old['DTB_SHA256'];r=subprocess.run([str(validate),'-s',str(schema),str(dtb)],capture_output=True,text=True,env=env,timeout=60);(O/(board+'.stdout')).write_text(r.stdout);(O/(board+'.stderr')).write_text(r.stderr);assert r.returncode==0 and not r.stdout and not r.stderr,(board,r.stderr[:1500]);rows.append(dict(board=board,DTB_SHA256=sha(dtb),returncode=0,silent=True))
 if board=='qcom-msm8926-lg-madai.dtb':tree=validator.decode_dtb(dtb.read_bytes())[0]
touch=tree['soc']['i2c@f9927000']['touchscreen@20'];panel=tree['soc']['display-subsystem@fd900000']['dsi@fd922800']['panel@0'];controls=[]
def check(label,node,valid,filter,prop=None):
 errors=list(validator.iter_errors(node,filter=[filter]));assert (not errors) if valid else bool(errors) and any(prop in str(e.path) or prop in str(e.schema_path) or prop in e.message or e.schema is False for e in errors),(label,[e.message for e in errors]);controls.append(dict(label=label,expected_valid=valid,diagnostics=len(errors),property=prop))
check('normal-I2C-panel-follower',copy.deepcopy(touch),True,'input/syna,rmi4.yaml');node=copy.deepcopy(touch);node.pop('panel');check('I2C-no-panel',node,True,'input/syna,rmi4.yaml');spi=copy.deepcopy(node);spi['compatible']=['syna,rmi4-spi'];spi.pop('syna,startup-delay-ms',None);spi.pop('syna,reset-delay-ms',None);check('SPI-no-panel',spi,True,'input/syna,rmi4.yaml')
for label,value in [('two-phandles',[[44],[44]]),('string',['not-a-phandle']),('empty',[])]:
 node=copy.deepcopy(touch);node['panel']=value;check('RMI-panel-'+label,node,False,'input/syna,rmi4.yaml','panel')
node=copy.deepcopy(spi);node['panel']=touch['panel'];check('SPI-with-panel',node,False,'input/syna,rmi4.yaml','panel');node=copy.deepcopy(touch);node['syna,unexpected-control']=[[1]];check('unknown-RMI-property',node,False,'input/syna,rmi4.yaml','syna,unexpected-control')
check('normal-production-panel',copy.deepcopy(panel),True,'display/panel/lg,fx0-panel.yaml')
for prop in ['reg','vdd-supply','reset-gpios','io-enable-gpios','positive-enable-gpios','negative-enable-gpios','backlight','port']:
 node=copy.deepcopy(panel);node.pop(prop);check('panel-missing-'+prop,node,False,'display/panel/lg,fx0-panel.yaml',prop)
for prop in ['reg','reset-gpios','backlight','io-enable-gpios']:
 node=copy.deepcopy(panel);node[prop]=panel[prop]*2;check('panel-duplicate-'+prop,node,False,'display/panel/lg,fx0-panel.yaml',prop)
node=copy.deepcopy(panel);node['lge,unexpected-control']=[[1]];check('unknown-panel-property',node,False,'display/panel/lg,fx0-panel.yaml','lge,unexpected-control')
check('normal-Madai-compatible',copy.deepcopy(tree),True,'arm/qcom.yaml')
for label,value in [('missing-fallback',['lg,madai','qcom,msm8926']),('wrong-order',['lg,madai','qcom,msm8226','qcom,msm8926'])]:
 node=copy.deepcopy(tree);node['compatible']=value;check('Madai-'+label,node,False,'arm/qcom.yaml','compatible')
(O/'full-schema-results.json').write_text(json.dumps(rows,indent=2)+'\n');(O/'qualification.json').write_text(json.dumps(dict(passed=True,DTBs=len(rows),all_prior_DTBs_byte_identical=True,full_current_LTS_family_schema_gate_passed=True,binding_cases=len(controls),controls=controls,processed_schema_SHA256=sha(schema),DTS_source_changed=False,runtime_firmware_or_hardware_execution=False,phone_access=False),indent=2)+'\n');print(json.dumps(dict(passed=True,full_schema_DTBS=len(rows),binding_cases=len(controls))))
