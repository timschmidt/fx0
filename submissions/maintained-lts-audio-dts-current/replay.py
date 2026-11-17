#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay public DTS/binding audits only; no audio, firmware or device I/O."""
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
j = dict(passed=False, state='prepared', manifest_verified_before_execution=True,
    audio_firmware_or_hardware_execution=False, phone_access=False)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
try:
    cmd = [sys.executable, '-B', str(P / 'audit.py'), '--source', str(P / 'source'),
        '--reference', str(P / 'reference'), '--dtbs', str(P / 'DTBs'),
        '--schema', str(P / 'processed-schema.json'),
        '--prior', str(P / 'evidence/prior-full19-schema.json'), '--output', str(O / 'audit')]
    with (O / 'stdout').open('xb') as stdout, (O / 'stderr').open('xb') as stderr:
        child = subprocess.Popen(cmd, env=os.environ | {'PYTHONDONTWRITEBYTECODE':'1'},
            stdout=stdout, stderr=stderr, start_new_session=True)
        j.update(state='running source/topology/binding audit', active_PID=child.pid)
        save()
        code = child.wait(timeout=120)
    assert code == 0 and not (O / 'stderr').read_bytes()
    receipt = json.loads((O / 'audit/qualification.json').read_text())
    assert receipt == json.loads((P / 'evidence/audit-03/qualification.json').read_text())
    assert all(sha(P / f) == h for f, h in m['files'].items())
    j.update(passed=True, state='terminal success', semantic_board_cases=19,
        semantic_controls=6, binding_controls=6, exact_receipt_match=True)
    print(json.dumps(dict(passed=True, semantic_boards=19, controls=12)))
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
