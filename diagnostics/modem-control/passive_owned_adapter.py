# SPDX-License-Identifier: MIT
"""Passive-r1 entry with qualified owned-child cleanup and unchanged image."""
import argparse
import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result

common = module('owned_passive_common', ROOT/'diagnostics/modem-control/passive_adapter.py')
ownership = module('qualified_native_ownership', ROOT/'diagnostics/kernel-maintenance/native_trial_adapter.py')
PlanRejected, regular, sha, now, source_module = common.PlanRejected, common.regular, common.sha, common.now, common.source_module
IMAGE_SHA256, IMAGE_BYTES, ANSWER = common.IMAGE_SHA256, common.IMAGE_BYTES, common.ANSWER
FIELDS = common.FIELDS
SOURCES = common.SOURCES | {
    'diagnostics/modem-control/passive_owned_adapter.py',
    'diagnostics/kernel-maintenance/native_trial_adapter.py',
}


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
        if (self.root/'diagnostics/modem-control/passive_owned_adapter.py').resolve() != Path(__file__).resolve():
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


def adapter_type(context, services):
    if sys.flags.optimize:
        raise PlanRejected('Optimized Python is forbidden')
    parent = common.adapter_type(context, services)
    # These three methods have no super()/native-profile dependencies. Keep
    # their actual code objects and closures; no native callbacks enter the MRO.
    owned = ownership.adapter_type(context, services)

    class Passive(parent):
        _cleanup_child = owned._cleanup_child
        spawn = owned.spawn
        close = owned.close

        def finish_observers(self):
            super().finish_observers()
            if self.state['processes']['observer']['process_deadline_expired']:
                raise RuntimeError('RAM observer failed at parent deadline')

    return Passive


def candidate_accepted(context, state):
    path = context.workspace/'serial-observation.json'
    if not path.exists():
        return False
    report = json.loads(path.read_text())
    process = state.get('processes', {}).get('observer', {})
    identity, worker = report.get('RAM_identity') or {}, report.get('worker_result') or {}
    boot = identity.get('boot_id')
    returned = state.get('native_return', {}).get('boot_id')
    generation = state.get('native_return_USB_generation')
    if not boot or not returned or type(generation) is not int or generation <= 0:
        return False
    markers = ['RMTFS_PASSIVE_BEGIN ' + boot, 'RMTFS_LOCAL_SERVICE_ABSENT',
               'RMTFS_LOCAL_SERVICE_PRESENT', 'RMTFS_RFSA_OPEN /dev/qcom_rmtfs_mem1',
               'RMTFS_LOCAL_SERVICE_ABSENT', 'RMTFS_PASSIVE_PASS']
    return bool(state.get('BOOT_attempted') and state.get('observer_returncode') == 0
                and process.get('owned_child_reaped') is True
                and process.get('process_deadline_expired') is False
                and report.get('state') == 'terminal' and report.get('console_closed') is True
                and report.get('candidate_seen') is True and report.get('worker_attempted') is True
                and report.get('returned_native_USB') is True
                and not report.get('observation_deadline_reached', False)
                and identity.get('kernel') == '6.18.63-fx0-vibrator-alpine'
                and identity.get('notes_SHA256') == '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
                and re.fullmatch('[a-f0-9]{8}(-[a-f0-9]{4}){3}-[a-f0-9]{12}', boot)
                and boot not in {context.plan['baseline_boot_id'], returned}
                and worker.get('complete') is True and worker.get('passed') is True
                and type(worker.get('returncode')) is int and worker['returncode'] == 0
                and worker.get('observed_markers') == markers and worker.get('expected_markers') == markers
                and str(report.get('native_return_USB_generation')) == str(generation))


def main(argv=None):
    phase, ops, previous_umask, port_lock, terminal_message = 'plan', None, None, None, None

    def execute():
        nonlocal phase, ops, previous_umask, port_lock, terminal_message
        try:
            parser = argparse.ArgumentParser(description=__doc__)
            parser.add_argument('--plan', type=Path, required=True)
            parser.add_argument('--plan-sha256', required=True)
            parser.add_argument('--check-inputs', action='store_true')
            args = parser.parse_args(argv)
            context = Context(args.plan, args.plan_sha256)
            phase = 'noncredential-inputs'
            context.verify_inputs()
            if args.check_inputs:
                print(json.dumps({'inputs_verified': True, 'credential_client_loaded': False, 'device_actions': False}))
                return 0
            phase = 'operator-receipt'
            context.check_operator()
            phase = 'client-setup'
            previous_umask = os.umask(0o077)
            native = source_module(Path(context.plan['credential_client']), 'private_native_client')
            boot = source_module(context.root/'scripts/boot_fx0_ram.py', 'qualified_boot_helper')
            runtime = source_module(context.root/'diagnostics/modem-control/passive_runtime.py', 'qualified_runtime')
            flow = source_module(context.root/'diagnostics/modem-control/passive_trial.py', 'qualified_flow')
            phase = 'trial'
            descriptor = os.open(Path(context.plan['port_lock_path']),
                                 os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            port_lock = os.fdopen(descriptor, 'a')
            fcntl.flock(port_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ops = adapter_type(context, {'n': native, 'boot': boot, 'runtime': runtime})()
            outcome = flow.Trial(ops).execute()
            candidate = candidate_accepted(context, ops.state)
            status = 0 if candidate else 1
            ops.save(state='terminal', outcome=outcome, candidate_RFSA_and_publication_passed=candidate,
                     native_return_verified=True, owner_return_UI_confirmation_pending=True,
                     returncode=status, finished_UTC=now())
            terminal_message = {'state': 'terminal', 'candidate_passed': candidate,
                                'native_return_verified': True, 'owner_UI_pending': True}
            return status
        except SystemExit as error:
            return error.code
        except BaseException as error:
            if ops is not None:
                try:
                    ops.save(state='stopped for inspection', error_type=type(error).__name__, finished_UTC=now())
                except BaseException:
                    pass
            print(json.dumps({'state': 'rejected-or-stopped', 'phase': phase,
                              'error_type': type(error).__name__, 'accepted': False}), file=sys.stderr)
            return 1

    cleanup_failed = False
    try:
        status = execute()
    finally:
        if ops is not None:
            try:
                ops.close()
            except BaseException as error:
                cleanup_failed = True
                print(json.dumps({'state': 'cleanup-failed', 'phase': 'owned-child-cleanup',
                                  'error_type': type(error).__name__, 'accepted': False}), file=sys.stderr)
        if port_lock is not None:
            port_lock.close()
        if previous_umask is not None:
            os.umask(previous_umask)
    if not cleanup_failed and terminal_message is not None:
        print(json.dumps(terminal_message))
    return 1 if cleanup_failed else status


if __name__ == '__main__':
    raise SystemExit(main())
