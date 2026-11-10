#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the corrected RMTFS daemon with synthetic sysfs and QRTR endpoints."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

CASES = ['passive', 'invalid-cli', 'memory-failure', 'storage-failure', 'state-missing',
         'nested-directory-failure', 'pipe-failure', 'worker-failure', 'qrtr-open-failure',
         'publish-failure', 'pending-shutdown', 'start-error', 'start-short', 'managed-shutdown',
         'driver-fallback', 'reconnect', 'reconnect-failure', 'stop-error', 'stop-short']


def fixture(root, case):
    files = {'class/remoteproc0/device/modalias': 'of:NremoteprocT(null)Cqcom,wcnss\n'}
    if case in {'driver-fallback', 'nested-directory-failure'}:
        files['driver/fixture-device/remoteproc/remoteproc1/state'] = 'offline\n'
    elif case != 'state-missing':
        files['class/remoteproc1/device/modalias'] = 'of:NremoteprocT(null)Cqcom,msm8926-mss-pil\n'
        files['class/remoteproc1/state'] = 'offline\n'
    for name, contents in files.items():
        path = root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(contents)
    return files


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'qrtr', 'harness', 'output']:
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--compiler-json', default='["clang"]')
    p.add_argument('--runner-json', default='[]')
    p.add_argument('--cflags-json', default='[]')
    a = p.parse_args()
    source, qrtr, harness, out = (path.resolve() for path in [a.source, a.qrtr, a.harness, a.output])
    out.mkdir(mode=0o700, exist_ok=False)
    library = [qrtr/'lib'/name for name in ['qrtr.c', 'qmi.c', 'logging.c']]
    inputs = [harness, *[source/name for name in ['rmtfs.c', 'rproc.c', 'rmtfs.h', 'qmi_rmtfs.c',
               'qmi_rmtfs.h', 'util.h']], *library,
              *[qrtr/'include'/name for name in ['libqrtr.h', 'logging.h', 'ns.h']]]
    binary = out/'lifecycle-harness'
    command = json.loads(a.compiler_json)+json.loads(a.cflags_json)+[
        '-ffunction-sections', '-fdata-sections', '-Wl,--gc-sections', '-pthread',
        '-I'+str(source), '-I'+str(qrtr/'include'), str(harness), str(source/'qmi_rmtfs.c'),
        *map(str, library), *['-Wl,--wrap=qrtr_'+n for n in ['open', 'publish', 'close', 'sendto']],
        '-o', str(binary)]
    build = subprocess.run(command, capture_output=True, text=True)
    (out/'build.log').write_text(build.stdout+build.stderr)
    build.check_returncode()
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    results = []
    for case in CASES:
        with tempfile.TemporaryDirectory(dir=out) as tmp:
            root = Path(tmp)
            files = fixture(root, case)
            try:
                run = subprocess.run(json.loads(a.runner_json)+[str(binary), case, tmp],
                                     capture_output=True, text=True, timeout=10, env=env)
                stdout, stderr, status = run.stdout, run.stderr, run.returncode
            except subprocess.TimeoutExpired as exc:
                stdout, stderr, status = str(exc.stdout), str(exc.stderr), 'timeout'
            unchanged = all((root/name).read_text() == content for name, content in files.items())
            (out/(case+'.log')).write_text(stdout+stderr)
            results.append({'case': case, 'returncode': status, 'fixture_unchanged': unchanged,
                            'passed': status == 0 and stdout.startswith('LIFECYCLE_CASE_PASS '+case+' ') and unchanged})
    sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {'cases': results, 'passed': sum(row['passed'] for row in results),
              'failed': sum(not row['passed'] for row in results),
              'inputs_sha256': {str(path): sha(path) for path in inputs},
              'binary_sha256': sha(binary), 'compiler_command': command,
              'runner': json.loads(a.runner_json), 'phone_operations': 0,
              'scope': 'Real RMTFS entry point, remoteproc worker, signals, poll and QMI codec. Synthetic sysfs, remoteproc writes, memory, storage and QRTR endpoints.'}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({k: record[k] for k in ['passed', 'failed', 'phone_operations']}))
    raise SystemExit(bool(record['failed']))


if __name__ == '__main__':
    main()
