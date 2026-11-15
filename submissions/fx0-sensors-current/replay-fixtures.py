#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay synthetic Sony/V4L2 fixtures without Git or a kernel tree.

Clang 21, sanitizer runtimes and standard Linux UAPI headers are required.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--compiler', default='clang-21')
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    base = Path(__file__).resolve().parent
    index = json.loads((base / 'fixture-index.json').read_text())
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1'}
    rows = []
    for entry in index['fixtures']:
        path = base / entry['path']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['SHA256']
        binary = args.output / path.stem
        build = subprocess.run([args.compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                                '-Wno-unused-parameter', '-Wno-unused-const-variable',
                                '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                                str(path), '-o', str(binary)], capture_output=True, timeout=60)
        (args.output / (path.stem + '-compile.stderr')).write_bytes(build.stderr)
        assert build.returncode == 0 and not build.stderr and not build.stdout
        run = subprocess.run([str(binary)], capture_output=True, env=env, timeout=60)
        (args.output / (path.stem + '.stdout')).write_bytes(run.stdout)
        (args.output / (path.stem + '.stderr')).write_bytes(run.stderr)
        assert not run.stderr and run.returncode == bool(entry['broken'])
        expected = 'cases={cases} broken={broken} stop={stop} format={format}\n'.format(**entry)
        assert run.stdout.decode() == expected
        rows.append(dict(name=path.stem, cases=entry['cases'], broken=entry['broken'],
                         stop=entry['stop'], format=entry['format'], expected_result_verified=True))
    record = dict(passed=True, rows=rows, Git_or_kernel_tree_required=False,
                  Linux_UAPI_headers_required=True, all_sanitizers_enabled=True,
                  full_native_build_PM_ioctl_control_cache_or_hardware_replayed=False,
                  phone_access=False)
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
