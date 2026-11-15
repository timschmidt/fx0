# SPDX-License-Identifier: GPL-2.0-only
"""Check complete actual-board WCNSS descriptions and preserved memory ranges."""
from pathlib import Path
from collections import Counter
import argparse, copy, hashlib, json, re, subprocess, sys
import dtschema

p=argparse.ArgumentParser(description=__doc__)
for name in ['inventory','baseline-build','candidate-build','baseline-log','candidate-log','binding-log','output','source']:
    p.add_argument('--'+name,type=Path,required=True)
a=p.parse_args()
source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip()
assert source_head=='c3bd956de3414d28aa8273e2a4c746134a4811d3'
assert not subprocess.check_output(['git','status','--porcelain'],cwd=a.source,text=True).strip()
a.output.mkdir(mode=0o700)
schema=a.candidate_build/'Documentation/devicetree/bindings/processed-schema.json'
v=dtschema.DTValidator([str(schema)])
pronto='/soc/remoteproc@fb204000';edge=pronto+'/smd-edge';ctrl=edge+'/wcnss';region='/reserved-memory/wcnss@d200000';smp='/smp2p-wcnss'
added={smp,smp+'/master-kernel',smp+'/slave-kernel',pronto,pronto+'/iris',edge,ctrl,ctrl+'/bluetooth',ctrl+'/wifi'}
def flatten(tree):
    out={}
    def walk(node,path):
        out[path]={k:x for k,x in node.items() if not isinstance(x,dict)}
        for k,x in node.items():
            if isinstance(x,dict):walk(x,path.rstrip('/')+'/'+k)
    walk(tree,'/');return out
def normalize(tree):
    flat=flatten(tree);ph={n['phandle']:path for path,n in flat.items() if 'phandle' in n};out=copy.deepcopy(flat)
    for path,node in out.items():
        node.pop('phandle',None)
        for prop,value in node.items():
            if v.property_get_type(prop) in [{'phandle'},{'phandle-array'}]:
                assert isinstance(value,list),(path,prop)
                for row in value:
                    assert isinstance(row,list) and row,(path,prop,row)
                    if row[0]:
                        assert row[0] in ph,(path,prop,row)
                        row[0]=ph[row[0]]
    return out
def overlap_pairs(flat):
    rows=[]
    for path,n in flat.items():
        if path.startswith('/reserved-memory/') and n.get('status',['okay'])!=['disabled']:
            for start,size in n.get('reg',[]):
                if size:rows.append((path,start,start+size))
    return sorted((x[0],y[0]) for i,x in enumerate(rows) for y in rows[i+1:] if x[0]!=y[0] and max(x[1],y[1])<min(x[2],y[2]))
