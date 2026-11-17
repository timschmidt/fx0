# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';j=json.loads((N/'native-01/controller.json').read_text());assert j['passed'];rows=[]
for profile in j['profiles']:
 out=N/'native-01'/(profile['profile']+'-out')
 for obj,h in profile['objects'].items():
  p=out/obj;file=obj[:-2]+'.c';md5=hashlib.md5((C/file).read_bytes()).hexdigest();r=subprocess.run(['llvm-dwarfdump-21','--debug-line',str(p)],capture_output=True,text=True,timeout=30);assert r.returncode==0;chunks=re.split(r'file_names\[',r.stdout);checks=[re.search(r'md5_checksum:\s+([0-9a-fA-F]+)',x)[1].lower() for x in chunks if re.search(r'name:\s+"[^"\n]*'+re.escape(Path(file).name)+'"',x)];assert checks and all(x==md5 for x in checks),(obj,checks,md5);assert hashlib.sha256(p.read_bytes()).hexdigest()==h;rows.append(dict(profile=profile['profile'],object=obj,object_SHA256=h,source_MD5_in_DWARF=checks))
(N/'native-source-binding.json').write_text(json.dumps(dict(passed=True,objects=len(rows),records=rows,phone_access=False),indent=2)+'\n');print(len(rows),'native ELF source checksums verified')
