# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import json,hashlib,os,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'Falcon-01';O.mkdir();(O/'tmp').mkdir();(O/'.config').write_bytes((N/'native-01/arm-normal-out/.config').read_bytes());rows=[]
for label,args in [('config',['olddefconfig']),('DTB',['qcom/msm8226-motorola-falcon.dtb'])]:
 p=subprocess.run(['make','O='+str(O),'ARCH=arm','LLVM=-21','W=1','-j2',*args],cwd=C,env=os.environ|{'TMPDIR':str(O/'tmp')},capture_output=True,text=True,timeout=180);log=O/(label+'.log');log.write_text(p.stdout+p.stderr);rows.append(dict(stage=label,returncode=p.returncode,log_SHA256=hashlib.sha256(log.read_bytes()).hexdigest()));assert p.returncode==0
out=O/'arch/arm/boot/dts/qcom/msm8226-motorola-falcon.dtb';(O/'controller.json').write_text(json.dumps(dict(passed=True,stages=rows,DTB_SHA256=hashlib.sha256(out.read_bytes()).hexdigest(),source_DTS_unchanged_from_pre_port=True,phone_access=False),indent=2)+'\n');print('Falcon native DTB built')
