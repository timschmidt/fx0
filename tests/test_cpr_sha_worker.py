"""Check the real checksum worker against hashlib and process-lifecycle controls."""
import hashlib
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'diagnostics/cpu-cpr-runtime/sha256-worker.c'

class WorkerTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temporary=tempfile.TemporaryDirectory();cls.base=Path(cls.temporary.name)
  cls.production=cls.base/'production';cls.short=cls.base/'short';cls.corrupt=cls.base/'corrupt'
  flags=['clang','-std=gnu11','-O2','-Wall','-Wextra','-Werror','-fsanitize=undefined','-fno-sanitize-recover=undefined']
  for output,extra,source in [(cls.production,[],SOURCE),(cls.short,['-DFX0_LOAD_SECONDS=1'],SOURCE)]:
   subprocess.run([*flags,*extra,str(source),'-o',str(output)],check=True,capture_output=True)
  changed=cls.base/'corrupt.c';changed.write_text(SOURCE.read_text().replace('fbbab289f7f94b25','0bbab289f7f94b25'))
  subprocess.run([*flags,str(changed),'-o',str(cls.corrupt)],check=True,capture_output=True)
 @classmethod
 def tearDownClass(cls):cls.temporary.cleanup()
 def test_digest_matches_independent_oracle_across_padding_boundaries(self):
  for size in [0,1,55,56,63,64,65,119,120,127,128,129,4096,1048575,1048576]:
   with self.subTest(size=size):
    expected=hashlib.sha256((bytes(range(256))*4096)[:size]).hexdigest()
    result=subprocess.run([str(self.production),'--digest',str(size)],capture_output=True,text=True,check=True)
    self.assertEqual(result.stdout,expected+'\n');self.assertEqual(result.stderr,'')
 def test_argument_and_unavailable_affinity_rejections(self):
  for args in [[],['--worker'],['--unknown','0'],['--digest','-1'],['--digest','1048577'],['--digest','1x'],['--worker','1024'],['--worker','-1']]:
   with self.subTest(args=args):
    result=subprocess.run([str(self.production),*args],capture_output=True,text=True)
    self.assertEqual(result.returncode,2);self.assertNotIn('CPR_LOAD_WORKER',result.stdout)
  result=subprocess.run([str(self.production),'--worker','1023'],capture_output=True,text=True)
  self.assertNotEqual(result.returncode,0);self.assertNotIn('CPR_LOAD_WORKER',result.stdout)
 def test_bounded_worker_reports_actual_affinity_and_CPU_accounting(self):
  cpu=min(os.sched_getaffinity(0))
  result=subprocess.run([str(self.short),'--worker',str(cpu)],capture_output=True,text=True,check=True,timeout=10)
  match=re.fullmatch(r'CPR_LOAD_WORKER cpu=(\d+) hashes=(\d+) bytes_per_hash=(\d+) cpu_ms=(\d+) wall_ms=(\d+) affinity=(\d+)\n',result.stdout)
  self.assertIsNotNone(match,result.stdout)
  actual,hashes,size,cpu_ms,wall_ms,affinity=map(int,match.groups())
  self.assertEqual((actual,size,affinity),(cpu,1048576,cpu));self.assertGreater(hashes,0)
  self.assertGreater(cpu_ms,0);self.assertGreaterEqual(wall_ms,1000);self.assertLess(wall_ms,5000);self.assertLessEqual(cpu_ms,wall_ms+10)
 def test_wrong_checksum_and_termination_cannot_report_success(self):
  cpu=min(os.sched_getaffinity(0))
  result=subprocess.run([str(self.corrupt),'--worker',str(cpu)],capture_output=True,text=True,timeout=5)
  self.assertEqual(result.returncode,1);self.assertIn('checksum mismatch',result.stderr);self.assertNotIn('CPR_LOAD_WORKER',result.stdout)
  process=subprocess.Popen([str(self.production),'--worker',str(cpu)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   time.sleep(0.05);self.assertIsNone(process.poll());process.send_signal(signal.SIGTERM);stdout,stderr=process.communicate(timeout=5)
   self.assertEqual(process.returncode,-signal.SIGTERM);self.assertNotIn('CPR_LOAD_WORKER',stdout)
  finally:
   if process.poll() is None:process.kill();process.wait()
if __name__=='__main__':unittest.main()
