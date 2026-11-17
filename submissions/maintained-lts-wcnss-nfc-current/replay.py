#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay pinned WCNSS/NFC C only against synthetic services; no real devices."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'};expected=json.loads((P/'expected-fixtures.json').read_text());j=dict(passed=False,state='prepared',stages=[],manifest_verified_before_execution=True,source_head=manifest['source_head'],normal_LSan_and_failfast_ASan_UBSan=True,phone_access=False,real_hardware_execution=False);child=None;save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
tasks=[('lifecycle-before',[P/'harness/nfc/check-nfc-lifecycle.py',P/'before',O/'lifecycle-before','--baseline'],{}),('lifecycle-after',[P/'harness/nfc/check-nfc-lifecycle.py',P/'source',O/'lifecycle-after'],{}),('clock',[P/'harness/nfc/check-nfc-clock.py',P/'source',O/'clock'],{}),('controls',[P/'harness/nfc/check-nfc-controls.py'],{'FX0_NFC_REMOVE_SOURCE':str(P/'source'),'FX0_NFC_REMOVE_OUTPUT':str(O/'controls'),'CC':'clang-21'}),('regulators',[P/'harness/wcnss/check-regulators.py','--source',P/'source','--output',O/'regulators','--expect','fixed'],{}),('regulator-regression',[P/'harness/wcnss/check-regulators.py','--source',P/'regulator-regression','--output',O/'regulator-regression','--expect','broken'],{}),('RF',[P/'check-RF.py','--source',P/'source','--output',O/'RF'],{})]
try:
 for label,args,extra in tasks:
  with (O/(label+'.stdout')).open('xb') as stdout,(O/(label+'.stderr')).open('xb') as stderr:
   child=subprocess.Popen([sys.executable,'-B',*map(str,args)],env=env|extra,stdout=stdout,stderr=stderr,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=120)
  assert code==0,label
  if label=='controls':assert 'Ran 6 tests' in (O/(label+'.stderr')).read_text() and 'OK' in (O/(label+'.stderr')).read_text()
  else:assert not (O/(label+'.stderr')).read_bytes(),label
  j['stages'].append(dict(label=label,returncode=code));save()
 for f,want in expected.items():assert sha(O/f)==want,f
 before=json.loads((O/'lifecycle-before/verification.json').read_text());after=json.loads((O/'lifecycle-after/verification.json').read_text());assert (before['modeled_cases'],before['failures'],after['modeled_cases'],after['failures'])==(9,9,10,0)
 assert json.loads((O/'regulators/controller.json').read_text())['result']==dict(cases=8,correct=8,wrong=0,error_controls=16);assert json.loads((O/'regulator-regression/controller.json').read_text())['result']['wrong']==6;assert json.loads((O/'clock/verification.json').read_text())['positive_cases']==9;assert json.loads((O/'controls/verification.json').read_text())['independent_regression_controls']==6
 assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success',suites=7,qualified_fixtures=len(expected),all_generated_fixtures_match=True);print(json.dumps(dict(passed=True,suites=7,qualified_fixtures=len(expected))))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
