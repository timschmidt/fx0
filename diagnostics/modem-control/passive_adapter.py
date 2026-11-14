# SPDX-License-Identifier: MIT
"""Public Fx0 passive-r1 adapter; private inputs require a reviewed plan digest."""
import argparse
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys
import time


IMAGE_SHA256 = '428779913614a376bd40844bf80b10d004de0571d721b1bb29b85b68f31d4f53'
IMAGE_BYTES = 6785024
ANSWER = 'Available; display and touch work'
SOURCES = {
    'diagnostics/modem-control/passive_adapter.py',
    'diagnostics/modem-control/passive_trial.py',
    'diagnostics/modem-control/passive_runtime.py',
    'diagnostics/modem-control/passive_serial.py',
    'diagnostics/modem-control/passive_observer.py',
    'diagnostics/modem-control/passive_native_probe.py',
    'scripts/boot_fx0_ram.py', 'scripts/transfer_fx0_ram.py',
}
FIELDS = {
    'format', 'repository_root', 'workspace', 'image_path', 'image_SHA256',
    'image_bytes', 'image_audit_path', 'image_audit_SHA256', 'baseline_boot_id',
    'workspace_inputs_SHA256', 'source_files_SHA256', 'credential_client',
    'device_record', 'usb_port', 'host_index_path', 'host_index_SHA256', 'port_lock_path',
}


class PlanRejected(RuntimeError):
    pass


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    try:
        return path.read_text().strip()
    except OSError:
        return None


