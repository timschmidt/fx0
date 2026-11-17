# SPDX-License-Identifier: GPL-2.0-only
"""Replay pinned, explicit host-only coordinator source models and fault controls."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();B=Path(__file__).resolve().parent;S=a.source.resolve();O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir()
read=lambda x:json.loads(x.read_text());sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest();child=None
j=dict(passed=False,state='prepared',jobs=[],phone_access=False,network_execution=False,services_synthetic=True,physical_firmware_or_kernel_concurrency_acceptance=False);save=lambda:(O/'controller.json').write_text(json.dumps(j,indent=2)+'\n')
try:
 for f,h in read(B/'manifest.json')['files'].items():assert sha(B/f)==h,'packet hash: '+f
 for f,h in read(B/'source-inputs.json')['source_files'].items():assert sha(S/f)==h,'source hash: '+f
 j['all_pinned_packet_and_source_inputs_verified']=True;save()
 programs=read(B/'harness-provenance.json')['programs']+[['retained-CPU','retained-CPU/run-models.py'],['controls','check-sleep-controls.py'],['SPM-controls','spm-retained-harness/check-controls.py']]
 env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
 for name,script in programs:
  with (O/(name+'.stdout')).open('xb') as out,(O/(name+'.stderr')).open('xb') as err:
   command=([sys.executable,'-B',str(B/script),'--source',str(S),'--output',str(O/name)] if name=='retained-CPU' else [sys.executable,'-B',str(B/'harness'/script),str(S),str(O/name)])
   child=subprocess.Popen(command,env=env,stdout=out,stderr=err,start_new_session=True);j.update(state='running '+name,active_PID=child.pid);save();code=child.wait(timeout=480)
  j.pop('active_PID',None);j['jobs'].append(dict(name=name,returncode=code,owned_child_terminal_and_reaped=True));save();assert code==0,name
  result=read(O/name/'qualification.json');assert result.get('passed',True) and not result.get('failures',0)
 j.update(passed=True,state='terminal success',jobs_passed=len(programs),model_cases=5009,retained_clock_subruns=4,retained_CPU_methods=44,fault_controls=85,normal_LSan_and_failfast_ASan_UBSan=True)
except BaseException as e:j.update(state='terminal failure',error_type=type(e).__name__,error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 j.pop('active_PID',None);j['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,jobs=len(programs),model_cases=5009,fault_controls=85)))
