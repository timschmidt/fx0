# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'native-01';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();files=['drivers/input/rmi4/rmi_i2c.c','drivers/input/rmi4/rmi_driver.c','drivers/gpu/drm/panel/panel-lg-fx0.c'];source_hashes={f:sha(C/f) for f in files};child=None;j=dict(passed=False,state='prepared',source_files=source_hashes,profiles=[],stages=[],ARM32_RT_unsupported_not_counted=True,phone_access=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for arch,rt,drm,seed in [('arm',False,'y','native-01/arm-normal-CPU-enabled-system-on-out'),('arm64',False,'m','native-01/arm64-normal-CPU-enabled-system-off-out'),('arm64',True,'m','native-02/arm64-rt-CPU-enabled-system-off-out'),('arm',False,'n','native-01/arm-normal-CPU-enabled-system-on-out')]:
  label=arch+('-rt' if rt else '-normal')+'-DRM-'+drm;out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((N.parent/'system-coordinator-01'/seed/'.config').read_bytes());env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'};op={'y':'--enable','m':'--module','n':'--disable'};mode='y' if drm=='y' else 'm'
  args=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--enable','INPUT','--enable','I2C','--enable','REGULATOR','--enable','GPIOLIB','--enable','BACKLIGHT_CLASS_DEVICE',op[drm],'DRM',op[mode],'RMI4_CORE',op[mode],'RMI4_I2C']
  if drm!='n':args+=['--enable','DRM_MIPI_DSI','--enable','DRM_PANEL',op[mode],'DRM_PANEL_LG_FX0']
  subprocess.run(args,cwd=C,check=True);make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j2'];selected=files if drm!='n' else files[:2]
  for phase,targets in [('config',['olddefconfig']),('objects',[f[:-2]+'.o' for f in selected])]:
   log=O/(label+'-'+phase+'.log')
   with log.open('xb') as stream:child=subprocess.Popen(make+targets,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label+' '+phase,active_PID=child.pid);save();code=child.wait(timeout=300)
   diagnostics=[l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(profile=label,phase=phase,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0
   # Keep and classify the pre-existing RMI header diagnostics; do not hide them.
   assert not diagnostics or all('rmi_driver.h:' in x and 'warning:' in x for x in diagnostics),diagnostics
  cfg=(out/'.config').read_text();assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt and ('CONFIG_DRM='+drm+'\n' in cfg if drm!='n' else '# CONFIG_DRM is not set\n' in cfg);assert 'CONFIG_RMI4_I2C='+mode+'\n' in cfg and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  assert all(sha(C/f)==h for f,h in source_hashes.items());symbols=subprocess.check_output(['llvm-nm-21',str(out/'drivers/input/rmi4/rmi_i2c.o')],text=True);assert ('rmi_i2c_panel_prepared' in symbols)==(drm!='n')
  j['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=rt,DRM=drm,RMI4_I2C=mode,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),objects={f[:-2]+'.o':sha(out/(f[:-2]+'.o')) for f in selected},panel_callbacks_present=drm!='n'));save()
 j.update(passed=True,state='terminal success',native_objects=11)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
