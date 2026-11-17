# SPDX-License-Identifier: GPL-2.0-only
"""Compile six affected and preserved MDP5/IOMMU/input objects under maintained LTS configs."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, os, signal, subprocess
B=Path(__file__).resolve().parent;R=B.parents[2]
C=R/'worktrees/linux-fx0-lts-integration-current-01'
previous=B.parent/'native-02'
O=B/'native-01';O.mkdir(exist_ok=False)
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
paths=['drivers/gpu/drm/msm/disp/mdp5/mdp5_pipe.c','drivers/gpu/drm/msm/disp/mdp5/mdp5_plane.c','drivers/gpu/drm/msm/disp/mdp5/mdp5_kms.c','drivers/gpu/drm/msm/disp/mdp5/mdp5_encoder.c','drivers/input/misc/pm8xxx-vibrator.c','drivers/iommu/arm/arm-smmu/qcom_iommu.c']
manifest={p:sha(C/p) for p in paths}
record=dict(started_UTC=datetime.now(timezone.utc).isoformat(),passed=False,state='prepared',
    source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip(),
    source_uncommitted=True,source_files=manifest,profiles=[],architecture_constraints=[],
    phone_access=False,published=False,full_kernel_package_or_physical_acceptance=False,seeds='Already qualified LTS native-02 configs; no 7.4 seed Kconfig type adaptation required',ARM32_RT_unsupported_not_counted=True,stages=[])
controller=O/'controller.json';child=None
def save():controller.write_text(json.dumps(record,indent=2)+'\n')
def interrupted(sig,frame):raise InterruptedError(str(sig))
signal.signal(signal.SIGTERM,interrupted)
def run(label,cmd,env,timeout=300):
 global child
 log=O/(label+'.log')
 with log.open('xb') as stream:
  child=subprocess.Popen(cmd,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
  record.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=timeout)
 record.pop('active_PID',None);lines=log.read_text(errors='replace').splitlines()
 record['stages'].append(dict(label=label,returncode=code,log_SHA256=sha(log),diagnostics=[l for l in lines if 'warning:' in l.lower() or 'error:' in l.lower()]));save();assert code==0,(label,code,lines[-12:])
try:
 for arch,rt,seed in [('arm',False,'arm-normal'),('arm64',False,'arm64-normal'),('arm64',True,'arm64-rt')]:
  label=arch+('-rt' if rt else '-normal');out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir()
  (out/'.config').write_bytes((previous/(seed+'-out/.config')).read_bytes())
  env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1','KBUILD_BUILD_USER':'fx0-review','KBUILD_BUILD_HOST':'source-check','KBUILD_BUILD_TIMESTAMP':'2026-11-16 00:00:00 UTC','KBUILD_BUILD_VERSION':'1'}
  options=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--enable' if rt else '--disable','PREEMPT_RT']
  for name in ['DRM_MSM_MDP5','QCOM_IOMMU','INPUT_PM8XXX_VIBRATOR']:options+=['--enable',name]
  if rt:options+=['--disable','PREEMPT','--disable','PREEMPT_LAZY','--disable','PREEMPT_DYNAMIC']
  make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','--jobserver-style=pipe','-j2']
  run(label+'-options',options,env)
  run(label+'-config',make+['olddefconfig'],env)
  cfg=(out/'.config').read_text();actual_rt='CONFIG_PREEMPT_RT=y\n' in cfg
  assert 'CONFIG_EXPERT=y\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  assert 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg
  for name in ['DRM_MSM_MDP5','QCOM_IOMMU','INPUT_PM8XXX_VIBRATOR']:
   assert any('CONFIG_'+name+'='+value+'\n' in cfg for value in ['y','m']),name
  if rt and not actual_rt:
   assert arch=='arm' and 'CONFIG_ARCH_SUPPORTS_RT=y\n' not in cfg, 'Supported RT request was unexpectedly lost'
   record['architecture_constraints'].append(dict(profile=label,requested_PREEMPT_RT=True,actual_PREEMPT_RT=False,ARCH_SUPPORTS_RT=False,config_SHA256=sha(out/'.config'),not_counted_as_RT_native_build=True))
   save();continue
  assert actual_rt==rt
  objects=[p[:-2]+'.o' for p in paths]
  run(label+'-objects',make+objects,env,600)
  assert manifest=={p:sha(C/p) for p in paths}
  record['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=actual_rt,EXPERT=True,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),source_files=manifest,objects={p:sha(out/p) for p in objects}))
  save()
 assert not [d for stage in record['stages'] for d in stage['diagnostics']], 'Unexpected native/config diagnostics'
 record.update(passed=True,state='terminal success',native_objects=sum(len(p['objects']) for p in record['profiles']),supported_profiles=len(record['profiles']),unsupported_RT_requests=len(record['architecture_constraints']))
except BaseException as error:
 record.update(state='terminal failure',error_type=type(error).__name__,error=str(error));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 record.pop('active_PID',None);record['owned_child_terminal_and_reaped']=child is None or child.returncode is not None
 record['finished_UTC']=datetime.now(timezone.utc).isoformat();save()
print(json.dumps(dict(passed=record['passed'],native_objects=record.get('native_objects'),unsupported_RT_requests=record.get('unsupported_RT_requests'))))
