# SPDX-License-Identifier: GPL-2.0-only
"""Replay source-only CPU foundation models; no device or network operations."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import signal
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--source', required=True, type=Path)
p.add_argument('--output', required=True, type=Path)
a = p.parse_args()
B = Path(__file__).resolve().parent
C = a.source.resolve()
O = a.output.resolve()
O.mkdir(mode=0o700)
(O / 'tmp').mkdir()
env = os.environ | {'TMPDIR': str(O / 'tmp'), 'GIT_NO_LAZY_FETCH': '1',
                    'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
record = dict(passed=False, stages=[], phone_access=False, network_access=False,
              physical_acceptance=False, native_build_or_schema_replayed=False)
child = None


def save():
    (O / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')


def interrupt(sig, frame):
    raise InterruptedError(str(sig))


def run(label, arguments):
    global child
    with (O / (label + '.log')).open('xb') as log:
        child = subprocess.Popen(['python3', *map(str, arguments)], env=env,
                                 stdout=log, stderr=subprocess.STDOUT,
                                 start_new_session=True)
        record.update(state='running ' + label, active_PID=child.pid)
        save()
        code = child.wait(timeout=120)
    record.pop('active_PID', None)
    record['stages'].append(dict(label=label, returncode=code))
    save()
    assert code == 0, label
    return json.loads((O / label / 'qualification.json').read_text())


signal.signal(signal.SIGTERM, interrupt)
try:
    expected = json.loads((B / 'source-current.json').read_text())
    for name, digest in expected['source_files'].items():
        assert hashlib.sha256((C / name).read_bytes()).hexdigest() == digest, name
    H = B / 'harness'
    for phase, driver, broken in [('before', B / 'before/drivers/nvmem/qfprom.c', 1),
                                   ('after', C / 'drivers/nvmem/qfprom.c', 0)]:
        label = 'reader-' + phase
        q = run(label, [H / 'check-reader.py', '--kernel', C, '--driver', driver,
                        '--output', O / label, '--expected-broken', str(broken)])
        assert q['passed'] and q['broken'] == broken and q['cases'] == 18393
    for label, script, cases in [('SCM-wire', 'check-SCM-wire.py', 667),
                                  ('SCM-API', 'check-SCM-API.py', 13),
                                  ('calibration', 'check-calibration-sanitized.py', 4068)]:
        q = run(label, [H / script, C, O / label])
        assert q['cases'] == cases and q['returncode'] == 0 and not q['sanitizer_diagnostics']
    for kind, script, mutations in [
            ('SCM', 'check-SCM-wire.py', ['wrong-command', 'swapped-words', 'ignored-status',
                                        'early-output', 'nonlegacy', 'alignment']),
            ('calibration', 'check-calibration-sanitized.py',
             ['clock-selector', 'conditional-minimum', 'read-error'])]:
        positive = json.loads((O / ('SCM-wire' if kind == 'SCM' else kind) / 'qualification.json').read_text())
        for mutation in mutations:
            label = kind + '-' + mutation
            q = run(label, [H / script, C, O / label, '--mutation', mutation])
            assert q['returncode'] == 1 and q['failures'] > 0 and not q['sanitizer_diagnostics']
            fingerprint = 'actual_header_SHA256' if kind == 'calibration' else 'program_SHA256'
            assert q[fingerprint] != positive[fingerprint]
    source = (C / 'drivers/nvmem/qfprom.c').read_text()
    for label, old, new, broken in [
            ('root-policy', '\t\teconfig.root_only = true;', '\t\teconfig.root_only = false;', 4),
            ('extra-resource', 'if (platform_get_resource(pdev, IORESOURCE_MEM, 1))',
             'if (false && platform_get_resource(pdev, IORESOURCE_MEM, 1))', 2),
            ('keepouts', '.nkeepout = ARRAY_SIZE(msm8926_raw_keepout),', '.nkeepout = 0,', 8158)]:
        assert source.count(old) == 1
        driver = O / (label + '.c')
        driver.write_text(source.replace(old, new))
        q = run(label, [H / 'check-reader.py', '--kernel', C, '--driver', driver,
                        '--output', O / label, '--expected-broken', str(broken)])
        assert q['passed'] and q['broken'] == broken
    q = run('helper-methods', [B / 'run-helper-methods.py', '--source', C,
                              '--output', O / 'helper-methods'])
    assert q['passed'] and q['tests'] == 16 and not q['skipped']
    record.update(passed=True, state='terminal success', positive_model_cases=4748,
                  NVMEM_assertion_checks=18393, helper_test_methods=16,
                  clean_behavioral_controls=12, LSan_enabled=True,
                  ctypes_shared_oracles_unsanitized=True)
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
    save()
print(json.dumps(record))
