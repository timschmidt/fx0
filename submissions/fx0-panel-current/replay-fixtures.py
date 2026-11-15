#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay the exported panel fixtures without a Git checkout or kernel tree."""
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
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1'}
    rows = []
    for entry in index['fixtures']:
        fixture = base / entry['path']
        assert hashlib.sha256(fixture.read_bytes()).hexdigest() == entry['SHA256']
        binary = args.output / fixture.stem
        build = subprocess.run([args.compiler, '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra',
                                '-Werror', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                                str(fixture), '-o', str(binary)], capture_output=True, timeout=60)
        (args.output / (fixture.stem + '-compile.stderr')).write_bytes(build.stderr)
        assert build.returncode == 0 and not build.stderr and not build.stdout
        if entry['kind'] == 'power':
            run = subprocess.run([str(binary)], capture_output=True, env=env, timeout=20)
            (args.output / (fixture.stem + '.stdout')).write_bytes(run.stdout)
            (args.output / (fixture.stem + '.stderr')).write_bytes(run.stderr)
            assert not run.stderr
            assert run.stdout == f"cases=16 broken={entry['broken']}\n".encode()
            assert run.returncode == bool(entry['broken'])
            rows.append(dict(name=fixture.stem, cases=16, broken=entry['broken'], expected_result_verified=True))
            continue
        differences, cases = 0, 0
        for phase, events in enumerate(index['command_phases']):
            total = sum(not event.startswith('W ') for event in events)
            for fail in range(total + 1):
                run = subprocess.run([str(binary), str(phase), str(fail)], capture_output=True, env=env, timeout=20)
                assert run.returncode == 0 and not run.stderr
                log = args.output / f'{fixture.stem}-{phase}-{fail}.trace'
                log.write_bytes(run.stdout)
                end, attempted = len(events), 0
                if fail:
                    for i, event in enumerate(events):
                        if not event.startswith('W '):
                            attempted += 1
                            if attempted == fail:
                                end = i + 1
                                break
                wanted = events[:end] + ['R ' + str(-5 if fail else 0)]
                differences += run.stdout.decode().splitlines() != wanted
                cases += 1
        assert cases == 18 and differences == entry['differences']
        rows.append(dict(name=fixture.stem, cases=cases, differences=differences, expected_result_verified=True))
    record = dict(passed=True, rows=rows, Git_or_kernel_tree_required=False,
                  native_builds_or_hardware_replayed=False, sanitizers='address,undefined,leak')
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
