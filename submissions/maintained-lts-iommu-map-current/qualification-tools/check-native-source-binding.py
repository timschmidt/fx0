# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';j=json.loads((N/'native-current.json').read_text());rows=[];assert j['passed'] and j['native_objects']==13
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for p in j['profiles']:
 out=N/p['output_relative'];assert sha(out/'.config')==p['config_SHA256']
 for name,digest in p['objects'].items():
  obj=out/name;source=name[:-2]+'.c';body=(C/source).read_bytes();md5=hashlib.md5(body).hexdigest();r=subprocess.run(['llvm-dwarfdump-21','--debug-line',str(obj)],capture_output=True,text=True,timeout=30);assert r.returncode==0 and sha(obj)==digest
  chunks=re.split(r'file_names\[',r.stdout);matches=[x for x in chunks if re.search(r'name:\s+"[^"\n]*'+re.escape(Path(source).name)+'"',x)];checks=[re.search(r'md5_checksum:\s+([0-9a-fA-F]+)',x).group(1).lower() for x in matches];assert checks and all(x==md5 for x in checks)
  rows.append(dict(profile=p['profile'],source=source,source_SHA256=sha(C/source),object_SHA256=digest,DWARF_source_MD5=checks))
assert len(rows)==13;(N/'native-source-binding.json').write_text(json.dumps(dict(passed=True,records=rows,native_IOMMU_and_MMCC_and_DSI_configs_verified=True,phone_access=False),indent=2)+'\n');print('Thirteen native ELF line tables bind the exact current source')
