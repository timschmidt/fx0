# SPDX-License-Identifier: GPL-2.0-only
"""Replay all geometry and format models from a source-only review export."""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
base = Path(__file__).resolve().parent
manifest = json.loads((base / 'files.json').read_text())
for p, expected in manifest.items():
    assert hashlib.sha256((base / p).read_bytes()).hexdigest() == expected, p
args.output.mkdir(mode=0o700)
cases = [('baseline', None, 1759), ('candidate', None, 0),
         ('no-hook', 'no-hook', 1623), ('height', 'height', 762),
         ('wm-index', 'wm-index', 1950), ('no-bounds', 'no-bounds', 105),
         ('no-limit', 'no-limit', 136), ('no-propagation', 'no-propagation', 88)]
results = []
for name, mutation, failures in cases:
    source = base / 'sources' / ('baseline' if name == 'baseline' else 'candidate')
    output = args.output / name
    command = [sys.executable, str(base / 'check-geometry.py'), str(source),
               str(base / 'sources/vendor'), str(output)]
    if mutation:
        command += ['--mutation', mutation]
    run = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (args.output / (name + '.stdout')).write_text(run.stdout)
    (args.output / (name + '.stderr')).write_text(run.stderr)
    assert run.returncode == 0 and not run.stderr, name
    q = json.loads((output / 'qualification.json').read_text())
    assert q['checks'] == 6433 and q['failures'] == failures, name
    assert q['returncode'] == int(bool(failures)) and not q['sanitizer_diagnostics'], name
    frozen = (base / 'fixtures' / (name + '.c')).read_bytes()
    body = frozen.split(b'/* BEGIN EXECUTED BODY */\n', 1)[1].split(b'/* END EXECUTED BODY */', 1)[0]
    assert body == (output / 'actual-functions.c').read_bytes(), name
    results.append(dict(case=name, checks=6433, expected_failures=failures, passed=True))
report = dict(passed=True, files_verified=len(manifest), cases=results,
              Git_used=False, network_or_phone_access=False,
              sanitizer_diagnostics=False, full_pipeline_or_hardware_acceptance=False)
(args.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
