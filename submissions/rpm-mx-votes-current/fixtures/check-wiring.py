# SPDX-License-Identifier: GPL-2.0-only
"""Check compiled MX/Pronto/CPR wiring and reject invalid binding instances."""
from pathlib import Path
import argparse
import copy
import json
import dtschema

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('schema', type=Path)
p.add_argument('ordinary', type=Path)
p.add_argument('candidate', type=Path)
p.add_argument('previous_cpu', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
validator = dtschema.DTValidator([str(a.schema)])
trees = [validator.decode_dtb(path.read_bytes())[0] for path in [a.ordinary, a.candidate, a.previous_cpu]]


def find(tree, compatible):
    hits = []
    def walk(node):
        if not isinstance(node, dict):
            return
        if compatible in node.get('compatible', []):
            hits.append(node)
        for item in node.values():
            walk(item)
    walk(tree)
    assert len(hits) == 1, (compatible, len(hits))
    return hits[0]


def errors(node):
    return list(validator.iter_errors(node, filter=['regulator/qcom,smd-rpm-regulator.yaml']))


ordinary, cpu, previous = trees
normal_regs = find(ordinary, 'qcom,rpm-pm8226-regulators')
regs = find(cpu, 'qcom,rpm-pm8226-regulators')
assert not errors(normal_regs) and not errors(regs)
assert 'l3-ao' not in normal_regs and 'l3-ao' in regs and 'l3' in regs
cpr = find(cpu, 'qcom,msm8926-cpr')
pronto = find(cpu, 'qcom,pronto-v2-pil')
assert cpr['vdd-mx-supply'] == [[regs['l3-ao']['phandle']]]
assert pronto['vddmx-supply'] == [[regs['l3']['phandle']]]
assert find(ordinary, 'qcom,pronto-v2-pil')['vddmx-supply'] == [[normal_regs['l3']['phandle']]]
assert regs['l3-ao']['regulator-min-microvolt'] == [[750000]]
assert regs['l3-ao']['regulator-max-microvolt'] == [[1337500]]
assert not any(key.startswith('regulator-state-') for key in regs['l3-ao'])
assert find(previous, 'qcom,msm8926-cpr')['vdd-mx-supply'] == [[find(previous, 'qcom,rpm-pm8226-regulators')['l3']['phandle']]]


def without_phandles(node):
    if isinstance(node, dict):
        return {k: without_phandles(v) for k, v in node.items() if k != 'phandle'}
    return node


for name in ['opp-table-cpu', 'opp-table-cpr']:
    assert without_phandles(cpu[name]) == without_phandles(previous[name]), name
controls = []
node = copy.deepcopy(regs); del node['l3']
assert errors(node); controls.append('alias-requires-normal-l3')
node = copy.deepcopy(regs); node['compatible'] = ['qcom,rpm-pm8916-regulators']
assert errors(node); controls.append('alias-requires-pm8226')
for state in ['mem', 'disk', 'standby']:
    node = copy.deepcopy(regs)
    node['l3-ao']['regulator-state-' + state] = {'regulator-off-in-suspend': True}
    assert errors(node); controls.append('AO-rejects-suspend-' + state)
node = copy.deepcopy(regs); node['l3-ao']['invented-property'] = True
assert errors(node); controls.append('AO-rejects-unknown-property')
report = dict(passed=True, compiled_normal_and_AO_phandles_distinct_and_correct=True,
    normal_board_has_no_alias=True, CPU_and_CPR_OPPs_preserved=True,
    negative_binding_controls=controls, physical_radio_and_CPU_acceptance_qualified=False)
a.output.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
