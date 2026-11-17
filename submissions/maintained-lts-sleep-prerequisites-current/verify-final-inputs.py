# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
s=read(N/'source-current.json');native=read(N/'native-current.json');assert native['passed']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==s['head']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
objects=0
for p in native['profiles']:
 out=N/'native-02'/(p['profile']+'-out');assert sha(out/'.config')==p['config_SHA256']
 for f,digest in p['source_files'].items():assert sha(C/f)==digest,f
 for f,digest in p['objects'].items():assert sha(out/f)==digest,f;objects+=1
assert objects==122
for f,digest in native['source_files'].items():assert sha(C/f)==digest,f
files=read(N/'combined-source-current.json')['source_files']|read(N/'retained-CPU/source-current.json')['source_files']|native['source_files']
extra=['drivers/regulator/core.c','kernel/power/suspend.c','include/linux/cpuidle.h','include/linux/firmware/qcom/qcom_scm.h']
files|={p:sha(C/p) for p in extra}
for f,digest in files.items():assert sha(C/f)==digest,f
DT=read(N/'DTBs-current.json');assert DT['passed'] and len(DT['schema_checks'])==119
for name,digest in DT['DTBs']['candidate'].items():assert sha(N/'DTBs-01/candidate-out/arch/arm/boot/dts/qcom'/name)==digest
style=read(N/'checkpatch-02.json');assert style['errors']==2 and style['warnings']==5
# Checkpatch's trailer recognizer misparses unchanged YAML context ending in -by.
context=[]
for short in ['6c9b8b686ea5','d2d0763fd351']:
 patch=N/'committed-patches-02'/(short+'.patch');lines=patch.read_text().splitlines();bad=[l for l in lines if l.strip()=='regulator-state-standby: false'];assert len(bad)==1 and bad[0].startswith(' '),short
 log=N/'committed-patches-02'/(short+'-checkpatch.log');assert "Unrecognized email address: 'false'" in log.read_text()
 context.append(dict(origin=short,unchanged_YAML_context_line=bad[0],patch_SHA256=sha(patch),log_SHA256=sha(log)))
assert 'F:\tdrivers/pmdomain/qcom/cpr*.h' in (C/'MAINTAINERS').read_text()
report=dict(passed=True,head=s['head'],source_files=files,native_objects_reverified=objects,configs_reverified=6,DTBs_reverified=17,full_link_package_or_hardware_acceptance=False,phone_access=False,checkpatch_gate_passed=False,checkpatch_errors=2,checkpatch_warnings=5,checkpatch_context_false_positives=context,remaining_checkpatch_warning='Generic new-file reminder; existing drivers/pmdomain/qcom/cpr*.h pattern covers cpr-sleep.h' ,human_review_and_DCO_pending=True)
(N/'final-input-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(passed=True,source_files=len(files),native_objects=objects,checkpatch_gate_passed=False)))
