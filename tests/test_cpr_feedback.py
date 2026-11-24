"""Run the real feedback shell trial with FIFO targets and simulated IRQ/results."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'diagnostics/cpu-cpr-runtime/feedback-600.sh'

class FeedbackTrialTests(unittest.TestCase):
 def run_case(self,mode='normal'):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);root=base/'root';binary=base/'bin';binary.mkdir();calls=[];stop=threading.Event()
   def put(name,text):
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
   put('etc/fx0-cpr-feedback-step','300-600\n');put('proc/sys/kernel/tainted','0\n');put('sys/devices/system/cpu/online','0-3\n')
   put('bin/cpr-register','#!/bin/sh\nexit '+('1' if mode=='registration' else '0')+'\n');(root/'bin/cpr-register').chmod(0o755)
   policy='sys/devices/system/cpu/cpufreq/policy0/'
   for key,value in [('scaling_governor','userspace'),('scaling_cur_freq','300000'),('scaling_max_freq','1190400'),('scaling_min_freq','300000')]:put(policy+key,value+'\n')
   put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 300000000\n');put('sys/kernel/debug/regulator/regulator_summary','mock vote observations\n');put('sys/class/thermal/thermal_zone0/temp','40000\n');(root/'tmp').mkdir()
   put('proc/interrupts','57: 0 0 0 0 GIC-0 47 Edge cpr\n')
   def observed(rate):
    put(policy+'scaling_cur_freq',str(rate)+'\n')
    put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 '+str((rate if mode!='clock' else 384000)*1000)+'\n')
    if rate==600000:
     apc=1100000;planned=1150000;ctl='0X20000429';irq=7
     if mode=='floor':apc=planned=1080000;ctl='0X20000469';irq=1
     if mode=='ceiling':apc=planned=1180000;ctl='0X2F000429';irq=1
     if mode in ['no_irq','unhandled_irq']:apc=planned=1150000;irq=0 if mode=='no_irq' else 1
     if mode=='low':apc=1070000
     if mode=='high':apc=1190000
     if mode=='grid':apc=1105000
     if mode=='loop':ctl='0X20000428'
     if mode=='storm':irq=20000
     if mode=='hot_after':put('sys/class/thermal/thermal_zone0/temp','60000\n')
    else:
     apc=planned=1080000;ctl='0X20000428';irq=7
     if mode=='return_voltage':apc=1150000
    cached=apc+10000 if mode=='cache' and rate==600000 else apc
    put('sys/kernel/debug/qcom_cpr/debug_info',f'corner, planned_volt = {planned} uV\ncorner, cached_volt = {cached} uV\ncorner_voltage_applied = 1\nfeedback_allowed = 1\napc_target = {apc} uV\nrbcpr_ctl = {ctl}\nrbcpr_result_0 = 0X0\n')
    put('proc/interrupts',f'57: {irq} 0 0 0 GIC-0 47 Edge cpr\n')
   if mode=='permit':put('etc/fx0-cpr-feedback-step','wrong')
   if mode=='governor':put(policy+'scaling_governor','schedutil\n')
   if mode=='taint':put('proc/sys/kernel/tainted','1\n')
   if mode=='online':put('sys/devices/system/cpu/online','0-2\n')
   if mode=='hot_before':put('sys/class/thermal/thermal_zone0/temp','60000\n')
   if mode=='irq_missing':put('proc/interrupts','57: 0 0 0 0 GIC-0 47 Edge other\n')
   fifo=root/(policy+'scaling_setspeed');os.mkfifo(fifo);fd=os.open(fifo,os.O_RDWR|os.O_NONBLOCK)
   def worker():
    buffer=b''
    while not stop.is_set():
     try:data=os.read(fd,1024)
     except BlockingIOError:time.sleep(0.001);continue
     buffer+=data
     while b'\n' in buffer:
      line,buffer=buffer.split(b'\n',1);rate=int(line);calls.append(rate)
      if mode!='stuck':observed(rate)
   thread=threading.Thread(target=worker);thread.start()
   (binary/'sleep').write_text('#!/bin/sh\nexec /usr/bin/sleep 0.001\n');(binary/'sleep').chmod(0o755)
   text=re.sub(r'/(?:sys|proc|etc|tmp)/|/bin/cpr-register\b',lambda m:str(root)+m.group(),SCRIPT.read_text());actual=base/'feedback.sh';actual.write_text(text)
   try:result=subprocess.run(['sh',str(actual)],env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH']),capture_output=True,text=True,timeout=15)
   finally:stop.set();thread.join(timeout=1);os.close(fd)
   return result,calls
 def test_voltage_adjustment_and_both_clamp_responses(self):
  for mode in ['normal','floor','ceiling']:
   with self.subTest(mode=mode):
    result,calls=self.run_case(mode);self.assertEqual(result.returncode,0,result.stderr);self.assertEqual(calls,[600000,300000]);self.assertIn('CPR_FEEDBACK_PASS',result.stdout);self.assertEqual(result.stdout.count('CPR_FEEDBACK_SAMPLE '),50)
 def test_irq_or_loop_enable_alone_is_not_a_feedback_pass(self):
  for mode in ['no_irq','unhandled_irq']:
   with self.subTest(mode=mode):
    result,calls=self.run_case(mode);self.assertEqual(result.returncode,2,result.stderr);self.assertEqual(calls,[600000,300000]);self.assertIn('CPR_FEEDBACK_INCONCLUSIVE',result.stdout);self.assertNotIn('CPR_FEEDBACK_PASS',result.stdout)
 def test_preflight_and_bad_observation_stop_further_requests(self):
  before=['permit','registration','governor','taint','online','hot_before','irq_missing']
  after=['stuck','low','high','grid','cache','clock','loop','storm','hot_after','return_voltage']
  for mode in before+after:
   with self.subTest(mode=mode):
    result,calls=self.run_case(mode);self.assertNotEqual(result.returncode,0);self.assertNotIn('CPR_FEEDBACK_PASS',result.stdout)
    self.assertEqual(calls,[] if mode in before else [600000,300000] if mode=='return_voltage' else [600000])
if __name__=='__main__':unittest.main()
