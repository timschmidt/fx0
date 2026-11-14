# SPDX-License-Identifier: MIT
"""Bounded read-only observation of unchanged-r2 health and installed-r1 return."""
import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('native_observer_profile', ROOT/'diagnostics/kernel-maintenance/native_trial_adapter.py')
adapter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adapter)
PROBE = """from pathlib import Path
import hashlib,json,subprocess
words=Path('/proc/cmdline').read_text().split()
print(json.dumps(dict(boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
 notes=hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest(),
 trial='fx0.native_trial=reproducible-r2-01' in words,
 any_trial=any(w.startswith('fx0.native_trial=') for w in words),
 uptime=float(Path('/proc/uptime').read_text().split()[0]),
 Sway=subprocess.run(['pgrep','-x','sway'],capture_output=True,text=True).stdout.strip())))"""


def atomic_json(workspace, name, data):
    temporary = workspace/('.' + name + '-' + secrets.token_hex(16) + '.tmp')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write((json.dumps(data, indent=2, allow_nan=False) + '\n').encode())
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, workspace/name)
        directory = os.open(workspace, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def observe(context, phone, *, run=subprocess.run, clock=time.monotonic, pause=time.sleep):
    """Tests replace every remote provider; production callers use the pinned client."""
    if sys.flags.optimize:
        raise RuntimeError('Optimized Python is forbidden')
    context.verify_inputs()
    context.check_operator()
    base = context.workspace
    adapter.regular(base/'attempt.claim')
    for name in ('native-observation.json', 'candidate-seen.json', 'candidate-ready.json'):
        if (base/name).exists() or (base/name).is_symlink():
            raise FileExistsError('Observer artifacts already exist; inspect the consumed attempt')
    fd = os.open(base/'observer.claim', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(b'No automatic observer reuse\n')
        stream.flush()
        os.fsync(stream.fileno())
    before = json.loads((base/'before.json').read_text())
    report = {'started_UTC': adapter.now(), 'candidate_seen': False,
              'candidate_health_passed': False, 'returned': False, 'probes': [], 'errors': []}

    def save():
        atomic_json(base, 'native-observation.json', report)

    save()
    start, last_health = clock(), -100
    while clock() - start < 1000:
        try:
            child = run([*phone.OPTS, 'python3 -B -c ' + shlex.quote(PROBE)], capture_output=True, timeout=10)
            if child.returncode:
                report['probes'].append({'UTC': adapter.now(), 'SSH_returncode': child.returncode})
                save()
                pause(2)
                continue
            current = json.loads(child.stdout)
            report['probes'].append({'UTC': adapter.now(), **current})
            save()
        except (subprocess.TimeoutExpired, ValueError) as error:
            report['errors'].append({'UTC': adapter.now(), 'probe_error_type': type(error).__name__})
            save()
            pause(2)
            continue
        if current['boot_id'] == before['boot_id']:
            pause(2)
            continue
        if not current['any_trial'] and not current['trial'] and current['notes'] == before['kernel_notes_SHA256']:
            report.update(returned=True, native_return=current, finished_UTC=adapter.now())
            save()
            return report
        if not (current['trial'] and current['any_trial'] and current['notes'] == adapter.NOTES):
            report['errors'].append({'UTC': adapter.now(), 'identity': 'unexpected notes or trial token'})
            save()
            pause(2)
            continue
        if not report['candidate_seen']:
            report.update(candidate_seen=True, candidate_boot_id=current['boot_id'])
            atomic_json(base, 'candidate-seen.json', current)
        if current['boot_id'] != report['candidate_boot_id']:
            raise RuntimeError('Candidate boot changed; no repeated health attempt allowed')
        if not report['candidate_health_passed'] and current['uptime'] < 290 and current['Sway'] and clock() - last_health > 8:
            last_health = clock()
            try:
                probe = (context.root/'diagnostics/kernel-maintenance/native_trial_health_probe.py').read_text()
                values = {'baseline-boot-id': before['boot_id'],
                          'package-db-sha256': before['files_sha256']['/lib/apk/db/installed'],
                          'world-sha256': before['files_sha256']['/etc/apk/world'],
                          'boot-sha256': before['boot_partition_sha256']}
                command = 'python3 -B -c ' + shlex.quote(probe)
                for key, value in values.items():
                    command += ' --' + key + ' ' + shlex.quote(value)
                health = json.loads(phone.run(command, root=True, timeout=45))
                if not adapter.health_accepted(health, current['boot_id']):
                    raise RuntimeError('Incomplete or wrong candidate health result')
                atomic_json(base, 'candidate-ready.json', health)
                report['candidate_health_passed'] = True
            except Exception as error:
                # Never copy client exception text/argv into observations.
                report['errors'].append({'UTC': adapter.now(), 'health_error_type': type(error).__name__})
        save()
        pause(2)
    report.update(observation_deadline=True, finished_UTC=adapter.now())
    save()
    raise RuntimeError('Native return not observed within bounded window')


def main(argv=None):
    previous_umask = None
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--plan', type=Path, required=True)
        parser.add_argument('--plan-sha256', required=True)
        args = parser.parse_args(argv)
        context = adapter.Context(args.plan, args.plan_sha256)
        context.verify_inputs()
        context.check_operator()
        adapter.regular(context.workspace/'attempt.claim')
        previous_umask = os.umask(0o077)
        phone = adapter.source_module(Path(context.plan['credential_client']), 'private_native_observer_client')
        observe(context, phone)
        return 0
    except SystemExit as error:
        return error.code
    except BaseException as error:
        print(json.dumps({'accepted': False, 'error_type': type(error).__name__}), file=sys.stderr)
        return 1
    finally:
        if previous_umask is not None:
            os.umask(previous_umask)


if __name__ == '__main__':
    raise SystemExit(main())
