#!/usr/bin/env python3
"""Own one stable CPR RAM trial, from an exact native UI gate to native return.

--run owns entry; its internal --observe child accesses diagnostic USB serial.
--check validates local inputs only. The private trial directory is reserved
once, and a BOOT acknowledgement failure is never replayed.
The two child helpers have no children of their own. Keep their Popen objects
until wait() returns; saved PIDs are informational only.
"""
import argparse
import datetime
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import select
import shlex
import subprocess
import sys
import termios
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
PROFILE = {
    'release': '6.18.63-fx0-cpr-nfc-alpine',
    'image_sha256': 'ef74c1beec542aa6eaaf7f30c98e15b4c3fb3db1de5853359251ef569643aa85',
    'image_bytes': 6244352,
    'kernel_sha256': '799bd981b46acd417041de4391e09ca07b3180308b0ca25362ea07e574106b04',
    'DTB_sha256': '0659e7bd3077f4c2895dcd4bee071b2f7c154a8933d211741a6313c54e6d04fe',
    'certificate_sha256': '4bee8da2c53bee3d50f65875614036a96c3be1b23aedcd896336dde1147ae748',
}
HELPERS = {
    'diagnostics/cpu-cpr-runtime/stable_ram.py',
    'diagnostics/cpu-cpr-runtime/register-stable.sh',
    'scripts/transfer_fx0_ram.py', 'scripts/boot_fx0_ram.py', 'local/nura_client.py',
}
NATIVE_FILES = {'/boot/vmlinuz', '/boot/initramfs', '/boot/boot.img',
                '/lib/apk/db/installed', '/etc/apk/world'}


class TrialError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise TrialError(message)


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def local_path(root, value):
    require(isinstance(value, str) and not Path(value).is_absolute(), 'Expected a relative local path')
    path = (root/value).resolve()
    require(path.is_relative_to(root/'local') and path != root/'local', 'Path escapes private local storage')
    return path


