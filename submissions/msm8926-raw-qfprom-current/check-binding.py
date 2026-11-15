# SPDX-License-Identifier: GPL-2.0-only
"""Validate raw/corrected QFPROM profiles using the complete Fx0 DTB."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['schema', 'board', 'validator', 'binding', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    expected = 'c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65'
    assert sha(args.board) == expected
    node = '/soc/efuse@fc4b8000'

    def cells(path, prop):
        return subprocess.check_output(['fdtget', '-t', 'u', str(args.board), path, prop], text=True).split()

    def validate(name, path):
        result = subprocess.run([str(args.validator), '-s', str(args.schema), '-l',
                                 'nvmem/qcom,qfprom.yaml', str(path)], capture_output=True, timeout=120)
        (args.output / (name + '.stdout')).write_bytes(result.stdout)
        (args.output / (name + '.stderr')).write_bytes(result.stderr)
        assert result.returncode == 0 and not result.stdout
        return result.stderr

    def case(name, edits):
        path = args.output / (name + '.dtb')
        path.write_bytes(args.board.read_bytes())
        for options, prop, values in edits:
            subprocess.run(['fdtput', *options, str(path), node, prop, *values], check=True)
        return path

    assert not validate('complete-unchanged-Fx0', args.board)
    positives = ['complete-unchanged-Fx0']
    compatibles = re.findall(r'^\s+- (qcom,[\w,-]+)$', args.binding.read_text(), re.M)
    assert len(compatibles) == 48 and len(set(compatibles)) == 48
    for compatible in compatibles:
        name = compatible.replace(',', '-')
        path = case(name, [(['-t', 's'], 'compatible', [compatible, 'qcom,qfprom'])])
        assert not validate(name, path), compatible
        positives.append(name)
    gpio_clock = cells('/soc/clock-controller@fc400000', 'phandle') + ['0']
    vcc = cells('/soc/display-subsystem@fd900000/dsi@fd922800/panel@0', 'vdd-supply')
    one_reg = cells(node, 'reg')
    negatives = []
    for name, edits, diagnostic in [
        ('missing-read-only', [(['-d'], 'read-only', [])], 'read-only'),
        ('missing-reg', [(['-d'], 'reg', [])], 'reg'),
        ('programming-regions', [(['-t', 'u'], 'reg', one_reg * 4)], 'reg'),
        ('three-regions', [(['-t', 'u'], 'reg', one_reg * 3)], 'reg'),
        ('clock', [(['-t', 'u'], 'clocks', gpio_clock)], 'False schema does not allow'),
        ('clock-name', [(['-t', 's'], 'clock-names', ['core'])], 'False schema does not allow'),
        ('vcc-supply', [(['-t', 'u'], 'vcc-supply', vcc)], 'False schema does not allow'),
        ('corrected-fallback', [(['-t', 's'], 'compatible', ['qcom,msm8926-qfprom-raw', 'qcom,qfprom'])], 'compatible'),
        ('duplicate-raw-compatible', [(['-t', 's'], 'compatible', ['qcom,msm8926-qfprom-raw'] * 2)], 'compatible'),
        ('unknown-property', [(['-t', 'u'], 'qcom,unexpected-control', ['1'])], 'qcom,unexpected-control'),
    ]:
        error = validate(name, case(name, edits))
        assert b'qcom,qfprom' in error and diagnostic.encode() in error, (name, error)
        negatives.append(name)
    assert sha(args.board) == expected
    record = dict(passed=True, positive_profiles=positives, rejected_controls=negatives,
                  all_48_existing_compatible_profiles_preserved=True,
                  corrected_profiles_are_schema_controls_not_physical_boards=True,
                  ordinary_binding_examples_checked_separately=True,
                  complete_original_Fx0_DTB_SHA256=expected, original_board_modified=False,
                  board_rebuilt=False, only_QFPROM_schema_selected=True,
                  full_board_schema_or_hardware_qualified=False,
                  schema_SHA256=sha(args.schema), binding_SHA256=sha(args.binding),
                  checker_SHA256=sha(Path(__file__)))
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, positive_profiles=len(positives), rejected_controls=len(negatives))))


if __name__ == '__main__':
    main()
