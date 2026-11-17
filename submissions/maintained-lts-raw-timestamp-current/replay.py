#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay complete pure timestamp source with synthetic times; no device access."""
from pathlib import Path
import argparse, hashlib, json, os, resource, signal, subprocess, sys
P = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
m = json.loads((P / 'manifest.json').read_text())
assert all(sha(P / f) == h for f, h in m['files'].items())
O = a.output.resolve()
O.mkdir(mode=0o700)
(O / 'tmp').mkdir()
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
env = os.environ | {'TMPDIR':str(O / 'tmp'), 'PYTHONDONTWRITEBYTECODE':'1',
    'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS':'halt_on_error=1'}
expected = json.loads((P / 'expected-fixtures.json').read_text())
tasks = [('before', P / 'before', None), ('after', P / 'source', None), ('official', P / 'official', None)]
tasks += [(mutation, P / 'source', mutation) for mutation in [
    'watermark', 'long-window', 'estimate-cap', 'first-transition',
    'odr-transition', 'reset-history', 'pending-odr']]
j = dict(passed=False, state='prepared', stages=[], source_head=m['source_head'],
    manifest_verified_before_execution=True, normal_LSan_and_failfast_ASan_UBSan=True,
    phone_access=False, real_hardware_execution=False)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
try:
    for label, source, mutation in tasks:
        cmd = [sys.executable, '-B', str(P / 'check-timestamp.py'), '--source', str(source), '--output', str(O / label)]
        if mutation: cmd += ['--mutation', mutation]
        with (O / (label + '.stdout')).open('xb') as stdout, (O / (label + '.stderr')).open('xb') as stderr:
            child = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, env=env, start_new_session=True)
            j.update(state='running ' + label, active_PID=child.pid)
            save()
            code = child.wait(timeout=90)
        assert code == 0 and not (O / (label + '.stderr')).read_bytes(), label
        receipt = json.loads((O / label / 'qualification.json').read_text())
        negative = label == 'before' or mutation is not None
        assert receipt['failures'] > 0 if negative else receipt['failures'] == 0
        assert receipt['cases'] == 504
        if label in ['after', 'official']:
            assert receipt['checks'] == 83780 and receipt['infeasible_budget_overshoot_ns'] == 480000
        if label == 'before': assert receipt['failures'] == 344
        assert sha(O / label / 'model.c') == expected[label]
        j['stages'].append(dict(label=label, returncode=code,
            model_returncode=receipt['returncode'], failed_checks=receipt['failures']))
        save()
    assert all(sha(P / f) == h for f, h in m['files'].items())
    j.update(passed=True, state='terminal success', tasks=10, qualified_fixtures=10,
        all_generated_fixtures_match=True, official_and_candidate_IRQ_limit_reproduced=True)
    print(json.dumps(dict(passed=True, tasks=10, qualified_fixtures=10)))
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    j.pop('active_PID', None)
    j['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    if not j['passed']: j['state'] = 'terminal failure'
    save()
