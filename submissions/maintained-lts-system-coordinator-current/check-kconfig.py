# SPDX-License-Identifier: GPL-2.0-only
"""Evaluate coordinator availability using the actual maintained-LTS Kconfig."""
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'Kconfig-04';O.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rows=[];child=None
cases=[('ARM-all-enabled','arm',False,{},True),('ARM-default-off','arm',False,{'QCOM_MSM8226_PM':'unset'},False),('ARM64-rejected','arm64',False,{},False),('ARM64-RT-rejected','arm64',True,{},False)]
for symbol in ['SMP','HOTPLUG_CPU','SUSPEND','CPU_PM','QCOM_CPR_MSM8926','QCOM_CPR','QCOM_SPM','QCOM_SMD_RPM','RPMSG_QCOM_SMD','QCOM_MPM']:
 cases.append(('without-'+symbol,'arm',False,{symbol:'n'},False))
for symbol in ['QCOM_CPR','QCOM_SPM','QCOM_SMD_RPM','RPMSG_QCOM_SMD','QCOM_MPM']:
 cases.append(('module-'+symbol,'arm',False,{symbol:'m'},False))
for value in ['n','m']:cases.append(('SCM-arch-forces-y-from-'+value,'arm',False,{'QCOM_SCM':value},True))
for label,arch,rt,changes,expected in cases:
 if label in ['without-QCOM_SPM','module-QCOM_SPM']:changes['ARM_QCOM_SPM_CPUIDLE']='n'
cases=cases[10:]
controller=dict(passed=False,state='prepared',actual_LTS_Kconfig=True,ARM32_RT_not_requested_or_counted=True,records=rows,phone_access=False);save=lambda:(O/'qualification.json').write_text(json.dumps(controller,indent=2)+'\n')
try:
 for label,arch,rt,changes,expected in cases:
  out=O/(label+'-out');out.mkdir();(out/'tmp').mkdir()
  if arch=='arm':seed=N/'native-01/arm-normal-CPU-enabled-system-on-out/.config'
  else:seed=N/'native-02/arm64-rt-CPU-enabled-system-off-out/.config' if rt else N/'native-01/arm64-normal-CPU-enabled-system-off-out/.config'
  text='\n'.join(l for l in seed.read_text().splitlines() if not l.startswith(('CONFIG_QCOM_MSM8226_PM=','# CONFIG_QCOM_MSM8226_PM ')))+'\n';(out/'.config').write_text(text)
  args=['scripts/config','--file',str(out/'.config')]
  if changes.get('QCOM_MSM8226_PM')!='unset':args+=['--enable','QCOM_MSM8226_PM']
  for sym,val in changes.items():
   if val!='unset':args+=['--enable' if val=='y' else '--module' if val=='m' else '--disable',sym]
  if len(args)>3:subprocess.run(args,cwd=C,check=True)
  with (O/(label+'.log')).open('xb') as log:
   child=subprocess.Popen(['make','O='+str(out),'ARCH='+arch,'LLVM=-21','-j2','olddefconfig'],cwd=C,env=os.environ|{'TMPDIR':str(out/'tmp')},stdout=log,stderr=subprocess.STDOUT,start_new_session=True);controller.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=180)
  assert code==0;cfg=(out/'.config').read_text();enabled='CONFIG_QCOM_MSM8226_PM=y\n' in cfg;actual={}
  for sym in changes:
   actual[sym]=next((l.split('=',1)[1] for l in cfg.splitlines() if l.startswith('CONFIG_'+sym+'=')),'n')
  assert enabled==expected,(label,actual,enabled)
  for sym,val in changes.items():
   if val!='unset':assert actual[sym]==('y' if sym in ['QCOM_SCM','HOTPLUG_CPU','CPU_PM'] else val),(label,sym,actual[sym])
  assert ('CONFIG_PREEMPT_RT=y\n' in cfg)==rt
  diagnostics=[l for l in (O/(label+'.log')).read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()];assert not diagnostics
  rows.append(dict(label=label,ARCH=arch,PREEMPT_RT=rt,requested=changes,actual=actual,coordinator_enabled=enabled,config_SHA256=sha(out/'.config'),diagnostics=[]));save()
 controller.update(passed=True,state='terminal success',cases=len(rows))
except BaseException as e:controller.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 controller.pop('active_PID',None);controller['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,cases=len(rows))))
