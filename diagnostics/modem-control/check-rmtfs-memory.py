#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify corrected RMTFS memory helpers and IOVEC preflight with synthetic backing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

CASES = ['mapped-roundtrip', 'fd-roundtrip', 'mapped-wide-roundtrip', 'fd-wide-roundtrip',
         'mapped-zero', 'fd-zero', 'allocation', 'mapped-below', 'fd-below',
         'mapped-cross-end', 'fd-cross-end', 'mapped-past-end', 'fd-past-end',
         'mapped-negative', 'fd-negative', 'mapped-null-buffer', 'fd-null-buffer',
         'empty-region', 'wrapped-region', 'invalid-fd', 'fd-offset-limit',
         'mapped-size-limit', 'null-region',
         *['io-'+mode+'-'+operation for mode in ['mapped', 'fd'] for operation in
           ['read', 'write', 'reject-read', 'reject-write', 'zero-write', 'empty-write']]]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'qrtr', 'provider', 'harness', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--compiler-json', default='["clang"]')
    p.add_argument('--runner-json', default='[]')
    p.add_argument('--cflags-json', default='[]')
    a = p.parse_args()
    source, qrtr, out = a.source.resolve(), a.qrtr.resolve(), a.output.resolve()
    out.mkdir(mode=0o700, exist_ok=False)
    inputs = [a.harness.resolve(), source/'sharedmem.c', source/'rmtfs.c', source/'rmtfs.h',
              source/'qmi_rmtfs.c', source/'qmi_rmtfs.h', source/'util.h',
              qrtr/'include/libqrtr.h', qrtr/'include/logging.h',
              qrtr/'lib/qmi.c', qrtr/'lib/logging.c', a.provider.resolve()/'libudev.h']
    binary = out/'memory-harness'
    command = json.loads(a.compiler_json)+json.loads(a.cflags_json)+[
        '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
        '-I'+str(source), '-I'+str(qrtr/'include'), '-I'+str(a.provider.resolve()),
        str(a.harness.resolve()), str(source/'qmi_rmtfs.c'), str(qrtr/'lib/qmi.c'), str(qrtr/'lib/logging.c'),
        *['-Wl,--wrap='+n for n in ['pread', 'pwrite', 'open', 'mmap', 'socket', 'qrtr_sendto']],
        '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    results = []
    for case in CASES:
        run = subprocess.run(json.loads(a.runner_json)+[str(binary), case], capture_output=True,
            text=True, timeout=15, env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1',
                                                   'UBSAN_OPTIONS': 'halt_on_error=1'})
        (out/(case+'.log')).write_text(run.stdout+run.stderr)
        results.append({'case': case, 'returncode': run.returncode,
                        'passed': run.returncode == 0 and 'MEMORY_CASE_PASS '+case in run.stdout})
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'cases': results, 'passed': sum(r['passed'] for r in results),
              'failed': sum(not r['passed'] for r in results),
              'inputs_sha256': {str(path): sha(path) for path in inputs},
              'binary_sha256': sha(binary), 'compiler_command': command,
              'runner': json.loads(a.runner_json), 'phone_operations': 0,
              'scope': 'Patched helpers and IOVEC handler/codec; synthetic mapped/fd RAM and mock storage/transport. Constructors, physical mapping, daemon startup and modem not exercised.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: record[k] for k in ['passed', 'failed', 'phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
