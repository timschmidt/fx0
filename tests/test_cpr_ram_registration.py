"""Run the real RAM registration shell script against instrumented fake sysfs."""
import hashlib
import os
import re
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'diagnostics/cpu-cpr-runtime/register.sh'

class RamRegistrationTests(unittest.TestCase):
 def run_case(self,fault=None):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);system=base/'root';binary=base/'bin';binary.mkdir()
   def put(name,value):
    p=system/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(value)
   put('etc/fx0-cpr-trial','registration-only\n')
   put('sys/module/module/parameters/sig_enforce','Y\n')
   put('sys/module/cpufreq/parameters/default_governor','userspace\n')
   put('proc/modules','');put('proc/sys/kernel/tainted','0\n');(system/'tmp').mkdir()
   put('sys/kernel/debug/qcom_cpr/debug_info','corner_voltage_applied = 0\nfeedback_allowed = 0\napc_target = 1150000 uV\nrbcpr_ctl = 0X20000428\n')
   put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 300000000\n')
   put('modules/cpufreq_userspace.ko','fake userspace module');put('modules/cpufreq-dt.ko','fake driver module')
   put('etc/fx0-cpr-modules.sha256',''.join(hashlib.sha256((system/'modules'/name).read_bytes()).hexdigest()+'  '+str(system/'modules'/name)+'\n' for name in ['cpufreq_userspace.ko','cpufreq-dt.ko']))
   (binary/'uname').write_text('#!/bin/sh\nprintf "%s\\n" "${TEST_UNAME:-6.18.59-fx0-cpr-observe}"\n');(binary/'uname').chmod(0o755)
   (binary/'insmod').write_text('''#!/usr/bin/env python3
import os,sys
from pathlib import Path
root=Path(os.environ['TEST_ROOT']);name=Path(sys.argv[1]).name
with Path(os.environ['TEST_CALLS']).open('a') as out:out.write(name+'\\n')
if name==os.environ.get('TEST_INSMOD_FAIL'):raise SystemExit(1)
module='cpufreq_userspace' if 'userspace' in name else 'cpufreq_dt'
(root/'sys/module'/module).mkdir(parents=True)
if module=='cpufreq_dt':
 p=root/'sys/devices/system/cpu/cpufreq/policy0';p.mkdir(parents=True)
 for n,v in [('scaling_governor',os.environ.get('TEST_GOVERNOR','userspace')+'\\n'),('scaling_cur_freq','300000\\n'),('scaling_available_frequencies','300000 384000 600000 787200 998400 1094400 1190400 \\n')]:
  (p/n).write_text(v)
 if os.environ.get('TEST_POST_APPLIED'):
  f=root/'sys/kernel/debug/qcom_cpr/debug_info';f.write_text(f.read_text().replace('corner_voltage_applied = 0','corner_voltage_applied = 1'))
''');(binary/'insmod').chmod(0o755)
   env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],TEST_ROOT=str(system),TEST_CALLS=str(base/'calls'))
   if fault=='kernel':env['TEST_UNAME']='6.18.59-fx0-dmp'
   if fault=='marker':put('etc/fx0-cpr-trial','wrong')
   if fault=='signature':put('sys/module/module/parameters/sig_enforce','N\n')
   if fault=='default':put('sys/module/cpufreq/parameters/default_governor','schedutil\n')
   if fault=='modules':put('proc/modules','already_loaded 1 0 - Live 0x0\n')
   if fault=='digest':put('modules/cpufreq-dt.ko','changed')
   if fault=='target':
    f=system/'sys/kernel/debug/qcom_cpr/debug_info';f.write_text(f.read_text().replace('1150000','1080000'))
   if fault=='control':
    f=system/'sys/kernel/debug/qcom_cpr/debug_info';f.write_text(f.read_text().replace('rbcpr_ctl = 0X20000428\n',''))
   if fault=='clock':put('sys/kernel/debug/clk/clk_summary',' a53mux@f9011000 1 1 0 800000000\n')
   if fault=='userspace_load':env['TEST_INSMOD_FAIL']='cpufreq_userspace.ko'
   if fault=='driver_load':env['TEST_INSMOD_FAIL']='cpufreq-dt.ko'
   if fault=='fallback':env['TEST_GOVERNOR']='schedutil'
   if fault=='post_applied':env['TEST_POST_APPLIED']='1'
   text=SCRIPT.read_text()
   # Rewrite only filesystem roots; run the real shell control flow and tools.
   text=re.sub(r'/(?:sys|proc|etc|modules|tmp)/',lambda match:str(system)+match.group(),text)
   actual=base/'register.sh';actual.write_text(text)
   result=subprocess.run(['sh',str(actual)],env=env,capture_output=True,text=True,timeout=10)
   calls=(base/'calls').read_text().splitlines() if (base/'calls').exists() else []
   return result,calls
 def test_registration_and_preflight_failures(self):
  result,calls=self.run_case();self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual(calls,['cpufreq_userspace.ko','cpufreq-dt.ko']);self.assertIn('CPR_REGISTRATION_PASS',result.stdout)
  for fault in ['kernel','marker','signature','default','modules','digest','target','control','clock']:
   with self.subTest(fault=fault):
    result,calls=self.run_case(fault);self.assertNotEqual(result.returncode,0);self.assertEqual(calls,[])
 def test_load_failure_and_post_registration_rejection(self):
  for fault,expected in [('userspace_load',['cpufreq_userspace.ko']),('driver_load',['cpufreq_userspace.ko','cpufreq-dt.ko']),('fallback',['cpufreq_userspace.ko','cpufreq-dt.ko']),('post_applied',['cpufreq_userspace.ko','cpufreq-dt.ko'])]:
   with self.subTest(fault=fault):
    result,calls=self.run_case(fault);self.assertNotEqual(result.returncode,0);self.assertEqual(calls,expected);self.assertNotIn('CPR_REGISTRATION_PASS',result.stdout)
if __name__=='__main__':unittest.main()
