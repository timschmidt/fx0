"""Execute the native overlay hook with real file hashes and modeled mounts."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT/'diagnostics/kernel-maintenance/native-modules-hook.sh'
RELEASE = '6.18.63-fx0-vibrator-alpine'
TOKEN = 'fx0.native_trial=stable-6.18.63-01'

class NativeOverlayTests(unittest.TestCase):
    def execute(self, fault=''):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            for name in ['root', 'proc/sys/kernel', 'sysroot/usr/lib/modules', 'initial', 'mock', 'etc']:
                (base/name).mkdir(parents=True)
            old = base/'sysroot/usr/lib/modules/original'
            old.write_text('installed kernel preserved\n')
            source = base/'sysroot/var/lib/fx0-diagnostics/kernel-native-6.18.63-01/candidate/lib/modules'/RELEASE
            source.mkdir(parents=True)
            payload = b'module-payload\n'
            (source/'module.ko.zst').write_bytes(payload if fault != 'payload' else payload+b'corrupt')
            digest = hashlib.sha256(payload).hexdigest()
            (base/'etc/fx0-native-modules.sha256').write_text(digest+'  module.ko.zst\n')
            for name in ['timer', 'service']:
                (base/f'etc/fx0-native-return.{name}').write_text(name+'\n')
            (base/'proc/cmdline').write_text('quiet '+(TOKEN+'-wrong' if fault=='permit' else TOKEN)+'\n')
            (base/'proc/sys/kernel/tainted').write_text('1\n' if fault=='taint' else '0\n')
            (base/'initial/initramfs.load').write_text('msm\n')
            (base/'armed').write_text('PID=123\nDEADLINE=420\n')
            scripts = {
                'uname': '#!/bin/sh\necho '+('wrong' if fault=='release' else RELEASE)+'\n',
                'mount': '''#!/bin/sh
printf '%s\\n' "$*" >>/audit/mount.log
if [ "$1" = --move ]; then
 mv /sysroot/usr/lib/modules /sysroot/usr/lib/modules.hidden
 cp -a /fx0-ram-modules /sysroot/usr/lib/modules
fi
''',
            }
            if fault=='copied':
                scripts['cp'] = '''#!/bin/sh
/usr/bin/cp "$@"
case "$*" in *"/fx0-ram-modules/") echo bad >>/fx0-ram-modules/'''+RELEASE+'''/module.ko.zst;; esac
'''
            for name, text in scripts.items():
                path = base/'mock'/name
                path.write_text(text)
                path.chmod(0o755)
            # Only replace fatal recovery with an exit for this host fixture.
            # Actual guard expressions, hash/copy operations and call order remain.
            text = HOOK.read_text()
            before = '''    sync
    reboot -f
    while :; do sleep 60; done'''
            self.assertEqual(text.count(before), 1)
            text = text.replace(before, '    exit 99')
            (base/'hook').write_text(text)
            cmd = ['bwrap', '--unshare-all', '--die-with-parent', '--clearenv',
                   '--setenv', 'PATH', '/mock:/usr/bin:/bin', '--tmpfs', '/']
            for name in ['usr', 'lib', 'lib64', 'bin', 'sbin']:
                if Path('/'+name).exists():
                    cmd += ['--ro-bind', '/'+name, '/'+name]
            cmd += ['--dev', '/dev', '--tmpfs', '/tmp', '--tmpfs', '/run',
                    '--ro-bind', str(base/'proc'), '/proc',
                    '--bind', str(base/'sysroot'), '/sysroot',
                    '--ro-bind', str(base/'initial'), '/usr/lib/modules',
                    '--ro-bind', str(base/'etc'), '/etc',
                    '--ro-bind', str(base/'mock'), '/mock',
                    '--bind', str(base), '/audit',
                    '--ro-bind', str(base/'armed'), '/tmp/fx0-native-return-armed',
                    '/bin/sh', '/audit/hook']
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
            mounts = (base/'mount.log').read_text() if (base/'mount.log').exists() else ''
            if not fault:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--move /fx0-ram-modules /sysroot/usr/lib/modules', mounts)
                self.assertEqual((base/'sysroot/usr/lib/modules'/RELEASE/'module.ko.zst').read_bytes(), payload)
                self.assertEqual((base/'sysroot/usr/lib/modules.hidden/original').read_text(), 'installed kernel preserved\n')
            else:
                self.assertEqual(result.returncode, 99, result.stderr)
                self.assertNotIn('--move', mounts)
                self.assertEqual(old.read_text(), 'installed kernel preserved\n')
                if fault!='copied':
                    self.assertEqual(mounts, '')
    def test_full_copy_verified_before_mount_move(self): self.execute()
    def test_identity_failures_do_not_mount(self):
        for fault in ['release','permit','taint']:
            with self.subTest(fault=fault): self.execute(fault)
    def test_staged_corruption_does_not_mount(self): self.execute('payload')
    def test_copy_corruption_does_not_hide_installed_tree(self): self.execute('copied')

if __name__=='__main__': unittest.main()
