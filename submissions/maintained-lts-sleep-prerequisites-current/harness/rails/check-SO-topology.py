# SPDX-License-Identifier: GPL-2.0-only
"""Compare actual factories registering the valid three-voter topology without contradictory assertions."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('boot', B / 'check-boot.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--baseline', action='store_true')
a = p.parse_args()
code, bindings = m.model(a.source, a.source, a.source)
code = code[:code.index('int main(void)\n{')]
code += '''int main(void)
{
    const struct regulator_ops *ops[] = {&rpm_smps_ldo_ops_fixed, &rpm_switch_ops,
        &rpm_bob_ops, &rpm_mp5496_ops};
    for (unsigned i = 0; i < sizeof(ops) / sizeof(ops[0]); ++i)
        EXPECT(ops[i]->set_suspend_disable == rpm_reg_set_suspend_disable);
    const unsigned permutations[6][3] = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    int result_codes[6]; unsigned registrations[6];
    for (unsigned order = 0; order < 6; ++order) {
        struct platform_device pdev; struct device parent; struct device_node bank, nodes[3];
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_boot(&pdev, &parent, &bank, &nodes[0], &nodes[1], &rpm, &ep, false, 1100000);
        nodes[2] = (struct device_node){.name = "l3-so", .available = true,
            .min_uV = 750000, .max_uV = 1337500};
        for (unsigned i = 0; i < 3; ++i)
            nodes[permutations[order][i]].next = i == 2 ? NULL : &nodes[permutations[order][i+1]];
        bank.child = &nodes[permutations[order][0]];
        int ret = rpm_reg_probe(&pdev);
        result_codes[order] = ret; registrations[order] = factory_registers;
        EXPECT(ret == 0 && factory_registers == 3); /* The valid new topology requires all three voters. */
        fprintf(stderr,"topology %u result %d registrations %u\\n", order, ret, factory_registers);
        release_arena();
        for (unsigned i = 0; i < 3; ++i) EXPECT(!nodes[i].refs);
        EXPECT(!allocated); ++cases;
    }
    printf("{\\"cases\\":%u,\\"checks\\":%u,\\"failures\\":%u}\\n", cases, checks, failures);
    return 0;
}
'''
j = m.pair.run_code(code, a.output)
assert j['cases'] == 6 and j['failures'] == (6 if a.baseline else 0)
j.update(actual_source_functions=bindings, baseline=a.baseline, valid_three_voter_topology_registered=(j['failures']==0), test_has_no_mutually_exclusive_expectations=True, unsupported_new_feature_not_generic_core_defect=True,
    baseline_comparison_is_factory_topology_only=True, full_new_feature_suite_not_claimed_on_unsupported_parent=True,
    normal_LSan_and_failfast_ASan_UBSan=True, no_phone_network_radio_or_audio_execution=True)
(a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
print(json.dumps({k:j[k] for k in ['cases','checks','failures']}))
