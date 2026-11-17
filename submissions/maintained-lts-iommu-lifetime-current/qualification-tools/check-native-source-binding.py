# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,re,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';file='drivers/iommu/arm/arm-smmu/qcom_iommu.c';body=(C/file).read_bytes();md5=hashlib.md5(body).hexdigest();j=json.loads((N/'native-01/controller.json').read_text());rows=[]
for p in j['profiles']:
 out=N/'native-01'/(p['profile']+'-out');obj=out/'drivers/iommu/arm/arm-smmu/qcom_iommu.o';r=subprocess.run(['llvm-dwarfdump-21','--debug-line',str(obj)],capture_output=True,text=True,timeout=30);assert r.returncode==0
 chunks=re.split(r'file_names\[',r.stdout);matches=[x for x in chunks if re.search(r'name:\s+"[^"\n]*qcom_iommu\.c"',x)];checks=[re.search(r'md5_checksum:\s+([0-9a-fA-F]+)',x).group(1).lower() for x in matches];assert checks and all(x==md5 for x in checks),(p['profile'],checks,md5)
 assert hashlib.sha256(obj.read_bytes()).hexdigest()==p['object_SHA256'];assert hashlib.sha256((out/'.config').read_bytes()).hexdigest()==p['config_SHA256'];cfg=(out/'.config').read_text();assert 'CONFIG_EXPERT=y\n' in cfg and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg;rows.append(dict(profile=p['profile'],object_SHA256=p['object_SHA256'],source_MD5_in_DWARF=checks,source_checksum_verified=True))
(N/'native-source-binding.json').write_text(json.dumps(dict(passed=True,source_file=file,source_SHA256=hashlib.sha256(body).hexdigest(),source_MD5=md5,records=rows,scope='All three compiled ELF line tables bind the exact current source bytes; source SHA256 recorded separately',phone_access=False),indent=2)+'\n');print('Three native ELF line tables bind the exact current IOMMU source')
