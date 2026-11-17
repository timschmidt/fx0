#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay only source-extracted IOMMU, MMCC and DSI host models."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',required=True,type=Path);a=parser.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();H=P/'harness';C=P/'source';resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1','FX0_KERNEL_SOURCE':str(C),'FX0_IOMMU_SOURCE':str(C/'drivers/iommu/arm/arm-smmu/qcom_iommu.c')};commands=[]
for label,path,wrong in [('before',P/'before-qcom_iommu.c',23),('after',C/'drivers/iommu/arm/arm-smmu/qcom_iommu.c',0),('missing-table-release',P/'mutants/missing-table-release.c',12),('partial-context-programming',P/'mutants/partial-context-programming.c',8),('missing-clock-rollback',P/'mutants/missing-clock-rollback.c',3)]:commands.append((label,[H/'check-errors.py',path,O/label,'--expected-wrong',str(wrong)],O/label/'model.c'))
commands += [('clock',[H/'check-clock.py','--source',C,'--output',O/'clock','--expect-mnd','fixed','--expect-axi','fixed'],O/'clock/fixture.c'),('halt',[H/'check-halt.py','--source',C,'--output',O/'halt'],O/'halt/candidate.c'),('probe',[H/'test-probe.py','-v'],None)]
for label,mutation in [('DSI',None),('DSI-unconditional','unconditional'),('DSI-lane-value','lane-value')]:
 args=[H/'DSI/check-phy.py',C/'drivers/gpu/drm/msm/dsi/phy/dsi_phy_28nm.c',P/'before-DSI-lane.c',P/'vendor-source/msm8226-mdss.dtsi',O/label]
 if mutation:args+=['--mutation',mutation]
 commands.append((label,args,O/label/'model.c'))
expected=json.loads((P/'expected-fixtures.json').read_text());j=dict(passed=False,source_head=manifest['source_head'],stages=[],manifest_verified=True,normal_LSan_and_failfast_ASan_UBSan=True,phone_access=False,real_hardware_or_full_kernel_driver_core_execution=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n');child=None
try:
 for label,args,fixture in commands:
  with (O/(label+'.stdout')).open('xb') as out,(O/(label+'.stderr')).open('xb') as err:
   child=subprocess.Popen([sys.executable,'-B',*map(str,args)],cwd=H,env=env,stdout=out,stderr=err,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=180)
  assert code==0,label
  if label=='probe':assert 'Ran 5 tests' in (O/(label+'.stderr')).read_text() and 'OK' in (O/(label+'.stderr')).read_text()
  else:assert not (O/(label+'.stderr')).read_bytes()
  if fixture is not None:assert sha(fixture)==expected[label],label
  if label.startswith('DSI'):
   r=json.loads((O/label/'qualification.json').read_text());assert r['cases']==192 and r['failures']==(0 if label=='DSI' else 144)
  j['stages'].append(dict(label=label,returncode=code,generated_fixture_matches_qualified_bytes=fixture is not None));save()
 assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success');print(json.dumps(dict(passed=True,suites=len(commands),generated_fixtures_verified=10)))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
