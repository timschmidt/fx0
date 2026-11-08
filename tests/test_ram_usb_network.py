"""Run the RAM-only network CLI against fake sysfs and NetworkManager failures."""
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class RamNetworkTests(unittest.TestCase):
    def exercise(self, *, fail_activation=False, wrong_port=False, fail_uuid_lookup=False):
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            usb = base / ('1-15' if wrong_port else '1-14')
            usb.mkdir()
            for name, value in {'idVendor': '1d6b', 'idProduct': '0104',
                                'serial': 'fx0-diagnostic'}.items():
                (usb / name).write_text(value)
            interface = base / 'net' / 'ram0'
            interface.mkdir(parents=True)
            (interface / 'device').symlink_to(usb, target_is_directory=True)
            (interface / 'address').write_text('02:46:58:30:00:02')
            report = base / 'report.json'
            original_iterdir, original_read_text = Path.iterdir, Path.read_text
            original_read_bytes = Path.read_bytes
            serial_reads = 0

            def iterdir(path):
                return iter([interface]) if path == Path('/sys/class/net') else original_iterdir(path)

            def read_text(path, *args, **kwargs):
                nonlocal serial_reads
                if path == usb / 'serial':
                    serial_reads += 1
                    return 'fx0-diagnostic' if serial_reads == 1 else 'native-return'
                return original_read_text(path, *args, **kwargs)

            def read_bytes(path):
                return b'nameserver 192.0.2.1\n' if path == Path('/etc/resolv.conf') else original_read_bytes(path)

            def run(command, **kwargs):
                calls.append(command)
                if command[0] == 'ip':
                    return subprocess.CompletedProcess(command, 0, '[{"dst":"default","dev":"unchanged"}]', '')
                if fail_uuid_lookup and command[:3] == ['nmcli', '-g', 'connection.uuid']:
                    raise AssertionError('Cleanup must not depend on a post-add UUID lookup')
                if fail_activation and 'up' in command:
                    raise subprocess.CalledProcessError(10, command, stderr='activation failed')
                return subprocess.CompletedProcess(command, 0, 'ok', '')

            arguments = ['connect_fx0_ram_usb.py', '--usb-port', '1-14', '--report', str(report), '--wait', '30']
            # Wrong identity expires without a real wait or any host mutation.
            ticks = iter([0, 0, 31, 31, 31]) if wrong_port else iter(range(100))
            with patch.object(sys, 'argv', arguments), patch.object(Path, 'iterdir', iterdir), \
                    patch.object(Path, 'read_text', read_text), patch.object(Path, 'read_bytes', read_bytes), \
                    patch('subprocess.run', run), patch('time.monotonic', lambda: next(ticks)), \
                    patch('time.sleep'), patch('builtins.print'):
                try:
                    runpy.run_path(str(ROOT / 'scripts/connect_fx0_ram_usb.py'), run_name='__main__')
                    code = 0
                except SystemExit as error:
                    code = error.code
            result = json.loads(report.read_text())
            self.assertEqual(report.stat().st_mode & 0o777, 0o600)
            self.assertEqual(result['host_default_routes_before'], result['host_default_routes_after'])
            self.assertEqual(result['resolver_sha256_before'], result['resolver_sha256_after'])
            return code, result, calls

    def test_detach_removes_only_owned_volatile_connection(self):
        code, result, calls = self.exercise(fail_uuid_lookup=True)
        self.assertEqual(code, 0)
        added = next(c for c in calls if c[:3] == ['nmcli', 'connection', 'add'])
        self.assertEqual(added[added.index('save') + 1], 'no')
        for setting, value in {'connection.autoconnect': 'no', 'ipv4.method': 'manual',
                               'ipv4.never-default': 'yes', 'ipv4.ignore-auto-dns': 'yes',
                               'ipv6.method': 'disabled'}.items():
            self.assertEqual(added[added.index(setting) + 1], value)
        self.assertEqual(added[added.index('connection.uuid') + 1], result['connection_UUID'])
        deleted = [c for c in calls if 'delete' in c]
        self.assertEqual(deleted, [['nmcli', 'connection', 'delete', 'uuid', result['connection_UUID']]])
        self.assertFalse(any('wifi' in word.lower() for c in calls for word in c))

    def test_activation_failure_cleans_up_and_fails(self):
        code, result, calls = self.exercise(fail_activation=True)
        self.assertEqual(code, 1)
        self.assertIn('error', result)
        self.assertEqual(result['cleanup']['returncode'], 0)
        self.assertEqual(sum('delete' in c for c in calls), 1)

    def test_wrong_physical_port_never_changes_network(self):
        code, result, calls = self.exercise(wrong_port=True)
        self.assertEqual(code, 1)
        self.assertIn('No matching RAM gadget', result['error'])
        self.assertFalse(any(c[0] == 'nmcli' for c in calls))


if __name__ == '__main__':
    unittest.main()
