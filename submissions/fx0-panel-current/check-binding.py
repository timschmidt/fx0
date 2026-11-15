# SPDX-License-Identifier: GPL-2.0-only
"""Validate the panel schema against the full unchanged Fx0 DTB and bad controls."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['schema', 'board', 'validator', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    expected = 'c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65'
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    assert sha(args.board) == expected
    node = '/soc/display-subsystem@fd900000/dsi@fd922800/panel@0'
    result = subprocess.run(['fdtget', str(args.board), node, 'compatible'], capture_output=True, check=True)
    assert result.stdout.strip() == b'lg,fx0-panel'

    def validate(name, path):
        result = subprocess.run([str(args.validator), '-s', str(args.schema), '-l',
                                 'display/panel/lg,fx0-panel.yaml', str(path)],
                                capture_output=True, timeout=120)
        (args.output / (name + '.stdout')).write_bytes(result.stdout)
        (args.output / (name + '.stderr')).write_bytes(result.stderr)
        assert result.returncode == 0 and not result.stdout
        return result.stderr

    assert not validate('complete-unchanged-Fx0', args.board)
    def cells(prop):
        return subprocess.check_output(['fdtget', '-t', 'u', str(args.board), node, prop],
                                       text=True).split()

    required = ['compatible', 'reg', 'vdd-supply', 'reset-gpios', 'io-enable-gpios',
                'positive-enable-gpios', 'negative-enable-gpios', 'backlight', 'port']
    # Removing compatible prevents this schema from selecting the node; test
    # only required properties whose deletion retains the real selector.
    controls = []
    for prop in required[1:]:
        path = args.output / ('missing-' + prop + '.dtb')
        path.write_bytes(args.board.read_bytes())
        if prop == 'port':
            subprocess.run(['fdtput', '-r', str(path), node + '/port'], check=True)
        else:
            subprocess.run(['fdtput', '-d', str(path), node, prop], check=True)
        error = validate('missing-' + prop, path)
        assert b'lg,fx0-panel' in error and prop.encode() in error and b'required' in error
        controls.append('missing-' + prop)
    for name, prop, kind, values, diagnostic in [
        ('two-addresses', 'reg', 'i', ['0', '1'], 'reg'),
        ('unknown-property', 'lge,unexpected-control', 'i', ['1'], 'lge,unexpected-control'),
        ('two-reset-GPIOs', 'reset-gpios', 'i', cells('reset-gpios') * 2, 'reset-gpios'),
        ('backlight-two-phandles', 'backlight', 'i', cells('backlight') * 2, 'backlight'),
        ('two-IO-GPIOs', 'io-enable-gpios', 'i', cells('io-enable-gpios') * 2, 'io-enable-gpios'),
    ]:
        path = args.output / (name + '.dtb')
        path.write_bytes(args.board.read_bytes())
        subprocess.run(['fdtput', '-t', kind, str(path), node, prop, *values], check=True)
        error = validate(name, path)
        assert b'lg,fx0-panel' in error and diagnostic.encode() in error, (name, error)
        controls.append(name)
    assert sha(args.board) == expected
    record = dict(passed=True, positive_cases=['complete-unchanged-Fx0'], rejected_controls=controls,
                  complete_original_Fx0_DTB_SHA256=expected, original_board_modified=False,
                  board_rebuilt=False, only_panel_schema_selected=True,
                  full_board_schema_or_hardware_qualified=False,
                  schema_SHA256=sha(args.schema), checker_SHA256=sha(Path(__file__)))
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
