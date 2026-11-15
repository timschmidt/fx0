# SPDX-License-Identifier: GPL-2.0-only
"""Verify the manifest and replay all source-bound DMA models without Git."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('output', type=Path)
args = parser.parse_args()
base = Path(__file__).resolve().parent
manifest = json.loads((base / 'files.json').read_text())
for path, expected in manifest.items():
    assert hashlib.sha256((base / path).read_bytes()).hexdigest() == expected, path
args.output.mkdir(mode=0o700)
before = args.output / 'source-before'
shutil.copytree(base / 'sources/candidate', before)
for path in (base / 'sources/baseline').rglob('*'):
    if path.is_file():
        dest = before / path.relative_to(base / 'sources/baseline')
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, dest)
cases = [('baseline', before, None, 14),
         ('candidate', base / 'sources/candidate', None, 0),
         ('no-limit', base / 'sources/candidate', 'no-limit', 6),
         ('no-guard', base / 'sources/candidate', 'no-guard', 8),
         ('single-segment', base / 'sources/candidate', 'single-segment', 3)]
results = []
for name, source, mutation, expected in cases:
    output = args.output / name
    command = [sys.executable, str(base / 'check-dma.py'), str(source), str(output)]
    if mutation:
        command += ['--mutation', mutation]
    if mutation == 'no-guard':
        command += ['--baseline-video', str(base / 'sources/baseline/drivers/media/platform/qcom/camss/camss-video.c')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (args.output / (name + '.stdout')).write_text(result.stdout)
    (args.output / (name + '.stderr')).write_text(result.stderr)
    assert result.returncode == 0 and not result.stderr, name
    qualification = json.loads((output / 'qualification.json').read_text())
    assert qualification['checks'] == 46 and qualification['failures'] == expected, name
    assert qualification['returncode'] == (1 if expected else 0), name
    assert not qualification['diagnostics'], name
    frozen = (base / 'fixtures' / (name + '.c')).read_bytes()
    frozen = frozen.split(b'/* BEGIN EXECUTED BODY */\n', 1)[1].split(b'/* END EXECUTED BODY */', 1)[0]
    assert frozen == (output / 'actual-functions.c').read_bytes(), name
    results.append(dict(case=name, checks=46, expected_failures=expected, passed=True))
report = dict(passed=True, files_verified=len(manifest), cases=results,
              Git_used=False, phone_or_network_access=False,
              sanitizer_diagnostics=False, hardware_acceptance=False)
(args.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