def write_json(path, value, *, first=False):
    data = (json.dumps(value, indent=2)+'\n').encode()
    if first:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    else:
        temporary = path.with_suffix('.tmp')
        with temporary.open('wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.chmod(0o600)
        temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def check_plan(root, plan, profile=None):
    root = Path(root).resolve()
    profile = PROFILE if profile is None else profile
    require(plan.get('schema') == 1, 'Unsupported trial plan')
    native = plan['native_expected']
    require(str(uuid.UUID(native['boot_id'])) == native['boot_id'], 'Invalid native boot identity')
    # This is deliberately before helper imports, private identity reads, state
    # creation, SSH, USB opens or process launches.
    owner_path = local_path(root, plan['owner_confirmation'])
    require(owner_path.is_file(), 'Current native display/touch confirmation is pending')
    owner = read_json(owner_path)
    require(owner.get('status') == 'confirmed' and owner.get('display_confirmed') is True
            and owner.get('touch_confirmed') is True, 'Current native display/touch confirmation is pending')
    require(owner.get('native_boot_id') == native['boot_id'], 'Owner answer belongs to a different boot')
    require(re.fullmatch(r'[0-9a-f]{64}', native['raw_boot_sha256']) is not None, 'Invalid native boot hash')
    require(set(native['files_sha256']) == NATIVE_FILES, 'Incomplete native payload/package baseline')
    require(all(re.fullmatch(r'[0-9a-f]{64}', v) for v in native['files_sha256'].values()), 'Invalid baseline file hash')
    require(bool(re.fullmatch(r'[0-9A-Za-z.+_-]+', native['kernel'])), 'Invalid native kernel release')
    require(re.fullmatch(r'[0-9]+-[0-9]+(?:\.[0-9]+)*', plan['USB_port']) is not None, 'Invalid physical USB port')
    require(set(plan['helper_sha256']) == HELPERS, 'Incomplete helper identity map')
    for name, digest in plan['helper_sha256'].items():
        require(sha(root/name) == digest, 'A pinned trial helper changed: '+name)
    receipt_path = local_path(root, plan['image_receipt'])
    require(sha(receipt_path) == plan['image_receipt_sha256'], 'Image receipt changed')
    image = read_json(receipt_path)
    for name in ['image_sha256', 'image_bytes', 'kernel_sha256', 'DTB_sha256', 'certificate_sha256']:
        require(image[name] == profile[name], 'Wrong stable image family: '+name)
    require(image['kernel_release'] == profile['release'], 'Wrong kernel release')
    require(image['return_after_seconds'] == 180 and image['module_signature_enforcement'] is True
            and image['default_governor'] == 'userspace', 'Wrong RAM bootstrap or return timer')
    require(image['explicit_frequency_or_voltage_requests'] == [], 'Registration trial must not request performance')
    require(set(image['selected_modules']) == {'cpufreq_userspace.ko', 'cpufreq-dt.ko'}, 'Wrong module selection')
    require(image['init_BusyBox_HTTP_timer_and_cmdline_unchanged'] is True
            and image['header_digest_addresses_and_ramdisk_readback_verified'] is True,
            'RAM image qualification is incomplete')
    payload = local_path(root, image['image_path'])
    require(payload.stat().st_size == profile['image_bytes'] and sha(payload) == profile['image_sha256'],
            'RAM image bytes changed')
    trial = local_path(root, plan['trial_directory'])
    require(trial.parent.is_dir() and not trial.exists(), 'Trial directory already exists or parent is absent; inspect before any retry')
    identity = local_path(root, plan['private_identity'])
    return dict(root=root, plan=plan, owner=owner, image=image, payload=payload,
                trial=trial, identity=identity, profile=profile)


def validate_native(actual, expected, *, returned=False):
    require(actual['kernel'] == expected['kernel'], 'Native kernel changed')
    require((actual['boot_id'] != expected['boot_id']) if returned else
            (actual['boot_id'] == expected['boot_id']), 'Unexpected native boot identity')
    require(actual['raw_boot_sha256'] == expected['raw_boot_sha256'], 'Persistent boot bytes changed')
    require(actual['files_sha256'] == expected['files_sha256'], 'Native payload/package baseline changed')
    require(actual['taint'] == 0 and actual['systemd'] == 'running' and not actual['failed_units']
            and not actual['jobs'], 'Native kernel/services are not ready')
    require(actual['Sway_count'] == actual['gesture_count'] == 1
            and actual['sensor_proxy'] == 'active', 'Native graphical/input services are not ready')
    require(actual['APC_registers'] == {'0x1740': 1, '0x1741': 115}, 'Native APC target is not restored')
    require(actual['governor'] == 'schedutil' and actual['available_frequencies'] == [300000, 384000, 600000, 787200],
            'Native CPU policy changed')
    require(len(actual['temperatures_mC']) == 2 and all(-40000 <= t < 60000 for t in actual['temperatures_mC']),
            'Native thermal precondition failed')


def validate_observation(report, expected, nonce):
    require(report.get('nonce') == nonce and report.get('state') == 'terminal', 'Wrong or incomplete serial observation')
    proof = report.get('proof', {})
    require(proof.get('kernel') == expected['profile']['release'], 'Candidate kernel not proved')
    require(str(uuid.UUID(proof['boot_id'])) == proof['boot_id']
            and proof['boot_id'] != expected['plan']['native_expected']['boot_id'], 'Candidate boot identity not proved')
    require(proof.get('registration_exit') == 0 and proof.get('registration_pass') is True,
            'Guarded CPU module registration did not pass')
    require(proof.get('taint') == 0 and proof.get('raw_boot_sha256') == expected['plan']['native_expected']['raw_boot_sha256'],
            'Candidate taint or persistent boot check failed')
    require(proof.get('complete') is True and not report.get('error'), 'Candidate serial evidence is incomplete')
    require(proof.get('timer_uptime_seconds', 0) >= 180 and proof.get('panic_free') is True,
            'Independent return timer or kernel health is not proved')


def run_trial(checked, backend_factory):
    trial = checked['trial']
    trial.mkdir(mode=0o700)  # Atomic reservation: no separate CLI BOOT step.
    state_path = trial/'controller.json'
    state = dict(started_UTC=now(), phase='reserved', boot_attempted=False,
                 reboot_requested=False, image_sha256=checked['image']['image_sha256'])
    write_json(state_path, state, first=True)
    backend = None
    observer = transfer = None
    failure = None
    nonce = uuid.uuid4().hex

    def phase(value):
        state['phase'] = value
        write_json(state_path, state)

    try:
        backend = backend_factory(checked)
        state['host_before'] = backend.host_state()
        phase('native preflight')
        before = backend.native_state()
        validate_native(before, checked['plan']['native_expected'])
        state['native_before'] = before
        require(backend.usb_mode() == 'native', 'Native USB identity changed')
        observer = backend.start_observer(nonce)
        backend.wait_observer_ready(observer, nonce)
        require(observer.poll() is None, 'Serial observer exited before reboot')
        phase('native reboot requested once')
        state['reboot_requested'] = True
        write_json(state_path, state)
        # A lost SSH reply does not authorize another reboot request.
        try:
            backend.reboot_bootloader()
        except Exception as error:
            state['reboot_acknowledgement_uncertain'] = type(error).__name__
            write_json(state_path, state)
        backend.wait_bootloader()
        phase('data-only transfer')
        transfer = backend.start_transfer()
        state['transfer_PID_informational'] = transfer.pid
        write_json(state_path, state)
        require(transfer.wait() == 0, 'RAM transfer failed; BOOT is forbidden')
        backend.verify_readback()
        require(observer.poll() is None, 'Serial observer exited; BOOT is forbidden')
        require(backend.usb_mode() == 'bootloader', 'Bootloader identity changed before BOOT')
        write_json(trial/'armed.json', dict(nonce=nonce, image_sha256=state['image_sha256']), first=True)
        state['boot_attempted'] = True
        phase('one BOOT requested')  # Durable before the command can be sent.
        try:
            backend.boot_once()
        except Exception as error:
            state['BOOT_acknowledgement_uncertain'] = type(error).__name__
            write_json(state_path, state)
        phase('waiting for independent timed native return')
        after = backend.wait_native_return()
        validate_native(after, checked['plan']['native_expected'], returned=True)
        state['native_after'] = after
        write_json(trial/'stop.json', dict(nonce=nonce), first=True)
        require(observer.wait() == 0, 'Serial observer failed')
        validate_observation(read_json(trial/'observation.json'), checked, nonce)
        require(backend.host_state() == state['host_before'], 'Host routes or resolver changed')
        state.update(result='registration-and-native-return-passed', physical_UI_after_return='pending')
    except BaseException as error:
        failure = error
        state.update(result='stopped-for-inspection', failure_type=type(error).__name__, failed_phase=state['phase'])
    finally:
        # Never infer termination from a PID file or send recovery while an
        # owned USB transfer still exists. These helpers do not fork children.
        if transfer is not None:
            state['transfer_terminal_code'] = transfer.wait()
        if observer is not None:
            stop = trial/'stop.json'
            if not stop.exists():
                write_json(stop, dict(nonce=nonce), first=True)
            state['observer_terminal_code'] = observer.wait()
        if failure is not None and backend is not None and state['reboot_requested'] and not state['boot_attempted']:
            try:
                if backend.usb_mode() == 'bootloader':
                    state['pre_BOOT_native_recovery_requested_once'] = True
                    write_json(state_path, state)
                    backend.recover_native_once()
                    recovered = backend.wait_native_return()
                    validate_native(recovered, checked['plan']['native_expected'], returned=True)
                    state['native_recovered'] = recovered
            except Exception as error:
                state['recovery_needs_inspection'] = type(error).__name__
        if backend is not None:
            try:
                state['host_after'] = backend.host_state()
                state['host_state_unchanged'] = state.get('host_before') == state['host_after']
            except Exception as error:
                state['host_postflight_error'] = type(error).__name__
            backend.close()
        state.update(finished_UTC=now(), owned_children_terminal=True)
        write_json(state_path, state)
    if failure is not None:
        raise TrialError('Trial stopped in '+state['failed_phase']+'; inspect its private receipts; never replay this directory') from None
    return state


NATIVE_PROBE = r'''
import hashlib,json,os,subprocess
from pathlib import Path
def output(*args):return subprocess.run(args,capture_output=True,text=True,timeout=15).stdout.strip()
def sha(name):
 with open(name,'rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
files=['/boot/vmlinuz','/boot/initramfs','/boot/boot.img','/lib/apk/db/installed','/etc/apk/world']
processes=output('ps','-e','-o','comm=').splitlines()
fd=os.open('/sys/kernel/debug/regmap/0-01/registers',os.O_RDONLY);rows={}
try:
 if Path('/sys/kernel/debug/regmap/0-01/range').read_text().strip()!='0-ffff':raise ValueError('dense map differs')
 for address in [0x1740,0x1741]:
  row=os.pread(fd,9,address*9).decode()
  if len(row)!=9 or not row.startswith(f'{address:04x}: '):raise ValueError('wrong PMIC row')
  rows[hex(address)]=int(row[6:8],16)
finally:os.close(fd)
policy=Path('/sys/devices/system/cpu/cpufreq/policy0')
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),kernel=output('uname','-r'),raw_boot_sha256=sha('/dev/mmcblk0p15'),files_sha256={p:sha(p) for p in files},taint=int(Path('/proc/sys/kernel/tainted').read_text()),systemd=output('systemctl','is-system-running'),failed_units=output('systemctl','--failed','--no-legend'),jobs=output('systemctl','list-jobs','--no-legend'),Sway_count=processes.count('sway'),gesture_count=processes.count('lisgd'),sensor_proxy=output('systemctl','is-active','iio-sensor-proxy'),APC_registers=rows,governor=(policy/'scaling_governor').read_text().strip(),available_frequencies=list(map(int,(policy/'scaling_available_frequencies').read_text().split())),temperatures_mC=[int(p.read_text()) for p in Path('/sys/class/thermal').glob('thermal_zone*/temp')])) )
'''


class NativeBackend:
    def __init__(self, checked):
        self.checked = checked
        self.root, self.trial = checked['root'], checked['trial']
        identity = read_json(checked['identity'])
        self.serial = identity['serial']
        require(isinstance(self.serial, str) and bool(self.serial), 'Missing private USB identity')
        self.port = Path('/sys/bus/usb/devices')/checked['plan']['USB_port']
        require(Path(identity['USB_port']).resolve() == self.port.resolve(), 'Private physical USB identity changed')
        spec = importlib.util.spec_from_file_location('fx0_native_client', self.root/'local/nura_client.py')
        self.native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.native)
        sys.path.insert(0, str(self.root/'scripts'))
        import boot_fx0_ram
        self.boot = boot_fx0_ram
        self.logs = []

    def close(self):
        for log in self.logs:
            log.close()

    def host_state(self):
        return dict(default_routes=json.loads(subprocess.check_output(['ip', '-j', 'route', 'show', 'default'])),
                    resolver_sha256=sha('/etc/resolv.conf'))

    def native_state(self):
        return json.loads(self.native.run('python3 -E -B -c '+shlex.quote(NATIVE_PROBE), root=True, timeout=50))

    def usb_mode(self):
        def value(name):
            try:
                return (self.port/name).read_text().strip()
            except OSError:
                return None
        pair = value('idVendor'), value('idProduct')
        if pair == ('18d1', 'd001') and value('serial') == self.serial:
            return 'native'
        if pair == ('18d1', 'd00d') and value('serial') == self.serial:
            return 'bootloader'
        if pair == ('1d6b', '0104') and value('serial') == 'fx0-diagnostic':
            return 'diagnostic'
        return 'other-or-absent'

    def spawn(self, args, name):
        log = (self.trial/(name+'.private.log')).open('xb')
        self.logs.append(log)
        return subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

    def start_observer(self, nonce):
        return self.spawn([sys.executable, '-E', '-B', str(Path(__file__).resolve()), '--observe',
                           str(self.trial), self.checked['plan']['USB_port'], nonce], 'observer')

    def wait_observer_ready(self, process, nonce):
        for _ in range(100):
            require(process.poll() is None, 'Serial observer stopped before readiness')
            path = self.trial/'observer-ready.json'
            if path.exists():
                require(read_json(path) == dict(nonce=nonce, USB_port=self.checked['plan']['USB_port']), 'Wrong observer readiness challenge')
                return
            time.sleep(.1)
        raise TrialError('Serial observer readiness deadline')

    def reboot_bootloader(self):
        self.native.run('systemctl reboot --reboot-argument=bootloader', root=True, timeout=40)

    def wait_bootloader(self):
        for _ in range(100):
            if self.usb_mode() == 'bootloader':
                self.boot.query(self.serial)
                return
            time.sleep(1)
        raise TrialError('Expected bootloader did not appear')

    def start_transfer(self):
        return self.spawn([sys.executable, '-E', '-B', str(self.root/'scripts/transfer_fx0_ram.py'),
                           '--serial', self.serial, '--payload', str(self.checked['payload']),
                           '--sha256', self.checked['image']['image_sha256'], '--output', str(self.trial/'transfer'),
                           '--pace-ms', '5'], 'transfer')

    def verify_readback(self):
        record = read_json(self.trial/'transfer/result.json')
        require(record['state'] == 'verified' and record['readback_sha256'] == self.checked['image']['image_sha256'], 'Transfer did not verify')
        require((self.trial/'transfer/readback.bin').read_bytes() == self.checked['payload'].read_bytes(), 'Transfer readback bytes differ')

    def boot_once(self):
        self.boot.query(self.serial, boot=True)

    def recover_native_once(self):
        require(self.usb_mode() == 'bootloader', 'Native recovery requires the same bootloader')
        self.boot.query(self.serial)  # Require a synchronized identity reply.
        with (self.trial/'native-recovery.private.log').open('xb') as log:
            subprocess.run(['fastboot', '-s', self.serial, 'reboot'], stdout=log, stderr=subprocess.STDOUT, check=True)

    def wait_native_return(self):
        deadline = time.monotonic()+600
        while time.monotonic() < deadline:
            if self.usb_mode() == 'native':
                try:
                    current = self.native_state()
                    validate_native(current, self.checked['plan']['native_expected'], returned=True)
                    return current
                except Exception:
                    pass
            time.sleep(2)
        raise TrialError('Native return needs inspection; no automatic command retry')


