# SPDX-License-Identifier: GPL-2.0-only
"""Require specific MX-voter regressions to fail the host-only model."""
from pathlib import Path
import argparse
import importlib.util
import json

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('pair_model', B / 'check-pair.py')
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
controls = []


def change(name, before, after, assertion):
    assert before != after, name
    if code.count(before) == 1:
        mutated = code.replace(before, after)
    else:
        pair_body = m.legacy.function(code, 'rpm_reg_write_pair')
        assert pair_body.count(before) == 1, name
        mutated = code.replace(pair_body, pair_body.replace(before, after))
    controls.append((name, mutated, assertion))


pair = m.legacy.function(code, 'rpm_reg_write_pair')
change('minimum-instead-of-maximum', '.uV = max(normal->uV, active_only->uV)',
       '.uV = (normal->uV < active_only->uV ? normal->uV : active_only->uV)', 'fw[0].uV')
change('CPU-vote-omitted', '.uV = max(normal->uV, active_only->uV)', '.uV = normal->uV', 'fw[0].uV')
change('normal-vote-omitted', '.uV = max(normal->uV, active_only->uV)', '.uV = active_only->uV', 'fw[0].uV')
change('AO-vote-in-sleep', '\tsleep = *normal;', '\tsleep = *active_only;', 'fw[1].enabled')
change('initial-sleep-not-established', '\tinitialize_sleep = !pair->sleep_initialized;',
       '\tinitialize_sleep = false;', 'fw[1].enabled')
change('cached-normal-sleep-not-invalidated', '\t\tif (!vreg->active_only)\n\t\t\tpair->sleep_initialized = false;',
       '\t\t(void)vreg;', 'fw[1].uV == f.pair.votes[0].uV')
change('failed-slot-not-restored', '\tpair->votes[vreg->active_only] = previous;',
       '\t(void)previous;', 'same_vote(f.pair.votes[actor], old[actor])')
change('failed-pair-error-discarded', pair, pair.replace('\treturn ret;\n}', '\treturn 0;\n}'),
       'ret == (failed ? errors[mode] : 0)')
change('AO-rewrites-normal-sleep', '\tif (!vreg->active_only && !initialize_sleep) {',
       '\tif (!initialize_sleep) {', 'alloc_calls == (failed ? stage : required)')
change('load-addition-wraps', '\tload = (u64)normal->load + active_only->load;',
       '\tload = normal->load + active_only->load;', 'fw[0].mA == UINT32_MAX / 1000')
change('partial-sleep-not-invalidated', '\t/* A partial or timed-out write may have changed the firmware sleep set. */\n\tpair->sleep_initialized = false;',
       '\t/* Mutant retains stale sleep-set validity. */', '!f.pair.sleep_initialized')
change('pair-mutex-omitted', pair, pair.replace('\tmutex_lock(&pair->lock);', '').replace('\tmutex_unlock(&pair->lock);', ''),
       'expected_pair && expected_pair->lock.held')
send = m.legacy.function(code, 'rpm_reg_send_vote')
change('wrong-resource-ID', send, send.replace('vreg->id,', 'vreg->id + 1,'), 'get_unaligned_le32(p + 20) == 3')
change('normal-sleep-voltage-override-lost', '\t\tsleep.uV = pair->sleep_uV;',
       '\t\tsleep.uV = normal->uV;', '!fw[1].enabled && fw[1].uV == 750000')
change('unrelated-ACK-accepted', 'rpm->pending_id == response_id',
       '(rpm->pending_id == response_id || response_id)', 'ret == (failed ? errors[mode] : 0)')
cpr = m.legacy.function(code, 'cpr_voltage_set')
before = '''	if (mx_min_uV > rails->mx_min_uV) {
		ret = cpr_voltage_vote_mx(rails, mx_min_uV);
		if (ret)
			return ret;
	}

	ret = regulator_set_voltage(rails->apc, apc_uV, apc_uV);'''
after = '''	ret = regulator_set_voltage(rails->apc, apc_uV, apc_uV);
	if (!ret && mx_min_uV > rails->mx_min_uV)
		ret = cpr_voltage_vote_mx(rails, mx_min_uV);'''
assert cpr.count(before) == 1
change('APC-raised-before-MX', cpr, cpr.replace(before, after),
       'fw[QCOM_SMD_RPM_ACTIVE_STATE].uV >= min_uV')
records = []
for name, mutated, assertion in controls:
    root = a.output / name
    report = m.run_code(mutated, root)
    stderr = (root / 'run.stderr').read_text()
    assert report['failures'] > 0 and assertion in stderr, (name, report, assertion, stderr)
    records.append(dict(name=name, rejected=True, failures=report['failures'], named_assertion=assertion))
report = dict(passed=True, controls=records, normal_LSan_and_failfast_ASan_UBSan=True,
              only_deterministic_logical_services=True, kernel_concurrency_or_firmware_qualified=False,
              no_hardware_phone_firmware_radio_audio_or_network_execution=True)
(a.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(passed=True, controls_rejected=len(records))))
