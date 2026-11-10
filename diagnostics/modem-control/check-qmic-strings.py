#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate normal schemas and verify C capacities and exact QMI wire bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

CASES = ['title-0', 'title-1', 'title-255', 'title-256', 'nested-0', 'nested-1',
         'nested-255', 'alias-absent', 'alias-present', 'open-0', 'open-1',
         'open-255', 'open-256', 'iovec-count', 'force-sync-count', 'response-256']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['qmic', 'rmtfs-schema', 'string-schema', 'qrtr', 'harness', 'output']:
        parser.add_argument('--'+name, required=True, type=Path)
    parser.add_argument('--generator-runner-json', default='[]')
    parser.add_argument('--compiler-json', default='["clang"]')
    parser.add_argument('--runner-json', default='[]')
    parser.add_argument('--cflags-json', default='[]')
    args = parser.parse_args()
    args.output.mkdir(mode=0o700, exist_ok=False)
    out, qrtr = args.output.resolve(), args.qrtr.resolve()
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    generated, generations = {}, []
    for name, schema in [('rmtfs', args.rmtfs_schema), ('strings', args.string_schema)]:
        repeats = []
        for n in range(2):
            directory = out/(name+'-'+str(n))
            directory.mkdir()
            command = json.loads(args.generator_runner_json)+[str(args.qmic.resolve()), '-k']
            p = subprocess.run(command, input=schema.read_bytes(), cwd=directory, capture_output=True)
            (directory/'generation.log').write_bytes(p.stdout+p.stderr)
            p.check_returncode()
            outputs = sorted(directory.glob('qmi_*.[ch]'))
            if len(outputs) != 2:
                raise ValueError('expected a generated C/header pair')
            repeats.append({p.name: sha(p) for p in outputs})
            generations.append({'schema': str(schema), 'schema_sha256': sha(schema), 'command': command,
                                'cwd': str(directory), 'outputs_sha256': repeats[-1]})
        if repeats[0] != repeats[1]:
            raise ValueError('regeneration was not deterministic')
        generated[name] = out/(name+'-0')
    binary = out/'qmic-strings-harness'
    sources = [args.harness.resolve(), generated['rmtfs']/'qmi_rmtfs.c',
               generated['strings']/'qmi_qmicstrings.c', qrtr/'lib/qmi.c', qrtr/'lib/logging.c']
    command = json.loads(args.compiler_json)+json.loads(args.cflags_json)+[
        '-I'+str(generated['rmtfs']), '-I'+str(generated['strings']), '-I'+str(qrtr/'include'),
        *map(str, sources), '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    results = []
    for case in CASES:
        p = subprocess.run(json.loads(args.runner_json)+[str(binary), case], capture_output=True, text=True,
                           timeout=15, env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1',
                           'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'})
        (out/(case+'.log')).write_text(p.stdout+p.stderr)
        results.append({'case': case, 'returncode': p.returncode,
                        'passed': p.returncode==0 and 'QMIC_STRING_CASE_PASS '+case in p.stdout})
    inputs = sources+[args.qmic.resolve(), args.rmtfs_schema.resolve(), args.string_schema.resolve(),
                     generated['rmtfs']/'qmi_rmtfs.h', generated['strings']/'qmi_qmicstrings.h',
                     qrtr/'include/libqrtr.h', qrtr/'include/logging.h']
    record = {'passed': sum(row['passed'] for row in results), 'failed': sum(not row['passed'] for row in results),
              'cases': results, 'generations': generations, 'compiler_command': command,
              'runner': json.loads(args.runner_json), 'inputs_sha256': {str(p): sha(p) for p in inputs},
              'binary_sha256': sha(binary), 'actual_phone_operations': 0,
              'scope': 'Normal generated schemas only; capacities, independent wire bytes and round trips. No malformed input, transport, physical memory or daemon lifecycle qualification.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({key: record[key] for key in ['passed', 'failed', 'actual_phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