def parse_serial(data, nonce):
    text = data.decode(errors='replace').replace('\r', '')
    require('__TRIAL_START__'+nonce+'\n' in text and '__TRIAL_END__'+nonce+'\n' in text,
            'Incomplete serial challenge')
    timers = re.findall(r'^\d+,\d+,(\d+),[^;\n]*;Returning to lk2nd for diagnostic retrieval$', text, re.M)
    require(len(timers) == 1, 'Independent return timer record is missing or duplicated')
    panic_free = not re.search(r'Kernel panic|\bOops:|\bBUG:|WARNING: CPU:|CFI failure|soft lockup|hard LOCKUP', text)
    text = text.split('__TRIAL_START__'+nonce+'\n', 1)[1].split('__TRIAL_END__'+nonce+'\n', 1)[0]
    def field(name):
        matches = re.findall(r'^__'+name+r'__(.+)$', text, re.M)
        require(len(matches) == 1, 'Missing or duplicate serial field: '+name)
        return matches[0]
    boot_hash = field('BOOT_HASH')
    require(re.fullmatch(r'[0-9a-f]{64}  /dev/mmcblk0p15', boot_hash) is not None, 'Wrong serial boot hash row')
    return dict(kernel=field('KERNEL'), boot_id=field('BOOT_ID'), registration_exit=int(field('REGISTRATION_EXIT')),
                registration_pass=bool(re.search(r'^STABLE_CPR_REGISTRATION_PASS: .+$', text, re.M)),
                taint=int(field('TAINT')), raw_boot_sha256=boot_hash.split()[0], complete=True,
                timer_uptime_seconds=int(timers[0])/1e6, panic_free=panic_free)


