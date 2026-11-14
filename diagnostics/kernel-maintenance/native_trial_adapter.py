# SPDX-License-Identifier: MIT
"""Unchanged-r2 repeat adapter using the qualified durable RAM-trial transport."""
import argparse
import datetime
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_trial_common', ROOT/'diagnostics/modem-control/passive_adapter.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
PlanRejected, regular, sha, now, source_module = common.PlanRejected, common.regular, common.sha, common.now, common.source_module
IMAGE_SHA256 = '49c23a63402b645c49c55ffbd44f140c64ad0bba722170472891fa3b1a45f0d1'
IMAGE_BYTES = 17272832
ANSWER = 'Available for another run'
MODULE_MANIFEST = 'e5844d5ba3b12935b73a3517d7be67a9d18e6013ac5f59d547c4177b1fd8cdfb'
NOTES = '1e9be71c9bb7ed42d12826a039097bd853bb6f9781325b47008ed46c679353e0'
INPUTS = {'before.json', 'preparation.json', 'stage-record.json', 'owner-display-touch-before.json'}
SOURCES = (common.SOURCES - {'diagnostics/modem-control/passive_observer.py', 'diagnostics/modem-control/passive_serial.py'}) | {
    'diagnostics/kernel-maintenance/native_trial_adapter.py',
    'diagnostics/kernel-maintenance/native_trial_observer.py',
    'diagnostics/kernel-maintenance/native_trial_stage_probe.py',
    'diagnostics/kernel-maintenance/native_trial_health_probe.py',
}
FIELDS = common.FIELDS


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
        if (self.root/'diagnostics/kernel-maintenance/native_trial_adapter.py').resolve() != Path(__file__).resolve():
            raise PlanRejected('Plan does not identify the executing public adapter')
        if p['image_SHA256'] != IMAGE_SHA256 or p['image_bytes'] != IMAGE_BYTES:
            raise PlanRejected('Plan must identify the unchanged r2 repeat image')
        if set(p['source_files_SHA256']) != SOURCES or set(p['workspace_inputs_SHA256']) != INPUTS:
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
        self.observer_path = self.root/'diagnostics/kernel-maintenance/native_trial_observer.py'
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
        if proof['image_SHA256'] != IMAGE_SHA256 or not proof['ordinary_native_init_preserved_and_three_actual_ARM_BusyBox_syntax_checks_passed'] or not proof['GNU_CPIO_both_members_and_all19_replacement_module_bodies_verified']:
            raise PlanRejected('Independent image qualification missing')
        if proof['early_return_seconds'] != 420 or proof['normal_return_seconds'] != 360:
            raise PlanRejected('Qualified r2 independent return required')
        stage = json.loads((self.workspace/'stage-record.json').read_text())
        ui = json.loads((self.workspace/'owner-display-touch-before.json').read_text())
        if stage['module_manifest_SHA256'] != MODULE_MANIFEST or stage['original_module_tree_digest'] != before['module_tree_digest']:
            raise PlanRejected('Retained r2 stage provenance differs from accepted baseline')
        if ui['boot_id'] != before['boot_id'] or not ui['display_confirmed'] or not ui['touch_confirmed']:
            raise PlanRejected('Accepted same-boot display and touch evidence required')

    def check_operator(self):
        regular(self.owner_path)
        owner = json.loads(self.owner_path.read_text())
        age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(owner['recorded_UTC'])).total_seconds()
        if owner['answer'] != ANSWER or owner['boot_id'] != self.plan['baseline_boot_id'] or owner['image_SHA256'] != IMAGE_SHA256 or not 0 <= age < 600:
            raise PlanRejected('Specific fresh operator/image/baseline receipt required')