def source_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def regular(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
        raise PlanRejected('Expected an owned regular input file')
    if info.st_mode & 0o022:
        raise PlanRejected('Input must not be writable by another account')
    return info


class Context:
    def __init__(self, path, expected):
        if sys.flags.optimize:
            raise PlanRejected('Optimized Python is forbidden')
        if re.fullmatch('[a-f0-9]{64}', expected) is None:
            raise PlanRejected('Reviewed plan SHA256 required')
        self.path = Path(path).absolute()
        if stat.S_IMODE(regular(self.path).st_mode) != 0o600:
            raise PlanRejected('Private plan must have mode 0600')
        if self.path.stat().st_size > 131072 or sha(self.path) != expected:
            raise PlanRejected('Private plan digest or size mismatch')
        self.expected = expected
        self.plan = json.loads(self.path.read_text())
        p = self.plan
        if set(p) != FIELDS or p['format'] != 1:
            raise PlanRejected('Unexpected private plan schema')
        self.root = Path(p['repository_root'])
        self.workspace = Path(p['workspace'])
        if not self.root.is_absolute() or not self.workspace.is_absolute():
            raise PlanRejected('Absolute source and workspace paths required')
        info = self.workspace.lstat()
        if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
            raise PlanRejected('Private owned mode-0700 workspace required')
        if self.path.parent != self.workspace:
            raise PlanRejected('Plan must be inside its private workspace')
        if (self.root/'diagnostics/modem-control/passive_adapter.py').resolve() != Path(__file__).resolve():
            raise PlanRejected('Plan does not identify the executing public adapter')
        if p['image_SHA256'] != IMAGE_SHA256 or p['image_bytes'] != IMAGE_BYTES:
            raise PlanRejected('Plan must identify the qualified passive-r1 image')
        if set(p['source_files_SHA256']) != SOURCES or set(p['workspace_inputs_SHA256']) != {'before.json', 'preparation.json'}:
            raise PlanRejected('Exact noncredential input roster required')
        if re.fullmatch(r'[0-9]+-[0-9]+(?:\.[0-9]+)*', p['usb_port']) is None:
            raise PlanRejected('Invalid selected USB port')
        for name in ['image_path', 'image_audit_path', 'credential_client', 'device_record', 'host_index_path', 'port_lock_path']:
            if not Path(p[name]).is_absolute():
                raise PlanRejected('Explicit absolute private input paths required')
        if Path(p['port_lock_path']).name != 'fx0-ram-port-' + p['usb_port'] + '.lock':
            raise PlanRejected('Shared selected-port lock path required')
        self.owner_path = self.workspace/'owner-availability.json'
        self.probe_path = self.root/'diagnostics/modem-control/passive_native_probe.py'
        self.observer_path = self.root/'diagnostics/modem-control/passive_observer.py'
        self.index_path = Path(p['host_index_path'])

    def verify_inputs(self):
        p = self.plan
        if sha(self.path) != self.expected:
            raise PlanRejected('Reviewed plan changed')
        excluded = {Path(p[name]).resolve() for name in ['credential_client', 'device_record']}
        checks = [(self.root/name, value) for name, value in p['source_files_SHA256'].items()]
        checks += [(self.workspace/name, value) for name, value in p['workspace_inputs_SHA256'].items()]
        checks += [(Path(p['image_path']), p['image_SHA256']),
                   (Path(p['image_audit_path']), p['image_audit_SHA256']),
                   (self.index_path, p['host_index_SHA256'])]
        for path, expected in checks:
            if path.resolve() in excluded or path.suffix in {'.rsa', '.pem', '.key'} or path.name in {'shadow', 'gshadow'}:
                raise PlanRejected('Credential/device-record bodies cannot enter the hash roster')
            regular(path)
            if re.fullmatch('[a-f0-9]{64}', expected) is None or sha(path) != expected:
                raise PlanRejected('Noncredential input digest mismatch')
        image = Path(p['image_path'])
        before = json.loads((self.workspace/'before.json').read_text())
        preparation = json.loads((self.workspace/'preparation.json').read_text())
        proof = json.loads(Path(p['image_audit_path']).read_text())
        if image.stat().st_size != IMAGE_BYTES or before['boot_id'] != p['baseline_boot_id'] or before['trial']:
            raise PlanRejected('Image or baseline identity mismatch')
        if before['kernel'] != '6.18.63-fx0-vibrator-alpine' or before['kernel_notes_SHA256'] != '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377':
            raise PlanRejected('Accepted r1 kernel identity required')
        if (self.root/preparation['image_path']).resolve() != image.resolve() or preparation['image_SHA256'] != IMAGE_SHA256 or preparation['image_bytes'] != IMAGE_BYTES:
            raise PlanRejected('Workspace preparation does not match the reviewed image')
        if proof['image_SHA256'] != IMAGE_SHA256 or not proof['initial_shell_alias_and_all_script_interpreters_present'] or not proof['GNU_cpio_independent_extraction_matches_every_entry']:
            raise PlanRejected('Independent image qualification missing')

    def check_operator(self):
        regular(self.owner_path)
        owner = json.loads(self.owner_path.read_text())
        age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(owner['recorded_UTC'])).total_seconds()
        if owner['answer'] != ANSWER or owner['boot_id'] != self.plan['baseline_boot_id'] or owner['image_SHA256'] != IMAGE_SHA256 or not 0 <= age < 600:
            raise PlanRejected('Specific fresh operator/image/baseline receipt required')


def wait_ssh(probe, observe, seconds=180, clock=time.monotonic, pause=time.sleep):
    deadline = clock() + seconds
    while clock() < deadline:
        try:
            result = probe()
        except subprocess.TimeoutExpired:
            observe(dict(timeout=True))
        else:
            observe(dict(returncode=result.returncode))
            if result.returncode == 0:
                return
        pause(2)
    raise RuntimeError('Native USB returned; pinned SSH not yet reachable')


