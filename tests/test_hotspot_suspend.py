import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HELPER = Path(__file__).resolve().parents[1] / 'diagnostics/hotspot-suspend/fx0-hotspot-suspend'
AP = '11111111-1111-4111-8111-111111111111'
STA = '22222222-2222-4222-8222-222222222222'
OTHER = '33333333-3333-4333-8333-333333333333'
FAKE = r'''#!/usr/bin/python3
import json,os,sys,signal
from pathlib import Path
name=Path(sys.argv[0]).name;args=sys.argv[1:];config=json.loads(Path(os.environ['FIXTURE_CONFIG']).read_text())
with Path(os.environ['FIXTURE_EVENTS']).open('a') as stream:stream.write(json.dumps([name,args])+'\n')
if name=='nmcli':
 if '--active' in args:
  if config.get('enumeration_fail'):sys.exit(1)
  print(config['active'])
 elif '802-11-wireless.mode' in args:print(config['modes'][args[-1]])
 elif 'down' in args and config.get('down_fail'):sys.exit(1)
 elif 'up' in args and config.get('up_fail'):sys.exit(1)
elif name=='readlink':print('/drivers/'+('iwlwifi' if '/wlo1/' in args[-1] else 'wcn36xx'))
elif name=='cat':
 assert args==['/sys/power/wakeup_count'];print('23')
elif name=='doas':
 assert args==['-n','tee','/sys/power/wakeup_count'];assert sys.stdin.read()=='23\n'
 if config.get('count_fail'):sys.exit(1)
elif name=='child':
 if config.get('signal_parent'):os.kill(os.getppid(),signal.SIGTERM)
 sys.exit(config.get('child_status',0))
'''

class HotspotSuspendTests(unittest.TestCase):
    def invoke(self, overrides=None, sync=False, no_nm=False):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);binary=base/'bin';binary.mkdir();events=base/'events';config=base/'config.json'
            values={'active':f'{AP}:802-11-wireless:wlan0\n{STA}:802-11-wireless:wlan1\n{OTHER}:802-11-wireless:wlo1','modes':{AP:'ap',STA:'infrastructure'}}
            values.update(overrides or {});config.write_text(json.dumps(values))
            for name in ['child'] if no_nm else ['nmcli','readlink','cat','doas','child']:
                p=binary/name;p.write_text(FAKE);p.chmod(0o755)
            env=dict(os.environ,FIXTURE_CONFIG=str(config),FIXTURE_EVENTS=str(events),TMPDIR=str(base),PATH=str(binary)+((':'+os.environ['PATH']) if not no_nm else ''))
            result=subprocess.run([str(HELPER),*(['--sync-wakeup-count'] if sync else []),'child'],env=env,capture_output=True,text=True,timeout=10)
            records=[json.loads(line) for line in events.read_text().splitlines()]
            self.assertFalse(list(base.glob('fx0-hotspot-suspend.*')))
            return result,records
    @staticmethod
    def operations(records):
        return [(args[args.index('connection')+1],args[-1]) for name,args in records if name=='nmcli' and 'connection' in args and ('down' in args or 'up' in args)]
    def test_only_wcn_ap_is_stopped_and_restored_around_child(self):
        result,records=self.invoke();self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(self.operations(records),[('down',AP),('up',AP)])
        self.assertLess(next(i for i,r in enumerate(records) if r[0]=='nmcli' and 'down' in r[1]),next(i for i,r in enumerate(records) if r[0]=='child'))
    def test_child_failure_still_restores_and_preserves_status(self):
        result,records=self.invoke({'child_status':7});self.assertEqual(result.returncode,7);self.assertEqual(self.operations(records)[-1],('up',AP))
    def test_preparation_failure_does_not_run_sleep(self):
        result,records=self.invoke({'down_fail':True});self.assertNotEqual(result.returncode,0);self.assertFalse(any(name=='child' for name,args in records));self.assertEqual(self.operations(records)[-1],('up',AP))
    def test_enumeration_failure_does_not_run_sleep_or_modify_connections(self):
        result,records=self.invoke({'enumeration_fail':True});self.assertNotEqual(result.returncode,0);self.assertFalse(any(name=='child' for name,args in records));self.assertEqual(self.operations(records),[])
    def test_wakeup_count_race_aborts_sleep_and_restores(self):
        result,records=self.invoke({'count_fail':True},sync=True);self.assertNotEqual(result.returncode,0);self.assertFalse(any(name=='child' for name,args in records));self.assertEqual(self.operations(records)[-1],('up',AP))
    def test_wakeup_count_is_refreshed_before_child(self):
        result,records=self.invoke(sync=True);self.assertEqual(result.returncode,0,result.stderr)
        names=[name for name,args in records];self.assertLess(names.index('doas'),names.index('child'))
    def test_signal_restores_ap(self):
        result,records=self.invoke({'signal_parent':True});self.assertEqual(result.returncode,143,result.stderr);self.assertEqual(self.operations(records)[-1],('up',AP))
    def test_restore_failure_is_reported(self):
        result,records=self.invoke({'up_fail':True});self.assertNotEqual(result.returncode,0);self.assertIn('Could not restore hotspot',result.stderr)
    def test_no_networkmanager_passes_through(self):
        result,records=self.invoke({'child_status':7},no_nm=True);self.assertEqual(result.returncode,7);self.assertEqual([name for name,args in records],['child'])

if __name__=='__main__':unittest.main()
