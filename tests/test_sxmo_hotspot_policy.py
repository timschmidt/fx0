"""Exercise only the patched hotspot predicate; other blockers never run."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'patches/sxmo/hotspot-suspend-detect-ap-mode.diff'


class HotspotPolicyTests(unittest.TestCase):
    def check_mode(self, active, modes='', enumeration_failure=False, mode_failure=False):
        # Extract the added function verbatim from the reviewable patch.
        added = '\n'.join(line[1:] for line in PATCH.read_text().splitlines()
                          if line.startswith('+') and not line.startswith('+++'))
        body = added[added.index('\t# Profile'):]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            nmcli = base / 'nmcli'
            nmcli.write_text('''#!/bin/sh
case "$*" in
  *--active*) [ "$ENUM_FAIL" = 0 ] || exit 1; printf '%s\\n' "$ACTIVE" ;;
  *) [ "$MODE_FAIL" = 0 ] || exit 1
     case "$*" in *"uuid ap-id") echo ap ;; *) printf '%s\\n' "$MODE" ;; esac ;;
esac
''')
            nmcli.chmod(0o755)
            script = 'hotspot_active() {\n' + body + '\n}\nhotspot_active\n'
            env = dict(os.environ, PATH=str(base), ACTIVE=active, MODE=modes,
                       ENUM_FAIL=str(int(enumeration_failure)), MODE_FAIL=str(int(mode_failure)))
            return subprocess.run(['/bin/sh', '-c', script], env=env,
                                  capture_output=True, text=True, timeout=5).returncode

    def test_renamed_ap_blocks(self):
        self.assertEqual(self.check_mode('ap-id:802-11-wireless'), 0)

    def test_station_and_ethernet_do_not_block(self):
        self.assertEqual(self.check_mode('sta-id:802-11-wireless\neth-id:802-3-ethernet', 'infrastructure'), 1)

    def test_no_active_connections_does_not_block(self):
        self.assertEqual(self.check_mode(''), 1)

    def test_ap_after_station_blocks(self):
        self.assertEqual(self.check_mode('sta-id:802-11-wireless\nap-id:802-11-wireless', 'infrastructure'), 0)

    def test_nm_failures_block_conservatively(self):
        self.assertEqual(self.check_mode('', enumeration_failure=True), 0)
        self.assertEqual(self.check_mode('sta-id:802-11-wireless', mode_failure=True), 0)


if __name__ == '__main__':
    unittest.main()
