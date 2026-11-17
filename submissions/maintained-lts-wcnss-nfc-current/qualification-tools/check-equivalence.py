# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[]
def function(t,n):m=re.search(r'^static int '+n+r'\(',t,re.M);assert m,n;return t[m.start():t.index('\n}',m.start())+2]
def block(t,marker):
 start=t.index(marker);i=t.index('{',start)+1;depth=1
 while depth:depth+=(t[i]=='{')-(t[i]=='}');i+=1
 return t[start:i+1]
p='arch/arm/boot/dts/qcom/qcom-msm8226.dtsi';dts=[]
for marker in ['wcnss_region:','smp2p-wcnss {','pronto:']:
 a=block((C/p).read_text(),marker);b=block((E/p).read_text(),marker);assert a.replace('MSM8226_VDDCX','RPMPD_VDDCX')==b,marker;dts.append(dict(node=marker,source_SHA256=hashlib.sha256(a.encode()).hexdigest()))
header=(C/'include/dt-bindings/power/qcom-rpmpd.h').read_text();assert re.search(r'#define MSM8226_VDDCX\s+RPMPD_VDDCX',header) and re.search(r'#define RPMPD_VDDCX\s+0',header)
for board in ['qcom-apq8026-samsung-milletwifi.dts','qcom-msm8926-htc-memul.dts']:
 p='arch/arm/boot/dts/qcom/'+board;assert '/delete-node/ &wcnss_region;' in (C/p).read_text();assert block((C/p).read_text(),'wcnss_region:')==block((E/p).read_text(),'wcnss_region:')
rows.append(dict(origin='c3bd956de3414d28aa8273e2a4c746134a4811d3',already_present=True,scope='WCNSS memory/signaling/remoteproc/BT/Wi-Fi node blocks and board delete/recreation overrides',DTS_nodes=dts,LTS_power_domain_alias_value_identical=True))
p='drivers/remoteproc/qcom_wcnss_iris.c';a=(C/p).read_text();b=(E/p).read_text()
for marker in ['static const struct of_device_id iris_of_match[]','static const struct iris_data wcn3680_data']:
 assert block(a,marker)==block(b,marker),marker
assert '{ .compatible = "qcom,wcn3660a", .data = &wcn3680_data }' in a;rows.append(dict(origin='77a38560ae9e8b820e742df2a7fc56e30c402bba',already_present=True,scope='Exact WCN3660A match and referenced regulator/XO data; newer allocation API retained out of LTS'))
p='drivers/remoteproc/qcom_wcnss.c';a=(C/p).read_text();b=(E/p).read_text();assert function(a,'wcnss_init_regulators')==function(b,'wcnss_init_regulators')
for variant in ['riva','pronto_v1','pronto_v2','pronto_v3']:assert block(a,'static const struct wcnss_data '+variant+'_data')==block(b,'static const struct wcnss_data '+variant+'_data')
assert json.loads((N/'regulators-existing-01/controller.json').read_text())['result']==dict(cases=8,correct=8,wrong=0,error_controls=16);assert json.loads((N/'regulators-regression-01/controller.json').read_text())['result']['wrong']==6;rows.append(dict(origin='e6ac7649341759bde8fd028e7db6d1f6c3316ae0',already_present=True,scope='Exact selector and platform tables; eight healthy and sixteen allocation/regulator fault cases; prior helper rejected in six cases'))
rf=json.loads((N/'RF-01/qualification.json').read_text());assert rf['passed'] and rf['rows'][0]['failures']==0 and rf['rows'][1]['failures']==1;rows.append(dict(origin='07eb1b7cff154595c7762fa563b0323754910a44',already_present=True,scope='Exact WCN3660A RF classification block; seven synthetic OF cases, wrong WCN3680 classification rejected'))
assert not any(re.search(r'^\s*#\s*define\s+devm_kzalloc_obj\b',p.read_text(errors='replace'),re.M) for p in (C/'include').rglob('*.h'))
inapplicable=dict(origin='20ad39f09cddd4283f25cf4e49dafc0bda1548b4',classification='newer typed-allocation API-only conversion inapplicable to LTS',LTS_macro_absent=True,current_typed_size_allocation_preserved=True)
for p,old,new in [('drivers/nfc/nxp-nci/core.c','devm_kzalloc(pdev, sizeof(struct nxp_nci_info), GFP_KERNEL)','devm_kzalloc_obj(pdev, struct nxp_nci_info)'),('drivers/nfc/nxp-nci/i2c.c','devm_kzalloc(&client->dev, sizeof(struct nxp_nci_i2c_phy),\n\t\t\t   GFP_KERNEL)','devm_kzalloc_obj(&client->dev, struct nxp_nci_i2c_phy)')]:
 a=(C/p).read_text();b=(E/p).read_text();assert a.replace(old,new)==b,p
# The binding adds clock properties only; the newer PN557 compatible is excluded.
p='Documentation/devicetree/bindings/net/nfc/nxp,nci.yaml';assert 'nxp,pn557' not in (C/p).read_text();assert (C/'drivers/nfc/nxp-nci/nxp-nci.h').read_bytes()==(E/'drivers/nfc/nxp-nci/nxp-nci.h').read_bytes()
for p in ['drivers/remoteproc/qcom_wcnss.c','drivers/remoteproc/qcom_wcnss.h','drivers/remoteproc/qcom_wcnss_iris.c','drivers/net/wireless/ath/wcn36xx/main.c','arch/arm/boot/dts/qcom/qcom-msm8226.dtsi','arch/arm/boot/dts/qcom/qcom-apq8026-samsung-milletwifi.dts','arch/arm/boot/dts/qcom/qcom-msm8926-htc-memul.dts','net/nfc/nci/core.c','net/nfc/nci/rsp.c']:assert (C/p).read_bytes()==(N/'before'/p).read_bytes(),p
prepared=json.loads((N/'prepared.json').read_text());changed=subprocess.check_output(['git','diff','--name-only',prepared['base']],cwd=C,text=True).splitlines();assert len(changed)==5
j=dict(passed=True,existing_equivalents=rows,inapplicable=inapplicable,changed_paths=changed,source_files={p:sha(C/p) for p in prepared['source_files']},all_unselected_driver_protocol_and_DTS_bytes_preserved=True,raw_clock_port_reconciled_to_absent_newer_base_cleanup=True,phone_access=False,radio_NFC_execution=False);(N/'source-equivalence.json').write_text(json.dumps(j,indent=2)+'\n');print('Four WCNSS origins equivalent; typed-allocation conversion inapplicable; NFC delta footprint verified')
