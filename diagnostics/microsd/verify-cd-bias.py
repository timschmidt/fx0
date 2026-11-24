#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile and compare the r50 SDHC2 card-detect bias candidate."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

BOARD = Path('arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dts')
HOST = '/soc/mmc@f98a4900'
PINS = '/soc/pinctrl@fd510000/sdhc2-cd-default-state'
MODULE = Path(__file__).resolve().parents[1]/'modem-control/verify-rmtfs-description.py'
SPEC = importlib.util.spec_from_file_location('dt_compare', MODULE)
DT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DT)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_change(baseline, candidate):
    old, new = DT.properties(baseline), DT.properties(candidate)
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    assert changed == {(PINS, 'bias-pull-up'), (PINS, 'bias-disable')}, sorted(changed)
    assert old[PINS, 'bias-pull-up'] == new[PINS, 'bias-disable'] == b''
    tree = DT.MOD.Fdt(candidate)
    assert tree.strings('/aliases', 'mmc1') == [HOST]
    assert tree.strings(HOST, 'status') == ['okay']
    assert tree.strings(PINS, 'pins') == ['gpio37'] and tree.strings(PINS, 'function') == ['gpio']
    assert tree.cells(PINS, 'drive-strength') == [2]
    assert tree.cells(HOST, 'bus-width') == [4]
    handle, pin, flags = tree.cells(HOST, 'cd-gpios')
    assert (pin, flags) == (37, 1) and tree.resolve(handle) == str(Path(PINS).parent)
    assert PINS in [tree.resolve(handle) for handle in tree.cells(HOST, 'pinctrl-0')]
    assert tree.cells(HOST, 'interrupts') == [0, 125, 4, 0, 221, 4]
    assert tree.prop(HOST, 'broken-cd') is None and tree.prop(HOST, 'non-removable') is None
    return sorted(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['source', 'patch', 'schema', 'dt-validate', 'output']:
        parser.add_argument('--'+name, type=Path, required=True)
    args = parser.parse_args()
    source, out = args.source.resolve(), args.output.resolve()
    out.mkdir(mode=0o700, exist_ok=False)
    env = os.environ | {'PYTHONDONTWRITEBYTECODE': '1', 'XDG_CACHE_HOME': str(out/'cache')}
    board = source/BOARD
    assert sha(board) == '5df5d19e8ab3cffebd0778a320298475ebe50e4e05712e40f654f44ea7ac3135'
    scratch = out/'source'
    (scratch/BOARD).parent.mkdir(parents=True)
    shutil.copy2(board, scratch/BOARD)
    patch = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(args.patch.resolve())],
                           cwd=scratch, capture_output=True, text=True, env=env)
    (out/'patch.log').write_text(patch.stdout+patch.stderr)
    patch.check_returncode()
    for name, path in [('baseline', board), ('candidate', scratch/BOARD)]:
        dts = out/(name+'.dts')
        with dts.open('wb') as file:
            subprocess.run(['cpp', '-nostdinc', '-undef', '-D__DTS__', '-x', 'assembler-with-cpp',
                            '-I'+str(source/'include'), '-I'+str(source/BOARD.parent.parent),
                            '-I'+str(source/BOARD.parent), str(path)], stdout=file, check=True, env=env)
        with (out/(name+'-dtc.log')).open('w') as file:
            subprocess.run(['dtc', '-I', 'dts', '-O', 'dtb', '-o', str(out/(name+'.dtb')), str(dts)],
                           stderr=file, check=True, env=env)
    baseline, candidate = out/'baseline.dtb', out/'candidate.dtb'
    assert sha(baseline) == '1658cb8cee4e8800c6163f76b5153f2a50eeae8bfbfcfbe2dd818ff3d3a87eda'
    changes = verify_change(baseline, candidate)

    def warnings(name):
        return [line.split(': Warning ', 1)[1] for line in (out/(name+'-dtc.log')).read_text().splitlines()
                if ': Warning ' in line]

    assert warnings('baseline') == warnings('candidate')
    schema_logs = {}
    for path in [baseline, candidate]:
        run = subprocess.run([str(args.dt_validate), '-s', str(args.schema), '-l', 'qcom,msm8226-pinctrl', str(path)],
                             capture_output=True, text=True, check=True, env=env)
        log = run.stdout+run.stderr
        (out/(path.stem+'-schema.log')).write_text(log)
        schema_logs[path.stem] = log.replace(str(path), '<dtb>')
    assert schema_logs['baseline'] == schema_logs['candidate']

    controls = []
    for name, path in [('unchanged-pull-up', baseline), ('wrong-polarity', out/'wrong-polarity.dtb')]:
        if name == 'wrong-polarity':
            shutil.copy2(candidate, path)
            tree = DT.MOD.Fdt(candidate)
            handle = tree.cells(HOST, 'cd-gpios')[0]
            subprocess.run(['fdtput', '-t', 'x', str(path), HOST, 'cd-gpios', hex(handle), '0x25', '0'],
                           check=True, env=env)
        try:
            verify_change(baseline, path)
        except AssertionError:
            controls.append(name)
        else:
            raise AssertionError(f'Accepted invalid {name} candidate')
    record = {'patch_sha256': sha(args.patch), 'baseline_dtb_sha256': sha(baseline),
              'candidate_dtb_sha256': sha(candidate), 'property_changes': changes,
              'inherited_dtc_warnings': len(warnings('baseline')), 'new_dtc_warnings': 0,
              'pinctrl_schema_diagnostics': schema_logs['candidate'], 'new_schema_diagnostics': 0,
              'negative_controls_rejected': controls, 'SDHC2_GPIO37_active_low_preserved': True,
              'physical_card_detect_and_suspend_qualified': False}
    (out/'verification.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
