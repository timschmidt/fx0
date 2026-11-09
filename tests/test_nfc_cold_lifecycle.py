"""Execute the actual cold lifecycle shell with simulated module/sysfs callbacks."""
import hashlib
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import threading
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/'diagnostics/nfc-startup/cold-lifecycle.sh'
FAKE=r'''#!/usr/bin/env python3
import json,os,shutil,sys,time
from pathlib import Path
r=Path(os.environ['TEST_ROOT']);fault=os.environ.get('TEST_FAULT','');calls=r/'tmp/calls';verb=Path(sys.argv[0]).name;name=Path(sys.argv[1]).name
with calls.open('a') as f:f.write(verb+' '+name+'\n')
if verb=='insmod' and ('unsigned' in name or 'badsig' in name):
 if fault==('accept_unsigned' if 'unsigned' in name else 'accept_badsig'):raise SystemExit(0)
 print('Invalid module format' if fault=='rejection_reason' else 'Key was rejected by service',file=sys.stderr);raise SystemExit(1)
name=name.removesuffix('.ko').replace('-','_')
if fault=='hang_load' and verb=='insmod' and name=='rfkill':time.sleep(1);raise SystemExit(1)
if fault=='load_error' and verb=='insmod' and name=='nci':raise SystemExit(1)
if fault=='unload_error' and verb=='rmmod' and name=='nxp_nci_i2c':raise SystemExit(1)
if fault=='silent_load' and verb=='insmod' and name=='nci':raise SystemExit(0)
if fault=='silent_unload' and verb=='rmmod' and name=='nxp_nci_i2c':raise SystemExit(0)
mods=(r/'proc/modules').read_text().splitlines();mods=[line for line in mods if line.split()[0]!=name]
if verb=='insmod':
 (r/'sys/module'/name).mkdir(exist_ok=True)
 mods.append(name+' 1234 0 - Live 0x0')
else:shutil.rmtree(r/'sys/module'/name)
if fault=='extra_module' and verb=='insmod' and name=='nci':mods.append('surprise 1234 0 - Live 0x0')
if fault=='module_not_live' and verb=='insmod' and name=='nci':mods=[line.replace(' Live ',' Loading ') for line in mods]
(r/'proc/modules').write_text('\n'.join(mods)+ ('\n' if mods else ''))
if verb=='insmod' and name=='nfc' and fault in ['post_taint','post_temperature','post_policy','post_online','post_mount','post_CPR','post_signature','post_governor','post_uptime']:
 paths={'post_taint':('proc/sys/kernel/tainted','4096\n'),'post_temperature':('sys/class/thermal/thermal_zone1/temp','60000\n'),'post_online':('sys/devices/system/cpu/online','0-2\n'),'post_mount':('proc/mounts','UUID=block /mnt ext4 ro 0 0\n'),'post_signature':('sys/module/module/parameters/sig_enforce','N\n'),'post_governor':('sys/module/cpufreq/parameters/default_governor','userspace\n'),'post_uptime':('proc/uptime','1100.0 0.0\n')}
 if fault in paths:
  target=r/paths[fault][0]
  if fault=='post_uptime':
   temporary=target.with_name('uptime-update');temporary.write_text(paths[fault][1]);os.replace(temporary,target)
  else:target.write_text(paths[fault][1])
 if fault=='post_policy':(r/'sys/devices/system/cpu/cpufreq/policy0').mkdir(parents=True)
 if fault=='post_CPR':p=r/'sys/kernel/debug/qcom_cpr/debug_info';p.parent.mkdir(parents=True);p.write_text('unexpected')
if name=='nxp_nci_i2c':
 # The same state helper is used for a completed module callback and FIFO bind callbacks.
 sys.path.insert(0,str(r/'tmp'));from model import binding
 binding(r,verb=='insmod',fault)
'''
MODEL=r'''
from pathlib import Path
import shutil

def binding(r,on,fault):
 client=r/'sys/bus/i2c/devices/1-0028';driver=r/'sys/bus/i2c/drivers/nxp-nci_i2c';classes=r/'sys/class/nfc';classes.mkdir(parents=True,exist_ok=True)
 link=client/'driver';node=client/'nfc/nfc0';classlink=classes/'nfc0';rf=r/'sys/class/rfkill/rfkill0'
 if on:
  node.mkdir(parents=True,exist_ok=True)
  if not link.exists():link.symlink_to(driver)
  if not classlink.exists():classlink.symlink_to(node)
  rf.mkdir(parents=True,exist_ok=True)
  for name,data in [('type','nfc\n'),('soft','0\n'),('hard','0\n')]: (rf/name).write_text(data)
  if not (rf/'device').exists():(rf/'device').symlink_to(node)
  if fault=='class_parent':classlink.unlink();classlink.symlink_to(driver)
  if fault=='rfkill_parent':(rf/'device').unlink();(rf/'device').symlink_to(driver)
  if fault=='missing_class':classlink.unlink()
  pins=''.join(f'pin {n} (GPIO_{n}): device 1-0028 function gpio group gpio{n}\n' for n in [20,21,22])
  irq=' 220: 0 0 0 0 msmgpio 21 Edge nxp-nci_i2c\n'
  if fault=='IRQ_storm':irq=irq.replace('0 0 0 0','9 0 0 0')
  if fault=='IRQ_missing':irq=''
  if fault=='owner':pins=pins.replace('device 1-0028','device another-client')
 else:
  if link.is_symlink():link.unlink()
  if classlink.is_symlink():classlink.unlink()
  if rf.exists():shutil.rmtree(rf)
  if node.parent.exists():shutil.rmtree(node.parent)
  pins=''.join(f'pin {n} (GPIO_{n}): UNCLAIMED\n' for n in [20,21,22]);irq=''
  if fault=='unbind_owner':pins=pins.replace('pin 21 (GPIO_21): UNCLAIMED','pin 21 (GPIO_21): GPIO stale-owner')
  if fault=='unbind_IRQ':irq=' 220: 0 0 0 0 msmgpio 21 Edge nxp-nci_i2c\n'
 (r/'sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins').write_text(pins)
 (r/'proc/interrupts').write_text(irq)
 gpio=' gpio20 : out low func0 2mA no pull\n gpio21 : in low func0 8mA pull down\n gpio22 : out low func0 8mA no pull\n'
 if fault=='GPIO_high' or (not on and fault=='unbind_GPIO'):gpio=gpio.replace('gpio20 : out low','gpio20 : out high')
 if fault=='GPIO_drive':gpio=gpio.replace('gpio22 : out low func0 8mA','gpio22 : out low func0 2mA')
 if fault=='IRQ_pin':gpio=gpio.replace('gpio21 : in low','gpio21 : out low')
 (r/'sys/kernel/debug/gpio').write_text(gpio)
 clock=' cxo_d1_pin 0 0 0 19200000\n'
 if fault=='clock_vote':clock=' cxo_d1_pin 1 1 0 19200000\n'
 (r/'sys/kernel/debug/clk/clk_summary').write_text(clock)
'''

