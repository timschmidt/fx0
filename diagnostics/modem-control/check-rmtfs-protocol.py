#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run actual RMTFS packet handlers with synthetic transport, RAM and files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile

CASES = ['open-reuse', 'close-verbose', 'close-invalid', 'close-foreign',
         'error-valid', 'error-invalid', 'error-foreign', 'error-closed',
         'allocation-global', 'allocation-oversize', 'io-invalid', 'io-foreign',
         'read-multiple', 'write-shadow', 'read-far', 'write-far', 'read-max-sector',
         'sync-error', 'memory-invalid', 'memory-read-error', 'memory-short', 'zero-sectors',
         'wrong-message-type', 'unknown-request', 'io-closed', 'malformed-close-missing',
         'malformed-alloc-missing', 'malformed-iovec-missing-direction', 'malformed-iovec-short-array',
         'malformed-close-optional-overrun', 'malformed-short-header', 'malformed-close-short-scalar']


def main():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'qrtr', 'harness', 'output']:
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--compiler-json', default='["clang"]')
    parser.add_argument('--runner-json', default='[]')
    parser.add_argument('--cflags-json', default='[]')
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    out, source, qrtr = args.output.resolve(), args.source.resolve(), args.qrtr.resolve()
    binary = out/'protocol-harness'
    inputs = [args.harness.resolve(), source/'rmtfs.c', source/'storage.c', source/'qmi_rmtfs.c',
              source/'rmtfs.h', source/'qmi_rmtfs.h', source/'util.h',
              qrtr/'include/libqrtr.h', qrtr/'include/logging.h', qrtr/'include/ns.h',
              qrtr/'lib/qmi.c', qrtr/'lib/qrtr.c', qrtr/'lib/logging.c']
    command = json.loads(args.compiler_json)+json.loads(args.cflags_json)+[
        '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections',
        '-I'+str(source), '-I'+str(qrtr/'include'), str(args.harness.resolve()),
        str(source/'storage.c'), str(source/'qmi_rmtfs.c'),
        *[str(qrtr/'lib'/name) for name in ['qmi.c', 'qrtr.c', 'logging.c']],
        *['-Wl,--wrap='+name for name in ['open', 'pwrite', 'fdatasync', 'socket',
          'recvfrom', 'qrtr_sendto', 'storage_pread', 'storage_pwrite', 'storage_sync']],
        '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    results = []
    for case in CASES:
        with tempfile.TemporaryDirectory(dir=out) as directory:
            root = Path(directory)
            for name in ['modem_fs1', 'modem_fs2']:
                (root/name).write_bytes(b'\x21'*4096)
            try:
                run = subprocess.run(json.loads(args.runner_json)+[str(binary), case, str(root)],
                    capture_output=True, text=True, timeout=15,
                    env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=0',
                                      'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
                stdout, stderr, code = run.stdout, run.stderr, run.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, code = str(exc.stdout), str(exc.stderr), 'timeout'
            (out/(case+'.log')).write_text(stdout+stderr)
            unchanged = all((root/name).read_bytes()==b'\x21'*4096 for name in ['modem_fs1', 'modem_fs2'])
            results.append({'case': case, 'returncode': code, 'backing_unchanged': unchanged,
                            'passed': code==0 and 'PROTOCOL_CASE_PASS '+case in stdout and unchanged})
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    record = {'cases': results, 'passed': sum(r['passed'] for r in results),
              'failed': sum(not r['passed'] for r in results),
              'inputs_sha256': {str(p): sha(p) for p in inputs},
              'binary_sha256': sha(binary), 'compiler_command': command,
              'runner': json.loads(args.runner_json), 'actual_phone_operations': 0,
              'scope': 'Real dispatcher, QRTR/QMI codec and shadow storage; mocked transport/memory; synthetic regular files. No physical/lifecycle/malformed-packet qualification.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: record[k] for k in ['passed', 'failed', 'actual_phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
