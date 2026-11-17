# SPDX-License-Identifier: GPL-2.0-only
"""Check synthetic compiled DT topology and reject malformed binding controls."""
from pathlib import Path
from collections import Counter
import hashlib,json,libfdt,re,struct,subprocess,sys
B=Path(__file__).resolve().parent;R=B.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=B/(sys.argv[1] if len(sys.argv)>1 else 'DT-wiring-01');O.mkdir(exist_ok=False)
controller=json.loads((B/'DTBs-01/controller.json').read_text());schema=B/'bindings-01-out/Documentation/devicetree/bindings/processed-schema.json';dtb=B/'DTBs-01/candidate-out/arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai-suspend.dtb';blob=dtb.read_bytes();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert controller['passed'] and sha(dtb)==controller['DTBs']['qcom-msm8926-lg-madai-suspend.dtb'];assert sha(schema)==controller['processed_schema_SHA256']
f=libfdt.Fdt(blob);nodes={}
def walk(off,path):
 nodes[path]=off
 try:child=f.first_subnode(off)
 except libfdt.FdtException as e:assert e.err==-libfdt.NOTFOUND;return
 while child>=0:
  walk(child,path.rstrip('/')+'/'+f.get_name(child))
  try:child=f.next_subnode(child)
  except libfdt.FdtException as e:assert e.err==-libfdt.NOTFOUND;break
walk(0,'/')
def prop(path,name):return f.getprop(nodes[path],name)
def words(path,name):return prop(path,name).as_uint32_list()
def compat(path,value):
 try:return value in prop(path,'compatible').as_stringlist()
 except libfdt.FdtException as e:assert e.err==-libfdt.NOTFOUND;return False
def find(value):
 found=[path for path in nodes if compat(path,value)];assert len(found)==1,(value,found);return found[0]
def phandle(path):return words(path,'phandle')[0]
def reference(path,name):return f.get_path(f.node_offset_by_phandle(words(path,name)[0]))
sleep=find('qcom,msm8226-system-pm');mpm=find('qcom,mpm');cpr=find('qcom,msm8926-cpr');l2=find('qcom,msm8226-saw2-v2.1-l2');rpm=find('qcom,rpm-msm8226');rpmproc=find('qcom,msm8226-rpm-proc');tlmm=find('qcom,msm8226-pinctrl');spmi=find('qcom,spmi-pmic-arb');mdss=find('qcom,mdss');tsens=find('qcom,msm8226-tsens')
assert sleep==rpm+'/system-sleep' and mpm==rpmproc+'/interrupt-controller'
for name,target in [('qcom,cpr',cpr),('qcom,mpm',mpm),('qcom,l2-spm',l2)]:assert reference(sleep,name)==target
assert words(mpm,'qcom,mpm-pin-count')==[64];assert words(mpm,'#interrupt-cells')==[2] and words(mpm,'#address-cells')==[0];assert words(mpm,'interrupts')==[0,171,1]
assert words(mpm,'qcom,mpm-pin-map')==[2,184,47,140,53,72,62,190];assert words(mpm,'mboxes')[1:]==[1]
sram=reference(mpm,'qcom,rpm-msg-ram');assert words(sram,'reg')==[0x1d0,0x30];assert reference(tlmm,'wakeup-parent')==mpm
for path,pin in [(spmi,62),(mdss,53),(tsens,2)]:assert words(path,'interrupts-extended')==[phandle(mpm),pin,4]
cpus=[]
for cpu in range(4):
 path='/cpus/cpu@'+str(cpu);assert words(path,'reg')==[cpu] and prop(path,'enable-method').as_str()=='qcom,msm8226-smp';saw=reference(path,'qcom,saw');acc=reference(path,'qcom,acc');assert compat(saw,'qcom,msm8226-saw2-v2.1-cpu');assert words(acc,'reg')[0]==0xf9088000+cpu*0x10000;cpus.append(dict(cpu=cpu,SAW=saw,ACC=acc))
