# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib,json,os,signal,subprocess
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'unsigned-link-02';P=N/'unsigned-relink-01';P.mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();prior=json.loads((O/'controller.json').read_text());assert prior['passed']
files={p:sha(C/p) for p in prior['source_files']};cfg=(O/'.config').read_text();assert '# CONFIG_MODULE_SIG_ALL is not set\n' in cfg and ('CONFIG_MODULE_SIG_KEY="'+str(N/'public-verification-certificate.pem')+'"\n') in cfg
j=dict(passed=False,state='prepared',source_files=files,config_SHA256=sha(O/'.config'),original_full_build_passed=True,automatic_signing_disabled=True,public_certificate_only=True,private_key_access_or_generation=False,normal_release_specific_APK_qualified=False,physical_acceptance=False,phone_access=False);child=None;save=lambda:(P/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 with (P/'relink.log').open('xb') as log:
  child=subprocess.Popen(['make','O='+str(O),'ARCH=arm','LLVM=-21','W=1','KCFLAGS=-Werror=incompatible-function-pointer-types','-j4','vmlinux','modules'],cwd=C,env=os.environ|{'TMPDIR':str(O/'tmp'),'GIT_NO_LAZY_FETCH':'1','KBUILD_BUILD_USER':'fx0-review','KBUILD_BUILD_HOST':'source-check','KBUILD_BUILD_TIMESTAMP':'2026-11-17 00:00:00 UTC','KBUILD_BUILD_VERSION':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running relink',active_PID=child.pid);save();code=child.wait(timeout=900)
 assert code==0;assert files=={p:sha(C/p) for p in files};mods=sorted(O.rglob('*.ko'));assert len(mods)==prior['raw_modules']==447
 assert all(not p.read_bytes().endswith(b'~Module signature appended~\n') for p in mods)
 assert not (O/'certs/signing_key.pem').exists();assert sha(O/'.config')==j['config_SHA256']
 j.update(passed=True,state='terminal success',returncode=code,vmlinux_SHA256=sha(O/'vmlinux'),raw_modules=len(mods),module_hashes={str(p.relative_to(O)):sha(p) for p in mods},all_modules_unsigned=True,no_development_key_or_generated_private_key_in_owned_output=True,kernel_release=(O/'include/config/kernel.release').read_text().strip(),log_SHA256=sha(P/'relink.log'))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,raw_modules=447,private_key_access=False)))
