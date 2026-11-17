# SPDX-License-Identifier: GPL-2.0-only
"""Correct commit references without changing any tested source tree."""
from pathlib import Path
from datetime import datetime,timezone
import json,os,re,subprocess,textwrap
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01'
j=json.loads((N/'source-current.json').read_text());assert len(j['commits'])==17
(N/'source-message-revision-01.json').write_text(json.dumps(j,indent=2)+'\n')
env=os.environ|{'GIT_NO_LAZY_FETCH':'1','GIT_COMMITTER_NAME':'Codex','GIT_COMMITTER_EMAIL':'codex@openai.com'}
def git(*args,data=None,environment=env):return subprocess.check_output(['git',*args],input=data,cwd=C,env=environment)
assert git('rev-parse','HEAD').decode().strip()==j['head'] and not git('status','--porcelain')
git('update-ref','refs/heads/archive/fx0-lts-sleep-prerequisite-messages-01',j['head'])
prior=json.loads((N.parent/'cpu-stack-01/source-current.json').read_text())
refs={r['origin_commit'][:12]:r['commit'][:12] for r in prior['commits']}
parent=j['base'];rows=[]
for r in j['commits']:
 old=r['commit'];origin=r['origin_commit'];message=(N/'commit-messages'/(origin[:12]+'.txt')).read_text()
 # Context-only old Fixes ID is the earlier version of this exact paired-voter patch.
 refs['fd2652968249']=refs.get('18bc0ef32ef2','fd2652968249')
 remaps=[]
 for a,b in refs.items():
  if 'Fixes: '+a in message:message=message.replace('Fixes: '+a,'Fixes: '+b);remaps.append(dict(original=a,maintained=b))
 a=message.index('Backported from commit '+origin)
 message=message[:a]+'\n'.join(textwrap.wrap('Backported from commit '+origin[:12]+' ("'+r['subject']+'")',width=70,break_long_words=False,break_on_hyphens=False))+'\n'
 p=N/'commit-messages'/(origin[:12]+'-02.txt');p.write_text(message)
 tree=git('rev-parse',old+'^{tree}').decode().strip()
 ae=env|{'GIT_AUTHOR_NAME':r['author'],'GIT_AUTHOR_EMAIL':r['author_email'],'GIT_AUTHOR_DATE':r['author_date']}
 head=git('commit-tree',tree,'-p',parent,'-F',str(p),environment=ae).decode().strip()
 assert git('rev-parse',head+'^{tree}')==git('rev-parse',old+'^{tree}')
 r.update(commit=head,parent=parent,previous_message_revision=old,Fixes_references_remapped=remaps)
 refs[origin[:12]]=head[:12];rows.append(r);parent=head
old_head=j['head'];git('update-ref','refs/heads/integration/fx0-lts-current-01',parent,old_head)
assert not git('status','--porcelain')
j.update(head=parent,commits=rows,all_message_only_revisions_preserve_exact_source_trees=True,initial_message_revision_head=old_head)
(N/'source-current.json').write_text(json.dumps(j,indent=2)+'\n')
for name in [N.parent/'source-current.json',N/'combined-source-current.json']:
 v=json.loads(name.read_text());v['head']=parent
 mapping={r['origin_commit']:r for r in rows}
 v['commits']=[mapping.get(r['origin_commit'],r) for r in v['commits']];name.write_text(json.dumps(v,indent=2)+'\n')
p=N.parent/'backport-ledger.json';v=json.loads(p.read_text());v['maintained_source_head']=parent
for r in v['commits']:
 if r['commit'] in {x['origin_commit'] for x in rows}:r['maintained_backport']=next(x['commit'] for x in rows if x['origin_commit']==r['commit'])
p.write_text(json.dumps(v,indent=2)+'\n')
print(json.dumps(dict(head=parent,source_trees_unchanged=True)))
