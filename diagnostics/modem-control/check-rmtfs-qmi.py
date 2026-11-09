#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the pinned QRTR QMI codec with exact-length synthetic wire buffers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess

CASES = (['short-header-'+str(i) for i in range(7)] +
         ['null-packet', 'null-data', 'header-length-short', 'header-length-long',
          'tlv-header-1', 'tlv-header-2', 'tlv-overrun', 'unknown-optional-overrun',
          'scalar-short', 'scalar-zero', 'scalar-extra', 'missing-close', 'missing-alloc'] +
         ['missing-iovec-'+str(i) for i in range(1, 5)] +
         ['array-missing-count', 'array-incomplete', 'array-short-member', 'array-trailing',
          'array-valid', 'array-zero', 'array-max', 'string-0', 'string-255', 'string-256',
          'string-257', 'unknown-optional', 'unknown-required', 'reordered',
          'nested-valid', 'nested-string-short', 'nested-missing-scalar', 'nested-missing-entry',
          'scalar-array-prefix-short', 'scalar-array-short', 'scalar-array-too-many',
          'scalar-array-valid', 'encode-open', 'encode-empty-open', 'encode-max-open',
          'iovec-reversed', 'nested-wide-string-valid', 'nested-wide-string-prefix-short'])


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['rmtfs', 'qrtr', 'harness', 'output']:
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--compiler-json', default='["clang"]')
    parser.add_argument('--runner-json', default='[]')
    parser.add_argument('--cflags-json', default='[]')
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    out, source, qrtr = args.output.resolve(), args.rmtfs.resolve(), args.qrtr.resolve()
    binary = out/'qmi-harness'
    inputs = [args.harness.resolve(), source/'qmi_rmtfs.c', source/'qmi_rmtfs.h',
              qrtr/'include/libqrtr.h', qrtr/'include/logging.h', qrtr/'lib/qmi.c', qrtr/'lib/logging.c']
    command = json.loads(args.compiler_json)+json.loads(args.cflags_json)+[
        '-I'+str(source), '-I'+str(qrtr/'include'), str(args.harness.resolve()),
        str(source/'qmi_rmtfs.c'), str(qrtr/'lib/qmi.c'), str(qrtr/'lib/logging.c'), '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    results = []
    for case in CASES:
        try:
            run = subprocess.run(json.loads(args.runner_json)+[str(binary), case],
                capture_output=True, text=True, timeout=15,
                env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=0',
                                  'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
            stdout, stderr, code = run.stdout, run.stderr, run.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = str(exc.stdout), str(exc.stderr), 'timeout'
        (out/(case+'.log')).write_text(stdout+stderr)
        results.append({'case': case, 'returncode': code,
                        'passed': code==0 and 'QMI_CASE_PASS '+case in stdout})
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    record = {'cases': results, 'passed': sum(r['passed'] for r in results),
              'failed': sum(not r['passed'] for r in results),
              'inputs_sha256': {str(p): sha(p) for p in inputs},
              'binary_sha256': sha(binary), 'compiler_command': command,
              'runner': json.loads(args.runner_json), 'actual_phone_operations': 0,
              'scope': 'Actual QRTR codec and RMTFS descriptors; exact-size synthetic heap wire buffers. No transport, shared-memory device or physical qualification.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: record[k] for k in ['passed', 'failed', 'actual_phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