# Check exact raw warning occurrence inheritance, without dropping categories.
normalize=lambda line:re.sub(r'^.*?/arch/arm/boot/dts/','arch/arm/boot/dts/',line)
prior=json.loads((B.parent/'sleep-prerequisites-01/DTBs-current.json').read_text())
old=Counter(prior['warnings']['candidate']);extra=Counter(controller['extra_warning_lines']);missing=Counter(controller['missing_warning_lines'])
assert controller['baseline_warning_lines']==68 and controller['candidate_warning_lines']==71 and not missing
assert sum(extra.values())==3 and all(k in old for k in extra)
# Vendor tuples are full GIC hwirqs; current MPM binding uses SPI numbers.
vendor=R/'src/vendor-linux/arch/arm/boot/dts/msm8226-v2-pm.dtsi';vendor_c=R/'src/vendor-linux/arch/arm/mach-msm/mpm-of.c';vtext=vendor.read_text();vc=vendor_c.read_text();source=(C/'drivers/irqchip/irq-qcom-mpm.c').read_text()
for pin,hw in [(2,216),(47,172),(53,104),(62,222)]:assert re.search(r'<'+str(pin)+r'\s+'+str(hw)+'>',vtext)
assert 'mpm_node->hwirq = hwirq;' in vc and 'node->hwirq == d->hwirq' in vc
assert 'parent_fwspec.param[0] = 0;' in source and 'parent_fwspec.param[1] = map->hwirq;' in source
validator=R/'local/power-managed-port-01/schema-venv/bin/dt-validate'
r=subprocess.run([str(validator),'-s',str(schema),'-l','power/qcom,msm8226-system-pm.yaml:interrupt-controller/qcom,mpm.yaml:soc/qcom/qcom,smd-rpm.yaml',str(dtb)],capture_output=True,text=True,timeout=30);assert r.returncode==0 and not r.stdout and not r.stderr
records=[]
def control(name,edit,needle):
 target=libfdt.Fdt(blob);target.resize(len(blob)+4096);edit(target);target.pack();out=O/(name+'.dtb');out.write_bytes(target.as_bytearray())
 r=subprocess.run([str(validator),'-s',str(schema),'-l','power/qcom,msm8226-system-pm.yaml:interrupt-controller/qcom,mpm.yaml:soc/qcom/qcom,smd-rpm.yaml',str(out)],capture_output=True,text=True,timeout=30);(O/(name+'.stderr')).write_text(r.stderr);(O/(name+'.stdout')).write_text(r.stdout)
 assert r.returncode==0 and needle in r.stderr and not r.stdout and not any(s in r.stderr for s in ['Traceback','FDT_ERR','RecursionError']), (name,r.stderr)
 records.append(dict(name=name,rejected_by_schema=True,expected_diagnostic=needle,stderr_SHA256=sha(O/(name+'.stderr'))))
for name in ['qcom,cpr','qcom,mpm','qcom,l2-spm']:
 control('missing-'+name.replace(',','-'),lambda t,n=name:t.delprop(t.path_offset(sleep),n),name)
 control('multiple-'+name.replace(',','-'),lambda t,n=name:t.setprop(t.path_offset(sleep),n,struct.pack('>II',words(sleep,n)[0],words(sleep,n)[0])),name)
control('unknown-coordinator-property',lambda t:t.setprop(t.path_offset(sleep),'qcom,unsafe-entry',b''),'qcom,unsafe-entry')
control('wrong-coordinator-name',lambda t:t.set_name(t.path_offset(sleep),'wrong-name'),'system-sleep')
control('other-rpm-soc',lambda t:t.setprop(t.path_offset(rpm),'compatible',b'qcom,rpm-msm8916\0qcom,smd-rpm\0'),'qcom,msm8226-system-pm')
control('mpm-address-cells-one',lambda t:t.setprop(t.path_offset(mpm),'#address-cells',struct.pack('>I',1)),'#address-cells')
control('mpm-missing-mailbox',lambda t:t.delprop(t.path_offset(mpm),'mboxes'),'mboxes')
control('mpm-missing-msg-ram',lambda t:t.delprop(t.path_offset(mpm),'qcom,rpm-msg-ram'),'qcom,rpm-msg-ram')
record=dict(passed=True,DTBs=18,seventeen_prior_DTBs_byte_identical=controller['seventeen_prior_DTBS_byte_identical'],selected_three_schemas_silent=True,full_global_schema_gate=False,DTB_SHA256=sha(dtb),processed_schema_SHA256=sha(schema),coordinator=sleep,suppliers=dict(CPR=cpr,MPM=mpm,L2=l2,RPM=rpm),CPUs=cpus,raw_DTC_occurrences=controller['candidate_warning_lines'],prior_raw_DTC_occurrences=controller['baseline_warning_lines'],extra_target_occurrences_of_existing_diagnostics=controller['extra_warning_lines'],new_unique_DTC_diagnostics=[],negative_binding_controls=records,vendor_GIC_hwirq_to_current_SPI_offset=32,vendor_source_SHA256=sha(vendor),vendor_mapping_implementation_SHA256=sha(vendor_c),physical_wake_routing_qualified=False,wrong_phandle_target_semantics_require_runtime_probe_checks=True,private_DTB_controls_not_for_publication=True,phone_access=False)
(O/'qualification.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(passed=True,DTBs=18,prior_unchanged=17,negative_binding_controls=len(records),new_unique_DTC_diagnostics=0)))
