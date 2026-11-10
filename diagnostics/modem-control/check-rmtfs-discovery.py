#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check corrected Linux RMTFS shared-memory discovery without device access."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'qrtr', 'provider', 'harness', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--compiler-json', default='["clang"]')
    p.add_argument('--runner-json', default='[]')
    p.add_argument('--cflags-json', default='[]')
    a = p.parse_args()
    source, qrtr, provider = (path.resolve() for path in [a.source, a.qrtr, a.provider])
    out = a.output.resolve()
    out.mkdir(mode=0o700, exist_ok=False)
    inputs = [a.harness.resolve(), source/'sharedmem.c', source/'rmtfs.h', source/'qmi_rmtfs.h',
              qrtr/'include/libqrtr.h', provider/'libudev.h']
    binary = out/'discovery-harness'
    command = json.loads(a.compiler_json)+json.loads(a.cflags_json)+[
        '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
        '-I'+str(source), '-I'+str(qrtr/'include'), '-I'+str(provider), str(a.harness.resolve()),
        '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    runner = json.loads(a.runner_json)+[str(binary)]
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    listing = subprocess.run(runner+['--list'], capture_output=True, text=True, timeout=15, env=env, check=True)
    cases = listing.stdout.splitlines()
    assert len(cases) == len(set(cases)) == 46
    assert all(name.isascii() and name.replace('-', '').isalnum() for name in cases)
    results = []
    for case in cases:
        run = subprocess.run(runner+[case], capture_output=True, text=True, timeout=15, env=env)
        (out/(case+'.log')).write_text(run.stdout+run.stderr)
        results.append({'case': case, 'returncode': run.returncode,
                        'passed': run.returncode == 0 and run.stdout.startswith('DISCOVERY_CASE_PASS '+case+' ')})
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'cases': results, 'passed': sum(r['passed'] for r in results),
              'failed': sum(not r['passed'] for r in results),
              'inputs_sha256': {str(path): sha(path) for path in inputs},
              'binary_sha256': sha(binary), 'compiler_command': command,
              'runner': json.loads(a.runner_json), 'phone_operations': 0,
              'scope': 'Actual corrected Linux constructors and teardown; virtual devices, directory fds, DT data, libudev and mappings. No real device, mmap, daemon or Android execution.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: record[k] for k in ['passed', 'failed', 'phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