def contract(tree):
    n=normalize(tree);s=n[smp];r=n[pronto];e=n[edge];c=n[ctrl];w=n[ctrl+'/wifi'];iris=n[pronto+'/iris']
    assert s['compatible']==['qcom,smp2p'] and s['qcom,smem']==[451,431]
    assert s['interrupts']==[[0,143,1]] and s['qcom,local-pid']==0 and s['qcom,remote-pid']==4
    assert s['mboxes']==[['/soc/mailbox@f9011000',18]]
    assert n[smp+'/master-kernel']['#qcom,smem-state-cells']==1
    assert n[smp+'/slave-kernel']['interrupt-controller'] and n[smp+'/slave-kernel']['#interrupt-cells']==2
    assert r['compatible']==['qcom,pronto-v2-pil','qcom,pronto'] and r['status']==['disabled']
    assert r['reg']==[[0xfb204000,0x2000],[0xfb202000,0x1000],[0xfb21b000,0x3000]] and r['reg-names']==['ccu','dxe','pmu']
    assert r['memory-region']==[[region]] and n[region]['no-map'] is True
    assert r['interrupts-extended']==[['/soc/interrupt-controller@f9000000',0,149,1],*[ [smp+'/slave-kernel',i,1] for i in range(4)]]
    assert r['interrupt-names']==['wdog','fatal','ready','handover','stop-ack']
    assert r['power-domain-names']==['cx'] and r['power-domains'][0][1]==0
    assert n[r['power-domains'][0][0]]['compatible']==['qcom,msm8226-rpmpd']
    assert r['qcom,smem-states']==[[smp+'/master-kernel',0]] and r['qcom,smem-state-names']==['stop']
    assert iris['compatible']==['qcom,wcn3660a'] and iris['clock-names']==['xo'] and iris['clocks'][0][1]==42
    assert e['interrupts']==[[0,142,1]] and e['mboxes']==[['/soc/mailbox@f9011000',17]]
    assert e['qcom,smd-edge']==6 and e['qcom,remote-pid']==4 and e['label']==['pronto']
    assert c['compatible']==['qcom,wcnss'] and c['qcom,smd-channels']==['WCNSS_CTRL'] and c['qcom,mmio']==[[pronto]] and c['status']==['disabled']
    assert n[ctrl+'/bluetooth']['compatible']==['qcom,wcnss-bt']
    assert w['compatible']==['qcom,wcnss-wlan'] and w['interrupts']==[[0,145,4],[0,146,4]] and w['interrupt-names']==['tx','rx']
    assert w['qcom,smem-state-names']==['tx-enable','tx-rings-empty'] and [r[1] for r in w['qcom,smem-states']]==[10,9]
    for r in w['qcom,smem-states']:assert r[0]=='/smsm/apps@0'
    assert not [pair for pair in overlap_pairs(n) if region in pair]
    return n

matrix=json.loads(a.inventory.read_text());assert len(matrix)==18
paths=[];comparisons=[];overrides=[]
for board in matrix:
    rel=Path('arch/arm/boot/dts')/board['target'];old=normalize(v.decode_dtb((a.baseline_build/rel).read_bytes())[0]);path=a.candidate_build/rel
    new=contract(v.decode_dtb(path.read_bytes())[0]);expected=added|({region} if region not in old else set())
    assert set(new)-set(old)==expected and not set(old)-set(new),board['target']
    for key,value in old.items():assert new[key]==value,(board['target'],key)
    assert overlap_pairs(old)==overlap_pairs(new),(board['target'],'reserved-memory overlap set changed')
    if region in old:
        overrides.append(dict(board=board['target'],reg=old[region]['reg'],all_original_properties_preserved=True))
    else:assert new[region]['reg']==[[0xd200000,0xa00000]]
    comparisons.append(dict(board=board['target'],existing_nodes_preserved=len(old),new_nodes=sorted(expected),SHA256=hashlib.sha256(path.read_bytes()).hexdigest()))
    paths.append(path)
assert len(overrides)==5
cli=Path(sys.executable).parent/'dt-validate'
filters='remoteproc/qcom,wcnss-pil.yaml:soc/qcom/qcom,wcnss.yaml:soc/qcom/qcom,smp2p.yaml:remoteproc/qcom,smd-edge.yaml:reserved-memory/:media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml:display/msm/gpu.yaml'
common=[str(cli),'-s',str(schema),'-l',filters]
def validate(name,path):
    r=subprocess.run(common+[str(path)],capture_output=True)
    (a.output/(name+'.stdout')).write_bytes(r.stdout);(a.output/(name+'.stderr')).write_bytes(r.stderr)
    return r
