# SPDX-License-Identifier: GPL-2.0-only
"""Own a bounded UML KUnit run containing only IIO formatter tests."""
from pathlib import Path
import hashlib,json,os,signal,subprocess,sys
N=Path(__file__).resolve().parent;R=N.parents[2];C=R/'worktrees/linux-fx0-lts-integration-current-01';O=N/'UML-02';O.mkdir();(O/'tmp').mkdir();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();j=dict(passed=False,state='prepared',source_files={f:sha(C/f) for f in ['drivers/iio/industrialio-core.c','drivers/iio/test/iio-test-format.c']},UML=True,phone_access=False,physical_devices=False);child=None;save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n');cmd=[sys.executable,'-B','tools/testing/kunit/kunit.py','run','--kunitconfig='+str(N/'format.kunitconfig'),'--build_dir='+str(N/'UML-01/out'),'--make_options=LLVM=-21','--make_options=W=1','--jobs=2','--timeout=90','--json='+str(O/'results.json'),'iio-format'];env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','GIT_NO_LAZY_FETCH':'1','KBUILD_BUILD_USER':'fx0-review','KBUILD_BUILD_HOST':'source-check','KBUILD_BUILD_TIMESTAMP':'2026-11-17 00:00:00 UTC'};env.pop('KBUILD_SIGN_PIN',None)
try:
 with (O/'run.log').open('xb') as log:
  child=subprocess.Popen(cmd,cwd=C,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);j.update(state='running bounded UML build and iio-format run',active_PID=child.pid);save();code=child.wait(timeout=900)
 j.update(returncode=code,log_SHA256=sha(O/'run.log'));assert code==0;cfg=(N/'UML-01/out/.config').read_text();assert 'CONFIG_IIO_FORMAT_KUNIT_TEST=y\n' in cfg and 'CONFIG_KUNIT=y\n' in cfg and 'CONFIG_NET=y\n' not in cfg and 'CONFIG_MODULES=y\n' not in cfg and 'CONFIG_MODULE_SIG=y\n' not in cfg and 'CONFIG_SYSTEM_TRUSTED_KEYRING=y\n' not in cfg;assert not (N/'UML-01/out/certs/signing_key.pem').exists();assert all(sha(C/f)==h for f,h in j['source_files'].items());j.update(passed=True,state='terminal success',config_SHA256=sha(N/'UML-01/out/.config'),results_SHA256=sha(O/'results.json'),private_key_or_network_configuration_used=False)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=j['passed'],UML=True)))
