# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,re,subprocess
B=Path(__file__).resolve().parent;R=B.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';E=R/'worktrees/linux-fx0-cpu-current-01'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
j=json.loads((B/'source-current.json').read_text());out=B/'committed-patches-02';out.mkdir()
objects=subprocess.check_output(['git','rev-parse','--git-path','objects'],cwd=E,text=True).strip();objects=str((E/objects).resolve())
env=os.environ|{'GIT_NO_LAZY_FETCH':'1','GIT_ALTERNATE_OBJECT_DIRECTORIES':objects}
rows=[]
for row in j['commits']:
 patch=out/(row['origin_commit'][:12]+'.patch');patch.write_bytes(subprocess.check_output(['git','format-patch','-1','--stdout',row['commit']],cwd=C,env=env))
 command=['perl','scripts/checkpatch.pl','--strict','--no-signoff',str(patch)]
 r=subprocess.run(command,cwd=C,env=env,capture_output=True,text=True,timeout=120)
 log=out/(row['origin_commit'][:12]+'-checkpatch.log');log.write_text(r.stdout+r.stderr)
 m=re.search(r'total: (\d+) errors, (\d+) warnings, (\d+) checks',log.read_text());assert m,(row,log.read_text())
 errors,warnings,checks=map(int,m.groups());rows.append(dict(commit=row['commit'],origin_commit=row['origin_commit'],returncode=r.returncode,errors=errors,warnings=warnings,checks=checks,patch_SHA256=sha(patch),log_SHA256=sha(log)))
report=dict(passed=all(r['returncode']==0 for r in rows),all_commits_zero_errors=all(not r['errors'] for r in rows),errors=sum(r['errors'] for r in rows),warnings=sum(r['warnings'] for r in rows),checks=sum(r['checks'] for r in rows),strict=True,ignored_check_types=[],signoff_check_disabled_because_no_human_DCO_certification_added=True,human_DCO_pending=True,records=rows)
(B/'checkpatch-02.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='records'}))
