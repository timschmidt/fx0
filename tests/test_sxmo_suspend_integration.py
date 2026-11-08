import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'worktrees/sxmo-hotspot/scripts/core/sxmo_suspend.sh'
FAKE = '''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
name=Path(sys.argv[0]).name
with open(os.environ['EVENTS'],'a') as f:f.write(json.dumps([name,sys.argv[1:]])+'\\n')
if name=='date':print('1000')
elif name=='sxmo_hook_mnc.sh':print(os.environ['MNC'])
elif name=='fx0-hotspot-suspend':sys.exit(int(os.environ['COORDINATOR_STATUS']))
'''


class SxmoSuspendIntegrationTests(unittest.TestCase):
    def invoke(self, device='lg,madai', mnc='100', coordinator_status=0):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            (base / 'sxmo_common.sh').write_text('sxmo_log() { :; }\n')
            for name in ['date', 'sxmo_hook_mnc.sh', 'fx0-hotspot-suspend',
                         'doas', 'sxmo_hook_postwake.sh', 'sxmo_wakelock.sh']:
                path = base / name
                path.write_text(FAKE)
                path.chmod(0o755)
            events = base / 'events'
            env = dict(os.environ, PATH=str(base), EVENTS=str(events),
                       SXMO_DEVICE_NAME=device, MNC=mnc,
                       COORDINATOR_STATUS=str(coordinator_status))
            result = subprocess.run(['/bin/sh', str(SCRIPT)], env=env,
                                    capture_output=True, text=True, timeout=5)
            return result, [json.loads(s) for s in events.read_text().splitlines()]

    def test_fx0_uses_original_absolute_deadline(self):
        result, events = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['fx0-hotspot-suspend', ['--sync-wakeup-count', 'doas', '-n',
                       'rtcwake', '-m', 'mem', '-t', '1090']], events)
        self.assertEqual(events[-1][0], 'sxmo_hook_postwake.sh')

    def test_coordinator_failure_skips_postwake(self):
        result, events = self.invoke(coordinator_status=1)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(any(name == 'sxmo_hook_postwake.sh' for name, args in events))

    def test_imminent_cron_holds_wakelock_without_sleep(self):
        result, events = self.invoke(mnc='12')
        self.assertEqual(result.returncode, 1)
        self.assertIn(['sxmo_wakelock.sh', ['lock', 'sxmo_waiting_cronjob', 'infinite']], events)
        self.assertFalse(any(name == 'fx0-hotspot-suspend' for name, args in events))

    def test_other_device_keeps_existing_relative_rtc_path(self):
        result, events = self.invoke(device='other,device')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(['doas', ['rtcwake', '-m', 'mem', '-s', '90']], events)
        self.assertFalse(any(name == 'fx0-hotspot-suspend' for name, args in events))


if __name__ == '__main__':
    unittest.main()
