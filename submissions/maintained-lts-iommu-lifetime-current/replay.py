#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay only the source-extracted IOMMU lifetime service model."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'};expected=json.loads((P/'expected-fixtures.json').read_text());j=dict(passed=False,stages=[],manifest_verified=True,source_head=manifest['source_head'],normal_LSan_and_failfast_ASan_UBSan=True,phone_access=False,real_hardware_or_full_driver_core_execution=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n');child=None
try:
 for label,driver,wrong,cases in [('before',P/'before-qcom_iommu.c',24,30),('after',P/'source/drivers/iommu/arm/arm-smmu/qcom_iommu.c',0,36),('manual-probe-PM',P/'mutants/manual-probe-PM.c',15,30),('early-parent-clear',P/'mutants/early-parent-clear.c',9,36),('children-before-clients',P/'mutants/children-before-clients.c',9,36)]:
  args=[sys.executable,'-B',str(P/'check-lifetime.py'),'--kernel',str(P/'source'),'--driver',str(driver),'--output',str(O/label),'--expected-wrong',str(wrong)]
  with (O/(label+'.stdout')).open('xb') as out,(O/(label+'.stderr')).open('xb') as err:
   child=subprocess.Popen(args,env=env,stdout=out,stderr=err,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=120)
  assert code==0 and not (O/(label+'.stderr')).read_bytes(),label;result=json.loads((O/label/'qualification.json').read_text());assert result['cases']==cases and result['wrong']==wrong;assert sha(O/label/'model.c')==expected[label],label;j['stages'].append(dict(label=label,returncode=code,generated_fixture_matches_qualified_bytes=True));save()
 assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success');print(json.dumps(dict(passed=True,suites=5,all_generated_fixtures_match=True)))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
