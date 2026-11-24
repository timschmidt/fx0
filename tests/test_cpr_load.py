"""Execute repeat/load shell control with instrumented points and real child cleanup."""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'diagnostics/cpu-cpr-runtime/load-600.sh'
SEQUENCE=[600000,300000]*6

class LoadTests(unittest.TestCase):
 def run_case(self,mode='normal'):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);root=base/'root';binary=base/'bin';binary.mkdir();calls=[];stop=threading.Event();trace=base/'worker-trace'
   def put(name,text):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   put('etc/fx0-cpr-load-step','600-repeat-load\n');put('proc/sys/kernel/tainted','0\n');put('sys/devices/system/cpu/online','0-3\n')
   put('bin/cpr-register','#!/bin/sh\nexit 0\n');(root/'bin/cpr-register').chmod(0o755)
   policy='sys/devices/system/cpu/cpufreq/policy0/'
   for key,value in [('scaling_governor','userspace'),('scaling_cur_freq','300000'),('scaling_max_freq','1190400'),('scaling_min_freq','300000')]:put(policy+key,value+'\n')
   put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 300000000\n');put('sys/kernel/debug/regulator/regulator_summary','mock votes\n')
   for n in range(2):put(f'sys/class/thermal/thermal_zone{n}/temp','40000\n')
   (root/'tmp').mkdir();put('proc/interrupts','57: 0 0 0 0 GIC-0 47 Edge cpr\n')
   def observed(rate):
    put(policy+'scaling_cur_freq',str(rate)+'\n');put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 '+str(rate*1000)+'\n')
    apc=1080000;ctl='0X20000469' if rate==600000 else '0X20000428'
    if mode=='later_voltage' and len(calls)>=5:apc=1190000
    if mode=='return_voltage' and rate==300000:apc=1150000
    if mode=='grid' and rate==600000:apc=1105000
    irq=1
    if mode=='no_feedback':irq=0;ctl='0X20000429' if rate==600000 else '0X20000428'
    put('sys/kernel/debug/qcom_cpr/debug_info',f'corner, planned_volt = 1080000 uV\ncorner, cached_volt = {apc} uV\ncorner_voltage_applied = 1\nfeedback_allowed = 1\napc_target = {apc} uV\nrbcpr_ctl = {ctl}\nrbcpr_result_0 = 0X2895\n')
    put('proc/interrupts',f'57: {irq} 0 0 0 GIC-0 47 Edge cpr\n')
   fixture=f'''#!{sys.executable}
import json,os,sys,time
from pathlib import Path
mode={mode!r};root=Path({str(root)!r});trace=Path({str(trace)!r})
if sys.argv[1]=='--digest':
 print({'0'*64 if mode=='worker_selfcheck' else 'fbbab289f7f94b25736c58be46a994c441fd02552cc6022352e3d86d2fab7c83'!r});sys.exit(0)
cpu=int(sys.argv[2]);fd=os.open(trace,os.O_WRONLY|os.O_CREAT|os.O_APPEND,0o600);os.write(fd,(json.dumps({{'cpu':cpu,'pid':os.getpid()}})+'\\n').encode());os.close(fd)
if cpu==0 and mode=='hot_load':(root/'sys/class/thermal/thermal_zone0/temp').write_text('60000\\n')
if cpu==0 and mode=='governor_load':(root/{policy+'scaling_governor'!r}).write_text('schedutil\\n')
if cpu==0 and mode=='worker_failure':print('checksum mismatch',flush=True);sys.exit(1)
if mode in ['worker_deadline','signal']:time.sleep(60)
time.sleep(0.15)
affinity=cpu+1 if mode=='worker_affinity' else cpu
cpu_ms=1 if mode=='worker_accounting' else 28000
wall_ms=36000 if mode=='worker_wall' else 30001
print(f'CPR_LOAD_WORKER cpu={{cpu}} hashes=100 bytes_per_hash=1048576 cpu_ms={{cpu_ms}} wall_ms={{wall_ms}} affinity={{affinity}}',flush=True)
'''
   put('bin/cpr-sha256',fixture);(root/'bin/cpr-sha256').chmod(0o755)
   digest=hashlib.sha256((root/'bin/cpr-sha256').read_bytes()).hexdigest()
   put('etc/fx0-cpr-load.sha256',('0'*64 if mode=='worker_sha' else digest)+'  '+str(root/'bin/cpr-sha256')+'\n')
   if mode=='permit':put('etc/fx0-cpr-load-step','wrong')
   if mode=='missing_thermal':(root/'sys/class/thermal/thermal_zone1/temp').unlink()
   fifo=root/(policy+'scaling_setspeed');os.mkfifo(fifo);fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK)
   def worker():
    buffer=b''
    while not stop.is_set():
     try:data=os.read(fd,1024)
     except BlockingIOError:time.sleep(0.001);continue
     buffer+=data
     while b'\n' in buffer:
      line,buffer=buffer.split(b'\n',1);rate=int(line);calls.append(rate);observed(rate)
   thread=threading.Thread(target=worker);thread.start()
   (binary/'sleep').write_text('#!/bin/sh\nexec /usr/bin/sleep 0.002\n');(binary/'sleep').chmod(0o755)
   text=re.sub(r'/(?:sys|proc|etc|tmp)/|/bin/cpr-(?:register|sha256)\b',lambda m:str(root)+m.group(),SCRIPT.read_text());actual=base/'load.sh';actual.write_text(text)
   process=subprocess.Popen(['sh',str(actual)],env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH']),stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
   try:
    if mode=='signal':
     deadline=time.monotonic()+20
     while time.monotonic()<deadline:
      if trace.exists() and len(trace.read_text().splitlines())==4:break
      if process.poll() is not None:break
      time.sleep(0.01)
     self.assertIsNone(process.poll(),'controller must be live with four workers before termination');process.send_signal(signal.SIGTERM)
    stdout,stderr=process.communicate(timeout=25)
   finally:
    if process.poll() is None:process.kill();process.wait()
    stop.set();thread.join(timeout=1);os.close(fd)
   children=[json.loads(line) for line in trace.read_text().splitlines()] if trace.exists() else []
   for child in children:
    with self.assertRaises(ProcessLookupError,msg='worker survived controller exit'):os.kill(child['pid'],0)
   return subprocess.CompletedProcess([],process.returncode,stdout,stderr),calls,children
 def test_full_repeat_load_and_terminal_workers_before_return(self):
  result,calls,children=self.run_case();self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(calls,SEQUENCE);self.assertEqual(sorted(c['cpu'] for c in children),[0,1,2,3])
  self.assertIn('CPR_LOAD_PASS:',result.stdout);self.assertEqual(len(re.findall(r'^CPR_LOAD_WORKER ',result.stdout,re.M)),4)
  self.assertLess(result.stdout.index('__CPR_LOAD_WORKERS_TERMINAL__'),result.stdout.rindex('__CPR_LOAD_REQUEST__300000'))
 def test_preflight_worker_and_thermal_mismatches_prevent_requests(self):
  for mode in ['permit','worker_sha','worker_selfcheck','missing_thermal']:
   with self.subTest(mode=mode):
    result,calls,children=self.run_case(mode);self.assertNotEqual(result.returncode,0);self.assertEqual(calls,[]);self.assertEqual(children,[])
 def test_failed_point_stops_later_transitions(self):
  for mode,expected in [('grid',[600000]),('return_voltage',SEQUENCE[:2]),('later_voltage',SEQUENCE[:5])]:
   with self.subTest(mode=mode):
    result,calls,children=self.run_case(mode);self.assertNotEqual(result.returncode,0);self.assertEqual(calls,expected);self.assertEqual(children,[])
 def test_load_errors_stop_all_workers_without_a_return_request(self):
  for mode in ['hot_load','governor_load','worker_failure','worker_affinity','worker_accounting','worker_wall','worker_deadline']:
   with self.subTest(mode=mode):
    result,calls,children=self.run_case(mode);self.assertNotEqual(result.returncode,0);self.assertNotIn('CPR_LOAD_PASS:',result.stdout);self.assertEqual(calls,SEQUENCE[:-1]);self.assertTrue(children)
 def test_missing_feedback_is_inconclusive_after_valid_return(self):
  result,calls,children=self.run_case('no_feedback');self.assertEqual(result.returncode,2,result.stderr);self.assertEqual(calls,SEQUENCE);self.assertIn('CPR_LOAD_INCONCLUSIVE:',result.stdout)
 def test_termination_stops_live_workers_without_return_request(self):
  result,calls,children=self.run_case('signal');self.assertNotEqual(result.returncode,0);self.assertEqual(calls,SEQUENCE[:-1]);self.assertEqual(len(children),4);self.assertNotIn('CPR_LOAD_PASS:',result.stdout)
if __name__=='__main__':unittest.main()
