# SPDX-License-Identifier: GPL-2.0-only
"""Reject independent SLEEP-voter regressions in generated synthetic models."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sleep_voter', B / 'check-sleep-voter.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--transport-source', required=True, type=Path)
p.add_argument('--cpu-source', required=True, type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = m.model(a.source, a.transport_source, a.cpu_source)
function = m.boot.pair.legacy.function
controls = []


def change(name, func, before, after, assertion):
    body = function(code, func)
    assert body.count(before) == 1 and before != after, name
    controls.append((name, code.replace(body, body.replace(before, after)), assertion))


change('SO-voltage-omitted', 'rpm_reg_pair_sleep_vote',
       'vote.uV = max(vote.uV, sleep_only->uV);', 'vote.uV = vote.uV;', 'fw[1].uV == 1337500')
change('SO-enable-omitted', 'rpm_reg_pair_sleep_vote',
       'vote.enabled |= sleep_only->enabled || pair->boot_sleep_uV;',
       'vote.enabled |= !!pair->boot_sleep_uV;', 'proposed.enabled && proposed.uV >= apc_voltage')
change('AO-contaminates-SLEEP', 'rpm_reg_pair_sleep_vote',
       'vote.uV = max(vote.uV, sleep_only->uV);',
       'vote.uV = max(max(vote.uV, sleep_only->uV), pair->votes[1].uV);', 'fw[1].uV == uv')
change('SO-contaminates-ACTIVE', 'rpm_reg_write_triple',
       '.uV = max(normal->uV, ao->uV),', '.uV = max(max(normal->uV, ao->uV), so->uV),',
       'fw[0].uV == 900000 && fw[1].uV == 1337500')
change('SO-sent-to-ACTIVE', 'rpm_reg_write_triple',
       'if (vreg->sleep_only) {\n\t\tret = rpm_reg_send_vote(vreg, QCOM_SMD_RPM_SLEEP_STATE, &sleep);',
       'if (vreg->sleep_only) {\n\t\tret = rpm_reg_send_vote(vreg, QCOM_SMD_RPM_ACTIVE_STATE, &sleep);',
       'states[i] == QCOM_SMD_RPM_SLEEP_STATE')
change('sleep-handoff-never-releases-ceiling', 'rpm_reg_write_triple',
       'pair->boot_sleep_uV = 0;', '(void)sleep_handoff;', 'pair->boot_sleep_uV == 0')
change('sleep-release-fails-to-rearm', 'rpm_reg_write_triple',
       'pair->boot_sleep_uV = pair->boot_max_uV;', 'pair->boot_sleep_uV = 0;',
       'pair->boot_sleep_uV == 1337500')
change('failed-release-loses-rearmed-hold', 'rpm_reg_write_triple',
       'pair->boot_sleep_uV = max(previous_boot_sleep, pair->boot_sleep_uV);',
       'pair->boot_sleep_uV = previous_boot_sleep;', 'f.pair.boot_sleep_uV == 1337500')
change('boot-sleep-voltage-omitted', 'rpm_reg_pair_sleep_vote',
       'vote.uV = max(vote.uV, pair->boot_sleep_uV);', 'vote.uV = vote.uV;',
       'proposed.enabled && proposed.uV >= apc_voltage')
change('normal-write-infers-SO-handoff', 'rpm_reg_pair_sleep_vote',
       'if (!handoff)', 'if (!(sleep_only->enabled && sleep_only->uV >= pair->boot_min_uV))',
       'fw[1].enabled && fw[1].uV == 1337500 && f.pair.boot_sleep_uV == 1337500')
change('SO-load-overflow-wraps', 'rpm_reg_pair_sleep_vote',
       '(u64)vote.load + sleep_only->load', 'vote.load + sleep_only->load',
       'UINT32_MAX / 1000')
change('SO-slot-not-restored', 'rpm_reg_write_triple',
       'pair->votes[index] = previous;', '(void)previous;', 'same_vote(f.pair.votes[actor], previous)')
change('normal-partial-policy-not-restored', 'rpm_reg_write_suspend_triple',
       'pair->sleep_voltage_valid = voltage_valid;', '(void)voltage_valid;',
       '!f.pair.sleep_voltage_valid')
change('SO-guard-policy-not-validated', 'rpm_reg_pair_init_boot',
       'ret = rpm_reg_pair_check_sleep_node(dev, max_uV);', 'ret = 0;',
       '!wire_calls && !live_count && !factory_registers')
change('boot-sleep-hold-not-initialized', 'rpm_reg_pair_init_boot',
       'pair->boot_sleep_uV = max_uV;', 'pair->boot_sleep_uV = 0;',
       'proposed.enabled && proposed.uV >= apc_voltage')
change('CPR-sleep-guard-disabled-in-DT', 'cpr_sleep_vote_init',
       'if (!of_property_present(dev->of_node, "vdd-mx-sleep-supply"))',
       'if (true || !of_property_present(dev->of_node, "vdd-mx-sleep-supply"))',
       'out == &f.so && f.so.enable_count == 1 && cleanup_action')
cleanup_main = '''int main(void)
{
    const struct regulator_ops *ops[] = {&rpm_smps_ldo_ops_fixed, &rpm_switch_ops,
        &rpm_bob_ops, &rpm_mp5496_ops};
    for (unsigned i = 0; i < sizeof(ops) / sizeof(ops[0]); ++i)
        EXPECT(ops[i]->set_suspend_disable == rpm_reg_set_suspend_disable);
    EXPECT(fault_errors[FAST] == 0);
    static struct fixture f; init_three(&f); reset_client(&f.so);
    clear_io(); fault_mode = SILENT; fault_at = 1; apply_uncertain = true;
    expect_fatal = true; fatal_calls = 0;
    if (!setjmp(fatal_target)) cpr_sleep_vote_disable(&f.so);
    expect_fatal = false;
    EXPECT(fatal_calls == 0 && !f.so.enable_count);
    EXPECT(disable_calls == 2);
    clear_io();
    if (f.so.enable_count) EXPECT(regulator_disable(&f.so) == 0);
    healthy(&f);
    printf("{\\"cases\\":1,\\"checks\\":%u,\\"failures\\":%u}\\n", checks, failures);
    return 0;
}
'''
cleanup_code = code[:code.index('int main(void)\n{')] + cleanup_main
positive = m.boot.pair.run_code(cleanup_code, a.output / 'cleanup-retry-positive')
assert positive['failures'] == 0
body = function(cleanup_code, 'cpr_sleep_vote_disable')
before = 'if (ret)\n\t\tret = regulator_disable(mx);'
assert body.count(before) == 1
controls.append(('cleanup-retry-omitted',
    cleanup_code.replace(body, body.replace(before, 'if (ret)\n\t\tret = 0;')),
    'fatal_calls == 0 && !f.so.enable_count'))
records = []
for name, mutated, assertion in controls:
    out = a.output / name
    # Each mutant must be a clean, runnable, sanitizer-clean program which fails
    # an intended behavioral assertion; compilation or sanitizer faults do not count.
    report = m.boot.pair.run_code(mutated, out)
    stderr = (out / 'run.stderr').read_text()
    assert report['failures'] > 0 and assertion in stderr, (name, report, assertion, stderr)
    records.append(dict(name=name, rejected=True, failures=report['failures'], named_assertion=assertion))
report = dict(passed=True, controls=records, normal_LSan_and_failfast_ASan_UBSan=True,
    only_synthetic_services=True, physical_or_kernel_concurrency_qualified=False,
    no_phone_radio_audio_network_or_firmware_execution=True)
(a.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, controls_rejected=len(records))))
