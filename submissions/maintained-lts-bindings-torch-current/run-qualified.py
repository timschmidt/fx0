# SPDX-License-Identifier: GPL-2.0-only
"""Replay the selected torch before/after and deliberate regression fixtures."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();B=Path(__file__).resolve().parent;S=a.source.resolve();O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir();child=None
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();j=dict(passed=False,state='prepared',jobs=[],phone_access=False,network_execution=False,all_device_services_synthetic=True,hardware_acceptance=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for f,d in read(B/'manifest.json')['files'].items():assert sha(B/f)==d,'packet hash: '+f
 for f,d in read(B/'source-current.json')['source_files'].items():assert sha(S/f)==d,'source hash: '+f
 jobs=[('before',[sys.executable,'-B',str(B/'harness/check-torch-errors.py'),'--source',str(B/'baseline'),'--output',str(O/'before'),'--expect','broken']),('after',[sys.executable,'-B',str(B/'harness/check-torch-errors.py'),'--source',str(S),'--output',str(O/'after'),'--expect','fixed']),('controls',[sys.executable,'-B',str(B/'harness/check-controls.py'),str(S),str(O/'controls')])]
 env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1'}
 for name,args in jobs:
  with (O/(name+'.stdout')).open('xb') as out,(O/(name+'.stderr')).open('xb') as err:
   child=subprocess.Popen(args,env=env,stdout=out,stderr=err,start_new_session=True);j.update(state='running '+name,active_PID=child.pid);save();code=child.wait(timeout=180)
  j.pop('active_PID',None);j['jobs'].append(dict(name=name,returncode=code));save();assert code==0,name
 assert read(O/'before/controller.json')['result']['off_wrong']==5 and read(O/'after/controller.json')['result']['off_wrong']==0 and len(read(O/'controls/qualification.json')['controls'])==2
 j.update(passed=True,state='terminal success',jobs_passed=3,normal_LSan_and_failfast_ASan_UBSan=True)
except BaseException as e:j.update(state='terminal failure',error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,jobs=3)))
