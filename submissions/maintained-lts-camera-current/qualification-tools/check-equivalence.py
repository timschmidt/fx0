# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';sha=lambda b:hashlib.sha256(b).hexdigest();rows=[];prefix='drivers/media/platform/qcom/camss/'
def declaration(t,name):
 m=re.search(r'^static const [^\n]*\b'+name+r'(?:\[\])? = \{',t,re.M);assert m,name;return t[m.start():t.index('\n};',m.start())+3]
def function(t,name):
 m=re.search(r'^static[^\n]*\b'+name+r'\(',t,re.M);assert m,name;return t[m.start():t.index('\n}',m.start())+2]
def norm(t):return re.sub(r'\s+','',t).replace('{.supply="vdda"}', '"vdda"')
p=prefix+'Kconfig';needle='depends on (ARCH_QCOM && (IOMMU_DMA || ARM_DMA_USE_IOMMU)) || COMPILE_TEST';assert needle in (C/p).read_text() and needle in (E/p).read_text();rows.append(dict(origin='aa5fe30a0176c9c2004a501326c8fbd21a0c8a10',already_present=True,scope='Exact ARM/backend dependency; actual full-Kconfig ARM and ARM64 built-in/module profiles all usable without COMPILE_TEST',evidence='Kconfig-01/qualification.json'))
p=prefix+'camss.c';c=(C/p).read_text();e=(E/p).read_text();resource_rows=[]
for name in ['csiphy_res_8x26','csid_res_8x26','ispif_res_8x26','vfe_res_8x26','msm8226_resources']:
 a=declaration(c,name);b=declaration(e,name);assert norm(a)==norm(b),name;resource_rows.append(dict(name=name,current_SHA256=sha(a.encode()),experimental_SHA256=sha(b.encode()),normalized_regulator_supply_representation_only=True))
assert '{ .compatible = "qcom,msm8226-camss", .data = &msm8226_resources }' in c
p=prefix+'camss-vfe.c';a=function((C/p).read_text(),'vfe_match_clock_names');b=function((E/p).read_text(),'vfe_match_clock_names');assert '!strcmp(clock->name, \"vfe_axi\")' in a; b=b.replace('!strcmp(clock->name, \"camnoc_axi\") ||\n\t\t!strcmp(clock->name, \"camnoc_rt_axi\")', '!strcmp(clock->name, \"camnoc_axi\")'); assert a==b
rows.append(dict(origin='d549a473d9820b90888fecd267841783bc7dafec',already_present=True,resources=resource_rows,clock_match_function_identical_except_unrelated_newer_cam_noc_RT_clock=True,compatible_and_resource_counts_present=True,regulator_bulk_data_newer_API_not_imported=True))
d=json.loads((N/'completion-03/qualification.json').read_text());assert d['passed'] and d['positive_cases']==84;rows.append(dict(origin='6e956fdc8c01cbda803f48f35988567eeb44038a',already_present=True,scope='Actual completion core/gen1/17x and all three dispatch functions byte-identical to reviewed original assembly; types and IRQ macros bound to LTS source',positive_cases=84,negative_variants=9,evidence='completion-03/qualification.json'))
# The sensor schema, register tables, controls, power and probe bytes remain intact.
for sensor in ['imx132','imx179']:
 p='drivers/media/i2c/'+sensor+'.c';before=(N/'before'/p).read_text();current=(C/p).read_text()
 stripped=current.replace('\tif (fmt->which == V4L2_SUBDEV_FORMAT_ACTIVE &&\n\t    v4l2_subdev_is_streaming(sd))\n\t\treturn -EBUSY;\n\n','').replace('\tif (ret)\n\t\treturn ret;\n\n\tpm_runtime_put('+sensor+'->dev);','\tpm_runtime_put('+sensor+'->dev);');assert stripped==before
 p='Documentation/devicetree/bindings/media/i2c/sony,'+sensor+'.yaml';assert (C/p).read_bytes()==(E/p).read_bytes()==(N/'before'/p).read_bytes()
for p in ['drivers/media/i2c/Kconfig','drivers/media/i2c/Makefile',prefix+'camss.c',prefix+'camss-vfe-4-7.c',prefix+'camss-vfe-4-8.c',prefix+'camss-vfe-17x.c',prefix+'camss-vfe.h']:
 assert (C/p).read_bytes()==(N/'before'/p).read_bytes(),p
# No DT/schema/header outside the exact selected files changed.
paths=subprocess.check_output(['git','diff','--name-only',json.loads((N/'prepared.json').read_text())['base']],cwd=C,text=True).splitlines();assert len(paths)==9
assert set(paths)==set().union(*(set(x['files']) for x in json.loads((N/'port-deltas.json').read_text())))
report=dict(passed=True,already_present=rows,equivalent_origins=3,source_files={p:sha((C/p).read_bytes()) for p in json.loads((N/'prepared.json').read_text())['source_files']},changed_paths=paths,sensor_register_power_probe_and_other_function_bytes_preserved=True,sensor_schema_and_DTS_bytes_preserved=True,previous_19_board_schema_evidence_reusable_not_new_DT_build=True,nonselected_CAMSS_sources_preserved=True,phone_access=False)
(N/'source-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print('Three existing camera origins qualified; exact change footprint and sensor preservation verified')
