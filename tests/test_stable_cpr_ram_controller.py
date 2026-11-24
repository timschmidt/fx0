"""Exercise entry/BOOT/return failures with real owned child processes."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch
import uuid

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('stable_ram', ROOT/'diagnostics/cpu-cpr-runtime/stable_ram.py')
M = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(M)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value))


class Fixture:
    def __init__(self, root):
        self.root = root
        (root/'local').mkdir()
        image = b'ANDROID!'+bytes(range(256))*8
        (root/'local/image.img').write_bytes(image)
        self.profile = M.PROFILE | dict(image_sha256=digest(image), image_bytes=len(image))
        receipt = {k: v for k, v in self.profile.items() if k != 'release'}
        receipt.update(kernel_release=self.profile['release'], image_path='local/image.img', return_after_seconds=180,
                       module_signature_enforcement=True, default_governor='userspace', explicit_frequency_or_voltage_requests=[],
                       selected_modules={'cpufreq_userspace.ko': {}, 'cpufreq-dt.ko': {}},
                       init_BusyBox_HTTP_timer_and_cmdline_unchanged=True,
                       header_digest_addresses_and_ramdisk_readback_verified=True)
        put(root/'local/image.json', receipt)
        self.boot_id = str(uuid.uuid4())
        self.owner = dict(status='confirmed', native_boot_id=self.boot_id,
                          display_confirmed=True, touch_confirmed=True)
        put(root/'local/owner.json', self.owner)
        helpers = {}
        for name in M.HELPERS:
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('fixture '+name)
            helpers[name] = M.sha(path)
        self.plan = dict(schema=1, native_expected=dict(boot_id=self.boot_id, kernel='6.18.59-fx0-dmp',
                         raw_boot_sha256='a'*64, files_sha256={p: 'b'*64 for p in M.NATIVE_FILES}),
                         USB_port='1-7', owner_confirmation='local/owner.json', private_identity='local/identity.private.json',
                         image_receipt='local/image.json', image_receipt_sha256=M.sha(root/'local/image.json'),
                         trial_directory='local/trial', helper_sha256=helpers)

    def check(self):
        return M.check_plan(self.root, self.plan, self.profile)


def healthy(expected, *, returned=False):
    return copy.deepcopy(expected) | dict(boot_id=str(uuid.uuid4()) if returned else expected['boot_id'], taint=0,
           systemd='running', failed_units='', jobs='', Sway_count=1, gesture_count=1, sensor_proxy='active',
           APC_registers={'0x1740': 1, '0x1741': 115}, governor='schedutil',
           available_frequencies=[300000, 384000, 600000, 787200], temperatures_mC=[40000, 41000])


OBSERVER = r'''
import json,sys,time
from pathlib import Path
p=Path(sys.argv[1]);nonce=sys.argv[2];proof=json.loads(sys.argv[3])
(p/'observer-ready.json').write_text(json.dumps(dict(nonce=nonce,USB_port='1-7')))
while not (p/'stop.json').exists() and not (p/'exit-now').exists():time.sleep(.005)
(p/'observation.json').write_text(json.dumps(dict(nonce=nonce,state='terminal',proof=proof)))
'''
TRANSFER = r'''
import hashlib,json,sys,time
from pathlib import Path
p=Path(sys.argv[1]);data=Path(sys.argv[2]).read_bytes();fault=sys.argv[3]
p.mkdir();time.sleep(.02)
(p/'readback.bin').write_bytes(data+b'changed' if fault=='readback' else data)
(p/'result.json').write_text(json.dumps(dict(state='verified',readback_sha256=hashlib.sha256(data).hexdigest())))
raise SystemExit(1 if fault=='transfer' else 0)
'''


class FakeBackend:
    def __init__(self, checked, fault=None):
        self.checked = checked
        self.root, self.trial = checked['root'], checked['trial']
        self.fault = fault
        self.calls = []
        self.children = []
        self.mode = 'native'
        self.observer = None
        self.host_reads = 0

    def close(self):
        self.calls.append('close')

    def host_state(self):
        self.host_reads += 1
        return {'routes': 'changed' if self.fault == 'host' and self.host_reads > 1 else 'same'}

    def native_state(self):
        self.calls.append('native')
        result = healthy(self.checked['plan']['native_expected'])
        if self.fault == 'boot_id':
            result['boot_id'] = str(uuid.uuid4())
        if self.fault == 'native_hash':
            result['raw_boot_sha256'] = '0'*64
        return result

    def usb_mode(self):
        return self.mode

    def start_observer(self, nonce):
        self.calls.append('observer')
        proof = dict(kernel=self.checked['profile']['release'], boot_id=str(uuid.uuid4()), registration_exit=0,
                     registration_pass=True, taint=0, raw_boot_sha256=self.checked['plan']['native_expected']['raw_boot_sha256'],
                     complete=True, timer_uptime_seconds=181.7, panic_free=True)
        if self.fault == 'registration':
            proof['registration_exit'] = 1
        if self.fault == 'early_return':
            proof['timer_uptime_seconds'] = 30
        if self.fault == 'panic':
            proof['panic_free'] = False
        process = subprocess.Popen([sys.executable, '-c', OBSERVER, str(self.trial), nonce, json.dumps(proof)])
        self.children.append(process)
        self.observer = process
        return process

    def wait_observer_ready(self, process, nonce):
        M.NativeBackend.wait_observer_ready(self, process, nonce)

    def reboot_bootloader(self):
        self.calls.append('reboot')
        self.mode = 'bootloader'
        if self.fault == 'reboot_ack':
            raise OSError('lost SSH reply')

    def wait_bootloader(self):
        self.calls.append('bootloader')

    def start_transfer(self):
        self.calls.append('transfer')
        # A stale cross-namespace PID file must have no authority.
        put(self.trial/'transfer-controller.json', dict(PID=2, returncode=0))
        process = subprocess.Popen([sys.executable, '-c', TRANSFER, str(self.trial/'transfer'),
                                    str(self.checked['payload']), self.fault or ''])
        self.children.append(process)
        if self.fault == 'observer_exit':
            (self.trial/'exit-now').touch()
            self.observer.wait()
        return process

    def verify_readback(self):
        self.calls.append('readback')
        M.NativeBackend.verify_readback(self)

    def boot_once(self):
        self.calls.append('BOOT')
        self.mode = 'diagnostic'
        if self.fault == 'BOOT_ack':
            raise OSError('lost BOOT reply')

    def wait_native_return(self):
        self.calls.append('return')
        self.mode = 'native'
        result = healthy(self.checked['plan']['native_expected'], returned=True)
        if self.fault == 'return_hash':
            result['files_sha256']['/boot/vmlinuz'] = '0'*64
        return result

    def recover_native_once(self):
        self.calls.append('recover')
        if any(child.poll() is None for child in self.children):
            raise AssertionError('Recovery raced an owned child')


class StableRamControllerTests(unittest.TestCase):
    def exercise(self, fault=None):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            checked = fixture.check()
            backend = FakeBackend(checked, fault)
            with patch('os.kill', side_effect=AssertionError('PID-file liveness is forbidden')):
                try:
                    result = M.run_trial(checked, lambda _: backend)
                    stopped = False
                except M.TrialError:
                    result = M.read_json(checked['trial']/'controller.json')
                    stopped = True
            self.assertTrue(all(c.poll() is not None for c in backend.children))
            self.assertTrue(result['owned_children_terminal'])
            return stopped, result, backend.calls

    def test_missing_or_stale_owner_stops_before_private_identity_or_trial_creation(self):
        modes = ['missing', 'pending', 'display', 'touch', 'different_boot', 'numeric_boolean']
        for mode in modes:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                fixture = Fixture(Path(directory))
                owner = fixture.owner.copy()
                if mode == 'missing':
                    (fixture.root/'local/owner.json').unlink()
                else:
                    if mode == 'pending': owner['status'] = 'pending'
                    if mode == 'display': owner['display_confirmed'] = False
                    if mode == 'touch': owner['touch_confirmed'] = False
                    if mode == 'numeric_boolean': owner['touch_confirmed'] = 1
                    if mode == 'different_boot': owner['native_boot_id'] = str(uuid.uuid4())
                    put(fixture.root/'local/owner.json', owner)
                with self.assertRaises(M.TrialError), patch('subprocess.Popen', side_effect=AssertionError('Must not launch')):
                    fixture.check()
                self.assertFalse((fixture.root/'local/trial').exists())
                self.assertFalse((fixture.root/'local/identity.private.json').exists())

    def test_changed_helpers_receipt_payload_and_path_escape_are_rejected(self):
        for mode in ['helper', 'receipt', 'payload', 'escape', 'native_files', 'existing_trial']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                fixture = Fixture(Path(directory))
                if mode == 'helper': (fixture.root/'scripts/transfer_fx0_ram.py').write_text('changed')
                if mode == 'receipt': (fixture.root/'local/image.json').write_text('{}')
                if mode == 'payload': (fixture.root/'local/image.img').write_bytes(b'changed')
                if mode == 'escape': fixture.plan['trial_directory'] = '../escape'
                if mode == 'native_files': fixture.plan['native_expected']['files_sha256'].pop('/etc/apk/world')
                if mode == 'existing_trial': (fixture.root/'local/trial').mkdir()
                with self.assertRaises(M.TrialError): fixture.check()

    def test_rehashed_wrong_family_or_bootstrap_receipt_is_rejected(self):
        changes = {'kernel_release': '6.18.63-fx0-nfc-alpine', 'certificate_sha256': '0'*64,
                   'kernel_sha256': '0'*64, 'DTB_sha256': '0'*64, 'image_sha256': '0'*64,
                   'image_bytes': 1, 'return_after_seconds': 0, 'module_signature_enforcement': False,
                   'default_governor': 'schedutil', 'explicit_frequency_or_voltage_requests': [600000],
                   'selected_modules': {'nxp_nci.ko': {}}}
        for name, value in changes.items():
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                fixture = Fixture(Path(directory))
                path = fixture.root/'local/image.json'
                put(path, M.read_json(path) | {name: value})
                fixture.plan['image_receipt_sha256'] = M.sha(path)
                with self.assertRaises(M.TrialError): fixture.check()

    def test_real_children_pass_and_informational_PID_file_is_ignored(self):
        stopped, state, calls = self.exercise()
        self.assertFalse(stopped)
        self.assertEqual(state['result'], 'registration-and-native-return-passed')
        self.assertEqual(calls.count('reboot'), 1)
        self.assertEqual(calls.count('BOOT'), 1)
        self.assertNotIn('recover', calls)
        self.assertLess(calls.index('readback'), calls.index('BOOT'))

    def test_uncertain_reboot_and_BOOT_acknowledgements_never_replay_commands(self):
        for fault in ['reboot_ack', 'BOOT_ack']:
            with self.subTest(fault=fault):
                stopped, state, calls = self.exercise(fault)
                self.assertFalse(stopped)
                self.assertEqual(calls.count('reboot'), 1)
                self.assertEqual(calls.count('BOOT'), 1)
                self.assertNotIn('recover', calls)

    def test_pre_BOOT_failures_reap_children_before_one_native_recovery(self):
        for fault in ['transfer', 'readback', 'observer_exit']:
            with self.subTest(fault=fault):
                stopped, state, calls = self.exercise(fault)
                self.assertTrue(stopped)
                self.assertNotIn('BOOT', calls)
                self.assertEqual(calls.count('recover'), 1)
                self.assertIn('native_recovered', state)

    def test_native_identity_or_hash_drift_prevents_reboot(self):
        for fault in ['boot_id', 'native_hash']:
            with self.subTest(fault=fault):
                stopped, _, calls = self.exercise(fault)
                self.assertTrue(stopped)
                self.assertNotIn('reboot', calls)
                self.assertNotIn('observer', calls)

    def test_candidate_and_return_failures_do_not_claim_pass_or_recover_after_BOOT(self):
        for fault in ['registration', 'return_hash', 'early_return', 'panic', 'host']:
            with self.subTest(fault=fault):
                stopped, state, calls = self.exercise(fault)
                self.assertTrue(stopped)
                self.assertEqual(state['result'], 'stopped-for-inspection')
                self.assertEqual(calls.count('BOOT'), 1)
                self.assertNotIn('recover', calls)

    def test_trial_directory_reservation_prevents_replay(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            checked = fixture.check()
            backend = FakeBackend(checked)
            M.run_trial(checked, lambda _: backend)
            before = (checked['trial']/'controller.json').read_bytes()
            with self.assertRaises(FileExistsError):
                M.run_trial(checked, lambda _: self.fail('Replay must not create a backend'))
            self.assertEqual(before, (checked['trial']/'controller.json').read_bytes())

    def test_guard_remains_effective_with_python_optimization(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Fixture(Path(directory))
            (fixture.root/'local/owner.json').unlink()
            script = ('import importlib.util,json;from pathlib import Path;'
                      f"s=importlib.util.spec_from_file_location('m',{str(SPEC.origin)!r});"
                      'm=importlib.util.module_from_spec(s);s.loader.exec_module(m);'
                      f'm.check_plan(Path({str(fixture.root)!r}),json.loads({json.dumps(fixture.plan)!r}),'
                      f'json.loads({json.dumps(fixture.profile)!r}))')
            result = subprocess.run([sys.executable, '-O', '-c', script], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('confirmation is pending', result.stderr)
            self.assertFalse((fixture.root/'local/trial').exists())


class SerialEvidenceTests(unittest.TestCase):
    def capture(self, nonce):
        return (f'__TRIAL_START__{nonce}\n__KERNEL__{M.PROFILE["release"]}\n'
                f'__BOOT_ID__{uuid.uuid4()}\nSTABLE_CPR_REGISTRATION_PASS: guarded registration passed\n'
                f'__REGISTRATION_EXIT__0\n__TAINT__0\n__BOOT_HASH__{"a"*64}  /dev/mmcblk0p15\n'
                f'__TRIAL_END__{nonce}\n6,123,181741527,-;Returning to lk2nd for diagnostic retrieval\n').encode()

    def test_challenge_and_raw_kernel_timer_record_are_required(self):
        nonce = uuid.uuid4().hex
        data = self.capture(nonce)
        result = M.parse_serial(data, nonce)
        self.assertAlmostEqual(result['timer_uptime_seconds'], 181.741527)
        self.assertTrue(result['panic_free'])
        for altered in [data.replace(nonce.encode(), b'other'), data.split(b'6,123')[0],
                        data+data.split(b'__TRIAL_END__')[1].split(b'\n', 1)[1],
                        data.replace(b'__TAINT__0', b'__TAINT__0\n__TAINT__0')]:
            with self.subTest(altered=altered[-90:]), self.assertRaises(M.TrialError):
                M.parse_serial(altered, nonce)

    def test_kernel_fault_after_registration_is_still_a_failure(self):
        nonce = uuid.uuid4().hex
        result = M.parse_serial(self.capture(nonce)+b'3,124,181900000,-;Kernel panic - not syncing\n', nonce)
        self.assertFalse(result['panic_free'])


class SerialObserverPtyTests(unittest.TestCase):
    def exercise(self, cancel=False):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            trial = base/'trial'
            trial.mkdir()
            usb = base/'usb/1-7'
            usb.mkdir(parents=True)
            for name, value in [('idVendor', '1d6b'), ('idProduct', '0104'), ('serial', 'fx0-diagnostic')]:
                (usb/name).write_text(value)
            tty = base/'tty/ttyACM999'
            tty.mkdir(parents=True)
            (tty/'device').symlink_to(usb, target_is_directory=True)
            nonce = uuid.uuid4().hex
            master, slave = os.openpty()
            original_open = os.open
            original_read_text, original_resolve, original_glob = Path.read_text, Path.resolve, Path.glob
            errors, commands = [], []
            physical = Path('/sys/bus/usb/devices/1-7')

            def read_text(path, *args, **kwargs):
                if path.is_relative_to(physical):
                    path = usb/path.relative_to(physical)
                return original_read_text(path, *args, **kwargs)

            def resolve(path, *args, **kwargs):
                return original_resolve(usb if path == physical else path, *args, **kwargs)

            def glob(path, pattern):
                return iter([tty]) if path == Path('/sys/class/tty') else original_glob(path, pattern)

            def open_fd(path, flags, *args, **kwargs):
                if path == '/dev/ttyACM999':
                    fd = os.dup(slave)
                    os.set_blocking(fd, False)
                    return fd
                return original_open(path, flags, *args, **kwargs)

            def device():
                try:
                    deadline = time.monotonic()+5
                    while not (trial/'observer-ready.json').exists():
                        if time.monotonic() > deadline: raise AssertionError('Observer not ready')
                        time.sleep(.005)
                    # Correct challenge with a wrong image must not arm serial.
                    put(trial/'armed.json', dict(nonce=nonce, image_sha256='0'*64))
                    self.assertFalse(select.select([master], [], [], .1)[0])
                    if cancel:
                        return
                    put(trial/'armed.json', dict(nonce=nonce, image_sha256=M.PROFILE['image_sha256']))
                    self.assertTrue(select.select([master], [], [], 3)[0])
                    commands.append(os.read(master, 65536))
                    data = SerialEvidenceTests().capture(nonce)
                    os.write(master, data)
                    capture = trial/'serial.private.txt'
                    while not capture.exists() or capture.stat().st_size < len(data):
                        if time.monotonic() > deadline: raise AssertionError('Capture did not complete')
                        time.sleep(.005)
                    (usb/'idVendor').write_text('18d1')
                except BaseException as error:
                    errors.append(error)
                finally:
                    put(trial/'stop.json', dict(nonce=nonce))

            worker = threading.Thread(target=device)
            with patch.object(Path, 'read_text', read_text), patch.object(Path, 'resolve', resolve), \
                    patch.object(Path, 'glob', glob), patch('os.open', open_fd):
                worker.start()
                try:
                    code = M.observe(trial, '1-7', nonce)
                finally:
                    put(trial/'stop.json', dict(nonce=nonce))
                    worker.join(timeout=6)
                    os.close(master)
                    os.close(slave)
            self.assertFalse(worker.is_alive())
            self.assertFalse(errors, errors)
            return code, M.read_json(trial/'observation.json'), commands

    def test_actual_observer_arms_once_and_captures_complete_pty_evidence(self):
        code, report, commands = self.exercise()
        self.assertEqual(code, 0)
        self.assertTrue(report['sent'])
        self.assertEqual(len(commands), 1)
        self.assertEqual(commands[0].count(b'/bin/cpr-register'), 1)
        self.assertIn(b'cat /dev/kmsg', commands[0])
        self.assertAlmostEqual(report['proof']['timer_uptime_seconds'], 181.741527)

    def test_unarmed_cancellation_exits_without_any_serial_command(self):
        code, report, commands = self.exercise(cancel=True)
        self.assertEqual(code, 0)
        self.assertFalse(report['sent'])
        self.assertEqual(commands, [])
        self.assertNotIn('proof', report)


if __name__ == '__main__':
    unittest.main()
