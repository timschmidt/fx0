# SPDX-License-Identifier: GPL-2.0-only
"""Exercise exact shared-voter, regulator-core and correlated RPM bodies."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('legacy_sleep', B / 'legacy/check-sleep.py')
legacy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(legacy)


def model(source, transport, cpu):
    code, bindings = legacy.model(source, transport)
    code = code[:code.index('enum { FAST, ALLOC, SEND, SILENT, STALE, NACK, BOUNDARY };')]
    stub = '\nstatic int rpm_reg_write_pair(struct qcom_rpm_reg *vreg) { CHECK(!"legacy fixture must not admit a pair"); return -EINVAL; }\n'
    assert code.count(stub) == 1
    code = code.replace(stub, '')
    code = code.replace('typedef uint32_t u32;', 'typedef uint64_t u64;\ntypedef uint32_t u32;\n#define U32_MAX UINT32_MAX\n#define max(a,b) ((a) > (b) ? (a) : (b))')
    code = code.replace('struct device {void *data;};', 'struct device_node;\nstruct device { void *data; struct device *parent; struct device_node *of_node; const void *match_data; };')
    code = code.replace('struct regulator_desc { const struct regulator_ops *ops; };', '''struct regulator_desc {
    const struct regulator_ops *ops;
    const char *name, *supply_name, *of_match;
    void *owner;
    int type;
};''')
    code = code.replace('struct regulator_dev {', '''struct regulator_voltage { int min_uV, max_uV; };
struct regulator {
    struct regulator_voltage voltage[5];
    struct regulator *next;
    struct regulator_dev *rdev;
    int enable_count;
    bool apc;
};
#define list_for_each_entry(pos, head, member) for ((pos) = *(head); (pos); (pos) = (pos)->next)
struct regulator_dev {
    struct regulator *consumer_list;''')
    driver = (source / 'drivers/regulator/qcom_smd-regulator.c').read_text()
    core = (source / 'drivers/regulator/core.c').read_text()
    cpr = (cpu / 'drivers/pmdomain/qcom/cpr-voltage.h').read_text()
    names = ['rpm_reg_send_vote', 'rpm_reg_write_pair']
    bodies = ''.join(legacy.function(driver, n) for n in names)
    code = code.replace(legacy.function(driver, 'rpm_reg_write_active'), bodies + legacy.function(driver, 'rpm_reg_write_active'))
    code += legacy.function(core, 'regulator_check_consumers')
    harness = (B / 'pair-model.c').read_text()
    cpr_bodies = legacy.block(cpr, r'^struct cpr_voltage \{') + ''.join(legacy.function(cpr, n) for n in ['cpr_voltage_vote_mx', 'cpr_voltage_bootstrap', 'cpr_voltage_set'])
    code += harness.replace('/* ACTUAL_CPR */', cpr_bodies)
    factory = (B / 'factory-model.c').read_text()
    table = legacy.block(driver, r'^static const struct rpm_regulator_data rpm_pm8226_regulators\[\] = \{')
    # Kernel KBUILD_CFLAGS disables missing-field-initializers for its tables.
    # Scope that matching diagnostic policy to the byte-exact catalogue only.
    data = legacy.block(driver, r'^struct rpm_regulator_data \{') + '\n#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wmissing-field-initializers"\n' + table + '\n#pragma GCC diagnostic pop\n'
    probe_names = (['rpm_reg_pair_init_boot'] if 'static int rpm_reg_pair_init_boot(' in driver else []) + ['rpm_regulator_init_vreg', 'rpm_reg_probe']
    factory = factory.replace('/* ACTUAL_CATALOGUE */', data)
    factory = factory.replace('/* ACTUAL_PROBE */', ''.join(legacy.function(driver, n) for n in probe_names))
    code = code.replace('int main(void)\n{', factory + '\nint main(void)\n{\n    factory_tests();')
    for text, group in [(driver, names + probe_names), (core, ['regulator_check_consumers']),
                        (cpr, ['cpr_voltage_vote_mx', 'cpr_voltage_bootstrap', 'cpr_voltage_set'])]:
        for name in group:
            body = legacy.function(text, name)
            assert body == legacy.function(code, name), name
            bindings[name] = hashlib.sha256(body.encode()).hexdigest()
    assert legacy.block(code, r'^static const struct rpm_regulator_data rpm_pm8226_regulators\[\] = \{') == table
    bindings['rpm_pm8226_regulators'] = hashlib.sha256(table.encode()).hexdigest()
    return code, bindings


def run_code(code, output):
    assert not output.exists()
    output.mkdir()
    (output / 'model.c').write_text(code)
    result = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                             '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
                             '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
                             str(output / 'model.c'), '-o', str(output / 'model')],
                            capture_output=True, text=True, timeout=60)
    (output / 'build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    result = subprocess.run([str(output / 'model')], capture_output=True, text=True, env=env, timeout=120)
    (output / 'run.stdout').write_text(result.stdout)
    (output / 'run.stderr').write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    assert not any(t in result.stderr for t in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'model invariant'])
    return json.loads(result.stdout)


def run(source, transport, cpu, output):
    code, bindings = model(source, transport, cpu)
    report = run_code(code, output)
    report.update(actual_function_and_table_bindings=bindings,
                  callback_and_ops_bodies_byte_exact=True,
                  generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
                  normal_LSan_and_failfast_ASan_UBSan=True,
                  deterministic_logical_PM_locks_core_services_and_firmware_state=True,
                  real_kernel_concurrency_and_firmware_qualified=False,
                  full_deep_PM_entry_abort_and_handoff_qualified=False,
                  no_phone_radio_audio_network_or_firmware_execution=True)
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['failures'] == 0, report
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--transport-source', required=True, type=Path)
    p.add_argument('--cpu-source', required=True, type=Path)
    a = p.parse_args()
    r = run(a.source, a.transport_source, a.cpu_source, a.output)
    print(json.dumps({k: r[k] for k in ['cases', 'checks', 'failures']}))
