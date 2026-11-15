# SPDX-License-Identifier: MIT
"""Trace and interrupt only a verified owned client after a native handshake."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import signal
import subprocess
import sys
import time

root = Path.cwd()
base = Path(__file__).resolve().parent
configuration = json.loads((base / 'plan.json').read_text())
runtime = Path(configuration['runtime_root'])
native = Path(configuration['native_root'])

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def verify():
    assert sha(native / 'lib/apk/db/installed') == configuration['expected_native_database_SHA256']
    plan = json.loads((base / 'plan.json').read_text())
    assert sha(Path(plan['strace_path'])) == plan['strace_SHA256']
    for name, expected in plan['input_SHA256'].items():
        assert sha(base / name) == expected, name

def descendants(pid):
    result = set()
    todo = [pid]
    while todo:
        parent = todo.pop()
        try:
            children = Path('/proc/%d/task/%d/children' % (parent, parent)).read_text().split()
        except FileNotFoundError:
            continue
        for child in map(int, children):
            if child not in result:
                result.add(child)
                todo.append(child)
    return result

def reap(process):
    if process is None:
        return
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)

if len(sys.argv) == 3 and sys.argv[1] == '_inside':
    case = sys.argv[2]
    assert case in ['control', 'eintr']
    verify()
    directory = base / case
    work = directory / 'work'
    os.chown(work, 12345, 12345)
    work.chmod(0o755)
    command = ['bwrap', '--die-with-parent', '--unshare-pid', '--unshare-net', '--unshare-ipc',
               '--unshare-uts', '--clearenv', '--ro-bind', str(native), '/', '--tmpfs', '/tmp',
               '--bind', str(work), '/tmp/work', '--ro-bind', str(base / 'inputs'), '/tmp/input',
               '--dev', '/dev', '--proc', '/proc', '--cap-add', 'CAP_SETUID', '--cap-add', 'CAP_SETGID',
               '--setenv', 'PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
               '--setenv', 'HOME', '/tmp/work', '--setenv', 'LC_ALL', 'C', '--setenv', 'TZ', 'UTC',
               '--setenv', 'PYTHONDONTWRITEBYTECODE', '1',
               '/bin/su', 'pmos', '-s', '/bin/sh', '-c', '/usr/bin/python3 -B /tmp/input/dispatch.py']
    child = tracer = None
    receipt = dict(started_UTC=now(), case=case, target_scope='One descendant of this owned bwrap process',
                   daemon_injection=False, phone_access=False, signers_mounted=False)
    try:
        child = subprocess.Popen(command, start_new_session=True)
        receipt['owned_bwrap_PID'] = child.pid
        deadline = time.monotonic() + 30
        while not (work / 'ready.json').exists():
            if child.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Native fixture handshake not reached')
            time.sleep(0.02)
        ready = json.loads((work / 'ready.json').read_text())
        candidates = []
        for pid in descendants(child.pid):
            try:
                arguments = Path('/proc/%d/cmdline' % pid).read_bytes().split(b'\0')
                status = Path('/proc/%d/status' % pid).read_text()
            except FileNotFoundError:
                continue
            if arguments[:3] == [b'/usr/bin/python3', b'-B', b'/tmp/input/fixture.py']:
                fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
                if fields['State'].strip().startswith('T') and int(fields['TracerPid']) == 0:
                    assert int(fields['NSpid'].split()[-1]) == ready['inner_PID']
                    candidates.append(pid)
        assert len(candidates) == 1, candidates
        target = candidates[0]
        receipt.update(target_PID=target, matched_inner_PID=ready['inner_PID'], verified_owned_target=True)
        trace = [configuration['strace_path'], '-ttt', '-o', str(directory / 'syscalls.log'),
                 '-e', 'trace=msgrcv,msgsnd,semop,semtimedop,rt_sigaction,rt_sigreturn', '-p', str(target)]
        if case == 'eintr':
            trace += ['-e', 'inject=msgrcv:error=EINTR:when=1']
        with (directory / 'tracer-output.log').open('xb') as log:
            tracer = subprocess.Popen(trace, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        deadline = time.monotonic() + 10
        while True:
            status = Path('/proc/%d/status' % target).read_text()
            fields = dict(line.split(':', 1) for line in status.splitlines() if ':' in line)
            if int(fields['TracerPid']) == tracer.pid:
                break
            if tracer.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Owned client tracer did not attach')
            time.sleep(0.02)
        receipt.update(target_PID=target, tracer_PID=tracer.pid, matched_inner_PID=ready['inner_PID'],
                       verified_owned_target_and_tracer=True, client_only_injection=case == 'eintr')
        os.kill(target, signal.SIGCONT)
        receipt['fixture_returncode'] = child.wait(timeout=30)
        receipt['tracer_returncode'] = tracer.wait(timeout=10)
        assert receipt['fixture_returncode'] == receipt['tracer_returncode'] == 0
        result = json.loads((work / 'result.json').read_text())
        assert result['passed']
        assert (work / 'payload/alpha').stat().st_uid == 12345
        receipt.update(real_payload_owner_after_fakeroot=12345, passed=True)
    except BaseException as error:
        receipt.update(error_type=type(error).__name__, error=str(error), passed=False)
        raise
    finally:
        reap(tracer)
        reap(child)
        if 'target_PID' in receipt:
            for _ in range(50):
                if not Path('/proc/%d' % receipt['target_PID']).exists():
                    break
                time.sleep(0.02)
            receipt['owned_target_no_longer_exists'] = not Path('/proc/%d' % receipt['target_PID']).exists()
        receipt.update(finished_UTC=now(), owned_processes_reaped=True)
        (directory / 'inner-controller.json').write_text(json.dumps(receipt, indent=2) + '\n')
    raise SystemExit(0)

assert len(sys.argv) == 2 and sys.argv[1] in ['control', 'eintr']
case = sys.argv[1]
verify()
directory = base / case
assert not directory.exists()
directory.mkdir(mode=0o700)
(directory / 'work').mkdir(mode=0o755)
command = ['podman', '--root', str(runtime / 'podman-storage'), '--runroot', str(runtime / 'podman-run'),
           '--storage-driver', 'vfs', '--cgroup-manager', 'cgroupfs', 'unshare',
           sys.executable, '-B', str(base / 'run.py'), '_inside', case]
record = dict(started_UTC=now(), case=case, launcher_SHA256=sha(Path(__file__)),
              plan_SHA256=sha(base / 'plan.json'), phone_access=False, signers_mounted=False)
with (directory / 'output.log').open('xb') as log:
    child = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    record['PID'] = child.pid
    (directory / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
    try:
        record['returncode'] = child.wait(timeout=65)
    finally:
        reap(child)
        record.update(finished_UTC=now(), owned_launcher_reaped=True)
        (directory / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
verify()
print(json.dumps(record))
raise SystemExit(record['returncode'])
