# SPDX-License-Identifier: GPL-2.0-only
"""Preserve every inherited property and validate all new APR/SLIMbus resources."""
from pathlib import Path
from collections import Counter
import argparse,copy,hashlib,json,re,subprocess,sys
import dtschema
assert not sys.flags.optimize
p=argparse.ArgumentParser(description=__doc__)
for name in ['source','build','baseline','baseline-log','candidate-log','output']:p.add_argument('--'+name,type=Path,required=True)
p.add_argument('--expected-source-head',default='a7ba24173e4618ace25b68ec36991fb08b7b552e')
a=p.parse_args();assert all(getattr(a,k).exists() for k in ['source','build','baseline','baseline_log','candidate_log']);a.output.mkdir(mode=0o700)
head=a.expected_source_head
assert hashlib.sha256((a.source/'arch/arm/boot/dts/qcom/qcom-msm8226.dtsi').read_bytes()).hexdigest()=='f3167d36ca540ffdd6a67211a37e5b595a731c856f763b07a8cfdb5b18243cba'
git_metadata_available=(a.source/'.git').exists()
if git_metadata_available:
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip()==head
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=a.source,text=True)
schema=a.build/'Documentation/devicetree/bindings/processed-schema.json';v=dtschema.DTValidator([str(schema)])
validator=Path(sys.executable).parent/'dt-validate'
def flatten(tree):
 out={}
 def walk(node,path):
  out[path]={k:value for k,value in node.items() if not isinstance(value,dict)}
  for k,value in node.items():
   if isinstance(value,dict):walk(value,path.rstrip('/')+'/'+k)
 walk(tree,'/');return out
def normalize(blob):
 flat=flatten(v.decode_dtb(blob)[0]);refs={node['phandle']:path for path,node in flat.items() if 'phandle' in node};out=copy.deepcopy(flat)
 for path,node in out.items():
  node.pop('phandle',None)
  for prop,value in node.items():
   if v.property_get_type(prop) in [{'phandle'},{'phandle-array'}]:
    for row in value:
     if row[0]:assert row[0] in refs,(path,prop,row);row[0]=refs[row[0]]
 return out
bam='/soc/dma-controller@fe104000';slim='/soc/slimbus@fe12f000';apr='/soc/remoteproc@fe200000/smd-edge/apr'
expected={bam:{'compatible':['qcom,bam-v1.4.0'],'reg':[[0xfe104000,0x20000]],'interrupts':[[0,164,4]],'#dma-cells':1,'qcom,ee':1,'qcom,controlled-remotely':True,'num-channels':31,'qcom,num-ees':2,'status':['disabled']},slim:{'compatible':['qcom,slim-ngd-v1.5.0'],'reg':[[0xfe12f000,0x35000]],'interrupts':[[0,163,4]],'dmas':[[bam,3],[bam,4]],'dma-names':['rx','tx'],'#address-cells':1,'#size-cells':0,'status':['disabled']},slim+'/slim@1':{'reg':[[1]],'#address-cells':2,'#size-cells':0},apr:{'compatible':['qcom,apr-v2'],'qcom,smd-channels':['apr_audio_svc'],'qcom,domain':4,'#address-cells':1,'#size-cells':0,'status':['disabled']}}
for service,compatible in [(3,'qcom,q6core'),(4,'qcom,q6afe'),(7,'qcom,q6asm'),(8,'qcom,q6adm')]:expected[apr+f'/service@{service:x}']={'compatible':[compatible],'reg':[[service]]}
for service,compatible in [(4,'qcom,q6afe-dais'),(7,'qcom,q6asm-dais')]:expected[apr+f'/service@{service}/dais']={'compatible':[compatible],'#address-cells':1,'#size-cells':0,'#sound-dai-cells':1}
for index in range(3):expected[apr+f'/service@7/dais/dai@{index}']={'reg':[[index]]}
expected[apr+'/service@8/routing']={'compatible':['qcom,q6adm-routing'],'#sound-dai-cells':0};assert len(expected)==14
matrix=json.loads((a.build.parent/'DTB-build-controller.json').read_text())['inherited_board_targets'];assert len(matrix)==18
comparisons=[];paths=[]
for target in matrix:
 rel=Path('arch/arm/boot/dts')/target;old=normalize((a.baseline/rel).read_bytes());new=normalize((a.build/rel).read_bytes());added=set(new)-set(old)
 assert not set(old)-set(new) and added==set(expected),(target,added)
 for path,node in old.items():assert new[path]==node,(target,path)
 for path,node in expected.items():assert new[path]==node,(target,path,new[path],node)
 comparisons.append({'board':target,'all_existing_nodes_properties_and_reserved_ranges_preserved':True,'existing_nodes':len(old),'exact_new_nodes':len(added),'DTB_SHA256':hashlib.sha256((a.build/rel).read_bytes()).hexdigest()});paths.append(a.build/rel)
filters='soc/qcom/qcom,apr.yaml:soc/qcom/qcom,apr-services.yaml:sound/qcom,q6:slimbus/:dma/qcom,bam-dma.yaml:remoteproc/qcom,wcnss-pil.yaml:leds/qcom,pm8941-flash-led.yaml:power/reset/qcom,pon.yaml:mfd/qcom,spmi-pmic.yaml:soc/qcom/qcom,wcnss.yaml:soc/qcom/qcom,smp2p.yaml:remoteproc/qcom,smd-edge.yaml:reserved-memory/:media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml:display/msm/gpu.yaml'
new_filters='soc/qcom/qcom,apr.yaml:soc/qcom/qcom,apr-services.yaml:sound/qcom,q6:slimbus/:dma/qcom,bam-dma.yaml'
def validate(name,files,selected=filters):
 r=subprocess.run([str(validator),'-s',str(schema),'-l',selected,*map(str,files)],capture_output=True,timeout=120)
 (a.output/(name+'.stdout')).write_bytes(r.stdout);(a.output/(name+'.stderr')).write_bytes(r.stderr);assert r.returncode==0
 return r
