# SPDX-License-Identifier: MIT
"""Validate the actual single-client interrupted receive and paired metadata."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import re

base = Path(__file__).resolve().parent
root = Path.cwd()

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

plan = json.loads((base / 'plan.json').read_text())
for name, expected in plan['input_SHA256'].items():
    assert sha(base / name) == expected
assert sha(Path(plan['strace_path'])) == plan['strace_SHA256']
results = []
for case in ['control', 'eintr']:
    directory = base / case
    outer = json.loads((directory / 'controller.json').read_text())
    inner = json.loads((directory / 'inner-controller.json').read_text())
    result = json.loads((directory / 'work/result.json').read_text())
    real = json.loads((directory / 'work/real-user.json').read_text())
    assert outer['returncode'] == 0 and outer['owned_launcher_reaped']
    assert outer['plan_SHA256'] == sha(base / 'plan.json')
    assert outer['launcher_SHA256'] == sha(base / 'run.py')
    assert inner['fixture_returncode'] == inner['tracer_returncode'] == 0
    assert inner['passed'] and inner['verified_owned_target_and_tracer']
    assert inner['owned_processes_reaped'] and inner['owned_target_no_longer_exists']
    assert inner['daemon_injection'] is False
    assert inner['client_only_injection'] == (case == 'eintr')
    assert real['uid'] == inner['real_payload_owner_after_fakeroot'] == 12345
    assert result['fake_uid'] == 0 and result['passed']
    assert result['metadata'] == {'.': [0, 0, 0o755], 'alpha': [321, 654, 0o640], 'beta': [0, 0, 0o644]}
    assert sha(directory / 'work/fixture.tar') == result['tar_SHA256']
    output = (directory / 'output.log').read_text().splitlines()
    messages = [line for line in output if 'error:' in line or 'internal error' in line]
    expected = ['libfakeroot internal error: payload not recognized!'] if case == 'eintr' else []
    assert messages == expected
    trace = (directory / 'syscalls.log').read_text().splitlines()
    injected = [i for i, line in enumerate(trace) if 'INJECTED' in line]
    assert len(injected) == (1 if case == 'eintr' else 0)
    if case == 'eintr':
        at = injected[0]
        line = trace[at]
        assert 'msgrcv(' in line and '= -1 EINTR ' in line
        queue = re.search(r'msgrcv\((\d+),', line)[1]
        next_receive = next(line for line in trace[at + 1:] if 'msgrcv(' in line)
        assert 'msgrcv(' + queue + ',' in next_receive
        assert re.search(r'\) = [1-9][0-9]*$', next_receive), next_receive
        assert not any('msgsnd(' in line for line in trace[at + 1:trace.index(next_receive)])
    assert not any(error in line for line in trace for error in ['EIDRM', 'EINVAL', 'EPERM'])
    results.append(result)
assert results[0] == results[1]
assert (base / 'control/work/fixture.tar').read_bytes() == (base / 'eintr/work/fixture.tar').read_bytes()
native = Path(plan['native_root'])
assert sha(native / 'lib/apk/db/installed') == plan['expected_native_database_SHA256']
record = dict(recorded_UTC=datetime.now(timezone.utc).isoformat(), native_fakeroot=plan['native_fakeroot_version'], host_strace=plan['strace_version'],
              case_returncodes=[0, 0], exact_notice_count={'control': 0, 'client_EINTR': 1},
              one_owned_client_receive_returned_EINTR=True, same_receive_retried_successfully=True,
              daemon_not_traced_or_interrupted=True, explicit_owned_target_handshake_and_attach_verified=True,
              fake_ownership_and_modes_exact=True, real_payload_owner_unchanged=12345,
              tar_metadata_entries=3, tar_bytes_identical=True, tar_SHA256=results[0]['tar_SHA256'],
              owned_processes_reaped_and_targets_gone=True,
              known_nonfatal_client_EINTR_mechanism_verified=True,
              real_signal_delivery_tested=False, original_package_diagnostic_cause_proven=False,
              all_fakeroot_notices_proven_benign=False,
              native_database_unchanged=True, signers_mounted=False, phone_access=False,
              scope='Actual installed native client and daemon with one owned receive error; not a replay or causal trace of the original abuild run',
              evidence_SHA256={str(path.relative_to(base)): sha(path) for path in sorted(base.rglob('*'))
                               if path.is_file() and path.name not in ['verification.json'] and '__pycache__' not in path.parts},
              passed=True)
with (base / 'verification.json').open('x') as stream:
    json.dump(record, stream, indent=2)
    stream.write('\n')
print(json.dumps({key: value for key, value in record.items() if key != 'evidence_SHA256'}))
