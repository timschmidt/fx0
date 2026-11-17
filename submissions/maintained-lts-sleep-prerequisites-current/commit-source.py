# SPDX-License-Identifier: GPL-2.0-only
"""Create only the seventeen qualified LTS prerequisite commits in a private index."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,re,subprocess,textwrap
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
plan=read(N/'prepared.json');composition=read(N/'composition.json');base=plan['base']
env=os.environ|{'GIT_NO_LAZY_FETCH':'1','GIT_COMMITTER_NAME':'Codex','GIT_COMMITTER_EMAIL':'codex@openai.com'}
def git(*args,data=None,source=C,environment=env):
 return subprocess.check_output(['git',*args],input=data,cwd=source,env=environment)
assert sha(R/'.git/index')=='bb68ca7f4caf5d5ac104e9292344226c602ae52f711819a6932813aea3bb4fdb'
assert git('rev-parse','HEAD').decode().strip()==base
assert not git('diff','--cached','--name-only')
for p in ['rails-after-03','boot-after','pair-after','legacy-after-02','SPM-after','L2-after','admission-after','PM-order','SO-after-02']:
 assert read(N/p/'qualification.json')['failures']==0,p
for p in ['all-controls.json','PM-controls/qualification.json','SPM-shared/qualification.json','retained-CPU-02/qualification.json','native-current.json','bindings-01-controller.json','DTBs-current.json']:
 assert read(N/p)['passed'],p
paths=sorted({f['path'] for r in composition['completed'] for f in r['files']});assert len(paths)==12
current={p:sha(C/p) for p in paths}
for p,digest in read(N/'native-current.json')['source_files'].items():assert sha(C/p)==digest,p
idx=N/'commit.index';assert not idx.exists();penv=env|{'GIT_INDEX_FILE':str(idx)}
git('read-tree',base,environment=penv)
messages=N/'commit-messages';messages.mkdir()
records=[];parent=base
for row in composition['completed']:
 origin=row['origin_commit'];stage=N/'stages'/origin[:12]
 author,email,date,body=git('show','-s','--format=%an%x00%ae%x00%aI%x00%B',origin,source=E).decode().split('\x00',3)
 removed=[];lines=[]
 for line in body.rstrip().splitlines():
  if line.lower().startswith('signed-off-by:') and any(t in line.lower() for t in ['codex','openai']):removed.append(line)
  else:lines.append(line)
 message='\n'.join(lines)+'\n\n'
 message+='Backport this prerequisite to maintained Linux 6.18.63. The complete\nseventeen-change batch passes native ARM, ARM64 and ARM64 RT object\nbuilds with the MSM8926 feature enabled and disabled. CPU-idle is ARM\nonly. Host fault models use synthetic services and normal LeakSanitizer;\nfirmware, electrical and physical suspend acceptance remain open.\n\n'
 if origin.startswith('18bc0ef'):
  message+='Use devm_kzalloc with sizeof(*pair) and GFP_KERNEL for the 6.18\nallocation API. Preserve the original zero-initialization semantics.\n\n'
 message+='Codex prepared this local backport and verification. Original authors,\ndates, licenses and human attribution tags are retained. Human DCO and\nreview remain pending. No phone access or publication occurred.\n\n'
 message+='\n'.join(textwrap.wrap('Backported from commit '+origin+' ("'+row['subject']+'")',width=70,break_long_words=False,break_on_hyphens=False))+'\n'
 messagepath=messages/(origin[:12]+'.txt');messagepath.write_text(message)
 for f in row['files']:
  p=f['path'];ours=(stage/p/'ours').read_bytes();after=(stage/p/'after').read_bytes()
  proc=subprocess.run(['git','show',':'+p],cwd=C,env=penv,capture_output=True)
  assert (proc.stdout if proc.returncode==0 else b'')==ours,(origin,p)
  blob=git('hash-object','-w','--stdin',data=after,environment=penv).decode().strip()
  git('update-index','--add','--cacheinfo','100644,'+blob+','+p,environment=penv)
 tree=git('write-tree',environment=penv).decode().strip()
 cenv=penv|{'GIT_AUTHOR_NAME':author,'GIT_AUTHOR_EMAIL':email,'GIT_AUTHOR_DATE':date}
 head=git('commit-tree',tree,'-p',parent,'-F',str(messagepath),environment=cenv).decode().strip()
 def delta(source,commit):
  patch=git('diff',commit+'^',commit,'--no-ext-diff','--no-renames','--unified=0',source=source).decode().splitlines()
  return [l for l in patch if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
 exact=delta(C,head)==delta(E,origin)
 records.append(dict(origin_commit=origin,commit=head,parent=parent,subject=row['subject'],author=author,author_email=email,author_date=date,paths=[f['path'] for f in row['files']],exact_added_removed_source_lines=exact,removed_nonhuman_signoff_tags=removed))
 parent=head
for p in paths:assert hashlib.sha256(git('show',parent+':'+p)).hexdigest()==current[p],p
assert current=={p:sha(C/p) for p in paths}
git('diff','--check',base,parent)
# Advance only this isolated branch, then synchronize its index to the already-built files.
git('update-ref','refs/heads/integration/fx0-lts-current-01',parent,base)
git('read-tree',parent)
assert not git('status','--porcelain')
report=dict(passed=True,recorded_UTC=datetime.now(timezone.utc).isoformat(),base=base,head=parent,branch='integration/fx0-lts-current-01',source_repo=str(C.relative_to(R)),commits=records,source_files=current,working_tree_clean=True,source_bytes_match_precommit_native_builds=True,native_objects=122,native_supported_profiles=6,CFI_nonpermissive=True,CPU_idle_ARM_only=True,ARM32_RT_unsupported_not_counted=True,source_commits=17,exact_source_deltas=sum(r['exact_added_removed_source_lines'] for r in records),reconciled_source_deltas=sum(not r['exact_added_removed_source_lines'] for r in records),normal_target_promoted=False,production_sleep_coordinator_included=False,full_link_APK_update_or_physical_qualification=False,phone_access=False,published=False,human_DCO_pending=True,full_goal_complete=False)
(N/'source-current.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(head=parent,commits=17,exact_source_deltas=report['exact_source_deltas'],reconciled_source_deltas=report['reconciled_source_deltas'])))
