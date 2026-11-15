# SPDX-License-Identifier: GPL-2.0-only
"""Compare real PM8226 boards and validate the enabled upstream torch example."""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,json,re,subprocess,sys
import dtschema
if sys.flags.optimize:
    raise RuntimeError('Assertions must remain enabled')
p=argparse.ArgumentParser(description=__doc__)
for name in ['inventory','affected-inventory','baseline-build','candidate-build','baseline-log','candidate-log','binding-log','source','output']:
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip()
assert head=='3c4dccb16e558b2100fdfb79cea0933cc8d223c7'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=a.source,text=True).strip()
a.output.mkdir(mode=0o700)
schema=a.candidate_build/'Documentation/devicetree/bindings/processed-schema.json'
v=dtschema.DTValidator([str(schema)])
def flatten(tree):
    out={}
    def walk(node,path):
        out[path]={k:x for k,x in node.items() if not isinstance(x,dict)}
        for k,x in node.items():
            if isinstance(x,dict):walk(x,path.rstrip('/')+'/'+k)
    walk(tree,'/');return out
def normalize(tree):
    flat=flatten(tree);refs={n['phandle']:path for path,n in flat.items() if 'phandle' in n};out=copy.deepcopy(flat)
    for path,n in out.items():
        n.pop('phandle',None)
        for prop,value in n.items():
            if v.property_get_type(prop) in [{'phandle'},{'phandle-array'}]:
                assert isinstance(value,list),(path,prop)
                for row in value:
                    assert isinstance(row,list) and row,(path,prop,row)
                    if row[0]:
                        assert row[0] in refs,(path,prop,row)
                        row[0]=refs[row[0]]
    return out
matrix=json.loads(a.inventory.read_text());affected={x['target'] for x in json.loads(a.affected_inventory.read_text())};assert len(matrix)==18 and len(affected)==17
paths=[];compared=[];controls=[];unaffected=[]
for board in matrix:
    rel=Path('arch/arm/boot/dts')/board['target'];old_bytes=(a.baseline_build/rel).read_bytes();path=a.candidate_build/rel;new_bytes=path.read_bytes()
    old=normalize(v.decode_dtb(old_bytes)[0]);new=normalize(v.decode_dtb(new_bytes)[0]);added=set(new)-set(old);assert not set(old)-set(new)
    for name,node in old.items():assert new[name]==node,(board['target'],name)
    if board['target'] in affected:
        assert len(added)==1,(board['target'],added)
        node=next(iter(added));assert node.endswith('/pm8226@1/led-controller@d300')
        assert new[node]=={'compatible':['qcom,pm8226-flash-led','qcom,pm8941-flash-led'],'reg':[[0xd300]],'status':['disabled']},(board['target'],new[node])
        parents=[n for n in new if n.endswith('/pm8226@0/pon@800')];assert len(parents)==1
        assert new[parents[0]]==old[parents[0]] and old[parents[0]]['compatible']==['qcom,pm8916-pon']
    else:
        assert not added and new_bytes==old_bytes,board['target'];unaffected.append(board['target'])
    compared.append({'board':board['target'],'existing_nodes_preserved':len(old),'added_nodes':sorted(added),'SHA256':hashlib.sha256(new_bytes).hexdigest()});paths.append(path)
assert unaffected==['qcom/qcom-msm8226-samsung-s3ve3g.dtb']
cli=Path(sys.executable).parent/'dt-validate'
filters='leds/qcom,pm8941-flash-led.yaml:power/reset/qcom,pon.yaml:mfd/qcom,spmi-pmic.yaml:remoteproc/qcom,wcnss-pil.yaml:soc/qcom/qcom,wcnss.yaml:soc/qcom/qcom,smp2p.yaml:remoteproc/qcom,smd-edge.yaml:reserved-memory/:media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml:display/msm/gpu.yaml'
common=[str(cli),'-s',str(schema),'-l',filters]
r=subprocess.run(common+list(map(str,paths)),capture_output=True,timeout=120)
(a.output/'direct-boards.stdout').write_bytes(r.stdout);(a.output/'direct-boards.stderr').write_bytes(r.stderr);assert r.returncode==0 and not r.stdout and not r.stderr
example=a.candidate_build/'Documentation/devicetree/bindings/leds/qcom,pm8941-flash-led.example.dtb';flat=flatten(v.decode_dtb(example.read_bytes())[0]);leds=[n for n,x in flat.items() if x.get('compatible')==['qcom,pm8226-flash-led','qcom,pm8941-flash-led']];assert len(leds)==1
controller=leds[0];led=controller+'/led'
def case(name,mutation):
    path=a.output/(name+'.dtb');path.write_bytes(example.read_bytes());subprocess.run(['fdtput',*mutation[:2],str(path),*mutation[2:]],check=True)
    r=subprocess.run(common+[str(path)],capture_output=True,timeout=30);(a.output/(name+'.stdout')).write_bytes(r.stdout);(a.output/(name+'.stderr')).write_bytes(r.stderr);return r
for name,mutation,diagnostic in [
    ('wrong-fallback',['-t','s',controller,'compatible','qcom,pm8226-flash-led','qcom,unrelated'],'compatible'),
    ('current-too-low',['-t','i',led,'led-max-microamp','12499'],'led-max-microamp'),
    ('current-too-high',['-t','i',led,'led-max-microamp','200001'],'led-max-microamp'),
    ('missing-current-limit',['-d','--',led,'led-max-microamp'],'led-max-microamp'),
    ('missing-LED',['-r','--',led],'led'),
    ('extra-LED',['-c','--',controller+'/led2'],'led2'),
    ('extra-register',['-t','x',controller,'reg','d300','d400'],'reg'),
]:
    r=case(name,mutation);assert r.returncode==0 and not r.stdout and diagnostic.encode() in r.stderr and b'from schema $id:' in r.stderr,name
    controls.append({'name':name,'expected_property_diagnostic_verified':True})
positive=[]
for name,mutation in [
    ('PM8941-only',['-t','s',controller,'compatible','qcom,pm8941-flash-led']),
    ('minimum-current',['-t','i',led,'led-max-microamp','12500']),
    ('non-multiple-limit',['-t','i',led,'led-max-microamp','12501']),
]:
    r=case(name,mutation);assert r.returncode==0 and not r.stdout and not r.stderr,name;positive.append(name)
def warnings(path):return Counter(re.sub(r'^.*?:\d+\.\d+(?:-\d+\.\d+)?: ','',line) for line in path.read_text().splitlines() if 'Warning (' in line)
oldw,neww=warnings(a.baseline_log),warnings(a.candidate_log);assert oldw==neww
assert not any('warning:' in s.lower() or 'error:' in s.lower() for s in a.binding_log.read_text().splitlines())
record={'passed':True,'source_head':head,'checker_SHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'PMIC_affected_boards':17,'total_DTBs':18,'unaffected_byte_identical_controls':unaffected,'comparisons':compared,'all_existing_nodes_and_properties_preserved':True,'PON_existing_properties_preserved':True,'new_torch_nodes_disabled':17,'existing_DTC_warnings':sum(oldw.values()),'new_DTC_warnings':0,'direct_targeted_DTB_schemas_empty':True,'enabled_ordinary_example_schema_controls':controls,'additional_positive_example_cases':positive,'complete_current_Fx0_DTB_qualified':False,'runtime_or_hardware_qualified':False,'phone_access':False}
(a.output/'qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['passed','PMIC_affected_boards','total_DTBs','existing_DTC_warnings','new_DTC_warnings']}))
