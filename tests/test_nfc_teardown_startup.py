"""Run the read-only NFC startup script against instrumented proc/sysfs fixtures."""
import hashlib
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/'diagnostics/nfc-startup/check-teardown-startup.sh'


class NFCTeardownStartupTests(unittest.TestCase):
    def run_case(self, fault=None):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); root=base/'root'; binary=base/'bin'; binary.mkdir()
            def put(name, data):
                p=root/name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data if isinstance(data, bytes) else data.encode())
                return p
            put('etc/fx0-nfc-trial','alpine-r58-moduleless-startup\n')
            notes=put('sys/kernel/notes',b'exact kernel-note fixture')
            put('etc/fx0-nfc-notes.sha256',hashlib.sha256(notes.read_bytes()).hexdigest()+'\n')
            put('proc/cmdline','rdinit=/init module.sig_enforce=1 cpufreq.default_governor=schedutil\n')
            put('proc/modules',''); put('proc/sys/kernel/tainted','0\n')
            put('proc/mounts','rootfs / rootfs rw 0 0\nproc /proc proc rw 0 0\n')
            put('sys/module/module/parameters/sig_enforce','Y\n')
            put('sys/module/cpufreq/parameters/default_governor','schedutil\n')
            put('sys/devices/system/cpu/online','0-3\n')
            for i in range(2): put(f'sys/class/thermal/thermal_zone{i}/temp','40000\n')
            node=root/'sys/firmware/devicetree/base/soc/i2c@f9925000/nfc@28'
            put(str(node.relative_to(root)/'compatible'),b'nxp,pn547\0nxp,nxp-nci-i2c\0')
            put(str(node.parent.relative_to(root)/'status'),b'okay\0')
            client=root/'sys/bus/i2c/devices/3-0028';client.mkdir(parents=True)
            (client/'of_node').symlink_to(node)
            (binary/'uname').write_text('#!/bin/sh\nprintf "%s\\n" "${TEST_UNAME:-6.18.59-fx0-nfc-teardown-alpine}"\n')
            (binary/'uname').chmod(0o755)
            for name in ['insmod','modprobe','i2cdetect','i2cget','i2cset','gpioset']:
                p=binary/name;p.write_text('#!/bin/sh\nprintf "%s\\n" "$0" >> "$TEST_CALLS"\nexit 99\n');p.chmod(0o755)
            env=dict(os.environ, PATH=str(binary)+os.pathsep+os.environ['PATH'],FX0_NFC_TEST_ROOT=str(root),TEST_CALLS=str(base/'calls'))
            if fault=='kernel':env['TEST_UNAME']='6.18.59-fx0-cpr-observe-alpine'
            if fault=='old_kernel':env['TEST_UNAME']='6.18.59-fx0-nfc-alpine'
            if fault=='old_marker':put('etc/fx0-nfc-trial','alpine-r56-moduleless-startup\n')
            if fault=='marker':put('etc/fx0-nfc-trial','other\n')
            if fault=='notes':notes.write_bytes(b'other linked kernel')
            if fault=='notes_missing':notes.unlink()
            if fault=='fingerprint':put('etc/fx0-nfc-notes.sha256','z'*64+'\n')
            if fault=='signature':put('sys/module/module/parameters/sig_enforce','N\n')
            if fault=='cmdline':put('proc/cmdline','rdinit=/init\n')
            if fault=='governor':put('sys/module/cpufreq/parameters/default_governor','userspace\n')
            if fault=='taint':put('proc/sys/kernel/tainted','4096\n')
            if fault=='modules':put('proc/modules','nfc 1234 0 - Live 0\n')
            if fault=='proc_modules_zero_size':
                p=root/'proc/modules';p.unlink();p.symlink_to('/proc/self/status');self.assertEqual(p.stat().st_size,0)
            if fault=='CPU':put('sys/devices/system/cpu/online','0-2\n')
            if fault=='policy':(root/'sys/devices/system/cpu/cpufreq/policy0').mkdir(parents=True)
            if fault=='CPR':put('sys/kernel/debug/qcom_cpr/debug_info','unexpected provider\n')
            if fault=='mount':put('proc/mounts','/dev/mmcblk0p22 /mnt ext4 ro 0 0\n')
            if fault=='mount_alias':put('proc/mounts','UUID=unqualified /mnt ext4 ro 0 0\n')
            if fault=='temperature':put('sys/class/thermal/thermal_zone1/temp','60000\n')
            if fault=='temperature_invalid':put('sys/class/thermal/thermal_zone1/temp','42x\n')
            if fault=='temperature_missing':(root/'sys/class/thermal/thermal_zone1/temp').unlink()
            if fault=='temperature_extra':put('sys/class/thermal/thermal_zone2/temp','40000\n')
            if fault=='compatible':(node/'compatible').write_bytes(b'nxp,wrong\0')
            if fault=='bus_disabled':(node.parent/'status').write_bytes(b'disabled\0')
            if fault=='client_disabled':(node/'status').write_bytes(b'disabled\0')
            if fault=='bound':(client/'driver').symlink_to(node)
            if fault=='dangling_driver':(client/'driver').symlink_to(node/'missing')
            if fault=='missing_client':(client/'of_node').unlink();client.rmdir()
            if fault=='duplicate_client':
                p=client.parent/'4-0028';p.mkdir();(p/'of_node').symlink_to(node)
            def snapshot():
                return {str(p.relative_to(root)):('symlink',str(p.readlink())) if p.is_symlink() else ('file',p.stat().st_mode,hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob('*') if p.is_symlink() or p.is_file()}
            before=snapshot();p=subprocess.run(['sh',str(SCRIPT)],env=env,capture_output=True,text=True)
            self.assertEqual(snapshot(),before,'Checker changed its proc/sysfs fixture')
            self.assertFalse((base/'calls').exists(),'Checker attempted a module/GPIO/I2C operation')
            return p

    def test_moduleless_startup_snapshot_is_read_only(self):
        p=self.run_case();self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('NFC_STARTUP_PASS',p.stdout)
        self.assertIn('__NFC_CLIENT__/sys/bus/i2c/devices/3-0028',p.stdout)

    def test_rejects_wrong_family_and_bootstrap_faults(self):
        faults={'old_kernel':'wrong kernel release','old_marker':'trial marker missing','kernel':'wrong kernel release','marker':'trial marker missing','notes':'wrong linked kernel build','notes_missing':'kernel notes unavailable','fingerprint':'invalid kernel-note fingerprint','signature':'module signatures not enforced','cmdline':'signature boot parameter missing','governor':'wrong compiled/default governor','taint':'kernel tainted','modules':'unexpected loaded modules','proc_modules_zero_size':'unexpected loaded modules','CPU':'CPU topology changed','policy':'unexpected CPUfreq policy','CPR':'unexpected CPR provider','mount':'unexpected filesystem mount','mount_alias':'unexpected filesystem mount','temperature':'temperature outside bounds','temperature_invalid':'invalid temperature','temperature_missing':'expected two temperature sensors','temperature_extra':'expected two temperature sensors','compatible':'wrong NFC compatible','bus_disabled':'QUP3 disabled','client_disabled':'NFC client disabled','bound':'NFC client unexpectedly bound','dangling_driver':'NFC client unexpectedly bound','missing_client':'expected one unbound QUP3 NFC client','duplicate_client':'expected one unbound QUP3 NFC client'}
        for fault,message in faults.items():
            with self.subTest(fault=fault):
                p=self.run_case(fault);self.assertNotEqual(p.returncode,0)
                self.assertIn(message,p.stderr)
                self.assertNotIn('NFC_STARTUP_PASS',p.stdout)


if __name__=='__main__':unittest.main()
