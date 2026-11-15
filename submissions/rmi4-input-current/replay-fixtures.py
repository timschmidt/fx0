# SPDX-License-Identifier: GPL-2.0-only
"""Replay the recorded callback fixtures without a kernel checkout or phone."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cc', default='clang-21')
parser.add_argument('--output', type=Path)
args = parser.parse_args()
base = Path(__file__).resolve().parent
qualification = json.loads((base / 'qualification.json').read_text())
temporary = None
if args.output:
    out = args.output.resolve()
    out.mkdir(mode=0o700)
else:
    temporary = tempfile.TemporaryDirectory(prefix='rmi4-host-replay-')
    out = Path(temporary.name)
results = []
try:
    for fixture in qualification['fixtures']:
        source = base / fixture['file']
        assert hashlib.sha256(source.read_bytes()).hexdigest() == fixture['SHA256']
        binary = out / fixture['name']
        command = [args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror', '-g', '-O1',
                   '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
                   str(source), '-o', str(binary)]
        compiled = subprocess.run(command, capture_output=True, timeout=60)
        (out / (fixture['name'] + '-compile.log')).write_bytes(compiled.stdout + compiled.stderr)
        assert compiled.returncode == 0 and not compiled.stderr
        run = subprocess.run([str(binary)], capture_output=True, timeout=60,
                             env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                                               'UBSAN_OPTIONS': 'halt_on_error=1'})
        (out / (fixture['name'] + '-run.log')).write_bytes(run.stdout + run.stderr)
        assert run.returncode == fixture['expected_exit'] and not run.stderr
        pattern = rb'cases=(\d+) ' + fixture['metric'].encode() + rb'=(\d+)\n$'
        summary = re.search(pattern, run.stdout)
        assert summary and int(summary[1]) == fixture['cases']
        assert int(summary[2]) == fixture['expected_failures']
        results.append(dict(name=fixture['name'], cases=int(summary[1]),
                            expected_failures=int(summary[2]), passed=True))
    (out / 'result.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(dict(passed=True, fixtures=results), indent=2))
finally:
    if temporary:
        temporary.cleanup()