def adapter_type(context, services):
    """Bind reviewed inputs and transport providers; tests supply offline providers.

    CLI callers cannot choose provider code through the plan. Its real providers
    are loaded only after the digest/input/operator barriers succeed.
    """
    if sys.flags.optimize:
        raise PlanRejected('Optimized Python is forbidden')
    root = context.root
    base = context.workspace
    owner_path = context.owner_path
    n = services['n']
    boot = services['boot']
    runtime = services['runtime']
    AttemptJournal = runtime.AttemptJournal
    wait_owned = services.get('wait_owned', runtime.wait_owned)
    wait_native = services.get('wait_ssh', wait_ssh)
    subprocess = services.get('subprocess', globals()['subprocess'])
    time = services.get('time', globals()['time'])
    fcntl = services.get('fcntl', globals()['fcntl'])
    read = services.get('read', globals()['read'])
    sha = globals()['sha']
    now = globals()['now']

    class Real:

        def __init__(self, device_record=None):
            context.check_operator()
            context.verify_inputs()
            self.port = Path('/sys/bus/usb/devices') / context.plan['usb_port']
            self.path = base / 'controller.json'
            self.journal = AttemptJournal(base)
            self.children = {}
            self.boot_sent = False
            self.state = dict(started_UTC=now(), state='preflight', processes={}, BOOT_attempted=False, phone_partition_writes=False, normal_native_root_mutable_state_writes_expected=True, USB_port=context.plan['usb_port'], transfer_observation_scope='Actual owned Popen children in this one controller namespace; no cross-command PID liveness inference')
            self.image = json.loads((base / 'preparation.json').read_text())
            self.payload = root / self.image['image_path']
            self.expected = self.image['image_SHA256']
            self.serial = json.loads((Path(context.plan['device_record']) if device_record is None else Path(device_record)).read_text())['serial']
            self.before = json.loads((base / 'before.json').read_text())
            self.save()

        def save(self, **kw):
            self.state.update(kw)
            self.journal.update(self.state)

        def mode(self, vendor, product):
            return read(self.port / 'idVendor') == vendor and read(self.port / 'idProduct') == product

        def wait(self, predicate, seconds):
            end = time.monotonic() + seconds
            while time.monotonic() < end:
                if predicate():
                    return
                time.sleep(0.25)
            raise RuntimeError('Expected selected USB mode did not appear')

        def fastboot(self):
            assert self.mode('18d1', 'd00d') and read(self.port / 'serial') == self.serial and (int(read(self.port / 'speed')) == 480)
            identity = boot.query(self.serial)
            assert identity == {'product': ['OKAYlk2nd-msm8226'], 'lk2nd_version': ['OKAYfx0-pon-reboot']}
            return identity

        def preflight(self):
            context.check_operator()
            context.verify_inputs()
            assert self.mode('18d1', 'd001') and int(read(self.port / 'speed')) == 480
            self.native_generation = int(read(self.port / 'devnum'))
            self.host = dict(default_routes=json.loads(subprocess.check_output(['ip', '-j', 'route', 'show', 'default'])), resolver_sha256=sha(Path('/etc/resolv.conf')), root_index_bytes_sha256=sha(context.index_path))
            (base / 'host-before.json').write_text(json.dumps(self.host, indent=2) + '\n')
            (base / 'device-private.json').write_text(json.dumps(dict(serial=self.serial, USB_port=str(self.port)), indent=2) + '\n')
            fresh = json.loads(n.run('python3 -B -c ' + shlex.quote(context.probe_path.read_text()), root=True, timeout=60))
            for key in ['boot_id', 'kernel', 'kernel_notes_SHA256', 'trial', 'taint', 'boot_partition_sha256', 'files_sha256', 'module_tree_digest', 'modules_FSType']:
                assert fresh[key] == self.before[key], key
            assert fresh['systemd'] == 'running' and fresh['Sway'] and fresh['gesture'] and (fresh['modules_FSType'] == 'ext4') and (fresh['taint'] == 0)
            (base / 'preflight.json').write_text(json.dumps(fresh, indent=2) + '\n')
            self.save(state='exact installed r1, owner availability and passive image preflight passed', image_sha256=self.expected, native_USB_generation=self.native_generation)

        def enter(self):
            self.save(state='one native bootloader reboot requested')
            print(self.state['state'], flush=True)
            try:
                n.run('systemctl reboot --reboot-argument=bootloader', root=True, timeout=40)
            except Exception as error:
                self.save(reboot_request_observation=type(error).__name__)
            self.wait(lambda: self.mode('18d1', 'd00d'), 100)
            assert int(read(self.port / 'devnum')) != self.native_generation
            identity = self.fastboot()
            self.save(state='installed lk2nd verified', lk2nd_identity=identity, lk2nd_USB_generation=int(read(self.port / 'devnum')))

        def spawn(self, name, command):
            log = (base / (name + '.log')).open('xb')
            child = subprocess.Popen([str(a) for a in command], stdout=log, stderr=subprocess.STDOUT)
            log.close()
            self.children[name] = child
            self.state['processes'][name] = dict(PID=child.pid, started_UTC=now())
            self.save()
            return child

        def reap(self, name, timeout=None):
            child = self.children[name]
            limits = {'transfer': 180, 'observer': 400, 'normal-reboot': 45}
            result = wait_owned(child, limits[name] if timeout is None else timeout)
            self.state['processes'][name].update(result, finished_UTC=now())
            self.save()
            return result['returncode']

        def stage(self):
            self.fastboot()
            self.save(state='one data transfer and exact readback')
            print(self.state['state'], flush=True)
            self.spawn('transfer', [sys.executable, root / 'scripts/transfer_fx0_ram.py', '--serial', self.serial, '--payload', self.payload, '--sha256', self.expected, '--output', base / 'transfer', '--pace-ms', '5'])
            code = self.reap('transfer')
            try:
                result = json.loads((base / 'transfer/result.json').read_text())
            except (OSError, ValueError):
                result = {}
            expired = self.state['processes']['transfer']['process_deadline_expired']
            timeout = bool(code != 0 and (not expired) and (result.get('last_IO', {}).get('errno') == 110))
            if expired and code == 0:
                raise RuntimeError('Transfer finished at parent deadline; inspect before any device action')
            self.save(state='transfer terminal', transfer_returncode=code, transfer_timeout=timeout, transfer_process_deadline_expired=expired)
            return dict(terminal=self.children['transfer'].poll() is not None, returncode=code, timeout=timeout)

        def readback_matches(self):
            try:
                result = json.loads((base / 'transfer/result.json').read_text())
                return result['state'] == 'verified' and result['readback_sha256'] == self.expected and ((base / 'transfer/readback.bin').read_bytes() == self.payload.read_bytes())
            except (OSError, ValueError, KeyError):
                return False

        def start_observers(self):
            self.spawn('observer', [sys.executable, context.observer_path, '--workspace', base, '--usb-port', context.plan['usb_port']])
            time.sleep(0.3)

        def observers_live(self):
            return self.children['observer'].poll() is None

        def stop_observers(self):
            child = self.children['observer']
            if child.poll() is None:
                child.terminate()
            self.reap('observer', timeout=2)

        def mark_boot_attempt(self):
            assert not self.boot_sent and self.observers_live()
            self.boot_sent = True
            self.save(state='one RAM BOOT requested', BOOT_attempted=True, BOOT_attempted_UTC=now())
            print(self.state['state'], flush=True)

        def boot(self):
            self.fastboot()
            self.save(BOOT_reply=boot.query(self.serial, boot=True), state='RAM BOOT acknowledged')

        def uncertain_boot(self, error):
            self.save(state='RAM BOOT acknowledgement uncertain; observe without retry', BOOT_error=type(error).__name__)

        def finish_observers(self):
            self.save(state='observing passive serial worker and independent180s return')
            print(self.state['state'], flush=True)
            code = self.reap('observer')
            self.save(observer_returncode=code)
            if code != 0:
                raise RuntimeError('RAM observer failed; worker acceptance forbidden')

        def return_native(self, reset):
            assert not self.boot_sent and self.children['transfer'].poll() is not None
            if reset:
                assert self.mode('18d1', 'd00d') and read(self.port / 'serial') == self.serial
                node, _, _, _ = boot.device(self.serial)
                descriptor = os.open(node, os.O_RDWR)
                try:
                    fcntl.ioctl(descriptor, 21780, 0)
                finally:
                    os.close(descriptor)
                self.save(USB_transport_reset_after_terminal_timeout=True)
                time.sleep(1)
            self.fastboot()
            self.save(state='one normal reboot to installed r1 requested')
            self.spawn('normal-reboot', ['fastboot', '-s', self.serial, 'reboot'])
            assert self.reap('normal-reboot') == 0

        def native(self):
            self.save(state='waiting for native r1 USB and SSH')
            print(self.state['state'], flush=True)
            self.wait(lambda: self.mode('18d1', 'd001'), 220)
            deadline = time.monotonic() + 180
            self.state['native_SSH_attempts'] = []

            def observe(result):
                self.state['native_SSH_attempts'].append(result)
                self.save()
            wait_native(lambda: subprocess.run([*n.OPTS, 'true'], capture_output=True, timeout=10), observe)
            source = context.probe_path.read_text()
            native = json.loads(n.run('python3 -c ' + shlex.quote(source), root=True, timeout=35))
            assert native['boot_id'] != self.before['boot_id'] and native['kernel'] == self.before['kernel'] and (native['taint'] == 0) and (native['boot_partition_sha256'] == self.before['boot_partition_sha256']) and (native['installed_DB_sha256'] == self.before['files_sha256']['/lib/apk/db/installed']) and (native['world_sha256'] == self.before['files_sha256']['/etc/apk/world'])
            assert not native['trial'] and native['kernel_notes_SHA256'] == self.before['kernel_notes_SHA256'] and (native['module_tree_digest'] == self.before['module_tree_digest']) and (native['modules_FSType'] == 'ext4') and (native['files_sha256'] == self.before['files_sha256']) and (native['systemd'] == 'running') and native['Sway'] and native['gesture']
            (base / 'native-return.json').write_text(json.dumps(native, indent=2) + '\n')
            assert json.loads(subprocess.check_output(['ip', '-j', 'route', 'show', 'default'])) == self.host['default_routes'] and sha(Path('/etc/resolv.conf')) == self.host['resolver_sha256'] and (sha(context.index_path) == self.host['root_index_bytes_sha256'])
            self.save(native_return=native, host_default_routes_resolver_and_root_index_unchanged=True, native_return_USB_generation=int(read(self.port / 'devnum')))

    return Real


