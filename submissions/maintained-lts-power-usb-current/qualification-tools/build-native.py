# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'native-02';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();files=['drivers/power/supply/qcom_smbb.c','drivers/usb/chipidea/udc.c','drivers/iio/adc/qcom-spmi-vadc.c','drivers/iio/adc/qcom-vadc-common.c','drivers/iio/inkern.c'];source_hashes={f:sha(C/f) for f in files};child=None
j=dict(passed=False,state='prepared',source_files=source_hashes,profiles=[],stages=[],ARM32_RT_unsupported_not_counted=True,phone_access=False,physical_acceptance=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for arch,rt,seed,managed in [('arm',False,'native-01/arm-normal-CPU-enabled-system-on-out',True),('arm64',False,'native-01/arm64-normal-CPU-enabled-system-off-out',True),('arm64',True,'native-02/arm64-rt-CPU-enabled-system-off-out',True),('arm',False,'native-01/arm-normal-CPU-enabled-system-on-out',False)]:
  label=arch+('-rt' if rt else '-normal')+('-managed' if managed else '-legacy');out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((N.parent/'system-coordinator-01'/seed/'.config').read_bytes());env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'}
  args=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--enable','POWER_SUPPLY','--enable','IIO','--enable','SPMI',('--enable' if managed else '--module'),'CHARGER_QCOM_SMBB','--module','QCOM_SPMI_VADC','--module','USB_CHIPIDEA','--enable','USB_CHIPIDEA_UDC',('--enable' if managed else '--disable'),'CHARGER_QCOM_SMBB_POLICY'];subprocess.run(args,cwd=C,check=True)
  make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j2']
  for phase,targets in [('config',['olddefconfig']),('object',[f[:-2]+'.o' for f in files])]:
   log=O/(label+'-'+phase+'.log')
   with log.open('xb') as stream:
    child=subprocess.Popen(make+targets,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label+' '+phase,active_PID=child.pid);save();code=child.wait(timeout=240)
   diagnostics=[l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(profile=label,phase=phase,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0 and not diagnostics
  cfg=(out/'.config').read_text();assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt and 'CONFIG_QCOM_SPMI_VADC=m\n' in cfg and ('CONFIG_CHARGER_QCOM_SMBB='+('y' if managed else 'm')+'\n') in cfg and 'CONFIG_USB_CHIPIDEA=m\n' in cfg and ('CONFIG_CHARGER_QCOM_SMBB_POLICY=y\n' in cfg)==managed and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  assert all(sha(C/f)==h for f,h in source_hashes.items());j['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=rt,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),objects={f[:-2]+'.o':sha(out/(f[:-2]+'.o')) for f in files},managed_policy=managed));save()
 j.update(passed=True,state='terminal success',native_objects=20)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,native_objects=20)))