positive=subprocess.run(common+list(map(str,paths)),capture_output=True)
(a.output/'direct-boards.stdout').write_bytes(positive.stdout);(a.output/'direct-boards.stderr').write_bytes(positive.stderr)
assert positive.returncode==0 and not positive.stderr and not positive.stdout
controls=[]
for name,mutation in [
    ('unknown-RF-compatible',['-t','s',pronto+'/iris','compatible','qcom,unrelated-rf']),
    ('invalid-SMP2P-smem-count',['-t','x',smp,'qcom,smem','1','2','3']),
    ('invalid-SMD-edge-type',['-t','s',edge,'qcom,smd-edge','invalid']),
    ('invalid-WCNSS-channel',['-t','s',ctrl,'qcom,smd-channels','unrelated']),
    ('invalid-WiFi-IRQ-name',['-t','s',ctrl+'/wifi','interrupt-names','unrelated']),
]:
    path=a.output/(name+'.dtb');path.write_bytes(paths[0].read_bytes());subprocess.run(['fdtput',*mutation[:2],str(path),*mutation[2:]],check=True)
    r=validate(name,path)
    expected_property={'unknown-RF-compatible':'iris:compatible','invalid-SMP2P-smem-count':'qcom,smem',
                       'invalid-SMD-edge-type':'qcom,smd-edge','invalid-WCNSS-channel':'qcom,smd-channels',
                       'invalid-WiFi-IRQ-name':'interrupt-names'}[name]
    assert r.returncode==0 and not r.stdout and expected_property.encode() in r.stderr,name
    assert b'from schema $id:' in r.stderr,name
    controls.append(dict(name=name,returncode=r.returncode,expected_property_diagnostic_verified=True))
contract_controls=[]
for name,node,prop,value in [
    ('wrong-WiFi-trigger',ctrl+'/wifi','interrupts',[[0,145,1],[0,146,1]]),
    ('swapped-SMEM-items',smp,'qcom,smem',[431,451]),
    ('wrong-SMP2P-doorbell',smp,'mboxes',None),
    ('wrong-SMD-pid',edge,'qcom,remote-pid',2),
    ('wrong-RF-identity',pronto+'/iris','compatible',['qcom,wcn3680']),
    ('reserved-WCNSS-overlap',region,'reg',[[0xd200000,0xb00000]]),
]:
    bad=v.decode_dtb(paths[0].read_bytes())[0];cur=bad
    for part in node.strip('/').split('/'):cur=cur[part]
    if value is None:cur[prop][0][1]=17
    else:cur[prop]=value
    try:contract(bad)
    except AssertionError:contract_controls.append(name)
    else:raise AssertionError(name)
# Exercise WCN3660A against the complete ordinary upstream binding example.
example=a.candidate_build/'Documentation/devicetree/bindings/remoteproc/qcom,wcnss-pil.example.dtb'
example_tree=v.decode_dtb(example.read_bytes())[0];flat=flatten(example_tree)
iris_paths=[p for p,n in flat.items() if n.get('compatible')==['qcom,wcn3620']];assert len(iris_paths)==1
rf=a.output/'ordinary-example-WCN3660A.dtb';rf.write_bytes(example.read_bytes());subprocess.run(['fdtput','-t','s',str(rf),iris_paths[0],'compatible','qcom,wcn3660a'],check=True)
r=validate('ordinary-example-WCN3660A',rf);assert r.returncode==0 and not r.stdout and not r.stderr
def warnings(path):return Counter(re.sub(r'^.*?:\d+\.\d+(?:-\d+\.\d+)?: ','',line) for line in path.read_text().splitlines() if 'Warning (' in line)
oldw,neww=warnings(a.baseline_log),warnings(a.candidate_log);assert oldw==neww
assert not any('warning:' in s.lower() or 'error:' in s.lower() for s in a.binding_log.read_text().splitlines())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip()==source_head
result=dict(passed=True,source_head=source_head,checker_SHA256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),board_count=18,comparisons=comparisons,existing_board_WCNSS_overrides=overrides,existing_nodes_and_all_reserved_ranges_preserved=True,
            new_default_regions=13,no_new_actual_reserved_memory_overlap=True,existing_DTC_warnings=sum(oldw.values()),new_DTC_warnings=0,
            direct_targeted_schemas_empty=True,ordinary_enabled_RF_binding_example_WCN3660A_passed=True,schema_controls=controls,platform_controls=contract_controls,
            disabled_common_nodes_preserved=True,board_enabled_supplies_or_current_Fx0_qualified=False,runtime_or_hardware_qualified=False,phone_access=False)
(a.output/'qualification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['passed','board_count','new_default_regions','existing_DTC_warnings','new_DTC_warnings']}))