def main(argv=None):
    stage = 'plan'
    ops = None
    previous_umask = None
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--plan', type=Path, required=True)
        parser.add_argument('--plan-sha256', required=True)
        parser.add_argument('--check-inputs', action='store_true')
        args = parser.parse_args(argv)
        context = Context(args.plan, args.plan_sha256)
        stage = 'noncredential-inputs'
        context.verify_inputs()
        if args.check_inputs:
            print(json.dumps({'inputs_verified': True, 'credential_client_loaded': False, 'device_actions': False}))
            return 0
        stage = 'operator-receipt'
        context.check_operator()
        stage = 'client-setup'
        previous_umask = os.umask(0o077)
        # Never hash, copy or expose the credential-bearing helper body. Normal
        # module loading is deferred until the specific operator gate passes.
        native = source_module(Path(context.plan['credential_client']), 'private_native_client')
        boot = source_module(context.root/'scripts/boot_fx0_ram.py', 'qualified_boot_helper')
        runtime = source_module(context.root/'diagnostics/modem-control/passive_runtime.py', 'qualified_runtime')
        flow = source_module(context.root/'diagnostics/modem-control/passive_trial.py', 'qualified_trial_flow')
        stage = 'trial'
        lock = Path(context.plan['port_lock_path'])
        descriptor = os.open(lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(descriptor, 'a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ops = adapter_type(context, {'n': native, 'boot': boot, 'runtime': runtime})()
            outcome = flow.Trial(ops).execute()
            observation = context.workspace/'serial-observation.json'
            serial = json.loads(observation.read_text()) if observation.exists() else {}
            candidate = bool(serial.get('candidate_seen') and serial.get('worker_attempted') and (serial.get('worker_result') or {}).get('passed'))
            status = 0 if candidate else 1
            ops.save(state='terminal', outcome=outcome, candidate_RFSA_and_publication_passed=candidate,
                     native_return_verified=True, owner_return_UI_confirmation_pending=True,
                     returncode=status, finished_UTC=now())
            print(json.dumps({'state': 'terminal', 'candidate_passed': candidate, 'native_return_verified': True, 'owner_UI_pending': True}))
            return status
    except SystemExit as error:
        return error.code
    except BaseException as error:
        # Client exceptions may embed credential-bearing argv/source. Report a
        # phase and type, never private values or a private exception traceback.
        if ops is not None:
            try:
                ops.save(state='stopped for inspection', error_type=type(error).__name__, finished_UTC=now())
            except BaseException:
                pass
        print(json.dumps({'state': 'rejected-or-stopped', 'phase': stage,
                          'error_type': type(error).__name__, 'accepted': False}), file=sys.stderr)
        return 1
    finally:
        if ops is not None:
            ops.journal.close()
        if previous_umask is not None:
            os.umask(previous_umask)


if __name__ == '__main__':
    raise SystemExit(main())
