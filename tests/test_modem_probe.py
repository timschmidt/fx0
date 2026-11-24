"""Execute the real offline-probe worker with mocked module syscalls and sysfs."""
import hashlib
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / 'diagnostics/modem-control/probe-only.sh'
ORDER = ['qcom_pil_info', 'qcom_common', 'qcom_q6v5', 'mdt_loader', 'qcom_q6v5_mss']
MODULE_HOOK = r'''#!/bin/sh
set -eu
root=$FX0_MODEM_TEST_ROOT
operation=${0##*/}
if [ "$operation" = insmod ]; then name=${1##*/}; name=${name%.ko}; else name=$1; fi
printf '%s %s\n' "$operation" "$name" >> "$root/trace"
mode=$(cat "$root/mode")
if [ "$mode" = "$operation-fail-$name" ]; then exit 9; fi
if [ "$mode" = hang ] && [ "$name" = qcom_pil_info ]; then /bin/sleep 2; exit 7; fi
platform="$root/sys/bus/platform/devices/fc880000.remoteproc"
if [ "$operation" = insmod ]; then
    printf '%s 1 0 - Live 0x0\n' "$name" >> "$root/proc/modules"
    if [ "$mode" = taint ]; then echo 1 > "$root/proc/sys/kernel/tainted"; fi
    if [ "$mode" = deadline ]; then echo '200.0 0' > "$root/proc/uptime"; fi
    if [ "$name" = qcom_q6v5_mss ]; then
        device="$root/sys/class/remoteproc/remoteproc0"
        mkdir -p "$device"
        echo fc880000.remoteproc > "$device/name"
        echo offline > "$device/state"
        echo mba.b00 > "$device/firmware"
        ln -s "$platform" "$device/device"
        ln -s "$root/sys/bus/platform/drivers/qcom-q6v5-mss" "$platform/driver"
        if [ "$mode" = running ]; then echo running > "$device/state"; fi
        if [ "$mode" = wrong-firmware ]; then echo other.mdt > "$device/firmware"; fi
        if [ "$mode" = boot-log ]; then echo 'remoteproc: powering up fc880000.remoteproc' > "$root/dmesg"; fi
        if [ "$mode" = irq-storm ]; then sed -i 's/: 0 /: 999 /' "$root/proc/interrupts"; fi
        if [ "$mode" = bam-child ]; then mkdir -p "$root/sys/bus/platform/devices/fc880000.remoteproc:bam-dmux"; fi
    fi
else
    awk -v n="$name" '$1!=n' "$root/proc/modules" > "$root/modules-next"
    mv "$root/modules-next" "$root/proc/modules"
    if [ "$name" = qcom_q6v5_mss ]; then
        rm -rf "$root/sys/class/remoteproc/remoteproc0"
        rm "$platform/driver"
    fi
fi
'''


