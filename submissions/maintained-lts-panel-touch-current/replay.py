#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Re-extract selected panel/touch host models from verified source snapshots."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);a=parser.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();H=P/'harness';C=P/'source';resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'};commands=[]
for label,path,broken in [('before',P/'before/rmi_i2c.c',16),('after',C/'drivers/input/rmi4/rmi_i2c.c',0),('runtime-suspend',P/'mutants/rmi_i2c_runtime_suspend.c',16),('runtime-resume',P/'mutants/rmi_i2c_runtime_resume.c',12)]:commands.append(('touch-'+label,[H/'check-touch.py',path,label,C/'drivers/input/rmi4/rmi_driver.c',O],O/('panel-'+label)/'result.json',broken,O/('panel-'+label)/'fixture.c'))
for label,path,broken in [('before',P/'before/panel-lg-fx0.c',8),('after',C/'drivers/gpu/drm/panel/panel-lg-fx0.c',0),('missing-cleanup-retry',P/'mutants/missing-cleanup-retry.c',3),('hidden-unprepare-error',P/'mutants/hidden-unprepare-error.c',5)]:commands.append(('panel-'+label,[H/'check-power-references.py','--kernel',C,'--driver',path,'--expected-broken',str(broken),'--extended','--output',O/('power-'+label)],O/('power-'+label)/'qualification.json',broken,O/('power-'+label)/'fixture.c'))
commands.append(('commands',[H/'check-command-trace.py','--kernel',C,'--driver',C/'drivers/gpu/drm/panel/panel-lg-fx0.c','--baseline',P/'before/panel-lg-fx0.c','--vendor-common',P/'vendor-source/msm8226-lge-panel.dtsi','--vendor-board',P/'vendor-source/msm8226-madai-panel.dtsi','--output',O/'commands'],O/'commands/qualification.json',None,O/'commands/candidate.c'))
expected=json.loads((P/'expected-fixtures.json').read_text());j=dict(passed=False,manifest_verified=True,source_head=manifest['source_head'],stages=[],phone_access=False,real_hardware_or_full_kernel_driver_core_execution=False,normal_LSan_and_failfast_ASan_UBSan=True);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n');child=None
try:
 for label,args,result,broken,fixture in commands:
  with (O/(label+'.stdout')).open('xb') as out,(O/(label+'.stderr')).open('xb') as err:
   child=subprocess.Popen([sys.executable,'-B',*map(str,args)],cwd=H,env=env,stdout=out,stderr=err,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=180)
  assert code==0 and not (O/(label+'.stderr')).read_bytes(),label;r=json.loads(result.read_text());assert (r['broken']==broken) if broken is not None else r['passed'];assert sha(fixture)==expected[label],label;j['stages'].append(dict(label=label,returncode=code,generated_fixture_matches_qualified_bytes=True));save()
 assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success');print(json.dumps(dict(passed=True,suites=len(commands),all_generated_fixtures_match=True)))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
