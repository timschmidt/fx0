"""Run the controller shell with the real cold fixtures and modeled NCI callbacks."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('cold_fixtures',ROOT/'tests/test_nfc_cold_lifecycle.py');cold=importlib.util.module_from_spec(spec);spec.loader.exec_module(cold)
SCRIPT=ROOT/'diagnostics/nfc-startup/controller-startup.sh'
WORKER=r'''#!/usr/bin/env python3
import json,os,sys,time
from pathlib import Path
r=Path(os.environ['TEST_ROOT']);fault=os.environ.get('TEST_FAULT','');action=sys.argv[1];index=int(sys.argv[2]);state=r/'tmp/controller-powered';before=int(state.read_text()) if state.exists() else 0
with (r/'tmp/controller-calls').open('a') as out:out.write(action+' '+str(index)+'\n')
if action not in ['get','up','down']:raise SystemExit(99)
if fault=='up_hang' and action=='up':time.sleep(1.5);raise SystemExit(1)
if fault in ['up_error','down_error'] and action==fault.split('_')[0]:print('{"ok":false}');raise SystemExit(1)
after=before
if action in ['up','down']:
 after=int(action=='up');state.write_text(str(after))
 (r/'sys/kernel/debug/clk/clk_summary').write_text(' cxo_d1_pin '+str(after)+' '+str(after)+' 0 19200000\n')
 (r/'sys/kernel/debug/gpio').write_text(' gpio20 : out '+('high' if after else 'low')+' func0 2mA no pull\n gpio21 : in low func0 8mA pull down\n gpio22 : out low func0 8mA no pull\n')
 irq=3 if after else 4
 (r/'proc/interrupts').write_text(f' 70: {irq} 0 0 0 msmgpio 21 Edge nxp-nci_i2c\n')
 log=r/'tmp/NCI-dmesg'
 with log.open('a') as out:
  out.write('[ 8.0] nci: nci_core_reset_rsp_packet: status 0x0\n')
  if after:
   out.write('[ 8.1] nci: nci_core_reset_rsp_packet: nci_ver 0x10, config_status 0x0\n[ 8.2] nci: nci_core_init_rsp_packet_v1: status 0x0\n[ 8.3] nci: nci_rf_disc_map_rsp_packet: status 0x0\n[ 8.4] nci: nci_core_init_rsp_packet: manufact_id 0x4\n[ 8.5] nci: nci_core_init_rsp_packet: manufact_specific_info 0x12345678\n')
 if after and fault=='active_clock':(r/'sys/kernel/debug/clk/clk_summary').write_text(' cxo_d1_pin 0 0 0 19200000\n')
 if after and fault=='active_GPIO':
  p=r/'sys/kernel/debug/gpio';p.write_text(p.read_text().replace('out high','out low'))
 if after and fault=='active_IRQ':(r/'proc/interrupts').write_text(' 70: 0 0 0 0 msmgpio 21 Edge nxp-nci_i2c\n')
 if not after and fault=='cold_clock':(r/'sys/kernel/debug/clk/clk_summary').write_text(' cxo_d1_pin 1 1 0 19200000\n')
 if not after and fault=='cold_GPIO':
  p=r/'sys/kernel/debug/gpio';p.write_text(p.read_text().replace('gpio20 : out low','gpio20 : out high'))
 if not after and fault=='close_reset_missing':
  lines=log.read_text().splitlines();log.write_text('\n'.join(lines[:-1])+'\n')
 if after and fault in ['init_status','init_missing','map_missing','identity_missing','version_missing']:
  data=log.read_text()
  if fault=='init_status':data=data.replace('nci_core_init_rsp_packet_v1: status 0x0','nci_core_init_rsp_packet_v1: status 0x1')
  if fault=='init_missing':data='\n'.join(line for line in data.splitlines() if 'init_rsp_packet_v1:' not in line)+'\n'
  if fault=='map_missing':data='\n'.join(line for line in data.splitlines() if 'disc_map' not in line)+'\n'
  if fault=='identity_missing':data='\n'.join(line for line in data.splitlines() if 'manufact_id' not in line)+'\n'
  if fault=='version_missing':data='\n'.join(line for line in data.splitlines() if 'nci_ver' not in line)+'\n'
  log.write_text(data)
if action=='get' and after==0 and state.exists() and fault=='cold_IRQ_changes':(r/'proc/interrupts').write_text(' 70: 5 0 0 0 msmgpio 21 Edge nxp-nci_i2c\n')
if action=='up' and fault=='bad_output':print('extra output')
if action=='up' and fault=='wrong_result':after=0
print(json.dumps({'ok':True,'action':action,'index':index,'name':'nfc'+str(index),'protocols':126,'powered_before':before,'powered_after':after,'rf_mode':2,'family':42,'requests':2 if action=='get' else 4,'elapsed_ms':1},separators=(',',':')))
'''
COPY=r'''#!/usr/bin/env python3
import os,sys
from pathlib import Path
r=Path(os.environ['TEST_ROOT']);source=Path(sys.argv[1]);target=Path(sys.argv[2]);fault=os.environ.get('TEST_FAULT','')
if source==r/'sys/kernel/debug/dynamic_debug/control':
 query=source.read_text();assert query.startswith('module nci func ') and query.endswith(' +p\n')
 with (r/'tmp/debug-calls').open('a') as out:out.write(query)
 functions=['nci_core_reset_rsp_packet','nci_core_init_rsp_packet','nci_core_init_rsp_packet_v1','nci_core_init_rsp_packet_v2','nci_rf_disc_map_rsp_packet','nci_core_reset_ntf_packet']
 data=''.join('net/nfc/nci/rsp.c:10 [nci]'+name+' ='+('_' if fault=='debug_disabled' else 'p')+' "fixture"\n' for name in functions)
 if fault=='debug_missing':data=''
 target.write_text(data)
else:os.execv('/usr/bin/cp',['cp',*sys.argv[1:]])
'''

class ControllerStartupTests(unittest.TestCase):
 def run_case(self,fault=None):
  original_run=subprocess.run;original_script=cold.SCRIPT;captured={}
  def instrument(args,*a,**kwargs):
   if args==['sh',str(SCRIPT)]:
    env=kwargs['env'];r=Path(env['TEST_ROOT']);binary=Path(env['PATH'].split(os.pathsep)[0])
    def put(name,data,mode=None):
     p=r/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
     if mode:p.chmod(mode)
     return p
    put('etc/fx0-nfc-controller','wrong\n' if fault=='controller_permit' else 'alpine-r58-controller-startup\n')
    worker=put('bin/nfc-state',WORKER,0o755)
    files=[r/'modules'/str(name+'.ko') for name in ['rfkill','nfc','nci','nxp-nci','nxp-nci_i2c']]+[worker]
    put('etc/fx0-nfc-controller.sha256',''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(r))+'\n' for p in files))
    put('sys/kernel/debug/dynamic_debug/control','')
    p=binary/'cp';p.write_text(COPY);p.chmod(0o755)
    p=binary/'dmesg';p.write_text('#!/bin/sh\ncat "$TEST_ROOT/tmp/NCI-dmesg"\n');p.chmod(0o755)
    result=original_run(args,*a,**kwargs)
    for name in ['controller-calls','debug-calls']:
     p=r/'tmp'/name;captured[name]=p.read_text().splitlines() if p.exists() else []
    return result
   return original_run(args,*a,**kwargs)
  cold.SCRIPT=SCRIPT;subprocess.run=instrument
  try:p,calls,modules=cold.ColdLifecycleTests().run_case(fault)
  finally:cold.SCRIPT=original_script;subprocess.run=original_run
  return p,calls,modules,captured
 def test_one_up_down_and_complete_cold_cleanup(self):
  p,calls,mods,c=self.run_case();self.assertEqual(p.returncode,0,p.stderr);self.assertEqual(mods,'')
  self.assertEqual(c['controller-calls'],['get 0','up 0','get 0','down 0','get 0'])
  self.assertEqual(len(c['debug-calls']),4)
  self.assertEqual(calls,['insmod '+name+'.ko' for name in ['rfkill','nfc','nci','nxp-nci','nxp-nci_i2c']]+['rmmod '+name for name in ['nxp_nci_i2c','nxp_nci','nci','nfc','rfkill']])
  self.assertIn('NFC_CONTROLLER_STARTUP_PASS',p.stdout);self.assertEqual(p.stdout.count('__NFC_CONTROLLER_SNAPSHOT__'),7)
 def test_preflight_and_debug_faults_prevent_controller_commands(self):
  for fault in ['controller_permit','kernel','notes','signature','temperature','modules','debug_disabled','debug_missing']:
   with self.subTest(fault=fault):
    p,calls,_,c=self.run_case(fault);self.assertNotEqual(p.returncode,0);self.assertEqual(c['controller-calls'],[]);self.assertNotIn('NFC_CONTROLLER_STARTUP_PASS',p.stdout)
 def test_uncertain_or_incorrect_active_state_stops_mutations(self):
  for fault in ['up_error','up_hang','bad_output','wrong_result','active_clock','active_GPIO','active_IRQ','init_status','init_missing','map_missing','identity_missing','version_missing']:
   with self.subTest(fault=fault):
    p,calls,_,c=self.run_case(fault);self.assertNotEqual(p.returncode,0,p.stdout);self.assertEqual(c['controller-calls'],['get 0','up 0']);self.assertFalse(any(x.startswith('rmmod') for x in calls));self.assertNotIn('NFC_CONTROLLER_STARTUP_PASS',p.stdout)
    if fault=='up_hang':self.assertIn('operation controller-up did not terminate',p.stderr)
 def test_close_ack_and_cold_flag_do_not_hide_failed_cleanup(self):
  for fault in ['down_error','cold_clock','cold_GPIO','close_reset_missing','cold_IRQ_changes']:
   with self.subTest(fault=fault):
    p,calls,_,c=self.run_case(fault);self.assertNotEqual(p.returncode,0,p.stdout);self.assertFalse(any(x.startswith('rmmod') for x in calls));self.assertNotIn('NFC_CONTROLLER_STARTUP_PASS',p.stdout)
    self.assertIn('down 0',c['controller-calls'])

if __name__=='__main__':unittest.main()
