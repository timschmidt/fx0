#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Rebuild the exact five-property passive-r1 DTB without reading a stock dump."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BOARD = 'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel-source', required=True, type=Path)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    require(not sys.flags.optimize, 'Optimized Python is forbidden')
    source, output = args.kernel_source.resolve(), args.output_dir.absolute()
    lock = json.loads((ROOT / 'manifests/passive-r1-dtb.json').read_text())
    require(lock['format'] == 1 and sha(source / BOARD) == lock['board_SHA256'],
            'Board source differs from the accepted r1 commit')
    patch = ROOT / 'diagnostics/modem-control/fx0-rmtfs-memory.patch'
    require(sha(patch) == lock['patch_SHA256'], 'RFSA patch differs')
    output.mkdir(mode=0o700, exist_ok=False)
    scratch = output / 'source'
    (scratch / BOARD).parent.mkdir(parents=True)
    shutil.copyfile(source / BOARD, scratch / BOARD)
    result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)],
                            cwd=scratch, capture_output=True, timeout=15)
    (output / 'patch.log').write_bytes(result.stdout + result.stderr)
    require(result.returncode == 0, 'RFSA patch failed; inspect retained patch.log')
    for name, board in [('baseline', source / BOARD), ('candidate', scratch / BOARD)]:
        with (output / (name + '.dts')).open('wb') as stream:
            subprocess.run(['cpp', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                            '-I' + str(source / 'include'), '-I' + str(source / 'arch/arm/boot/dts'),
                            '-I' + str(source / 'arch/arm/boot/dts/qcom'), str(board)],
                           stdout=stream, timeout=30, check=True)
        with (output / (name + '-dtc.log')).open('wb') as stream:
            subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(output / (name + '.dtb')),
                            str(output / (name + '.dts'))], stderr=stream, timeout=30, check=True)
        require(sha(output / (name + '.dtb')) == lock[name + '_SHA256'], 'Rebuilt DTB differs')
    spec = importlib.util.spec_from_file_location(
        'public_passive_r1_description', ROOT / 'diagnostics/modem-control/verify-rmtfs-description.py')
    dt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dt)
    dt.check(output / 'candidate.dtb')
    old, new = dt.properties(output / 'baseline.dtb'), dt.properties(output / 'candidate.dtb')
    changes = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    require(changes == {tuple(row) for row in lock['changes']}, 'Unexpected property change')
    report = {'baseline_SHA256': lock['baseline_SHA256'], 'candidate_SHA256': lock['candidate_SHA256'],
              'property_changes': sorted(changes), 'phone_access': False,
              'stock_dump_read': False, 'physical_qualification': False}
    (output / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
