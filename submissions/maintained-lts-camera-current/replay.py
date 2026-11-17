#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay only pinned camera C against synthetic services, with no Git/device use."""
from pathlib import Path
import argparse,hashlib,json,os,resource,signal,subprocess,sys
P=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args();sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();manifest=json.loads((P/'manifest.json').read_text());assert all(sha(P/f)==h for f,h in manifest['files'].items());O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();resource.setrlimit(resource.RLIMIT_CORE,(0,0));env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'};spec=json.loads((P/'replay-spec.json').read_text());j=dict(passed=False,state='prepared',stages=[],manifest_verified_before_execution=True,source_head=manifest['source_head'],normal_LSan_and_failfast_ASan_UBSan=True,physical_acceptance=False,phone_access=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n');child=None
try:
 for task in spec['models']:
  label=task['name'];root=P/task['source'];out=O/label;kind=task['kind'];script=P/('harness/'+kind+'/check-'+('callbacks' if kind=='sensors' else 'dma' if kind=='DMA' else 'geometry')+'.py');cmd=[sys.executable,'-B',str(script)]
  if kind=='sensors':cmd+=['--kernel',str(root),'--driver',str(P/task['driver']),'--sensor',task['sensor'],'--output',str(out),'--expected-broken',str(task['result'])]
  else:
   cmd.append(str(root))
   if kind=='geometry':cmd.append(str(P/'vendor'))
   cmd.append(str(out))
   if task.get('mutation'):cmd+=['--mutation',task['mutation']]
  with (O/(label+'.stdout')).open('xb') as stdout,(O/(label+'.stderr')).open('xb') as stderr:
   child=subprocess.Popen(cmd,env=env,stdout=stdout,stderr=stderr,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=120)
  assert code==0 and not (O/(label+'.stderr')).read_bytes(),label;d=json.loads((out/'qualification.json').read_text());assert d['broken' if kind=='sensors' else 'failures']==task['result'] and d['cases' if kind=='sensors' else 'checks']==task['checks'],label;assert sha(out/('fixture.c' if kind=='sensors' else 'model.c'))==task['fixture_SHA256'],label;j['stages'].append(dict(label=label,returncode=0,generated_fixture_matches_qualified_bytes=True));save()
 label='completion';cmd=[sys.executable,'-B',str(P/'check-completion.py'),'--kernel',str(P/'source'),'--templates',str(P/'templates'),'--output',str(O/label)]
 with (O/(label+'.stdout')).open('xb') as stdout,(O/(label+'.stderr')).open('xb') as stderr:
  child=subprocess.Popen(cmd,env=env,stdout=stdout,stderr=stderr,start_new_session=True);j.update(state='running '+label,active_PID=child.pid);save();code=child.wait(timeout=120)
 assert code==0 and not (O/(label+'.stderr')).read_bytes();d=json.loads((O/label/'qualification.json').read_text());assert d['passed'] and len(d['records'])==12
 for row,want in zip(d['records'],spec['completion']):assert row==want,(row,want)
 j['stages'].append(dict(label=label,returncode=0,generated_fixtures_matching_qualified_bytes=12));assert all(sha(P/f)==h for f,h in manifest['files'].items());j.update(passed=True,state='terminal success',suites=22,qualified_fixtures=33);print(json.dumps(dict(passed=True,suites=22,qualified_fixtures=33)))
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
