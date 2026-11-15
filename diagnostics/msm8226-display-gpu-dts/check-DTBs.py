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
parser.add_argument('--iommu-source', required=True, type=Path)
args = parser.parse_args()
base = args.output.resolve()
base.mkdir(mode=0o700)
matrix = json.loads(args.inventory.read_text())
output = base / 'DTB-checks.json'
schema = args.candidate_build / 'Documentation/devicetree/bindings/processed-schema.json'
validator = dtschema.DTValidator([str(schema)])
added = {'/soc/iommu@fd928000', '/soc/iommu@fd928000/iommu-ctx@0',
         '/soc/iommu@fd928000/iommu-ctx@1000', '/soc/iommu@fd928000/iommu-ctx@2000',
         '/soc/iommu@fdb10000', '/soc/iommu@fdb10000/iommu-ctx@0',
         '/soc/iommu@fdb10000/iommu-ctx@1000'}


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

driver_head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=args.iommu_source, text=True).strip()
assert driver_head == '1d1963872f0f38d2c78aba1c97dc3ba01d6bbf23'
driver_path = args.iommu_source / 'drivers/iommu/arm/arm-smmu/qcom_iommu.c'
driver = driver_path.read_text()
clock_header = (args.iommu_source / 'include/dt-bindings/clock/qcom,mmcc-msm8974.h').read_text()
clock_ids = {name: int(value, 0) for name, value in re.findall(r'^#define\s+(\w+)\s+(0x[0-9a-fA-F]+|[0-9]+)\s*$', clock_header, re.M)}
scm = (args.iommu_source / 'include/linux/firmware/qcom/qcom_scm.h').read_text()
assert re.search(r'QCOM_SCM_MDSS_DEV_ID\s*=\s*1\s*,', scm)
sid_match = re.search(r'static const struct qcom_iommu_sid msm8974_gpu_sids\[\] = \{(.*?)\n\};', driver, re.S)
assert sid_match
sid_pairs = [(int(a), int(b)) for a, b in re.findall(r'\.cbndx = (\d+), \.sid = (\d+)', sid_match[1])]
assert sid_pairs == [(0, 0), (1, 1)]
bfb = {}
for name, count in [('gpu', 12), ('mdp', 18)]:
    match = re.search(r'static const struct qcom_iommu_bfb_reg msm8226_' + name + r'_bfb\[\] = \{(.*?)\n\};', driver, re.S)
    assert match
    offsets = [int(x, 16) for x in re.findall(r'\{ (0x[0-9a-f]+),', match[1])]
    assert len(offsets) == count
    bfb[name] = offsets
    cfg = re.search(r'static const struct qcom_iommu_cfg msm8226_' + name + r'_cfg = \{(.*?)\n\};', driver, re.S)
    assert cfg and '.fmt = ARM_V7S' in cfg[1] and '.ctx_restore = true' in cfg[1]
    if name == 'gpu':
        assert '.sids = msm8974_gpu_sids' in cfg[1]
    else:
        assert '.sids =' not in cfg[1]  # MDP mappings are managed by secure firmware.

