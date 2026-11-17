# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'native-01';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();file='drivers/leds/flash/leds-qcom-flash-v1.c';source_hash=sha(C/file);child=None
j=dict(passed=False,state='prepared',source_files={file:source_hash},profiles=[],stages=[],ARM32_RT_unsupported_not_counted=True,phone_access=False,physical_acceptance=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for arch,rt,seed in [('arm',False,'native-01/arm-normal-CPU-enabled-system-on-out'),('arm64',False,'native-01/arm64-normal-CPU-enabled-system-off-out'),('arm64',True,'native-02/arm64-rt-CPU-enabled-system-off-out')]:
  label=arch+('-rt' if rt else '-normal');out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((N.parent/'system-coordinator-01'/seed/'.config').read_bytes());env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'}
  args=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--module','LEDS_QCOM_FLASH_V1'];subprocess.run(args,cwd=C,check=True)
  make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j2']
  for phase,targets in [('config',['olddefconfig']),('object',['drivers/leds/flash/leds-qcom-flash-v1.o'])]:
   log=O/(label+'-'+phase+'.log')
   with log.open('xb') as stream:
    child=subprocess.Popen(make+targets,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label+' '+phase,active_PID=child.pid);save();code=child.wait(timeout=240)
   diagnostics=[l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(profile=label,phase=phase,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0 and not diagnostics
  cfg=(out/'.config').read_text();assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt and 'CONFIG_LEDS_QCOM_FLASH_V1=m\n' in cfg and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  assert sha(C/file)==source_hash;j['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=rt,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),object_SHA256=sha(out/'drivers/leds/flash/leds-qcom-flash-v1.o')));save()
 j.update(passed=True,state='terminal success',native_objects=3)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,native_objects=3)))
