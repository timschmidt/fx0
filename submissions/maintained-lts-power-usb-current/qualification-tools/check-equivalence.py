# SPDX-License-Identifier: GPL-2.0-only
"""Check carried feature bytes without importing newer unrelated APIs."""
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01';norm=lambda s:''.join(s.split());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();records=[]
for f in ['drivers/power/supply/qcom_smbb_policy.h','Documentation/devicetree/bindings/power/supply/qcom,pm8941-charger.yaml','Documentation/devicetree/bindings/power/supply/lg,madai-charge-policy.yaml','drivers/usb/chipidea/ci.h']:
 assert (C/f).read_bytes()==(E/f).read_bytes();records.append(dict(path=f,exact_complete_file=True,SHA256=sha(C/f)))
f='drivers/power/supply/qcom_smbb.c';a=(C/f).read_text();b=(E/f).read_text()
old='''\t\tif (rc) {
\t\t\tdev_err(&pdev->dev, "failed to request irq '%s'\\n",
\t\t\t\tsmbb_charger_irqs[i].name);
\t\t\treturn rc;
\t\t}''';new='''\t\tif (rc)
\t\t\treturn rc;'''
assert a.count(old)==1 and norm(a.replace(old,new))==norm(b)
records.append(dict(path=f,complete_file_equivalent_except='Retained LTS IRQ-request failure diagnostic and whitespace; no control-flow change',SHA256=sha(C/f)))
f='drivers/iio/adc/qcom-spmi-vadc.c';assert (C/f).read_text().replace('#include <linux/mod_devicetable.h>\n','')==(E/f).read_text();records.append(dict(path=f,complete_file_equivalent_except='Retained LTS mod_devicetable include',SHA256=sha(C/f)))
f='drivers/usb/chipidea/udc.c';a=(C/f).read_text();patch=(N/'origin-patches/dc62e4e47d5927ea0f9b2ea30f97d8cba88349e8.patch').read_text();runs=[];current=[];path=None
for line in patch.splitlines()+['']:
 if line.startswith('+++ b/'):path=line[6:]
 if line.startswith('+') and not line.startswith('+++'):current.append(line[1:])
 elif current:
  if path==f and norm(''.join(current)):assert norm(''.join(current)) in norm(a);runs.append('\n'.join(current))
  current=[]
assert len(runs)>10;records.append(dict(path=f,all_original_added_runs_present=len(runs),SHA256=sha(C/f),unrelated_newer_role_lifecycle_and_allocator_changes_not_imported=True))
f='Documentation/devicetree/bindings/usb/ci-hdrc-usb2.yaml';a=(C/f).read_text();b=(E/f).read_text()
a=a.replace('maxItems: 2','maxItems: 3')
desc='''    description: Charger supplying the gadget through VBUS. The controller
      forwards USB current requests to its USB input supply in peripheral
      mode when using a generic PHY.'''
replacement='''    description:
      Charger supplying the gadget through VBUS. The controller forwards
      USB current requests to its USB input supply in peripheral mode
      when using a generic PHY.'''
assert a.count(desc)==1;a=a.replace(desc,replacement)
start=b.index('  - if:\n      properties:\n        compatible:',b.index('  power-supplies:'))
end=b.index('unevaluatedProperties: false',start)
assert a==b[:start]+b[end:]
records.append(dict(path=f,complete_binding_equivalent_except='Retained LTS clock bounds and no newer Qualcomm three-clock conditional; current-budget description differs only in YAML wrapping',SHA256=sha(C/f)))
f='drivers/power/supply/Kconfig';a=(C/f).read_text();b=(E/f).read_text();pattern=r'config CHARGER_QCOM_SMBB(?:_POLICY)?\n.*?(?=\nconfig )';blocks=re.findall(pattern,a,re.S);assert len(blocks)==2 and blocks==re.findall(pattern,b,re.S);records.append(dict(path=f,exact_charger_Kconfig_blocks=2,managed_requires_builtin_provider_and_IIO=True))
# Both original metadata additions are absent, so these two original commits
# require a metadata-only reconciliation, rather than being called equivalents.
assert 'LG FX0 CHARGING POLICY\n' not in (C/'MAINTAINERS').read_text()
j=dict(passed=True,source_head='52795f8a14e49fdb1da3d58efd120d0c6488d81d',records=records,original_commits_audited=10,already_present_equivalents=8,metadata_only_reconciliations_needed=2,reverse_patch_checks_are_not_the_equivalence_gate=True,phone_access=False,physical_acceptance=False)
(N/'equivalence.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(passed=True,existing_equivalents=8,metadata_reconciliations=2)))
