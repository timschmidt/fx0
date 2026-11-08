#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded four-core load/thermal observation; no frequency or trip changes."""
from pathlib import Path
import argparse,hashlib,json,multiprocessing as mp,os,signal,time
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();os.umask(0o077);a.output.mkdir(parents=True,exist_ok=False);out=a.output
policy=Path('/sys/devices/system/cpu/cpufreq/policy0');zones=sorted(Path('/sys/class/thermal').glob('thermal_zone*'))
assert Path('/sys/devices/system/cpu/online').read_text().strip()=='0-3'
assert Path('/proc/sys/kernel/tainted').read_text().strip()=='0'
assert len(zones)==2 and all(0<int((z/'temp').read_text())<60000 for z in zones)
config_keys=['scaling_governor','scaling_min_freq','scaling_max_freq']
config={k:(policy/k).read_text().strip() for k in config_keys};boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
def snapshot(phase):
 return {'phase':phase,'boottime':time.clock_gettime(time.CLOCK_BOOTTIME),'temperatures_mC':{(z/'type').read_text().strip():int((z/'temp').read_text()) for z in zones},'frequency_kHz':int((policy/'scaling_cur_freq').read_text()),'CPU_stat':[s for s in Path('/proc/stat').read_text().splitlines() if s.startswith(('cpu0 ','cpu1 ','cpu2 ','cpu3 '))],'idle':{str(p):p.read_text().strip() for p in Path('/sys/devices/system/cpu').glob('cpu[0-3]/cpuidle/state*/usage')}}
ctx=mp.get_context('fork');stop=ctx.Event();queue=ctx.Queue();workers=[];samples=[];interrupted=False
# Fixed byte sequence, verified against a separately computed host digest.
expected='fbbab289f7f94b25736c58be46a994c441fd02552cc6022352e3d86d2fab7c83'
def work(cpu):
 os.sched_setaffinity(0,{cpu});blob=bytes(range(256))*4096;n=0;start=time.process_time()
 try:
  while not stop.is_set():
   if hashlib.sha256(blob).hexdigest()!=expected:raise RuntimeError('Hash mismatch')
   n+=1
  queue.put({'cpu':cpu,'hashes':n,'bytes_per_hash':len(blob),'cpu_seconds':time.process_time()-start,'affinity':sorted(os.sched_getaffinity(0))})
 except BaseException as exc:queue.put({'cpu':cpu,'error':repr(exc)})
def interrupt(signum,frame):
 global interrupted
 interrupted=True;stop.set()
for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGHUP):signal.signal(sig,interrupt)
result={'status':'running','boot_id':boot,'original_policy':config,'temperature_stop_mC':65000,'samples':samples}
try:
 for phase,seconds in [('baseline',5),('load',30),('recovery',15)]:
  if phase=='load':
   for cpu in range(4):
    child=ctx.Process(target=work,args=(cpu,));child.start();workers.append(child)
  deadline=time.monotonic()+seconds;print('PHASE',phase,flush=True)
  while time.monotonic()<deadline and not interrupted:
   row=snapshot(phase);samples.append(row)
   if max(row['temperatures_mC'].values())>=65000:raise RuntimeError('Temperature stop reached')
   time.sleep(1)
  if phase=='load':
   stop.set()
   for child in workers:child.join(timeout=5)
  if interrupted:raise InterruptedError('Trial interrupted')
 result['workers']=[queue.get(timeout=5) for _ in workers]
 assert all(c.exitcode==0 for c in workers)
 assert len(result['workers'])==4 and all('error' not in r and r['hashes']>0 and r['affinity']==[r['cpu']] for r in result['workers'])
 result['status']='bounded load passed'
except BaseException as exc:
 result['status']='failed or interrupted';result['error']=repr(exc);raise
finally:
 stop.set()
 for child in workers:
  child.join(timeout=5)
  if child.is_alive():child.terminate();child.join(timeout=5)
 result['policy_after']={k:(policy/k).read_text().strip() for k in config_keys}
 result['policy_unchanged']=result['policy_after']==config
 result['taint_after']=int(Path('/proc/sys/kernel/tainted').read_text());result['boot_unchanged']=Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
 result['children_terminal']=all(not c.is_alive() for c in workers)
 (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['policy_unchanged'] and result['taint_after']==0 and result['boot_unchanged']
print('PASS bounded four-core load and recovery',flush=True)
