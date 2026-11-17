# SPDX-License-Identifier: GPL-2.0-only
"""Replay the maintained-LTS source models without device or network access."""
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
              physical_acceptance=False, full_link_or_package_qualification=False)
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
        code = child.wait(timeout=60)
    record.pop('active_PID', None)
    record['stages'].append(dict(label=label, returncode=code))
    save()
    assert code == 0, label


def result(label):
    return json.loads((O / label / 'qualification.json').read_text())


def extract(text, name):
    start = text.index('static void ' + name + '(')
    opened = text.index('{', start)
    depth = 0
    for end in range(opened, len(text)):
        if text[end] == '{':
            depth += 1
        elif text[end] == '}':
            depth -= 1
            if not depth:
                return text[start:end + 1]
    raise ValueError(name)


signal.signal(signal.SIGTERM, interrupt)
try:
    expected = json.loads((B / 'source-current.json').read_text())
    for name, digest in expected['source_files'].items():
        assert hashlib.sha256((C / name).read_bytes()).hexdigest() == digest, name
    H = B / 'harness'
    for kind, cases, failures in [('plane', 1258, 1052), ('vibrator', 12303, 8160)]:
        for phase, source in [('before', B / 'before'), ('after', C)]:
            label = kind + '-' + phase
            path = source if kind == 'plane' else source / 'drivers/input/misc/pm8xxx-vibrator.c'
            run(label, [H / ('check-' + kind + '.py'), path, O / label])
            q = result(label)
            assert q['cases'] == cases and not q['sanitizer_diagnostics']
            assert q['failures'] == (failures if phase == 'before' else 0)
            assert q['returncode'] == (1 if phase == 'before' else 0)
        mutations = (['left-only', 'ignore-error', 'drop-owned', 'right-old-only', 'right-new-only']
                     if kind == 'plane' else ['wrong-range', 'missing-limit', 'stale-drive', 'upper-left'])
        for mutation in mutations:
            label = kind + '-' + mutation
            path = C if kind == 'plane' else C / 'drivers/input/misc/pm8xxx-vibrator.c'
            run(label, [H / ('check-' + kind + '.py'), path, O / label, '--mutation', mutation])
            q = result(label)
            assert q['body_SHA256'] != result(kind + '-after')['body_SHA256']
            assert q['failures'] > 0 and q['returncode'] == 1 and not q['sanitizer_diagnostics']
    run('iommu', [H / 'check-halt.py', '--source', C, '--output', O / 'iommu'])
    q = json.loads((O / 'iommu/controller.json').read_text())
    assert q['passed'] and q['positive_cases'] == 4
    before = (B / 'before/drivers/iommu/arm/arm-smmu/qcom_iommu.c').read_text()
    negative = (O / 'iommu/negative.c').read_text()
    for name in ['qcom_iommu_halt', 'qcom_iommu_unhalt']:
        assert extract(before, name) == extract(negative, name)
    for mutation in [None, 'late-flush', 'no-start']:
        label = 'encoder' + ('-' + mutation if mutation else '')
        run(label, [H / 'check-encoder.py', C, O / label] +
            (['--mutation', mutation] if mutation else []))
        q = result(label)
        assert q['cases'] == 241 and not q['sanitizer_diagnostics']
        assert q['returncode'] == (1 if mutation else 0)
        if mutation:
            assert q['failures'] > 0 and q['body_SHA256'] != result('encoder')['body_SHA256']
        else:
            assert q['failures'] == 0
    record.update(passed=True, state='terminal success', positive_cases=13806,
                  clean_behavioral_controls=11, exact_baseline_UB_reproducers=2,
                  LSan_enabled=True, paired_CTL_paths_not_qualified=True)
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
