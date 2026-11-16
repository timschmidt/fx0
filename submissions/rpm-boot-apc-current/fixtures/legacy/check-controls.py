# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('sleep', B / 'check-sleep.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
p = argparse.ArgumentParser(description='Reject regulator sleep-state regressions with logical services.')
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--transport-source', required=True, type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = m.model(a.source, a.transport_source)
controls = []


def change(name, before, after, assertion):
    assert before != after and code.count(before) == 1, name
    controls.append((name, code.replace(before, after), assertion))


write = m.function(code, 'rpm_reg_write_suspend')
change('sleep-request-uses-active-set', write, write.replace('QCOM_SMD_RPM_SLEEP_STATE', 'QCOM_SMD_RPM_ACTIVE_STATE'), 'get_unaligned_le32(p + 12) ==')
call = '\t\treturn qcom_rpm_smd_write(smd_vreg_rpm, QCOM_SMD_RPM_SLEEP_STATE,\n\t\t\t\t\t vreg->type, vreg->id, &req, sizeof(req));'
change('sleep-request-errors-discarded', write, write.replace(call, call.replace('return ', '') + '\n\treturn 0;'), 'ret == (failed ? errors[mode] : 0)')
change('wrong-resource-ID', write, write.replace('vreg->type, vreg->id,', 'vreg->type, vreg->id + 1,'), 'get_unaligned_le32(p + 20) ==')
change('wrong-KVP-length', write, write.replace('cpu_to_le32(sizeof(u32))', 'cpu_to_le32(8)'), 'get_unaligned_le32(p + offset + 4) == 4')
change('sleep-clears-pending-active-cache', write, write.replace(call, '\tvreg->enabled_updated = vreg->uv_updated = vreg->load_updated = 0;\n' + call), '!memcmp(&before, &vreg, sizeof(vreg))')
disable = m.function(code, 'rpm_reg_set_suspend_disable')
change('suspend-disable-enables', disable, disable.replace('RPM_KEY_SWEN, 0', 'RPM_KEY_SWEN, 1'), 'value == (alloc_calls == 1 ?')
voltage = m.function(code, 'rpm_reg_set_suspend_voltage')
change('suspend-voltage-clamped-to-one-value', voltage, voltage.replace('RPM_KEY_UV, uV', 'RPM_KEY_UV, 750000'), 'value == (alloc_calls == 1 ?')
for name in ['rpm_smps_ldo_ops', 'rpm_smps_ldo_ops_fixed', 'rpm_switch_ops', 'rpm_bob_ops', 'rpm_mp5496_ops']:
    table = m.block(code, r'^static const struct regulator_ops ' + name + r' = \{')
    lines = [line for line in table.splitlines(keepends=True) if '.set_suspend_' not in line]
    change(name + '-suspend-hooks-disconnected', table, ''.join(lines), 'alloc_calls == attempts')
change('unrelated-ACK-accepted', 'rpm->pending_id == response_id', '(rpm->pending_id == response_id || response_id)', 'ret == (failed ? errors[mode] : 0)')
change('previous-completion-not-reinitialized', 'reinit_completion(&rpm->ack);', '(void)rpm;', '!c->done')
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
env.pop('LSAN_OPTIONS', None)
records = []
for name, text, assertion in controls:
    root = a.output / name
    root.mkdir()
    (root / 'model.c').write_text(text)
    c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                        str(root / 'model.c'), '-o', str(root / 'model')],
                       capture_output=True, text=True, timeout=60)
    (root / 'build.log').write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    c = subprocess.run([str(root / 'model'), str(root / 'active-trace.bin')],
                       capture_output=True, text=True, env=env, timeout=60)
    (root / 'run.stdout').write_text(c.stdout)
    (root / 'run.stderr').write_text(c.stderr)
    assert c.returncode == 0, c.stderr
    assert not any(t in c.stderr for t in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'model invariant'])
    j = json.loads(c.stdout)
    assert j['cases'] == 6310 and j['failures'] > 0 and assertion in c.stderr, (name, j, assertion)
    records.append(dict(name=name, rejected=True, failures=j['failures'], named_assertion=assertion))
report = dict(passed=True, controls=records, normal_LSan_and_failfast_ASan_UBSan=True,
              all_provider_and_transport_services_synthetic=True, no_device_network_or_real_suspend=True)
(a.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
