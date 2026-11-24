"""Exercise the actual first-step shell control with FIFO-backed target writes."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'diagnostics/cpu-cpr-runtime/first-step.sh'

class FirstStepTests(unittest.TestCase):
 def run_case(self,fault=None):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);root=base/'root';binary=base/'bin';binary.mkdir();calls=[];stop=threading.Event()
   def put(name,text):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   put('etc/fx0-cpr-first-step','300-384\n');put('proc/sys/kernel/tainted','0\n')
   put('bin/cpr-register','#!/bin/sh\nexit '+('1' if fault=='registration' else '0')+'\n');(root/'bin/cpr-register').chmod(0o755)
   policy='sys/devices/system/cpu/cpufreq/policy0/'
   for key,value in [('scaling_governor','userspace'),('scaling_cur_freq','300000'),('scaling_max_freq','1190400'),('scaling_min_freq','300000')]:put(policy+key,value+'\n')
   put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 300000000\n')
   put('sys/kernel/debug/regulator/regulator_summary','mock regulator observations\n');put('sys/class/thermal/thermal_zone0/temp','40000\n');(root/'tmp').mkdir()
   def observed(rate):
    put(policy+'scaling_cur_freq',str(rate)+'\n')
    put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 '+str((rate if fault!='clock' else 600000)*1000)+'\n')
    text='corner, cached_volt = 1080000 uV\ncorner_voltage_applied = 1\nfeedback_allowed = 1\napc_target = '+('1150000' if fault=='voltage' else '1080000')+' uV\nrbcpr_ctl = '+('0X20000429' if fault=='loop' else '0X20000428')+'\n'
    put('sys/kernel/debug/qcom_cpr/debug_info',text)
    if fault=='taint':put('proc/sys/kernel/tainted','1\n')
   observed(300000)
   if fault=='permit':put('etc/fx0-cpr-first-step','wrong')
   if fault=='governor':put(policy+'scaling_governor','schedutil\n')
   fifo=root/(policy+'scaling_setspeed');os.mkfifo(fifo)
   # Keep one read/write descriptor open so each script write is one line.
   fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK)
   def worker():
    buffer=b''
    while not stop.is_set():
     try:data=os.read(fd,1024)
     except BlockingIOError:time.sleep(0.001);continue
     buffer+=data
     while b'\n' in buffer:
      line,buffer=buffer.split(b'\n',1);rate=int(line);calls.append(rate)
      if fault=='stuck':continue
      observed(rate)
   thread=threading.Thread(target=worker);thread.start()
   (binary/'sleep').write_text('#!/bin/sh\nexec /usr/bin/sleep 0.005\n');(binary/'sleep').chmod(0o755)
   text=SCRIPT.read_text();text=re.sub(r'/(?:sys|proc|etc|tmp)/|/bin/cpr-register\b',lambda m:str(root)+m.group(),text)
   actual=base/'first.sh';actual.write_text(text)
   try:result=subprocess.run(['sh',str(actual)],env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH']),capture_output=True,text=True,timeout=8)
   finally:stop.set();thread.join(timeout=1);os.close(fd)
   return result,calls,(root/(policy+'scaling_max_freq')).read_text(),(root/(policy+'scaling_min_freq')).read_text()
 def test_exact_first_corner_requests_and_hold(self):
  result,calls,maximum,minimum=self.run_case();self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(calls,[384000,300000]);self.assertEqual(maximum,'384000\n');self.assertEqual(minimum,'300000\n');self.assertIn('CPR_FIRST_STEP_PASS',result.stdout)
 def test_refuses_bad_setup_and_stops_on_bad_observation(self):
  for fault in ['permit','registration','governor','stuck','voltage','clock','loop','taint']:
   with self.subTest(fault=fault):
    result,calls,maximum,minimum=self.run_case(fault);self.assertNotEqual(result.returncode,0);self.assertNotIn('CPR_FIRST_STEP_PASS',result.stdout)
    self.assertEqual(calls,[] if fault in ['permit','registration','governor'] else [384000])
if __name__=='__main__':unittest.main()
