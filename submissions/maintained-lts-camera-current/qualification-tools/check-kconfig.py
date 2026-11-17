# SPDX-License-Identifier: GPL-2.0-only
"""Actual full LTS Kconfig via source views; only camera select differs."""
from pathlib import Path
import hashlib,json,os,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'Kconfig-02';O.mkdir();rows=[];sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();target='drivers/media/platform/qcom/camss/Kconfig'
def view(src,dst,relative=''):
 dst.mkdir()
 for p in src.iterdir():
  rel=relative+p.name
  if p.name=='.git':continue
  q=dst/p.name
  if rel==target:q.write_bytes((N/'before'/target).read_bytes())
  elif target.startswith(rel+'/'):view(p,q,rel+'/')
  elif rel=='Makefile':q.write_bytes(p.read_bytes())
  else:q.symlink_to(p,target_is_directory=p.is_dir())
v=O/'before-source';view(C,v)
j=dict(passed=False,records=rows,actual_full_LTS_Kconfig=True,baseline_view='Symlink source view with byte-identical copied root Makefile and original CAMSS Kconfig only',phone_access=False);save=lambda:(O/'qualification.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for fixed,source in [(True,C)]:
  for arch in ['arm','arm64']:
   out=O/(('after' if fixed else 'before')+'-'+arch+'-out');out.mkdir();(out/'tmp').mkdir()
   for mode in ['y','m']:
    seed=out/('CAMSS-'+mode+'.seed');cfg=dict(MODULES='y',ARCH_QCOM='y',OF='y',PM='y',COMMON_CLK='y',IOMMU_SUPPORT='y',ARM_SMMU='y',MEDIA_SUPPORT='y',MEDIA_SUPPORT_FILTER='y',MEDIA_CAMERA_SUPPORT='y',MEDIA_PLATFORM_SUPPORT='y',MEDIA_PLATFORM_DRIVERS='y',VIDEO_DEV='y',V4L_PLATFORM_DRIVERS='y',VIDEO_QCOM_CAMSS=mode)
    if arch=='arm':cfg.update(ARCH_MULTI_V7='y',MMU='y')
    seed.write_text(''.join('CONFIG_'+k+'='+val+'\n' for k,val in cfg.items()));r=subprocess.run(['make','O='+str(out),'ARCH='+arch,'LLVM=-21','KCONFIG_ALLCONFIG='+str(seed),'allnoconfig'],cwd=source,capture_output=True,text=True,timeout=180,env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'})
    log=out/('CAMSS-'+mode+'.log');log.write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
    assert not any(s in (r.stdout+r.stderr).lower() for s in ['warning:','error:'])
    text=(out/'.config').read_text();f=out/('CAMSS-'+mode+'.config');f.write_text(text)
    def value(k):return next((l.split('=',1)[1] for l in text.splitlines() if l.startswith('CONFIG_'+k+'=')),'n')
    vals={k:value(k) for k in ['VIDEO_QCOM_CAMSS','GENERIC_PHY_MIPI_DPHY','GENERIC_PHY','IOMMU_DMA','ARM_DMA_USE_IOMMU','COMPILE_TEST','ARCH_QCOM']};assert vals['VIDEO_QCOM_CAMSS']==mode and vals['COMPILE_TEST']=='n',vals
    reachable=vals['GENERIC_PHY_MIPI_DPHY']=='y';assert not reachable,vals
    rows.append(dict(fixed=fixed,ARCH=arch,CAMSS=mode,actual=vals,newer_only_helper_selected=reachable,config_SHA256=sha(f),source_Kconfig_SHA256=sha(source/target),diagnostics=0));save()
 j.update(passed=True,cases=len(rows),unneeded_helper_absent_in_all_four=True)
except BaseException as e:j.update(error=str(e));raise
finally:j['terminal']=True;save()
print(json.dumps(dict(passed=True,cases=len(rows),unneeded_helper_absent_in_all_four=True)))
