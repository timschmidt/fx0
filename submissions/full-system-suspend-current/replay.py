#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay synthetic source models offline; never access the Fx0."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path, help='Pristine export of the pinned Linux commit')
parser.add_argument('output', type=Path, help='New private result directory')
args = parser.parse_args()
packet = Path(__file__).resolve().parent
source = args.source.resolve()
output = args.output.resolve()
spec_bytes = (packet / 'source-and-fixtures.json').read_bytes()
spec = json.loads(spec_bytes)
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
assert not output.exists(), 'Refusing to reuse a result directory'
assert not (source / '.git').exists(), 'Use a source export without Git metadata'
assert spec['source_files'] == {p: sha(source / p) for p in spec['source_files']}
assert spec['maintainer_source_and_fixture_files'] == {p: sha(packet / p) for p in spec['maintainer_source_and_fixture_files']}
output.mkdir(parents=True)
workspace = output / 'workspace'
workspace.mkdir()
(workspace / 'worktrees').mkdir()
(workspace / 'worktrees/linux-fx0-cpu-current-01').symlink_to(source, target_is_directory=True)
for name, digest in spec['fixture_source_files'].items():
    fixture = packet / 'fixtures' / name
    assert sha(fixture) == digest, name
    dst = workspace / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(fixture, dst)
shim = output / 'git-denied'
shim.mkdir()
(shim / 'git').write_text('#!/bin/sh\necho "Git disabled for this replay" >&2\nexit 125\n')
(shim / 'git').chmod(0o755)
temporary = output / 'tmp'
temporary.mkdir()
env = os.environ | {'PATH': str(shim) + os.pathsep + os.environ['PATH'],
    'TMPDIR': str(temporary), 'GIT_NO_LAZY_FETCH': '1', 'PYTHONDONTWRITEBYTECODE': '1',
    'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1:abort_on_error=1',
    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
fixtures = workspace / 'local/fx0-full-suspend-current-01'
results = output / 'results'
results.mkdir()
controller = output / 'controller.json'
record = dict(started_UTC=datetime.now(timezone.utc).isoformat(), passed=False,
    state='prepared', source_head=spec['source_head'], packet_spec_SHA256=hashlib.sha256(spec_bytes).hexdigest(), replay_script_SHA256=sha(Path(__file__)), phone_access=False,
    network_requested=False, Git_denied=True, synthetic_services=True,
    kernel_concurrency_qualified=False, physical_acceptance=False, stages=[])
child = None
def save():
    controller.write_text(json.dumps(record, indent=2) + '\n')
def interrupted(sig, frame):
    raise InterruptedError(str(sig))
signal.signal(signal.SIGTERM, interrupted)
def run_command(label, command, timeout):
    global child
    with (output / (label + '.log')).open('xb') as stream:
        child = subprocess.Popen(command, cwd=workspace, env=env,
            stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        record.update(state='running ' + label, active_PID=child.pid)
        save()
        code = child.wait(timeout=timeout)
    record.pop('active_PID', None)
    record['stages'].append(dict(label=label, returncode=code,
        log_SHA256=sha(output / (label + '.log'))))
    save()
    assert code == 0, (label, code)
    return json.loads((results / label / 'qualification.json').read_text())
def run(label, script, timeout):
    return run_command(label, ['python3', '-B', str(fixtures / script), str(source), str(results / label)], timeout)
try:
    total = 0
    for label, script in spec['programs']:
        result = run(label, script, 180)
        assert result.get('passed', True) and not result.get('failures', 0), label
        total += result.get('cases', 0)
    controls = run('controls', 'check-sleep-controls.py', 300)
    spm = run('spm-controls', 'spm-retained-harness/check-controls.py', 300)
    assert controls['passed'] and controls['controls'] == 56
    assert spm['passed'] and len(spm['controls']) == 29
    assert total == spec['expected_cases'] == 5009
    assert spec['source_files'] == {p: sha(source / p) for p in spec['source_files']}
    assert spec['fixture_source_files'] == {p: sha(workspace / p) for p in spec['fixture_source_files']}
    maintainer_cases = baseline_assertions = 0
    for kind, tree in [('edge', 'rpmsg'), ('state', 'rpmsg'), ('mpm', 'irq')]:
        for phase in ['before', 'after']:
            label = 'maintainer-' + kind + '-' + phase
            cmd = ['python3', '-B', str(packet / 'maintainer-fixes/harness/check.py'), kind, str(packet / 'maintainer-fixes' / phase / tree), str(results / label)]
            if phase == 'before':
                cmd.append('--expect-failure')
            result = run_command(label, cmd, 60)
            assert result['passed']
            if phase == 'after':
                maintainer_cases += result['cases']
            else:
                baseline_assertions += result['failures']
    assert maintainer_cases == spec['expected_maintainer_cases'] == 473
    assert baseline_assertions == spec['expected_maintainer_baseline_assertions'] == 49
    assert spec['maintainer_source_and_fixture_files'] == {p: sha(packet / p) for p in spec['maintainer_source_and_fixture_files']}
    record.update(passed=True, state='terminal success', host_cases=total, maintainer_cases=maintainer_cases, maintainer_baseline_assertions=baseline_assertions,
                  clean_behavioral_controls=85, retained_clock_programs=4)
except BaseException as error:
    record.update(state='terminal failure', error_type=type(error).__name__, error=str(error))
    raise
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    record.pop('active_PID', None)
    record['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    record['finished_UTC'] = datetime.now(timezone.utc).isoformat()
    save()
print(json.dumps(dict(passed=record['passed'], host_cases=record.get('host_cases'),
                      controls=record.get('clean_behavioral_controls'))))