r=validate('all18-inherited',paths);assert not r.stdout and not r.stderr
# Enabled fixture comes from a real inherited board, not a replacement for the full Fx0.
enabled=a.output/'enabled-common-positive.dtb';enabled.write_bytes(paths[0].read_bytes())
for node in [bam,slim,apr]:subprocess.run(['fdtput','-t','s',str(enabled),node,'status','okay'],check=True)
r=validate('enabled-common-positive',[enabled]);assert not r.stdout and not r.stderr
fx0=a.build/'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb';assert fx0.is_file()
r=validate('complete-Fx0-new-prerequisites',[fx0],new_filters);assert not r.stdout and not r.stderr
full=normalize(fx0.read_bytes())
for path,node in expected.items():
 candidate=copy.deepcopy(full[path]);candidate.pop('phandle',None)
 if path in [bam,slim,apr]:assert candidate.pop('status')==['okay'];node={k:value for k,value in node.items() if k!='status'}
 assert candidate==node,(path,candidate,node)
controls=[]
def mutated(name,args):
 path=a.output/(name+'.dtb');path.write_bytes(enabled.read_bytes());subprocess.run(['fdtput',*args[:2],str(path),*args[2:]],check=True);return path
for name,args,diagnostic in [
 ('APR-invalid-domain',['-t','i',apr,'qcom,domain','0'],'qcom,domain'),
 ('APR-wrong-channel',['-t','s',apr,'qcom,smd-channels','wrong-channel'],'qcom,smd-channels'),
 ('APR-two-transports',['-t','s',apr,'qcom,glink-channels','apr_audio_svc'],'False schema does not allow'),
 ('APR-service-ID-out-of-range',['-t','i',apr+'/service@3','reg','14'],'reg'),
 ('ASM-missing-DAI-reg',['-d','--',apr+'/service@7/dais/dai@1','reg'],'reg'),
 ('ASM-invalid-direction',['-t','i',apr+'/service@7/dais/dai@0','direction','3'],'direction'),
 ('SLIM-reversed-DMA-names',['-t','s',slim,'dma-names','tx','rx'],'dma-names'),
 ('SLIM-missing-DMAs',['-d','--',slim,'dmas'],'dmas'),
 ('BAM-invalid-EE',['-t','i',bam,'qcom,ee','8'],'qcom,ee'),
 ('BAM-missing-remote-channel-count',['-d','--',bam,'num-channels'],'num-channels')]:
 path=mutated(name,args);r=validate(name,[path]);assert not r.stdout and diagnostic.encode() in r.stderr and b'from schema $id:' in r.stderr,name;controls.append(name)
 if name=='APR-two-transports':assert b'/soc/qcom/qcom,apr.yaml' in r.stderr
platform=[]
for name,args,node,prop in [
 ('platform-wrong-BAM-window',['-t','x',bam,'reg','fe104000','10000'],bam,'reg'),
 ('platform-wrong-SLIM-IRQ-type',['-t','i',slim,'interrupts','0','163','1'],slim,'interrupts'),
 ('platform-wrong-core-service-ID',['-t','i',apr+'/service@3','reg','4'],apr+'/service@3','reg')]:
 path=mutated(name,args);new=normalize(path.read_bytes());assert new[node][prop]!=expected[node][prop],name
 # Record generic schema coverage accurately rather than claiming it enforces platform wiring.
 r=validate(name,[path]);platform.append({'name':name,'independent_exact_platform_contract_rejects':True,'generic_schema_rejected':bool(r.stderr)})
# Compare warning multisets after removing only the two additional full-Fx0 warnings.
def warnings(path):return Counter(re.sub(r'^.*?:\d+\.\d+(?:-\d+\.\d+)?: ','',line) for line in path.read_text().splitlines() if 'Warning (' in line)
oldw=warnings(a.baseline_log);neww=warnings(a.candidate_log)
for message in [x for x in neww if '/soc/efuse@fc4bc000/s1-p1@1c4:' in x or '/soc/efuse@fc4bc000/s0-p2@1cd:' in x]:neww[message]-=1
neww+=Counter();assert neww==oldw,(neww-oldw,oldw-neww)
record={'passed':True,'source_head':head,'common_source_file_SHA256_verified':True,'Git_metadata_verified':git_metadata_available,'checker_SHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'all18_inherited_boards_compiled_and_compared':True,'all_existing_nodes_properties_and_reserved_ranges_preserved':True,'exact_new_disabled_nodes_per_board':14,'comparisons':comparisons,'direct_18_board_schemas_empty':True,'enabled_real_board_positive_passed':True,'complete_unchanged_Fx0_compiles':True,'complete_Fx0_new_APR_SLIM_prerequisites_schema_clean':True,'schema_rejection_controls':controls,'platform_contract_controls':platform,'existing_inherited_DTC_warnings':sum(oldw.values()),'new_inherited_DTC_warnings':0,'complete_Fx0_existing_efuse_warnings':2,'complete_Fx0_unfiltered_schema_and_hardware_qualified':False,'phone_access':False}
(a.output/'qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps({k:record[k] for k in ['passed','exact_new_disabled_nodes_per_board','existing_inherited_DTC_warnings','new_inherited_DTC_warnings','complete_unchanged_Fx0_compiles','complete_Fx0_unfiltered_schema_and_hardware_qualified']}))
