# SPDX-License-Identifier: GPL-2.0-only
"""Compare real affected DTBs and exercise targeted schema rejection."""
from pathlib import Path
from collections import Counter
import argparse
import sys
import copy
import hashlib
import json
import re
import subprocess
import dtschema

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--inventory', required=True, type=Path)
parser.add_argument('--baseline-build', required=True, type=Path)
parser.add_argument('--candidate-build', required=True, type=Path)
parser.add_argument('--baseline-log', required=True, type=Path)
parser.add_argument('--candidate-log', required=True, type=Path)
parser.add_argument('--binding-log', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
base = args.output.resolve()
base.mkdir(mode=0o700)
matrix = json.loads(args.inventory.read_text())
output = base / 'DTB-checks.json'
schema = args.candidate_build / 'Documentation/devicetree/bindings/processed-schema.json'
validator = dtschema.DTValidator([str(schema)])
added = {'/soc/camss@fda0ac00', '/soc/camss@fda0ac00/ports',
         '/soc/iommu@fda44000', '/soc/iommu@fda44000/iommu-ctx@0',
         '/soc/iommu@fda44000/iommu-ctx@1000', '/soc/iommu@fda44000/iommu-ctx@2000'}

def flatten(tree):
    result = {}
    def walk(node, path):
        result[path] = {k: v for k, v in node.items() if not isinstance(v, dict)}
        for key, value in node.items():
            if isinstance(value, dict):
                walk(value, path.rstrip('/') + '/' + key)
    walk(tree, '/')
    return result

def normalize(tree):
    flat = flatten(tree)
    phandles = {node['phandle']: path for path, node in flat.items() if 'phandle' in node}
    normalized = copy.deepcopy(flat)
    for path, node in normalized.items():
        node.pop('phandle', None)
        for prop, value in node.items():
            types = validator.property_get_type(prop)
            if types in [{'phandle'}, {'phandle-array'}]:
                assert isinstance(value, list), (path, prop, value)
                for row in value:
                    assert isinstance(row, list) and row, (path, prop, row)
                    if row[0] == 0:
                        # A null phandle is a real empty slot (e.g. SMSM mboxes).
                        continue
                    assert row[0] in phandles, (path, prop, row)
                    row[0] = phandles[row[0]]
    return normalized

comparisons = []
paths = []
for board in matrix:
    rel = Path('arch/arm/boot/dts') / board['target']
    old_path = args.baseline_build / rel
    new_path = args.candidate_build / rel
    old = normalize(validator.decode_dtb(old_path.read_bytes())[0])
    new_tree = validator.decode_dtb(new_path.read_bytes())[0]
    new = normalize(new_tree)
    assert set(new) - set(old) == added
    assert not set(old) - set(new)
    for path, props in old.items():
        assert props == new[path], (board['target'], path)
    cam = new_tree['soc']['camss@fda0ac00']
    iommu = new_tree['soc']['iommu@fda44000']
    assert cam['status'] == iommu['status'] == ['disabled']
    assert 'vdda-supply' not in cam
    assert len(cam['clocks']) == 18 and len(cam['reg']) == 9 and len(cam['interrupts']) == 6
    assert cam['iommus'][0][0] == iommu['phandle'] and cam['iommus'][0][1] == 0
    assert iommu['reg'] == [[0xfda44000, 0x2600]]
    assert iommu['ranges'] == [[0, 0xfda4c000, 0x3000]]
    assert [x[1] for x in iommu['clocks']] == [90, 91, 85]
    for i in range(3):
        ctx = iommu['iommu-ctx@' + format(i * 0x1000, 'x')]
        assert ctx['reg'] == [[i * 0x1000, 0x1000]]
        assert ctx['interrupts'] == [[0, 65, 4]]
    comparisons.append({'board': board['target'], 'existing_nodes_unchanged_after_schema_typed_phandle_resolution': len(old),
                        'added_nodes': sorted(added), 'candidate_SHA256': hashlib.sha256(new_path.read_bytes()).hexdigest()})
    paths.append(new_path)

cli = Path(sys.executable).parent / 'dt-validate'
filters = 'media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml'
common = [str(cli), '-s', str(schema), '-l', filters]
positive = subprocess.run(common + list(map(str, paths)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(base / 'direct-board-schema.stdout').write_bytes(positive.stdout)
(base / 'direct-board-schema.stderr').write_bytes(positive.stderr)
assert positive.returncode == 0 and not positive.stdout and not positive.stderr

controls_dir = base / 'actual-board-schema-controls-01'
controls_dir.mkdir()
controls = []
cam = '/soc/camss@fda0ac00'
iommu = '/soc/iommu@fda44000'
mutations = [
    ('invalid-CAMSS-clock-name', ['-t', 's', cam, 'clock-names', 'unrelated']),
    ('invalid-VFE-clock-name', ['-t', 's', iommu, 'clock-names', 'unrelated']),
    ('invalid-VFE-context-compatible', ['-t', 's', iommu + '/iommu-ctx@0', 'compatible', 'qcom,unrelated-context']),
    ('enabled-CAMSS-missing-board-supply', ['-t', 's', cam, 'status', 'okay']),
    ('invalid-CAMSS-register-count', ['-t', 'x', cam, 'reg', 'fda0ac00', '200']),
    ('invalid-IOMMU-cell-count', ['-t', 'x', iommu, '#iommu-cells', '2']),
]
for name, mutation in mutations:
    path = controls_dir / (name + '.dtb')
    path.write_bytes(paths[0].read_bytes())
    options = mutation[:2]
    subprocess.run(['fdtput', *options, str(path), *mutation[2:]], check=True)
    result = subprocess.run(common + [str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (controls_dir / (name + '.stdout')).write_bytes(result.stdout)
    (controls_dir / (name + '.stderr')).write_bytes(result.stderr)
    assert result.stderr, name
    if name == 'enabled-CAMSS-missing-board-supply':
        assert b'vdda-supply' in result.stderr and b'required' in result.stderr
    controls.append(dict(name=name, returncode=result.returncode, diagnostics=result.stderr.decode()))

def warnings(name):
    return Counter(re.sub(r'^.*?:\d+\.\d+(?:-\d+\.\d+)?: ', '', line)
                   for line in name.read_text().splitlines() if 'Warning (' in line)
old_warnings = warnings(args.baseline_log)
new_warnings = warnings(args.candidate_log)
assert old_warnings == new_warnings
assert not any('warning:' in line.lower() or 'error:' in line.lower()
               for line in args.binding_log.read_text().splitlines())
record = dict(passed=True, board_count=len(paths), comparisons=comparisons,
              ordinary_kernel_bindings_and_DTB_checks_passed=True,
              direct_targeted_schema_diagnostics_empty=True,
              existing_DTC_warning_count=sum(old_warnings.values()), new_DTC_warnings=0,
              rejection_controls=controls, board_specific_supply_requirement_preserved=True,
              common_nodes_disabled=True, enabled_Fx0_board_qualified=False,
              runtime_or_hardware_qualified=False, phone_access=False)
output.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ['passed', 'board_count', 'existing_DTC_warning_count', 'new_DTC_warnings']}))
