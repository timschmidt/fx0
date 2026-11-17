#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay completion ownership on synthetic work and messages; no Wi-Fi scan."""
from pathlib import Path
import argparse, hashlib, json, os, signal, subprocess, sys
P = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
m = json.loads((P / 'manifest.json').read_text())
assert all(sha(P / f) == h for f, h in m['files'].items())
O = a.output.resolve()
O.mkdir(mode=0o700)
expected = json.loads((P / 'expected-fixtures.json').read_text())
j = dict(passed=False, stages=[], manifest_verified_before_execution=True,
    normal_LSan_and_failfast_ASan_UBSan=True, phone_access=False, WiFi_scans=False)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
try:
    for label in ['positive', 'no-deferred-work', 'retain-delivered-message']:
        cmd = [sys.executable, '-B', str(P / 'harness/check-scan-lifecycle.py'),
            str(P / 'source/net/wireless/scan.c'), str(O / label)]
        if label != 'positive': cmd += ['--mutation', label]
        with (O / (label + '.stdout')).open('xb') as stdout, (O / (label + '.stderr')).open('xb') as stderr:
            child = subprocess.Popen(cmd, stdout=stdout, stderr=stderr, start_new_session=True)
            j.update(state='running ' + label, active_PID=child.pid)
            save()
            code = child.wait(timeout=90)
        assert code == 0 and not (O / (label + '.stderr')).read_bytes()
        receipt = json.loads((O / label / 'qualification.json').read_text())
        assert receipt['failures'] == 0 if label == 'positive' else receipt['failures'] > 0
        assert receipt['cases'] == 30 and sha(O / label / 'model.c') == expected[label]
        j['stages'].append(dict(label=label, returncode=code, failed_checks=receipt['failures']))
    assert all(sha(P / f) == h for f, h in m['files'].items())
    j.update(passed=True, state='terminal success', qualified_fixtures=3)
    print(json.dumps(dict(passed=True, qualified_fixtures=3)))
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    j.pop('active_PID', None)
    j['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    save()