def platform_contract(tree):
    soc = tree['soc']
    mdp = soc['iommu@fd928000']
    gpu = soc['iommu@fdb10000']
    assert mdp['status'] == gpu['status'] == soc['gpu@fdb00000']['status'] == ['disabled']
    assert soc['display-subsystem@fd900000']['status'] == ['disabled']
    assert mdp['compatible'] == ['qcom,msm8226-mdp-iommu']
    assert gpu['compatible'] == ['qcom,msm8226-gpu-iommu']
    assert mdp['qcom,iommu-secure-id'] == 1 and 'qcom,iommu-secure-id' not in gpu
    assert mdp['ranges'] == [[0, 0xfd930000, 0x3000]]
    assert gpu['ranges'] == [[0, 0xfdb18000, 0x2000]]
    for name, node, address, names, clock_names, irq, security in [
        ('mdp', mdp, 0xfd928000, ['MDSS_AHB_CLK', 'MDSS_AXI_CLK'], ['iface', 'bus'], 47, ['ns', 'sec', 'sec']),
        ('gpu', gpu, 0xfdb10000, ['OXILICX_AHB_CLK', 'OXILICX_AXI_CLK', 'OXILI_GFX3D_CLK'], ['iface', 'bus', 'tbu'], 241, ['ns', 'ns']),
    ]:
        assert node['reg'] == [[address, 0x2600]]
        assert node['#iommu-cells'] == 1
        assert [x[1] for x in node['clocks']] == [clock_ids[x] for x in names]
        assert node['clock-names'] == clock_names
        assert node['power-domains'][0][1] == clock_ids['MDSS_GDSC' if name == 'mdp' else 'OXILICX_GDSC']
        assert len([k for k in node if k.startswith('iommu-ctx@')]) == len(security)
        for i, suffix in enumerate(security):
            ctx = node['iommu-ctx@' + format(i * 0x1000, 'x')]
            assert ctx['reg'] == [[i * 0x1000, 0x1000]]
            assert ctx['interrupts'] == [[0, irq, 4]]
            assert ctx['compatible'] == ['qcom,msm-iommu-v1-' + suffix]
        assert all(0x2000 + off + 4 <= node['reg'][0][1] for off in bfb[name])
    assert soc['gpu@fdb00000']['iommus'] == [[gpu['phandle'], 0]]
    assert 0 in [sid for _, sid in sid_pairs]

comparisons = []
paths = []
for board in matrix:
    rel = Path('arch/arm/boot/dts') / board['target']
    old_path = args.baseline_build / rel
    new_path = args.candidate_build / rel
    old = normalize(validator.decode_dtb(old_path.read_bytes())[0])
    new_tree = validator.decode_dtb(new_path.read_bytes())[0]
    platform_contract(new_tree)
    new = normalize(new_tree)
    assert set(new) - set(old) == added
    assert not set(old) - set(new)
    assert 'iommus' not in old['/soc/gpu@fdb00000']
    assert new['/soc/gpu@fdb00000'].pop('iommus') == [['/soc/iommu@fdb10000', 0]]
    for path, props in old.items():
        assert props == new[path], (board['target'], path)
    comparisons.append({'board': board['target'], 'existing_nodes_preserved_except_disabled_GPU_attachment': len(old),
                        'added_nodes': sorted(added), 'candidate_SHA256': hashlib.sha256(new_path.read_bytes()).hexdigest()})
    paths.append(new_path)

contract_controls = []
tree = validator.decode_dtb(paths[0].read_bytes())[0]
for name in ['GPU-stream-outside-contexts', 'MDP-secured-bank-made-nonsecure', 'GPU-global-window-too-small', 'GPU-context-offset-changed']:
    bad = copy.deepcopy(tree)
    if name == 'GPU-stream-outside-contexts':
        bad['soc']['gpu@fdb00000']['iommus'][0][1] = 2
    elif name == 'MDP-secured-bank-made-nonsecure':
        bad['soc']['iommu@fd928000']['iommu-ctx@1000']['compatible'] = ['qcom,msm-iommu-v1-ns']
    elif name == 'GPU-global-window-too-small':
        bad['soc']['iommu@fdb10000']['reg'][0][1] = 0x1000
    else:
        bad['soc']['iommu@fdb10000']['iommu-ctx@1000']['reg'][0][0] = 0x2000
    try:
        platform_contract(bad)
    except AssertionError:
        contract_controls.append(name)
    else:
        raise AssertionError(name)

