# SPDX-License-Identifier: GPL-2.0-only
"""Validate both sensor bindings with the complete unchanged Fx0 DTB."""
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
    sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
    expected = 'c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65'
    assert sha(args.board) == expected
    rows = []
    for sensor, address, lanes in [('imx132', '36', [1]), ('imx179', '10', [1, 2, 3, 4])]:
        node = '/soc/cci@fda0c000/i2c-bus@0/camera@' + address
        endpoint = node + '/port/endpoint'

        def validate(name, path):
            result = subprocess.run([str(args.validator), '-s', str(args.schema), '-l',
                                     'media/i2c/sony,' + sensor + '.yaml', str(path)],
                                    capture_output=True, timeout=120)
            (args.output / (sensor + '-' + name + '.stdout')).write_bytes(result.stdout)
            (args.output / (sensor + '-' + name + '.stderr')).write_bytes(result.stderr)
            assert result.returncode == 0 and not result.stdout
            return result.stderr

        def cells(path, prop):
            return subprocess.check_output(['fdtget', '-t', 'u', str(args.board), path, prop], text=True).split()

        def case(name, edits):
            path = args.output / (sensor + '-' + name + '.dtb')
            path.write_bytes(args.board.read_bytes())
            for options, target, prop, values in edits:
                if options == ['-r']:
                    subprocess.run(['fdtput', '-r', str(path), target], check=True)
                else:
                    subprocess.run(['fdtput', *options, str(path), target, prop, *values], check=True)
            return path

        assert not validate('complete-unchanged-Fx0', args.board)
        positives = ['complete-unchanged-Fx0']
        if sensor == 'imx132':
            path = case('two-lane-hardware-binding', [(['-t', 'u'], endpoint, 'data-lanes', ['1', '2'])])
            assert not validate('two-lane-hardware-binding', path)
            positives.append('two-lane-hardware-binding')
        negatives = []
        for prop in ['reg', 'clocks', 'dovdd-supply', 'avdd-supply', 'dvdd-supply', 'reset-gpios']:
            name = 'missing-' + prop
            error = validate(name, case(name, [(['-d'], node, prop, [])]))
            assert (sensor + '.yaml').encode() in error and prop.encode() in error and b'required' in error
            negatives.append(name)
        name = 'missing-port'
        error = validate(name, case(name, [(['-r'], node + '/port', '', [])]))
        assert (sensor + '.yaml').encode() in error and b'port' in error and b'required' in error
        negatives.append(name)
        for name, target, options, prop, values, diagnostic in [
            ('missing-data-lanes', endpoint, ['-d'], 'data-lanes', [], 'data-lanes'),
            ('missing-link-frequency', endpoint, ['-d'], 'link-frequencies', [], 'link-frequencies'),
            ('wrong-lane-order', endpoint, ['-t', 'u'], 'data-lanes', ['2'], 'data-lanes'),
            ('too-many-lanes', endpoint, ['-t', 'u'], 'data-lanes', ['1', '2', '3'] if sensor == 'imx132' else ['1', '2', '3', '4', '5'], 'data-lanes'),
            ('unknown-endpoint-property', endpoint, ['-t', 'u'], 'sony,unexpected-control', ['1'], 'sony,unexpected-control'),
            ('unknown-sensor-property', node, ['-t', 'u'], 'sony,unexpected-control', ['1'], 'sony,unexpected-control'),
            ('two-addresses', node, ['-t', 'u'], 'reg', cells(node, 'reg') * 2, 'reg'),
            ('two-clocks', node, ['-t', 'u'], 'clocks', cells(node, 'clocks') * 2, 'clocks'),
            ('two-reset-GPIOs', node, ['-t', 'u'], 'reset-gpios', cells(node, 'reset-gpios') * 2, 'reset-gpios'),
        ]:
            error = validate(name, case(name, [(options, target, prop, values)]))
            assert (sensor + '.yaml').encode() in error and diagnostic.encode() in error, (sensor, name, error)
            negatives.append(name)
        rows.append(dict(sensor=sensor, positive_profiles=positives, rejected_controls=negatives))
    assert sha(args.board) == expected
    record = dict(passed=True, rows=rows, complete_original_Fx0_DTB_SHA256=expected,
                  original_board_modified=False, board_rebuilt=False,
                  only_sensor_schemas_selected=True, full_board_schema_or_hardware_qualified=False,
                  IMX132_two_lane_profile_is_binding_capability_not_current_driver_support=True,
                  schema_SHA256=sha(args.schema), checker_SHA256=sha(Path(__file__)))
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(dict(passed=True, positive_profiles=sum(len(r['positive_profiles']) for r in rows),
                         rejected_controls=sum(len(r['rejected_controls']) for r in rows))))


if __name__ == '__main__':
    main()
