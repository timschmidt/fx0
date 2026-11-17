# SPDX-License-Identifier: GPL-2.0-only
"""Link an unsigned host-only maintained-LTS integration kernel and modules."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'unsigned-link-02';O.mkdir();(O/'tmp').mkdir()
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();seed=N/'native-01/arm-normal-CPU-enabled-system-on-out/.config';(O/'.config').write_bytes(seed.read_bytes())
j=dict(passed=False,state='prepared',started_UTC=datetime.now(timezone.utc).isoformat(),source_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip(),source_uncommitted=True,phone_access=False,published=False,installation=False,automatic_module_signing_disabled=True,module_verification_enabled=True,public_certificate_only=True,public_certificate_SHA256='585115a58829f235ff9904dd559de3cf37df07918578cabaf1b806435bd6c186',private_key_access_or_generation=False,normal_signed_APK_qualification=False,physical_acceptance=False,stages=[]);child=None
save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
env=os.environ|{'TMPDIR':str(O/'tmp'),'GIT_NO_LAZY_FETCH':'1','KBUILD_BUILD_USER':'fx0-review','KBUILD_BUILD_HOST':'source-check','KBUILD_BUILD_TIMESTAMP':'2026-11-17 00:00:00 UTC','KBUILD_BUILD_VERSION':'1'}
def run(label,args,timeout=1800):
 global child
 with (O/(label+'.log')).open('xb') as log:
  child=subprocess.Popen(args,cwd=C,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=timeout)
 j.pop('active_PID',None);j['stages'].append(dict(label=label,returncode=code,log_SHA256=sha(O/(label+'.log'))));save();assert code==0,label
try:
 options=['scripts/config','--file',str(O/'.config'),'--enable','MODULE_SIG','--disable','MODULE_SIG_ALL','--disable','MODULE_COMPRESS_ALL','--set-str','MODULE_SIG_KEY',str(N/'public-verification-certificate.pem'),'--set-str','SYSTEM_TRUSTED_KEYS','','--set-str','SYSTEM_REVOCATION_KEYS','','--disable','SYSTEM_EXTRA_CERTIFICATE']
 run('signing-disabled-options',options)
 make=['make','O='+str(O),'ARCH=arm','LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j4']
 run('config',make+['olddefconfig']);cfg=(O/'.config').read_text();assert 'CONFIG_MODULE_SIG=y\n' in cfg and '# CONFIG_MODULE_SIG_ALL is not set\n' in cfg and ('CONFIG_MODULE_SIG_KEY="'+str(N/'public-verification-certificate.pem')+'"\n') in cfg and 'CONFIG_SYSTEM_TRUSTED_KEYS=""\n' in cfg
 assert b'PRIVATE KEY' not in (N/'public-verification-certificate.pem').read_bytes()
 assert 'CONFIG_QCOM_MSM8226_PM=y\n' in cfg and 'CONFIG_QCOM_CPR_MSM8926=y\n' in cfg and 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg
 j.update(config_SHA256=sha(O/'.config'),source_files={p:sha(C/p) for p in json.loads((N/'native-current.json').read_text())['source_files']});save()
 run('vmlinux-and-modules',make+['vmlinux','modules'],3600)
 assert j['source_files']=={p:sha(C/p) for p in j['source_files']};mods=sorted(O.rglob('*.ko'));assert mods and (O/'vmlinux').is_file()
 j.update(passed=True,state='terminal success',vmlinux_SHA256=sha(O/'vmlinux'),raw_modules=len(mods),modules_SHA256={str(p.relative_to(O)):sha(p) for p in mods},private_signing_material_generated=False)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,raw_modules=len(mods),private_key_access=False)))
