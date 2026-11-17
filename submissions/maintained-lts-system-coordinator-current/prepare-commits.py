# SPDX-License-Identifier: GPL-2.0-only
"""Prepare attributed candidate commits without advancing the source build HEAD."""
from pathlib import Path
import hashlib,json,os,subprocess,textwrap
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01'
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();plan=read(N/'prepared.json');composition=read(N/'composition.json')
env=os.environ|{'GIT_NO_LAZY_FETCH':'1','GIT_COMMITTER_NAME':'Codex','GIT_COMMITTER_EMAIL':'codex@openai.com'}
def git(*args,data=None,source=C,environment=env):return subprocess.check_output(['git',*args],input=data,cwd=source,env=environment)
assert git('rev-parse','HEAD').decode().strip()==plan['base'] and not git('diff','--cached','--name-only')
assert read(N/'models-current.json')['positive_cases']==5009 and read(N/'models-current.json')['controls']==85
assert read(N/'native-current.json')['native_objects']==175 and read(N/'DTBs-01/controller.json')['passed']
assert read(N/'bindings-01-controller.json')['passed'] and read(N/'DT-wiring-02/qualification.json')['passed']
paths=sorted({f['path'] for r in composition['completed'] for f in r['files']});assert len(paths)==29
current={p:sha(C/p) for p in paths};idx=N/'candidate-03.index';ie=env|{'GIT_INDEX_FILE':str(idx)};git('read-tree',plan['base'],environment=ie)
messages=N/'commit-messages-03';messages.mkdir(exist_ok=True);patches=N/'origin-patches';patches.mkdir(exist_ok=True);parent=plan['base'];rows=[]
for ordinal,row in enumerate(composition['completed']):
 origin=row['origin_commit'];author,email,date,body=git('show','-s','--format=%an%x00%ae%x00%aI%x00%B',origin,source=E).decode().split('\x00',3)
 (patches/(origin[:12]+'.patch')).write_bytes(git('format-patch','-1','--stdout',origin,source=E))
 paragraphs=body.rstrip().split('\n\n');keep=2 if ordinal in [5,8] else 1
 mechanism=paragraphs[1:1+keep]
 message=paragraphs[0]+'\n\n'+'\n\n'.join(textwrap.fill(' '.join(x.splitlines()),width=70,break_long_words=False,break_on_hyphens=False) for x in mechanism)+'\n\n'
 if ordinal==3:message+='The independent sleep-only vote stays at 1337500 uV; lowering that\nfloor has not been authorized or physically qualified.\n\n'
 message+='Backport onto maintained Linux 6.18.63 while preserving its platform\ncontext and APIs. The ten-change batch passes 5009 synthetic model cases,\n85 fault controls and 175 selected native objects across seven supported\nfeature/config profiles. ARM32 RT is unsupported and is not counted.\n\n'
 if ordinal in [0,9]:message+='All 18 family DTBs build and 180 selected schema checks are silent;\nthe 17 prior DTBs are byte-identical. The new target repeats three\nexisting DTC warnings. Unfiltered schema validation still rejects the\nexisting PM8226 torch child; that independent port remains pending.\n\n'
 message+='Services and faults are synthetic. Firmware, kernel concurrency, normal\npackage integration and physical acceptance remain open. Codex prepared\nthis local backport and verification. Original authors, dates and source\nnotices are retained; no human DCO or publication is claimed.\n\n'
 message+='\n'.join(textwrap.wrap('Backported from commit '+origin[:12]+' ("'+row['subject']+'")',width=70,break_long_words=False,break_on_hyphens=False))+'\n'
 p=messages/(origin[:12]+'.txt');p.write_text(message)
 for f in row['files']:
  name=f['path'];folder=N/'stages'/origin[:12]/name;ours=(folder/'ours').read_bytes();after=(folder/'after').read_bytes();q=subprocess.run(['git','show',':'+name],cwd=C,env=ie,capture_output=True);assert (q.stdout if q.returncode==0 else b'')==ours,name
  blob=git('hash-object','-w','--stdin',data=after).decode().strip();git('update-index','--add','--cacheinfo','100644',blob,name,environment=ie)
 tree=git('write-tree',environment=ie).decode().strip();ae=env|{'GIT_AUTHOR_NAME':author,'GIT_AUTHOR_EMAIL':email,'GIT_AUTHOR_DATE':date};head=git('commit-tree',tree,'-p',parent,'-F',str(p),environment=ae).decode().strip()
 def delta(source,commit):return [l for l in git('diff',commit+'^',commit,'--no-ext-diff','--no-renames','--unified=0',source=source).decode().splitlines() if l.startswith(('+','-')) and not l.startswith(('+++','---'))]
 exact=delta(C,head)==delta(E,origin)
 rows.append(dict(origin_commit=origin,commit=head,parent=parent,subject=row['subject'],author=author,author_email=email,author_date=date,paths=[f['path'] for f in row['files']],exact_added_removed_source_lines=exact,original_message_preserved_in_origin_patch=True));parent=head
for p in paths:assert hashlib.sha256(git('show',parent+':'+p)).hexdigest()==current[p],p
assert current=={p:sha(C/p) for p in paths};git('diff','--check',plan['base'],parent)
report=dict(passed=True,base=plan['base'],head=parent,source_repo=str(C.relative_to(R)),branch='integration/fx0-lts-current-01',commits=rows,source_files=current,source_commits=10,exact_source_deltas=sum(r['exact_added_removed_source_lines'] for r in rows),reconciled_source_deltas=sum(not r['exact_added_removed_source_lines'] for r in rows),source_branch_not_advanced=True,normal_target_promoted=False,published=False,phone_access=False,human_DCO_pending=True,full_goal_complete=False)
(N/'candidate-source.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(dict(candidate_head=parent,commits=10,exact=report['exact_source_deltas'],reconciled=report['reconciled_source_deltas'],source_HEAD_unchanged=True)))
