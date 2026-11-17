# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'native-01';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();objects=['drivers/nfc/nxp-nci/'+x+'.o' for x in ['core','firmware','i2c']]+['net/nfc/nci/'+x+'.o' for x in ['core','data','lib','ntf','rsp','hci']]+['drivers/remoteproc/qcom_wcnss.o','drivers/remoteproc/qcom_wcnss_iris.o','drivers/soc/qcom/wcnss_ctrl.o']+['drivers/net/wireless/ath/wcn36xx/'+x+'.o' for x in ['main','dxe','txrx','smd','pmc','debug','firmware','testmode']];assert len(objects)==20;source_files=[p[:-2]+'.c' for p in objects];hashes={f:sha(C/f) for f in source_files};child=None;j=dict(passed=False,state='prepared',source_files=hashes,profiles=[],stages=[],ARM32_RT_unsupported_not_counted=True,phone_access=False,wireless_or_NFC_execution=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for arch,rt,mode,acpi,seed in [('arm',False,'y',False,'native-01/arm-normal-CPU-enabled-system-on-out'),('arm64',False,'m',False,'native-01/arm64-normal-CPU-enabled-system-off-out'),('arm64',True,'m',True,'native-02/arm64-rt-CPU-enabled-system-off-out')]:
  label=arch+('-rt' if rt else '-normal')+'-NFC-WCNSS-'+mode;out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir();(out/'.config').write_bytes((N.parent/'system-coordinator-01'/seed/'.config').read_bytes());env=os.environ|{'TMPDIR':str(out/'tmp'),'GIT_NO_LAZY_FETCH':'1'};args=['scripts/config','--file',str(out/'.config'),'--enable','EXPERT','--disable','COMPILE_TEST','--enable','MODULES']
  for sym in ['NET','NETDEVICES','WIRELESS','WLAN','WLAN_VENDOR_ATH','RFKILL','I2C','REGULATOR','GPIOLIB','REMOTEPROC','ARCH_QCOM','RPMSG','QCOM_SMEM','RPMSG_QCOM_SMD','DEBUG_FS','WCN36XX_DEBUGFS','NL80211_TESTMODE']:
   args+=['--enable',sym]
  for sym in ['NFC','NFC_NCI','NFC_NXP_NCI','NFC_NXP_NCI_I2C','QCOM_WCNSS_PIL','QCOM_WCNSS_CTRL','CFG80211','MAC80211','WCN36XX']:args+=['--enable' if mode=='y' else '--module',sym]
  args+=['--enable' if acpi else '--disable','ACPI']
  if acpi:args+=['--enable','PCI','--enable','EFI']
  subprocess.run(args,cwd=C,check=True);make=['make','O='+str(out),'ARCH='+arch,'LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j2']
  for phase,targets in [('config',['olddefconfig']),('objects',objects)]:
   log=O/(label+'-'+phase+'.log')
   with log.open('xb') as stream:
    child=subprocess.Popen(make+targets,cwd=C,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label+' '+phase,active_PID=child.pid);save();code=child.wait(timeout=600)
   diagnostics=[l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];j['stages'].append(dict(profile=label,phase=phase,returncode=code,diagnostics=diagnostics,log_SHA256=sha(log)));save();assert code==0 and not diagnostics,diagnostics
  cfg=(out/'.config').read_text();assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt and ('CONFIG_ACPI=y\n' in cfg)==acpi and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg and '# CONFIG_COMPILE_TEST is not set\n' in cfg
  for sym in ['NFC','NFC_NCI','NFC_NXP_NCI','NFC_NXP_NCI_I2C','QCOM_WCNSS_PIL','QCOM_WCNSS_CTRL','CFG80211','MAC80211','WCN36XX']:assert 'CONFIG_'+sym+'='+mode+'\n' in cfg,(sym,mode)
  assert 'CONFIG_NL80211_TESTMODE=y\n' in cfg and 'CONFIG_WCN36XX_DEBUGFS=y\n' in cfg;assert all(sha(C/f)==h for f,h in hashes.items());j['profiles'].append(dict(profile=label,ARCH=arch,PREEMPT_RT=rt,ACPI=acpi,mode=mode,CFI=True,CFI_PERMISSIVE=False,config_SHA256=sha(out/'.config'),objects={f:sha(out/f) for f in objects}));save()
 j.update(passed=True,state='terminal success',native_objects=60)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,native_objects=60)))