cli = Path(sys.executable).parent / 'dt-validate'
filters = 'media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml:display/msm/gpu.yaml'
common = [str(cli), '-s', str(schema), '-l', filters]
positive = subprocess.run(common + list(map(str, paths)), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(base / 'direct-board-schema.stdout').write_bytes(positive.stdout)
(base / 'direct-board-schema.stderr').write_bytes(positive.stderr)
assert positive.returncode == 0 and not positive.stdout and not positive.stderr

controls_dir = base / 'actual-board-schema-controls-01'
controls_dir.mkdir()
controls = []
schema_coverage_limits = []
mdp = '/soc/iommu@fd928000'
gpu = '/soc/iommu@fdb10000'
mutations = [
    ('invalid-MDP-clock-name', ['-t', 's', mdp, 'clock-names', 'unrelated']),
    ('invalid-GPU-IOMMU-clock-name', ['-t', 's', gpu, 'clock-names', 'unrelated']),
    ('invalid-MDP-context-compatible', ['-t', 's', mdp + '/iommu-ctx@0', 'compatible', 'qcom,unrelated-context']),
    ('invalid-GPU-IOMMU-cell-count', ['-t', 'x', gpu, '#iommu-cells', '2']),
    ('invalid-GPU-context-IRQ-type', ['-t', 's', gpu + '/iommu-ctx@0', 'interrupts', 'invalid']),
    ('invalid-Adreno-clock-count', ['-t', 'x', '/soc/gpu@fdb00000', 'clocks', '0']),
]
for name, mutation in mutations:
    path = controls_dir / (name + '.dtb')
    path.write_bytes(paths[0].read_bytes())
    options = mutation[:2]
    subprocess.run(['fdtput', *options, str(path), *mutation[2:]], check=True)
    result = subprocess.run(common + [str(path)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    (controls_dir / (name + '.stdout')).write_bytes(result.stdout)
    (controls_dir / (name + '.stderr')).write_bytes(result.stderr)
    if name == 'invalid-GPU-context-IRQ-type':
        # Generic IRQ matrices do not encode the GIC's three-cell contract.
        # Preserve the malformed-DTB control and verify the platform check
        # rejects the actual decoded input despite an empty schema diagnostic.
        assert result.returncode == 0 and not result.stderr and not result.stdout
        bad = validator.decode_dtb(path.read_bytes())[0]
        assert bad['soc']['iommu@fdb10000']['iommu-ctx@0']['interrupts'] == [[1768846945, 1818846208]]
        try:
            platform_contract(bad)
        except AssertionError:
            schema_coverage_limits.append(dict(name=name, schema_returncode=result.returncode,
                                              schema_diagnostics_empty=True, platform_contract_rejected=True))
        else:
            raise AssertionError(name)
    else:
        assert result.stderr, name
        controls.append(dict(name=name, returncode=result.returncode, diagnostics=result.stderr.decode()))

def warnings(name):
    return Counter(re.sub(r'^.*?:\d+\.\d+(?:-\d+\.\d+)?: ', '', line)
                   for line in name.read_text().splitlines() if 'Warning (' in line)
old_warnings = warnings(args.baseline_log)
new_warnings = warnings(args.candidate_log)
assert old_warnings == new_warnings
assert not any('warning:' in line.lower() or 'error:' in line.lower()
               for line in args.binding_log.read_text().splitlines())
enabled = controls_dir / 'enabled-IOMMU-schema-positive.dtb'
enabled.write_bytes(paths[0].read_bytes())
for node in [mdp, gpu]:
    subprocess.run(['fdtput', '-t', 's', str(enabled), node, 'status', 'okay'], check=True)
result = subprocess.run(common + [str(enabled)], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
(controls_dir / 'enabled-IOMMU-schema-positive.stderr').write_bytes(result.stderr)
assert result.returncode == 0 and not result.stderr and not result.stdout
record = dict(passed=True, board_count=len(paths), comparisons=comparisons,
              ordinary_kernel_bindings_and_DTB_checks_passed=True,
              direct_targeted_schema_diagnostics_empty=True,
              existing_DTC_warning_count=sum(old_warnings.values()), new_DTC_warnings=0,
              schema_rejection_controls=controls, platform_contract_rejection_controls=contract_controls,
              schema_coverage_limits=schema_coverage_limits,
              enabled_IOMMU_schema_only_positive_passed=True,
              IOMMU_driver_head=driver_head, IOMMU_driver_SHA256=hashlib.sha256(driver_path.read_bytes()).hexdigest(),
              GPU_stream_context_pairs=sid_pairs, MDP_prefetch_entries=len(bfb['mdp']), GPU_prefetch_entries=len(bfb['gpu']),
              MDP_security_and_SCM_ID_verified=True, common_nodes_and_GPU_disabled=True,
              enabled_Fx0_board_qualified=False, runtime_or_hardware_qualified=False, phone_access=False)
output.write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k: record[k] for k in ['passed', 'board_count', 'existing_DTC_warning_count', 'new_DTC_warnings']}))
