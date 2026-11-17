# SPDX-License-Identifier: GPL-2.0-only
"""Validate compiled legacy/VFE examples and active schema rejection controls."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import dtschema

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--build', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
assert not args.output.exists()
schema = args.build / 'Documentation/devicetree/bindings/processed-schema.json'
example = args.build / 'Documentation/devicetree/bindings/iommu/qcom,iommu.example.dtb'
validator = dtschema.DTValidator([str(schema)])
tree = validator.decode_dtb(example.read_bytes())[0]
legacy = tree['example-0']['iommu@1e20000']
vfe = tree['example-1']['iommu@fda44000']

def errors(node, name):
    node = copy.deepcopy(node)
    node['$nodename'] = [name]
    return list(validator.iter_errors(node, filter=['iommu/qcom,iommu.yaml']))

assert not errors(legacy, 'iommu@1e20000')
assert not errors(vfe, 'iommu@fda44000')
without_local = copy.deepcopy(legacy)
del without_local['reg']
assert not errors(without_local, 'iommu@1e20000')
assert 'qcom,iommu-secure-id' not in vfe
assert vfe['reg'] == [[0xfda44000, 0x2600]]
assert vfe['ranges'] == [[0, 0xfda4c000, 0x3000]]
assert vfe['clock-names'] == ['iface', 'bus', 'tbu']
assert [clock[1] for clock in vfe['clocks']] == [90, 91, 85]
assert vfe['power-domains'][0][1] == 3
assert vfe['#iommu-cells'] == 1
for index in range(3):
    ctx = vfe['iommu-ctx@' + format(index * 0x1000, 'x')]
    assert ctx['reg'] == [[index * 0x1000, 0x1000]]
    assert ctx['interrupts'] == [[0, 65, 4]]
    assert ctx['compatible'] == ['qcom,msm-iommu-v1-ns']

controls = []
for prop in ['reg', 'ranges']:
    bad = copy.deepcopy(vfe)
    del bad[prop]
    assert errors(bad, 'iommu@fda44000'), prop
    controls.append('missing ' + prop)
bad = copy.deepcopy(vfe)
bad['clocks'] = bad['clocks'][:1]
assert errors(bad, 'iommu@fda44000')
controls.append('only one clock')
bad = copy.deepcopy(vfe)
bad['clock-names'][0] = 'unrelated'
assert errors(bad, 'iommu@fda44000')
controls.append('incorrect clock name')
bad = copy.deepcopy(vfe)
bad['#iommu-cells'] = 2
assert errors(bad, 'iommu@fda44000')
controls.append('incorrect iommu cells')
bad = copy.deepcopy(vfe)
bad['iommu-ctx@0']['compatible'] = ['qcom,unrelated-context']
assert errors(bad, 'iommu@fda44000')
controls.append('incorrect context compatible')
bad = copy.deepcopy(vfe)
del bad['iommu-ctx@0']['interrupts']
assert errors(bad, 'iommu@fda44000')
controls.append('missing context IRQ')
bad = copy.deepcopy(vfe)
bad['undocumented-property'] = True
assert errors(bad, 'iommu@fda44000')
controls.append('undocumented property')
source = (args.source / 'drivers/iommu/arm/arm-smmu/qcom_iommu.c').read_text()
match = re.search(r'static const struct qcom_iommu_sid msm8226_vfe_sids\[\] = \{(.*?)\n\};', source, re.S)
assert match
pairs = [(int(a), int(b)) for a, b in re.findall(r'\.cbndx = (\d+), \.sid = (\d+)', match[1])]
assert pairs == [(0, 0), (1, 1), (2, 2)]
match = re.search(r'static const struct qcom_iommu_bfb_reg msm8226_vfe_bfb\[\] = \{(.*?)\n\};', source, re.S)
assert match
offsets = [int(a, 16) for a in re.findall(r'\{ (0x[0-9a-f]+),', match[1])]
assert len(offsets) == 18 and all(0x2000 + off + 4 <= 0x2600 for off in offsets)
result = dict(passed=True, positive_schema_cases=3, schema_rejection_controls=controls,
              actual_VFE_context_banks=3, VFE_stream_to_context_pairs=pairs,
              VFE_prefetch_registers_within_declared_global_window=len(offsets),
              example_SHA256=hashlib.sha256(example.read_bytes()).hexdigest(),
              driver_SHA256=hashlib.sha256(source.encode()).hexdigest(),
              legacy_optional_local_region_preserved=True,
              scope='Compiled examples, schema and platform-data contract; no board DTB or hardware acceptance',
              phone_access=False)
args.output.write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
