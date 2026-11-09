"""Run the read-only NFC startup script against instrumented proc/sysfs fixtures."""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(os.environ.get('FX0_NFC_OPEN_STARTUP_SCRIPT', ROOT/'diagnostics/nfc-startup/check-open-teardown-startup.sh'))


class NFCOpenTeardownStartupTests(unittest.TestCase):
    def run_case(self, fault=None):
        with tempfile.TemporaryDirectory() as directory:
            base=Path(directory); root=base/'root'; binary=base/'bin'; binary.mkdir()
            def put(name, data):
                p=root/name; p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(data if isinstance(data, bytes) else data.encode())
                return p
            put('etc/fx0-nfc-trial','alpine-r59-moduleless-startup\n')
            notes=put('sys/kernel/notes',b'exact kernel-note fixture')
            put('etc/fx0-nfc-notes.sha256',hashlib.sha256(notes.read_bytes()).hexdigest()+'\n')
            put('proc/sys/kernel/random/boot_id','b6f50df4-8290-4b44-83aa-fc2cd784d902\n')
            put('sys/kernel/debug/clk/clk_summary','cxo_d1_pin 0 0 0 19200000 0 0 50000 Y deviceless no_connection_id\n')
            put('sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins',''.join(f'pin {i} (GPIO_{i}): UNCLAIMED\n' for i in [20,21,22]))
            gpio='gpio20 : in low func0 2mA pull down\ngpio21 : in high func0 2mA pull up\ngpio22 : in low func0 2mA pull down\n'
            put('sys/kernel/debug/gpio',gpio)
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
            (binary/'uname').write_text('#!/bin/sh\nprintf "%s\\n" "${TEST_UNAME:-6.18.59-fx0-nfc-open-teardown-alpine}"\n')
            (binary/'uname').chmod(0o755)
            busybox=os.environ.get('FX0_NFC_TEST_BUSYBOX')
            if busybox:
                for name in ['cat','sha256sum','awk','readlink','tr']:
                    p=binary/name
                    p.write_text('#!/bin/sh\nexec /usr/bin/qemu-arm-static '+shlex.quote(busybox)+' '+name+' "$@"\n')
                    p.chmod(0o755)
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
            if fault=='previous_kernel':env['TEST_UNAME']='6.18.59-fx0-nfc-teardown-alpine'
            if fault=='previous_marker':put('etc/fx0-nfc-trial','alpine-r58-moduleless-startup\n')
            if fault=='boot_id_missing':(root/'proc/sys/kernel/random/boot_id').unlink()
            if fault=='boot_id_shape':put('proc/sys/kernel/random/boot_id','not-a-boot-id\n')
            if fault=='boot_id_nonhex':put('proc/sys/kernel/random/boot_id','z6f50df4-8290-4b44-83aa-fc2cd784d902\n')
            if fault=='boot_id_extra_dash':put('proc/sys/kernel/random/boot_id','-6f50df4-8290-4b44-83aa-fc2cd784d902\n')
            if fault=='clock_missing':(root/'sys/kernel/debug/clk/clk_summary').unlink()
            if fault=='clock_duplicate':put('sys/kernel/debug/clk/clk_summary','cxo_d1_pin 0 0 0 19200000\n'*2)
            if fault in ['clock_enable','clock_prepare','clock_protect','clock_rate']:
                columns=['cxo_d1_pin','0','0','0','19200000']
                columns[{'clock_enable':1,'clock_prepare':2,'clock_protect':3,'clock_rate':4}[fault]]='1'
                put('sys/kernel/debug/clk/clk_summary',' '.join(columns)+'\n')
            if fault=='pin_owned':put('sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins','pin 20 (GPIO_20): device 1-0028 function gpio group gpio20\npin 21 (GPIO_21): UNCLAIMED\npin 22 (GPIO_22): UNCLAIMED\n')
            if fault=='pin_missing':put('sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins','pin 20 (GPIO_20): UNCLAIMED\npin 22 (GPIO_22): UNCLAIMED\n')
            if fault=='pin_duplicate':put('sys/kernel/debug/pinctrl/fd510000.pinctrl/pinmux-pins','pin 20 (GPIO_20): UNCLAIMED\n'*2+'pin 21 (GPIO_21): UNCLAIMED\npin 22 (GPIO_22): UNCLAIMED\n')
            if fault=='gpio_enable_high':put('sys/kernel/debug/gpio',gpio.replace('gpio20 : in low','gpio20 : in high'))
            if fault=='gpio_firmware_high':put('sys/kernel/debug/gpio',gpio.replace('gpio22 : in low','gpio22 : in high'))
            if fault=='gpio_output':put('sys/kernel/debug/gpio',gpio.replace('gpio20 : in low','gpio20 : out low'))
            if fault=='gpio_missing':put('sys/kernel/debug/gpio',gpio.split('gpio22')[0])
            if fault=='gpio_IRQ_drive':put('sys/kernel/debug/gpio',gpio.replace('gpio21 : in high func0 2mA','gpio21 : in high func0 8mA'))
            def snapshot():
                return {str(p.relative_to(root)):('symlink',str(p.readlink())) if p.is_symlink() else ('file',p.stat().st_mode,hashlib.sha256(p.read_bytes()).hexdigest()) for p in root.rglob('*') if p.is_symlink() or p.is_file()}
            shell=shlex.split(os.environ.get('FX0_NFC_TEST_SHELL','sh'))
            before=snapshot();p=subprocess.run([*shell,str(SCRIPT)],env=env,capture_output=True,text=True,timeout=15)
            self.assertEqual(snapshot(),before,'Checker changed its proc/sysfs fixture')
            self.assertFalse((base/'calls').exists(),'Checker attempted a module/GPIO/I2C operation')
            return p

    def test_moduleless_startup_snapshot_is_read_only(self):
        p=self.run_case();self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn('NFC_STARTUP_PASS',p.stdout)
        self.assertIn('__NFC_BOOT_ID__b6f50df4-8290-4b44-83aa-fc2cd784d902',p.stdout)
        self.assertIn('__NFC_CLIENT__/sys/bus/i2c/devices/3-0028',p.stdout)

    def test_rejects_wrong_family_and_bootstrap_faults(self):
        faults={'old_kernel':'wrong kernel release','old_marker':'trial marker missing','kernel':'wrong kernel release','marker':'trial marker missing','notes':'wrong linked kernel build','notes_missing':'kernel notes unavailable','fingerprint':'invalid kernel-note fingerprint','signature':'module signatures not enforced','cmdline':'signature boot parameter missing','governor':'wrong compiled/default governor','taint':'kernel tainted','modules':'unexpected loaded modules','proc_modules_zero_size':'unexpected loaded modules','CPU':'CPU topology changed','policy':'unexpected CPUfreq policy','CPR':'unexpected CPR provider','mount':'unexpected filesystem mount','mount_alias':'unexpected filesystem mount','temperature':'temperature outside bounds','temperature_invalid':'invalid temperature','temperature_missing':'expected two temperature sensors','temperature_extra':'expected two temperature sensors','compatible':'wrong NFC compatible','bus_disabled':'QUP3 disabled','client_disabled':'NFC client disabled','bound':'NFC client unexpectedly bound','dangling_driver':'NFC client unexpectedly bound','missing_client':'expected one unbound QUP3 NFC client','duplicate_client':'expected one unbound QUP3 NFC client'}
        faults.update({'previous_kernel': 'wrong kernel release', 'previous_marker': 'trial marker missing', 'boot_id_missing': 'RAM boot ID unavailable', 'boot_id_shape': 'invalid RAM boot ID', 'boot_id_nonhex': 'invalid RAM boot ID', 'boot_id_extra_dash': 'invalid RAM boot ID', 'clock_missing': 'moduleless reference-clock vote changed', 'clock_duplicate': 'moduleless reference-clock vote changed', 'clock_enable': 'moduleless reference-clock vote changed', 'clock_prepare': 'moduleless reference-clock vote changed', 'clock_protect': 'moduleless reference-clock vote changed', 'clock_rate': 'moduleless reference-clock vote changed', 'pin_owned': 'moduleless NFC pin owner present', 'pin_missing': 'moduleless NFC pin owner present', 'pin_duplicate': 'moduleless NFC pin owner present', 'gpio_enable_high': 'moduleless enable/firmware GPIO changed', 'gpio_firmware_high': 'moduleless enable/firmware GPIO changed', 'gpio_output': 'moduleless enable/firmware GPIO changed', 'gpio_missing': 'moduleless enable/firmware GPIO changed', 'gpio_IRQ_drive': 'moduleless IRQ GPIO changed'})
        for fault,message in faults.items():
            with self.subTest(fault=fault):
                p=self.run_case(fault);self.assertNotEqual(p.returncode,0)
                self.assertIn(message,p.stderr)
                self.assertNotIn('NFC_STARTUP_PASS',p.stdout)


if __name__=='__main__':unittest.main()