def adapter_type(context, services):
    """Reuse the qualified concrete transport; specialize native r2 evidence."""
    if sys.flags.optimize:
        raise PlanRejected('Optimized Python is forbidden')
    parent = common.adapter_type(context, services)
    wait_owned = services.get('wait_owned', services['runtime'].wait_owned)
    pause = services.get('time', common.time).sleep
    native_client = services['n']

    class Native(parent):
        def preflight(self):
            super().preflight()
            probe = (context.root/'diagnostics/kernel-maintenance/native_trial_stage_probe.py').read_text()
            command = 'python3 -B -c ' + shlex.quote(probe) + ' --baseline-boot-id ' + shlex.quote(self.before['boot_id'])
            stage = json.loads(native_client.run(command, root=True, timeout=60))
            if stage.get('module_manifest_SHA256') != MODULE_MANIFEST or stage.get('all478_staged_files_exact') is not True:
                raise RuntimeError('Fresh staged r2 module guard failed')
            (context.workspace/'stage-guard.json').write_text(json.dumps(stage, indent=2) + '\n')
            self.save(state='exact installed r1 and unchanged staged r2 preflight passed')

        def reap(self, name, timeout=None):
            if name != 'observer' or timeout is not None:
                return super().reap(name, timeout)
            # The native observer has its own 1000-second loop, with bounded
            # SSH/health calls. Its parent deadline allows those calls to finish.
            result = wait_owned(self.children[name], 1100)
            self.state['processes'][name].update(result, finished_UTC=now())
            self.save()
            return result['returncode']

        def start_observers(self):
            self.spawn('observer', [sys.executable, context.observer_path,
                                   '--plan', context.path, '--plan-sha256', context.expected])
            pause(0.3)

        def finish_observers(self):
            self.save(state='observing unchanged r2 native startup and independent return')
            code = self.reap('observer')
            self.save(observer_returncode=code)
            if code != 0 or self.state['processes']['observer']['process_deadline_expired']:
                raise RuntimeError('Native observer failed; candidate acceptance forbidden')

    return Native


def health_accepted(health, boot_id):
    required = ['exact_r2_notes_verified', 'all478_new_module_metadata_files_verified',
                'early_static_helper_alive_and_exact_binary', 'primary_return_timer_active',
                'four_cpus_schedutil_787200_max', 'touch_device_open',
                'package_DB_world_and_raw_boot_unchanged', 'read_only']
    return bool(health.get('boot_id') == boot_id and health.get('systemd') == 'running'
                and health.get('taint') == 0 and all(health.get(name) is True for name in required)
                and isinstance(health.get('serious_kernel_pattern_counts'), dict)
                and health['serious_kernel_pattern_counts']
                and not any(health['serious_kernel_pattern_counts'].values()))


def candidate_accepted(context, state):
    """Candidate health and a matching verified native return are separate gates."""
    path = context.workspace/'native-observation.json'
    ready = context.workspace/'candidate-ready.json'
    if not path.exists() or not ready.exists():
        return False
    report, health = json.loads(path.read_text()), json.loads(ready.read_text())
    candidate = report.get('candidate_boot_id')
    returned = state.get('native_return', {}).get('boot_id')
    process = state.get('processes', {}).get('observer', {})
    return bool(state.get('BOOT_attempted') and state.get('observer_returncode') == 0
                and process.get('owned_child_reaped') is True
                and process.get('process_deadline_expired') is False
                and report.get('candidate_seen') is True and report.get('candidate_health_passed') is True
                and report.get('returned') is True and candidate and returned
                and candidate not in {context.plan['baseline_boot_id'], returned}
                and report.get('native_return', {}).get('boot_id') == returned
                and health_accepted(health, candidate))


def main(argv=None):
    phase, ops, previous_umask = 'plan', None, None
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
        with os.fdopen(descriptor, 'a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            ops = adapter_type(context, {'n': native, 'boot': boot, 'runtime': runtime})()
            outcome = flow.Trial(ops).execute()
            candidate = candidate_accepted(context, ops.state)
            status = 0 if candidate else 1
            ops.save(state='terminal', outcome=outcome, candidate_health_passed=candidate,
                     native_return_verified=True, owner_return_UI_confirmation_pending=True,
                     returncode=status, finished_UTC=now())
            print(json.dumps({'state': 'terminal', 'candidate_passed': candidate,
                              'native_return_verified': True, 'owner_UI_pending': True}))
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
    finally:
        if ops is not None:
            ops.journal.close()
        if previous_umask is not None:
            os.umask(previous_umask)


if __name__ == '__main__':
    raise SystemExit(main())