class ColdLifecycleTests(unittest.TestCase):
 def run_case(self,fault=None):
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);r=base/'root';binary=base/'bin';binary.mkdir()
   def put(name,value):
    p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(value if isinstance(value,bytes) else value.encode());return p
   put('etc/fx0-nfc-trial','alpine-r58-moduleless-startup\n');put('etc/fx0-nfc-lifecycle','alpine-r58-cold-lifecycle\n')
   notes=put('sys/kernel/notes',b'kernel fixture');put('etc/fx0-nfc-notes.sha256',hashlib.sha256(notes.read_bytes()).hexdigest()+'\n')
   put('proc/cmdline','module.sig_enforce=1 cpufreq.default_governor=schedutil\n');put('proc/modules','');put('proc/sys/kernel/tainted','0\n');put('proc/sys/kernel/random/boot_id','fixture-boot\n');put('proc/mounts','rootfs / rootfs rw 0 0\n');put('proc/uptime','1000.0 0.0\n');put('proc/interrupts','')
   put('sys/module/module/parameters/sig_enforce','Y\n');put('sys/module/cpufreq/parameters/default_governor','schedutil\n');put('sys/devices/system/cpu/online','0-3\n')
   for n in range(2):put(f'sys/class/thermal/thermal_zone{n}/temp','40000\n')
   node=r/'sys/firmware/devicetree/base/soc/i2c@f9925000/nfc@28';put(str(node.relative_to(r)/'compatible'),b'nxp,pn547\0nxp,nxp-nci-i2c\0');put(str(node.parent.relative_to(r)/'status'),b'okay\0')
   client=r/'sys/bus/i2c/devices/1-0028';client.mkdir(parents=True);(client/'of_node').symlink_to(node)
   put('sys/kernel/debug/clk/clk_summary',' cxo_d1_pin 0 0 0 19200000\n');put('sys/kernel/debug/gpio',' gpio20 : in low func0 2mA pull down\n gpio21 : in high func0 2mA pull up\n gpio22 : in low func0 2mA pull down\n');put('sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins',''.join(f'pin {n} (GPIO_{n}): UNCLAIMED\n' for n in [20,21,22]))
   names=['rfkill-unsigned','rfkill-badsig','rfkill','nfc','nci','nxp-nci','nxp-nci_i2c']
   for name in names:put('modules/'+name+'.ko','fixture '+name)
   put('etc/fx0-nfc-modules.sha256',''.join(hashlib.sha256((r/'modules'/str(name+'.ko')).read_bytes()).hexdigest()+'  modules/'+name+'.ko\n' for name in names))
   check=put('bin/nfc-startup-check','#!/bin/sh\nexec sh '+str(ROOT/'diagnostics/nfc-startup/check-teardown-startup.sh')+'\n');check.chmod(0o755)
   model=put('tmp/model.py',MODEL)
   for name in ['insmod','rmmod']:
    p=binary/name;p.write_text(FAKE);p.chmod(0o755)
   (binary/'uname').write_text('#!/bin/sh\necho "${TEST_UNAME:-6.18.59-fx0-nfc-teardown-alpine}"\n');(binary/'uname').chmod(0o755)
   (binary/'sleep').write_text('#!/bin/sh\nexec /usr/bin/sleep 0.02\n');(binary/'sleep').chmod(0o755)
   for name in ['modprobe','i2cdetect','i2cget','i2cset','gpioset','rfkill']:
    p=binary/name;p.write_text('#!/bin/sh\necho forbidden >> "$TEST_ROOT/tmp/forbidden"\nexit 99\n');p.chmod(0o755)
   env=dict(os.environ,PATH=str(binary)+os.pathsep+os.environ['PATH'],TEST_ROOT=str(r),FX0_NFC_TEST_ROOT=str(r),TEST_FAULT=fault or '',PYTHONDONTWRITEBYTECODE='1')
   if fault=='permit':put('etc/fx0-nfc-lifecycle','wrong\n')
   if fault=='kernel':env['TEST_UNAME']='6.18.59-fx0-nfc-alpine'
   if fault=='notes':notes.write_bytes(b'wrong')
   if fault=='signature':put('sys/module/module/parameters/sig_enforce','N\n')
   if fault=='modules':put('proc/modules','other 1 0 - Live 0\n')
   if fault=='digest':put('modules/rfkill.ko','changed')
   if fault=='temperature':put('sys/class/thermal/thermal_zone0/temp','60000\n')
   if fault=='uptime':put('proc/uptime','invalid\n')
   driver=r/'sys/bus/i2c/drivers/nxp-nci_i2c';driver.mkdir(parents=True);fds={};stop=threading.Event();errors=[]
   import importlib.util
   spec=importlib.util.spec_from_file_location('fixture_model',model);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   for operation in ['bind','unbind']:
    p=driver/operation
    if fault==operation+'_error':p.symlink_to('/dev/full')
    else:os.mkfifo(p);fds[os.open(p,os.O_RDWR|os.O_NONBLOCK)]=operation
   def serve():
    try:
     while not stop.is_set():
      ready,_,_=select.select(list(fds),[],[],0.02)
      for fd in ready:
       data=os.read(fd,4096)
       if not data:continue
       self.assertEqual(data,b'1-0028\n')
       operation=fds[fd]
       with (r/'tmp/calls').open('a') as out:out.write(operation+' 1-0028\n')
       m.binding(r,operation=='bind',fault or '')
    except BaseException as error:errors.append(error)
   thread=threading.Thread(target=serve);thread.start()
   try:p=subprocess.run(['sh',str(SCRIPT)],env=env,capture_output=True,text=True,timeout=15)
   finally:stop.set();thread.join(timeout=2);[os.close(fd) for fd in fds]
   self.assertFalse(thread.is_alive());self.assertEqual(errors,[])
   calls=(r/'tmp/calls').read_text().splitlines() if (r/'tmp/calls').exists() else []
   self.assertFalse((r/'tmp/forbidden').exists())
   return p,calls,(r/'proc/modules').read_text()

 def test_three_cold_bind_rounds_and_reverse_cleanup(self):
  p,calls,mods=self.run_case();self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(mods,'')
  expected=['insmod rfkill-unsigned.ko','insmod rfkill-badsig.ko']+['insmod '+name+'.ko' for name in ['rfkill','nfc','nci','nxp-nci','nxp-nci_i2c']]+['unbind 1-0028','bind 1-0028']*3+['rmmod '+name for name in ['nxp_nci_i2c','nxp_nci','nci','nfc','rfkill']]
  self.assertEqual(calls,expected);self.assertIn('NFC_COLD_LIFECYCLE_PASS',p.stdout)
  self.assertEqual(p.stdout.count('__NFC_SIGNATURE_REJECTED__'),2)
  self.assertEqual(p.stdout.count('__NFC_COLD_SNAPSHOT__'),12)

 def test_bootstrap_faults_reach_no_module_operations(self):
  for fault in ['permit','kernel','notes','signature','modules','digest','temperature','uptime']:
   with self.subTest(fault=fault):
    p,calls,_=self.run_case(fault);self.assertNotEqual(p.returncode,0);self.assertEqual(calls,[]);self.assertNotIn('NFC_COLD_LIFECYCLE_PASS',p.stdout)

 def assert_fault(self,fault):
  p,calls,_=self.run_case(fault);self.assertNotEqual(p.returncode,0,p.stdout);self.assertNotIn('NFC_COLD_LIFECYCLE_PASS',p.stdout)
  if fault=='hang_load':self.assertIn('operation load-rfkill did not terminate',p.stderr)
  if fault=='post_uptime':self.assertIn('overall deadline',p.stderr)
  if fault=='rejection_reason':self.assertIn('rejection was not a key error',p.stderr)
  if fault in ['hang_load','load_error','silent_load','extra_module','module_not_live'] or fault.startswith('post_'):
   self.assertFalse(any(line.startswith(('bind ','unbind ','rmmod ')) for line in calls),calls)
  if fault in ['unbind_owner','unbind_IRQ','unbind_GPIO','unbind_error']:
   self.assertFalse(any(line.startswith(('bind ','rmmod ')) for line in calls),calls)
  if fault=='bind_error':self.assertFalse(any(line.startswith('rmmod ') for line in calls),calls)

 def test_rejection_registration_and_cleanup_faults_stop(self):
  faults=['accept_unsigned','accept_badsig','rejection_reason','hang_load','load_error','silent_load','extra_module','module_not_live','post_taint','post_temperature','post_policy','post_online','post_mount','post_CPR','post_signature','post_governor','post_uptime','class_parent','rfkill_parent','missing_class','owner','IRQ_missing','IRQ_storm','GPIO_high','GPIO_drive','IRQ_pin','clock_vote','unbind_error','unbind_owner','unbind_IRQ','unbind_GPIO','bind_error','unload_error','silent_unload']
  for fault in faults:
   with self.subTest(fault=fault):self.assert_fault(fault)

if __name__=='__main__':unittest.main()