def observe(trial, usb_port, nonce):
    require(re.fullmatch(r'[0-9a-f]{32}', nonce) is not None, 'Invalid observer challenge')
    trial = Path(trial).resolve()
    port = Path('/sys/bus/usb/devices')/usb_port
    def value(name):
        try:
            return (port/name).read_text().strip()
        except OSError:
            return None
    def diagnostic():
        return (value('idVendor'), value('idProduct'), value('serial')) == ('1d6b', '0104', 'fx0-diagnostic')
    def stopped():
        path = trial/'stop.json'
        return path.exists() and read_json(path).get('nonce') == nonce
    def same_parent(path):
        return any(p.resolve() == port.resolve() for p in [path, *path.parents] if (p/'idVendor').exists())
    report = dict(started_UTC=now(), nonce=nonce, state='waiting', sent=False)
    write_json(trial/'observer-ready.json', dict(nonce=nonce, USB_port=usb_port), first=True)
    fd = None
    capture = bytearray()
    try:
        deadline = time.monotonic()+600
        while time.monotonic() < deadline:
            if stopped():
                break
            armed = trial/'armed.json'
            if (diagnostic() and armed.exists() and read_json(armed).get('nonce') == nonce
                    and read_json(armed).get('image_sha256') == PROFILE['image_sha256']):
                matches = [p for p in Path('/sys/class/tty').glob('ttyACM*') if same_parent((p/'device').resolve())]
                require(len(matches) <= 1, 'Multiple serial devices on selected port')
                if matches:
                    try:
                        fd = os.open('/dev/'+matches[0].name, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
                        break
                    except PermissionError:
                        pass
            time.sleep(.1)
        if fd is not None:
            require(diagnostic(), 'USB identity changed before serial configuration')
            attrs = termios.tcgetattr(fd)
            attrs[0] = attrs[1] = attrs[3] = 0
            attrs[2] = termios.CS8 | termios.CREAD | termios.CLOCAL
            attrs[4] = attrs[5] = termios.B115200
            attrs[6][termios.VMIN] = 0
            attrs[6][termios.VTIME] = 1
            termios.tcsetattr(fd, termios.TCSANOW, attrs)
            command = (f"printf '__TRIAL_START__%s\\n' {nonce}; printf '__KERNEL__'; uname -r; "
                       "printf '__BOOT_ID__'; cat /proc/sys/kernel/random/boot_id; /bin/cpr-register; "
                       "registration_status=$?; printf '__REGISTRATION_EXIT__%s\\n' \"$registration_status\"; "
                       "printf '__TAINT__'; cat /proc/sys/kernel/tainted; printf '__BOOT_HASH__'; "
                       f"sha256sum /dev/mmcblk0p15; printf '__TRIAL_END__%s\\n' {nonce}; cat /dev/kmsg")
            payload = ('\nexec /bin/sh -c '+shlex.quote(command)+'\n').encode()
            write_json(trial/'serial-request.json', dict(nonce=nonce, command_sha256=hashlib.sha256(payload).hexdigest()), first=True)
            require(os.write(fd, payload) == len(payload), 'Short serial command write; never resend')
            report['sent'] = True
            with (trial/'serial.private.txt').open('xb', buffering=0) as output:
                while time.monotonic() < deadline and not stopped():
                    if not diagnostic():
                        break
                    ready, _, _ = select.select([fd], [], [], .2)
                    if ready:
                        try:
                            data = os.read(fd, 65536)
                        except BlockingIOError:
                            continue
                        except OSError as error:
                            if error.errno in [errno.EIO, errno.ENODEV] and not diagnostic():
                                break
                            raise
                        if not data:
                            break
                        require(len(capture)+len(data) <= 16*1024*1024, 'Serial capture exceeded its bound')
                        output.write(data)
                        capture.extend(data)
            report['proof'] = parse_serial(capture, nonce)
    except Exception as error:
        report['error'] = type(error).__name__
    finally:
        if fd is not None:
            os.close(fd)
        report.update(finished_UTC=now(), state='terminal', serial_bytes=len(capture))
        write_json(trial/'observation.json', report, first=True)
    return 1 if report.get('error') else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observe', nargs=3, metavar=('TRIAL', 'USB_PORT', 'NONCE'))
    parser.add_argument('--plan', type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--check', action='store_true')
    modes.add_argument('--run', action='store_true')
    args = parser.parse_args()
    os.umask(0o077)
    if args.observe:
        require(args.plan is None and not args.check and not args.run, 'Observer cannot enter the phone')
        return observe(*args.observe)
    require(args.plan is not None and (args.check or args.run), 'Select --plan and --check or --run')
    checked = check_plan(ROOT, read_json(args.plan))
    if args.check:
        print('Local image, helper and exact native owner inputs verified; no phone command sent')
        return 0
    state = run_trial(checked, NativeBackend)
    print(state['result']+'; physical display/touch confirmation of the new native return is pending')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(type(error).__name__+': '+str(error), file=sys.stderr)
        raise SystemExit(1)
