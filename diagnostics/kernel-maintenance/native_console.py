# SPDX-License-Identifier: MIT
"""Capture private pre/post-trial pstore records and emit fixed-vocabulary summaries."""
import argparse
import base64
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shlex
import sys

ROOT = Path(__file__).resolve().parents[2]
HERE = ROOT/'diagnostics/kernel-maintenance'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


native = module('console_native_profile', HERE/'native_trial_adapter.py')
probe = module('console_capture_protocol', HERE/'native_console_probe.py')
analysis = module('console_known_signals', HERE/'native_console_analysis.py')
SOURCE_FILES = {'diagnostics/kernel-maintenance/native_console.py',
                'diagnostics/kernel-maintenance/native_console_probe.py',
                'diagnostics/kernel-maintenance/native_console_analysis.py',
                'manifests/display-handoff-trace-sites.json'}
PACKET_LIMIT = 8 * 1024 * 1024


def source_lock(context, expected):
    path = ROOT/'manifests/native-console-capture.json'
    native.regular(path)
    if re.fullmatch('[a-f0-9]{64}', expected) is None or native.sha(path) != expected:
        raise ValueError('Reviewed capture source-lock digest required')
    lock = json.loads(path.read_text())
    if set(lock) != {'format', 'files_SHA256'} or lock['format'] != 1 or set(lock['files_SHA256']) != SOURCE_FILES:
        raise ValueError('Unexpected capture source roster')
    excluded = {Path(context.plan[key]).resolve() for key in ('credential_client', 'device_record')}
    contents = {}
    for name, digest in lock['files_SHA256'].items():
        path = ROOT/name
        if path.resolve() in excluded:
            raise ValueError('Private client/device record cannot enter capture source hashes')
        native.regular(path)
        body = path.read_bytes()
        if hashlib.sha256(body).hexdigest() != digest:
            raise ValueError('Capture source differs from reviewed lock')
        contents[name] = body
    return contents


def expected_identity(context, phase):
    before = json.loads((context.workspace/'before.json').read_text())
    if phase == 'before':
        context.check_operator()
        for name in ('attempt.claim', 'controller.json', 'observer.claim'):
            if (context.workspace/name).exists() or (context.workspace/name).is_symlink():
                raise FileExistsError('Before capture requires an undispatched attempt')
        return before
    native.regular(context.workspace/'attempt.claim')
    path = context.workspace/'native-return.json'
    native.regular(path)
    returned = json.loads(path.read_text())
    if returned['boot_id'] == before['boot_id']:
        raise ValueError('A distinct verified native return is required')
    for name in ('kernel', 'kernel_notes_SHA256', 'boot_partition_sha256',
                 'files_sha256', 'module_tree_digest', 'modules_FSType'):
        if returned[name] != before[name]:
            raise ValueError('Returned native baseline differs')
    if returned['trial'] or returned['taint'] != 0 or returned['modules_FSType'] != 'ext4' or returned['systemd'] != 'running' or not returned['Sway'] or not returned['gesture']:
        raise ValueError('Accepted installed-r1 return required')
    return returned


def validate_packet(raw, expected):
    if not isinstance(raw, bytes) or len(raw) > PACKET_LIMIT:
        raise ValueError('Console transport exceeds explicit limit')
    packet = json.loads(raw)
    if (packet.get('format') != 1 or packet.get('read_only') is not True or
        packet.get('boot_id') != expected['boot_id'] or
        packet.get('kernel_notes_SHA256') != expected['kernel_notes_SHA256'] or
        set(packet.get('records', {})) != set(probe.PATHS)):
        raise ValueError('Unexpected console identity or path roster')
    total, complete = 0, True
    for row in packet['records'].values():
        state = row.get('state')
        if state in ('captured', 'changed-during-read'):
            body = base64.b64decode(row['content_base64'], validate=True)
            if len(body) > probe.PER_FILE or len(body) != row['bytes'] or hashlib.sha256(body).hexdigest() != row['SHA256']:
                raise ValueError('Captured console digest or size differs')
            if (state == 'captured') != (row['stable'] is True):
                raise ValueError('Captured console stability differs')
            total += len(body)
        elif state not in ('missing', 'rejected'):
            raise ValueError('Unknown console record state')
        complete &= state in ('captured', 'missing')
    if total > probe.TOTAL or total != packet['captured_bytes'] or packet['complete'] is not complete:
        raise ValueError('Console budget or completion metadata differs')
    return packet


def save_private(directory, name, value):
    fd = os.open(directory/name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write((json.dumps(value, indent=2, allow_nan=False) + '\n').encode())
        stream.flush()
        os.fsync(stream.fileno())
    fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def main(argv=None):
    phase, previous_umask = 'inputs', None
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--plan', type=Path, required=True)
        parser.add_argument('--plan-sha256', required=True)
        parser.add_argument('--source-lock-sha256', required=True)
        parser.add_argument('--phase', choices=('before', 'after'), required=True)
        parser.add_argument('--check-inputs', action='store_true')
        args = parser.parse_args(argv)
        context = native.Context(args.plan, args.plan_sha256)
        context.verify_inputs()
        sources = source_lock(context, args.source_lock_sha256)
        if args.check_inputs:
            print(json.dumps({'inputs_verified': True, 'credential_client_loaded': False, 'device_actions': False}))
            return 0
        phase = 'capture-gate'
        expected = expected_identity(context, args.phase)
        output = context.workspace/('console-' + args.phase)
        if output.exists() or output.is_symlink():
            raise FileExistsError('Capture workspace already exists; preserve it')
        previous_umask = os.umask(0o077)
        fd = os.open(Path(context.plan['port_lock_path']), os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
        with os.fdopen(fd, 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            phase = 'client-setup'
            client = native.source_module(Path(context.plan['credential_client']), 'private_console_client')
            command = 'python3 -B -c ' + shlex.quote(sources['diagnostics/kernel-maintenance/native_console_probe.py'].decode())
            command += ' --expected-boot-id ' + shlex.quote(expected['boot_id'])
            command += ' --expected-notes-sha256 ' + shlex.quote(expected['kernel_notes_SHA256'])
            phase = 'read-only-capture'
            packet = validate_packet(client.run(command, root=True, timeout=20), expected)
            output.mkdir(mode=0o700, exist_ok=False)
            save_private(output, 'capture.private.json', packet)
            save_private(output, 'provenance.json', {'plan_SHA256': context.expected,
                'source_lock_SHA256': args.source_lock_sha256, 'phase': args.phase,
                'read_only': True, 'raw_capture_kept_private': True})
            paired = False
            if args.phase == 'after' and (context.workspace/'console-before/capture.private.json').is_file():
                path = context.workspace/'console-before/capture.private.json'
                native.regular(path)
                before = validate_packet(path.read_bytes(), json.loads((context.workspace/'before.json').read_text()))
                save_private(output, 'comparison.json', analysis.compare(before, packet))
                paired = True
        print(json.dumps({'capture_saved_privately': True, 'complete': packet['complete'],
                          'paired_comparison_written': paired, 'read_only': True,
                          'raw_console_included': False, 'reset_cause_proven': False}))
        return 0 if packet['complete'] else 1
    except SystemExit as error:
        return error.code
    except BaseException as error:
        print(json.dumps({'capture_failed': True, 'phase': phase,
                          'error_type': type(error).__name__}), file=sys.stderr)
        return 1
    finally:
        if previous_umask is not None:
            os.umask(previous_umask)


if __name__ == '__main__':
    raise SystemExit(main())
