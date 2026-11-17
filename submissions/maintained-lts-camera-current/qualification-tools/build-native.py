# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,re,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'native-05';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();prefix='drivers/media/platform/qcom/camss/'
objects=list(dict.fromkeys(prefix+x for x in re.findall(r'\b(camss[\w-]*\.o)\b',(C/(prefix+'Makefile')).read_text())))+['drivers/media/i2c/imx132.o','drivers/media/i2c/imx179.o'];assert len(objects)==26
files=[x[:-2]+'.c' for x in objects];source_hashes={f:sha(C/f) for f in files};child=None;j=dict(passed=False,state='prepared',source_files=source_hashes,profiles=[],stages=[],ARM32_RT_unsupported_not_counted=True,phone_access=False,full_kernel_link=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for arch,rt,mode,seed in [('arm',False,'y','native-01/arm-normal-CPU-enabled-system-on-out'),('arm64',False,'m','native-01/arm64-normal-CPU-enabled-system-off-out'),('arm64',True,'m','native-02/arm64-rt-CPU-enabled-system-off-out')]:
  label=arch+('-rt' if rt else '-normal')+'-CAMSS-'+mode;out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((N.parent/'system-coordinator-01'/seed/'.config').read_bytes());env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'}
  args=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--enable','MODULES']
  for sym in ['ARCH_QCOM','I2C','IOMMU_SUPPORT','ARM_SMMU','MEDIA_SUPPORT','MEDIA_SUPPORT_FILTER','MEDIA_CAMERA_SUPPORT','MEDIA_PLATFORM_SUPPORT','MEDIA_PLATFORM_DRIVERS','V4L_PLATFORM_DRIVERS','VIDEO_DEV','MEDIA_CONTROLLER','VIDEO_V4L2_SUBDEV_API','MEDIA_SUBDRV_AUTOSELECT']:
   args+=['--enable',sym]
  for sym in ['VIDEO_QCOM_CAMSS','VIDEO_IMX132','VIDEO_IMX179']:args+=['--enable' if mode=='y' else '--module',sym]
  subprocess.run(args,cwd=C,check=True);make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j2']
  for phase,targets in [('config',['olddefconfig']),('objects',objects)]:
   log=O/(label+'-'+phase+'.log')
   with log.open('xb') as stream:
    child=subprocess.Popen(make+targets,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label+' '+phase,active_PID=child.pid);save();code=child.wait(timeout=600)
   diagnostics=[l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(profile=label,phase=phase,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0 and not diagnostics,diagnostics
  cfg=(out/'.config').read_text();assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  for sym in ['VIDEO_QCOM_CAMSS','VIDEO_IMX132','VIDEO_IMX179']:assert 'CONFIG_'+sym+'='+mode+'\n' in cfg,(sym,mode)
  aggregate=out/'source-only-camss-partial.o';subprocess.run(['ld.lld-21','-r','-o',str(aggregate),*[str(out/f) for f in objects if f.startswith(prefix)]],check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  symbols=subprocess.check_output(['llvm-nm-21','--undefined-only',str(aggregate)],text=True);assert 'phy_mipi_dphy' not in symbols
  (out/'aggregate-undefined-symbols.log').write_text(symbols)
  assert all(sha(C/f)==h for f,h in source_hashes.items());j['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=rt,CAMSS=mode,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),objects={f:sha(out/f) for f in objects},aggregate_SHA256=sha(aggregate),partial_link_not_Kbuild_final_module=True,no_unresolved_MIPI_DPHY_helpers=True));save()
 j.update(passed=True,state='terminal success',native_objects=len(objects)*len(j['profiles']))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,native_objects=j['native_objects'])))
