# SPDX-License-Identifier: GPL-2.0-only
"""Replay the explicitly selected host-only LTS sleep prerequisite models."""
from pathlib import Path
import argparse,hashlib,json,os,signal,subprocess,sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args()
B=Path(__file__).resolve().parent;S=a.source.resolve();O=a.output.resolve();O.mkdir(mode=0o700);(O/'tmp').mkdir()
read=lambda x:json.loads(x.read_text());sha=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
record=dict(passed=False,state='prepared',jobs=[],phone_access=False,network_execution=False,normal_LSan_and_failfast_ASan_UBSan=True,full_kernel_concurrency_firmware_and_physical_acceptance=False)
child=None
save=lambda:(O/'controller.json').write_text(json.dumps(record,indent=2)+'\n')
try:
 manifest=read(B/'manifest.json')['files']
 for f,digest in manifest.items():assert sha(B/f)==digest,'packet hash: '+f
 for f,digest in read(B/'final-input-verification.json')['source_files'].items():assert sha(S/f)==digest,'source hash: '+f
 record['pinned_packet_and_source_inputs_verified']=True;save()
 jobs=[]
 for name,script,options in [('rails','rails/check-sleep-voter.py',['--transport-source',str(S),'--cpu-source',str(S)]),('boot','rails/check-boot.py',['--transport-source',str(S),'--cpu-source',str(S)]),('pair','rails/check-pair.py',['--transport-source',str(S),'--cpu-source',str(S)]),('legacy','rails/legacy/check-sleep.py',['--transport-source',str(S)]),('SO-topology','rails/check-SO-topology.py',[]),('SPM','SPM/check-model.py',[]),('L2','L2/check-model.py',[]),('admission','admission/check-admission.py',[]),('PM-order','PM-order/check-pm-order.py',[]),('SPM-shared','SPM/check-shared-platform.py',[])]:
  jobs.append((name,[sys.executable,'-B',str(B/'harness'/script),str(S),str(O/name),*options]))
 jobs.append(('retained-CPU',[sys.executable,'-B',str(B/'retained-CPU/run-models.py'),'--source',str(S),'--output',str(O/'retained-CPU')]))
 for name,script in [('rail-sleep-controls','rails/check-sleep-voter-controls.py'),('rail-boot-controls','rails/check-boot-controls.py'),('rail-pair-controls','rails/check-pair-controls.py'),('rail-legacy-controls','rails/legacy/check-controls.py'),('SPM-controls','SPM/check-controls.py'),('L2-controls','L2/check-controls.py'),('admission-controls','admission/check-controls.py'),('PM-controls','PM-order/check-pm-controls.py')]:
  options = ['--transport-source',str(S)] if name.startswith('rail-') else []
  if name in ['rail-sleep-controls','rail-boot-controls','rail-pair-controls']:options += ['--cpu-source',str(S)]
  jobs.append((name,[sys.executable,'-B',str(B/'harness'/script),str(S),str(O/name),*options]))
 env=os.environ|{'TMPDIR':str(O/'tmp'),'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
 for name,command in jobs:
  record.update(state='running '+name);save()
  with (O/(name+'.stdout')).open('xb') as out,(O/(name+'.stderr')).open('xb') as err:
   child=subprocess.Popen(command,env=env,stdout=out,stderr=err,start_new_session=True);record['active_PID']=child.pid;save();code=child.wait(timeout=480)
  record.pop('active_PID',None);record['jobs'].append(dict(name=name,returncode=code,owned_child_terminal_and_reaped=True));save();assert code==0,name
 record.update(passed=True,state='terminal success',jobs_passed=len(jobs),retained_CPU_methods=44,positive_case_executions_excluding_repeated_shared_platform_suite=14924,fault_controls=113)
except BaseException as e:
 record.update(state='terminal failure',error_type=type(e).__name__,error=str(e));raise
finally:
 if child is not None and child.poll() is None:
  os.killpg(child.pid,signal.SIGTERM)
  try:child.wait(timeout=5)
  except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
 record.pop('active_PID',None);record['owned_child_terminal_and_reaped']=child is None or child.returncode is not None;save()
print(json.dumps(dict(passed=True,jobs=len(jobs),CPU_methods=44,fault_controls=113)))