class ModemProbeTests(unittest.TestCase):
    def fixture(self, directory, mode='pass'):
        root = Path(directory)
        def put(name, data):
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data.encode() if isinstance(data, str) else data)
        files = {'etc/fx0-modem-trial': 'native-r50-offline-probe\n',
                 'proc/sys/kernel/random/boot_id': '12345678-1234-1234-1234-123456789abc\n',
                 'etc/fx0-modem-native-boot-id': 'c3ac8f04-888e-493c-bb5d-a1729a275f7d\n',
                 'sys/module/module/parameters/sig_enforce': 'Y\n',
                 'proc/cmdline': 'rdinit=/init module.sig_enforce=1\n',
                 'sys/module/cpufreq/parameters/default_governor': 'schedutil\n',
                 'sys/devices/system/cpu/online': '0-3\n', 'proc/sys/kernel/tainted': '0\n',
                 'sys/module/firmware_class/parameters/path': '\n',
                 'proc/uptime': '10.0 1.0\n', 'proc/modules': '',
                 'proc/mounts': 'rootfs / rootfs rw 0 0\nproc /proc proc rw 0 0\n',
                 'sys/kernel/notes': 'fixture kernel notes',
                 'sys/class/thermal/thermal_zone0/temp': '40000\n',
                 'sys/class/thermal/thermal_zone1/temp': '41000\n',
                 'sys/kernel/debug/regulator/regulator_summary': 'fixture regulator report\n',
                 'sys/firmware/devicetree/base/soc/remoteproc@fc880000/compatible': b'qcom,msm8926-mss-pil\0',
                 'mode': mode, 'dmesg': '', 'trace': ''}
        files['proc/interrupts'] = ''.join(f'{i}: 0 0 0 0 GIC q6v5 {name}\n' for i, name in enumerate(['wdog', 'fatal', 'ready', 'handover', 'stop']))
        for name, data in files.items():
            put(name, data)
        put('etc/fx0-modem-notes.sha256', hashlib.sha256((root / 'sys/kernel/notes').read_bytes()).hexdigest() + '\n')
        prop = 'sys/firmware/devicetree/base/soc/remoteproc@fc880000/compatible'
        put('etc/fx0-modem-DT.sha256', hashlib.sha256((root / prop).read_bytes()).hexdigest() + '  ' + prop + '\n')
        for module in ORDER:
            put('modules/' + module + '.ko', 'mock module ' + module)
        put('etc/fx0-modem-modules.sha256', ''.join(hashlib.sha256((root / ('modules/' + name + '.ko')).read_bytes()).hexdigest() + '  modules/' + name + '.ko\n' for name in ORDER))
        for name in ['tmp', 'sys/class/remoteproc', 'sys/bus/platform/devices/fc880000.remoteproc', 'sys/bus/platform/drivers/qcom-q6v5-mss', 'bin']:
            (root / name).mkdir(parents=True, exist_ok=True)
        hooks = {'insmod': MODULE_HOOK, 'rmmod': MODULE_HOOK,
                 'uname': '#!/bin/sh\nprintf "%s\\n" "${FX0_MOCK_RELEASE:-6.18.59-fx0-dmp}"\n',
                 'dmesg': '#!/bin/sh\ncat "$FX0_MODEM_TEST_ROOT/dmesg"\n',
                 'sleep': '#!/bin/sh\n/bin/sleep 0.05\n'}
        busybox = os.environ.get('FX0_MODEM_TEST_BUSYBOX')
        if busybox:
            for applet in ['cat', 'awk', 'sha256sum', 'sort', 'tr', 'head', 'grep', 'mkdir', 'readlink', 'wc']:
                hooks[applet] = '#!/bin/sh\nexec /usr/bin/qemu-arm-static ' + shlex.quote(busybox) + ' ' + applet + ' "$@"\n'
        for name, data in hooks.items():
            put('bin/' + name, data)
            (root / 'bin' / name).chmod(0o755)
        return root

    def run_worker(self, root, release=None):
        env = os.environ | {'FX0_MODEM_TEST_ROOT': str(root), 'PATH': str(root / 'bin') + ':' + os.environ['PATH']}
        if release:
            env['FX0_MOCK_RELEASE'] = release
        shell = shlex.split(os.environ.get('FX0_MODEM_TEST_SHELL', '/bin/sh'))
        return subprocess.run([*shell, str(WORKER)], capture_output=True, text=True, env=env, timeout=15)

    def test_full_offline_probe_and_reverse_cleanup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            result = self.run_worker(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('MODEM_PROBE_PASS', result.stdout)
            self.assertEqual((root / 'trace').read_text().splitlines(),
                             ['insmod ' + name for name in ORDER] + ['rmmod ' + name for name in reversed(ORDER)])
            self.assertEqual((root / 'proc/modules').read_text(), '')
            self.assertEqual(list((root / 'sys/class/remoteproc').iterdir()), [])
            previous = (root / 'trace').read_bytes()
            self.assertNotEqual(self.run_worker(root).returncode, 0)
            self.assertEqual((root / 'trace').read_bytes(), previous)

    def test_preflight_refusals_have_no_module_operations(self):
        cases = [('etc/fx0-modem-trial', 'wrong'), ('sys/module/module/parameters/sig_enforce', 'N'),
                 ('proc/cmdline', 'rdinit=/init'), ('sys/module/cpufreq/parameters/default_governor', 'performance'),
                 ('sys/devices/system/cpu/online', '0'), ('sys/kernel/notes', 'wrong notes'),
                 ('sys/firmware/devicetree/base/soc/remoteproc@fc880000/compatible', 'wrong DT'),
                 ('modules/qcom_q6v5_mss.ko', 'wrong module'), ('sys/module/firmware_class/parameters/path', '/firmware'),
                 ('proc/sys/kernel/tainted', '1'), ('proc/sys/kernel/random/boot_id', 'bad'),
                 ('proc/sys/kernel/random/boot_id', '-------- ---- ---- ---- ------------'.replace(' ', '-')),
                 ('proc/sys/kernel/random/boot_id', 'c3ac8f04-888e-493c-bb5d-a1729a275f7d'),
                 ('proc/uptime', 'bad'), ('proc/mounts', '/dev/mmcblk0p35 / ext4 rw 0 0'),
                 ('sys/class/thermal/thermal_zone0/temp', '60000'), ('proc/modules', 'other 1 0 - Live 0x0\n')]
        for path, value in cases:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                (root / path).write_text(value)
                result = self.run_worker(root)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual((root / 'trace').read_text(), '')
        with tempfile.TemporaryDirectory() as directory:
            root = self.fixture(directory)
            self.assertNotEqual(self.run_worker(root, release='wrong-kernel').returncode, 0)
            self.assertEqual((root / 'trace').read_text(), '')

    def test_loader_paths_and_policy_nodes_are_refused(self):
        for path in ['lib/firmware', 'usr/lib/firmware', 'lib/modules', 'sbin/modprobe', 'sbin/udevd', 'sbin/init',
                     'sys/devices/system/cpu/cpufreq/policy0', 'sys/kernel/debug/qcom_cpr/debug_info',
                     'sys/firmware/devicetree/base/soc/remoteproc@fc880000/qcom,ext-bhs-reg']:
            with self.subTest(path=path), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory)
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text('unexpected')
                self.assertNotEqual(self.run_worker(root).returncode, 0)
                self.assertEqual((root / 'trace').read_text(), '')

    def test_operation_failure_stops_without_retry_or_followup(self):
        for operation, order in [('insmod', ORDER), ('rmmod', list(reversed(ORDER)))]:
            for name in order:
                with self.subTest(operation=operation, module=name), tempfile.TemporaryDirectory() as directory:
                    root = self.fixture(directory, operation + '-fail-' + name)
                    result = self.run_worker(root)
                    self.assertNotEqual(result.returncode, 0)
                    trace = (root / 'trace').read_text().splitlines()
                    self.assertEqual(trace[-1], operation + ' ' + name)
                    self.assertEqual(trace.count(trace[-1]), 1)

    def test_dynamic_state_changes_stop_before_further_operations(self):
        for mode in ['taint', 'deadline', 'running', 'wrong-firmware', 'boot-log', 'irq-storm', 'bam-child', 'hang']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = self.fixture(directory, mode)
                result = self.run_worker(root)
                self.assertNotEqual(result.returncode, 0)
                trace = (root / 'trace').read_text().splitlines()
                self.assertTrue(trace)
                self.assertTrue(all(row.startswith('insmod ') for row in trace))
                self.assertEqual(len(trace), 1 if mode in ['taint', 'deadline', 'hang'] else 5)
                self.assertNotIn('MODEM_PROBE_PASS', result.stdout)


if __name__ == '__main__':
    unittest.main()
