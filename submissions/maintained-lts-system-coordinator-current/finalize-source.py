# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];Q=N.parent;C=R/'worktrees/linux-fx0-lts-integration-current-01';read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();j=read(N/'candidate-source.json');env=os.environ|{'GIT_NO_LAZY_FETCH':'1'}
def git(*args):return subprocess.check_output(['git',*args],cwd=C,env=env)
assert git('rev-parse','HEAD').decode().strip()==j['base'] and not git('diff','--cached','--name-only')
for p,digest in j['source_files'].items():assert sha(C/p)==digest,p
native=read(N/'native-current.json');assert native['passed'] and native['native_objects']==175 and native['coordinator_instruction_and_relocation_streams_unchanged']
for p,digest in native['source_files'].items():assert sha(C/p)==digest,p
link=read(N/'unsigned-relink-01/controller.json');assert link['passed'] and link['owned_child_terminal_and_reaped'] and link['raw_modules']==447 and link['all_modules_unsigned']
for p,digest in link['source_files'].items():assert sha(C/p)==digest,p
for record in ['models-current.json','Kconfig-current.json','DTBs-01/controller.json','DT-wiring-02/qualification.json','bindings-01-controller.json','full-build-diagnostic-audit.json']:
 assert read(N/record)['passed'],record
style=read(N/'checkpatch-03.json');assert style['all_commits_zero_errors'] and style['errors']==0 and style['warnings']==6 and style['checks']==2
assert sha(R/'.git/index')=='bb68ca7f4caf5d5ac104e9292344226c602ae52f711819a6932813aea3bb4fdb'
git('diff','--check',j['base'],j['head']);git('update-ref','refs/heads/integration/fx0-lts-current-01',j['head'],j['base']);git('read-tree',j['head']);assert not git('status','--porcelain')
j.update(recorded_UTC=datetime.now(timezone.utc).isoformat(),source_branch_not_advanced=False,working_tree_clean=True,source_bytes_match_precommit_native_and_integration_link=True,native_objects=175,supported_native_profiles=7,host_model_cases=5009,fault_controls=85,DTBS=18,previous_DTBS_byte_identical=17,selected_schema_checks=180,Kconfig_cases=21,negative_binding_controls=12,full_host_integration_link_passed=True,raw_unsigned_modules=447,automatic_module_signing_disabled=True,public_verification_certificate_only=True,private_key_access_or_generation=False,release_specific_APK_qualified=False,strict_checkpatch_passed=False,checkpatch_errors=0,checkpatch_warnings=6,checkpatch_checks=2,full_schema_gate_passed=False,physical_acceptance=False,human_DCO_pending=True,phone_access=False,published=False,maintainer_contact=False)
(N/'source-current.json').write_text(json.dumps(j,indent=2)+'\n')
combined=read(Q/'source-current.json');(N/'combined-source-before.json').write_text(json.dumps(combined,indent=2)+'\n');combined['head']=j['head'];combined['commits']+=j['commits'];combined['source_files']|=j['source_files'];combined.update(working_tree_clean=True,focused_cases=combined['focused_cases']+5009,native_objects=combined['native_objects']+175,system_coordinator_host_models=13,system_coordinator_native_objects=175,system_coordinator_full_integration_link=True,system_coordinator_unsigned_modules=447,latest_phase='maintained LTS system coordinator',strict_checkpatch_passed=False,full_link_and_release_specific_package_qualification=False)
assert len(combined['commits'])==48;(Q/'source-current.json').write_text(json.dumps(combined,indent=2)+'\n');(N/'combined-source-current.json').write_text(json.dumps(combined,indent=2)+'\n')
ledger=read(Q/'backport-ledger.json');(N/'ledger-before.json').write_text(json.dumps(ledger,indent=2)+'\n')
for row in j['commits']:
 item=next(r for r in ledger['commits'] if r['commit']==row['origin_commit']);assert item['maintained_backport'] is None;item.update(maintained_backport=row['commit'],status='exact source delta backported; maintained-LTS system coordinator qualified' if row['exact_added_removed_source_lines'] else 'source delta reconciled to LTS board Makefile or generic cacheflush wrapper; system coordinator qualified')
ledger.update(maintained_source_head=j['head'],exact_backports=ledger['exact_backports']+8,reconciled_backports=ledger['reconciled_backports']+2,remaining_applicability_audits=ledger['remaining_applicability_audits']-10);assert ledger['exact_backports']==40 and ledger['reconciled_backports']==8 and ledger['remaining_applicability_audits']==91
(Q/'backport-ledger.json').write_text(json.dumps(ledger,indent=2)+'\n');print(json.dumps(dict(source_head=j['head'],source_commits=48,exact=40,reconciled=8,remaining=91)))
