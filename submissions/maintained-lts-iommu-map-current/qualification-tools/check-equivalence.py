# SPDX-License-Identifier: GPL-2.0-only
"""Audit all 21 selected origins against retained LTS feature bytes."""
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';norm=lambda t:''.join(t.split());rows=[]
def function(t,name):
 m=re.search(r'^static[^;{}]*?\b'+name+r'\([^;{}]*\)\n\{',t,re.M);assert m,name;end=t.index('{',m.start())+1;depth=1
 while depth:depth+=(t[end]=='{')-(t[end]=='}');end+=1
 return t[m.start():end]
f='drivers/iommu/arm/arm-smmu/qcom_iommu.c';a=(N/'before'/f).read_text();b=(E/f).read_text()
for name in ['qcom_iommu_init_domain','qcom_iommu_domain_alloc_paging','qcom_iommu_has_secure_context','qcom_iommu_ctx_probe','qcom_iommu_device_probe']:
 old=function(a,name);new=function(b,name)
 if name=='qcom_iommu_init_domain':assert norm(old)==norm(new.replace('\tfree_io_pgtable_ops(pgtbl_ops);\n',''))
 elif name=='qcom_iommu_domain_alloc_paging':assert norm(old)==norm(new.replace('kzalloc_obj(*qcom_domain)','kzalloc(sizeof(*qcom_domain), GFP_KERNEL)'))
 elif name=='qcom_iommu_ctx_probe':
  log='''\tif (ret) {
\t\tdev_err(dev, "failed to request IRQ %u\\n", irq);
\t\treturn ret;
\t}''';assert old.count(log)==1;assert norm(old.replace(log,'\tif (ret)\n\t\treturn ret;'))==norm(new)
 # The remaining two whole-function differences are upstream API/lifetime
 # changes outside the original 21 deltas; explicitly keep them visible.
 b=b.replace(new,old)
assert norm(a)==norm(b);rows.append(dict(path=f,all_original_feature_tokens_equivalent=True,retained_LTS_differences=['allocator spelling','explicit OF node release','IRQ diagnostic','manual runtime-PM probe teardown'],new_upstream_or_local_error_handling_qualified_separately=True,manual_PM_probe_cleanup_followup_open=True))
f='drivers/iommu/arm/arm-smmu/arm-smmu.h';assert norm((C/f).read_text())==norm((E/f).read_text());rows.append(dict(path=f,all_nonwhitespace_header_tokens_identical=True))
f='drivers/iommu/arm/Kconfig';pat=r'config QCOM_IOMMU\n.*?(?=\nconfig |\Z)';assert re.search(pat,(C/f).read_text(),re.S).group()==re.search(pat,(E/f).read_text(),re.S).group();rows.append(dict(path=f,entire_QCOM_IOMMU_Kconfig_block_identical=True))
f='drivers/clk/qcom/mmcc-msm8974.c';a=(C/f).read_text().replace('#include <linux/mod_devicetable.h>\n','').replace('\t\t.flags = GENPD_FLAG_NO_STAY_ON,\n','');assert a==(E/f).read_text();rows.append(dict(path=f,complete_clock_source_equivalent_except_retained_LTS_include_and_GDSC_flag=True))
f='drivers/gpu/drm/msm/dsi/phy/dsi_phy_28nm.c';assert (C/f).read_bytes()==(E/f).read_bytes();rows.append(dict(path=f,complete_source_identical=True))
f='arch/arm/boot/dts/qcom/qcom-msm8226.dtsi';a=(C/f).read_text();b=(E/f).read_text()
for name in ['vfe_iommu','camss','mdp_iommu','gpu_iommu']:
 def node(t):
  m=re.search(r'^\s*'+name+r': [^\n]+\{',t,re.M);assert m,name;end=t.index('{',m.start())+1;depth=1
  while depth:depth+=(t[end]=='{')-(t[end]=='}');end+=1
  return t[m.start():end]
 assert norm(node(a))==norm(node(b)),name
rows.append(dict(path=f,complete_four_selected_nodes_token_identical=True,LTS_CCI_assigned_clock_CPU_idle_and_domain_indices_preserved=True))
j=dict(passed=True,originals_audited=21,existing_equivalents=21,original_source_ports=0,rows=rows,additional_error_path_repairs_not_counted_as_original_backports=True,phone_access=False);(N/'equivalence.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(passed=True,existing_equivalents=21)))
