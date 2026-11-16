# SPDX-License-Identifier: GPL-2.0-only
"""Compose exact regulator core/provider/RPM bodies with logical services."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

B = Path(__file__).resolve().parent


def block(text, pattern):
    m = re.search(pattern, text, re.M)
    assert m, pattern
    end = text.index('{', m.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if text[end:end + 1] == ';':
        end += 1
    return text[m.start():end] + '\n'


def function(text, name):
    return block(text, r'^(?:static\s+(?:inline\s+)?)?(?:const\s+)?(?:struct\s+\w+|int|void)[ \t*]*\n?' + re.escape(name) + r'\([^;{}]*\)\n\{')


def model(source, transport):
    driver = (source / 'drivers/regulator/qcom_smd-regulator.c').read_text()
    core = (source / 'drivers/regulator/core.c').read_text()
    rpm = (transport / 'drivers/soc/qcom/smd-rpm.c').read_text()
    header = (transport / 'include/linux/soc/qcom/smd-rpm.h').read_text()
    code = (B / 'sleep-model.c').read_text().replace('/* PREFIX */', (B / 'rpm-prefix.c').read_text())
    bindings = {}
    types = ''.join(block(rpm, r'^struct ' + n + r' \{') for n in ['qcom_smd_rpm', 'qcom_rpm_header', 'qcom_rpm_request', 'qcom_rpm_message'])
    code = code.replace('/* ACTUAL_RPM_TYPES */', types)
    constants = '\n'.join(line for line in rpm.splitlines() if line.startswith('#define RPM_'))
    code = code.replace('/* ACTUAL_RPM_DEFINES */', constants)
    pair_types = ['rpm_reg_vote', 'rpm_reg_pair'] if 'struct rpm_reg_pair {' in driver else []
    types = ''.join(block(driver, r'^struct ' + n + r' \{') for n in pair_types + ['qcom_rpm_reg', 'rpm_regulator_req'])
    if pair_types:
        types += '\nstatic int rpm_reg_write_pair(struct qcom_rpm_reg *vreg) { CHECK(!\"legacy fixture must not admit a pair\"); return -EINVAL; }\n'
    code = code.replace('/* ACTUAL_REG_TYPES */', types)
    defines = [line for line in driver.splitlines() if line.startswith('#define RPM_KEY_')]
    for name in ['QCOM_SMD_RPM_ACTIVE_STATE', 'QCOM_SMD_RPM_SLEEP_STATE', 'QCOM_SMD_RPM_LDOA', 'QCOM_SMD_RPM_SMPA']:
        defines.append(re.search(r'^#define[ \t]+' + name + r'[^\n]*', header, re.M).group(0))
    code = code.replace('/* ACTUAL_REG_DEFINES */', '\n'.join(defines))
    reg_names = ['rpm_reg_write_active', 'rpm_reg_enable', 'rpm_reg_is_enabled', 'rpm_reg_disable',
                 'rpm_reg_get_voltage', 'rpm_reg_set_voltage', 'rpm_reg_set_load']
    if 'static int rpm_reg_write_suspend(' in driver:
        reg_names += ['rpm_reg_write_suspend', 'rpm_reg_set_suspend_voltage', 'rpm_reg_set_suspend_enable', 'rpm_reg_set_suspend_disable']
    groups = {
        'RPM': (rpm, ['qcom_rpm_smd_write', 'qcom_smd_rpm_callback']),
        'REG': (driver, reg_names),
        'CORE': (core, ['regulator_get_suspend_state', 'regulator_get_suspend_state_check', '__suspend_set_state', 'regulator_suspend']),
    }
    for marker, (text, names) in groups.items():
        code = code.replace('/* ACTUAL_' + marker + ' */', ''.join(function(text, n) for n in names))
        for name in names:
            assert function(text, name) == function(code, name)
            bindings[name] = hashlib.sha256(function(text, name).encode()).hexdigest()
    tables = ['rpm_smps_ldo_ops', 'rpm_smps_ldo_ops_fixed', 'rpm_switch_ops', 'rpm_bob_ops', 'rpm_mp5496_ops']
    bodies = [block(driver, r'^static const struct regulator_ops ' + n + r' = \{') for n in tables]
    code = code.replace('/* ACTUAL_OPS */', ''.join(bodies))
    for n, body in zip(tables, bodies):
        assert block(code, r'^static const struct regulator_ops ' + n + r' = \{') == body
        bindings[n] = hashlib.sha256(body.encode()).hexdigest()
    return code, bindings


def run(source, transport, output, baseline=False):
    assert not output.exists()
    output.mkdir()
    code, bindings = model(source, transport)
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
    result = subprocess.run([str(output / 'model'), str(output / 'active-trace.bin')],
                            capture_output=True, text=True, env=env, timeout=60)
    (output / 'run.stdout').write_text(result.stdout)
    (output / 'run.stderr').write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    assert not any(s in result.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'model invariant'])
    report = json.loads(result.stdout)
    report.update(actual_function_and_table_bindings=bindings, callback_and_ops_bodies_byte_exact=True,
                  generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
                  active_trace_bytes=(output / 'active-trace.bin').stat().st_size,
                  active_trace_SHA256=hashlib.sha256((output / 'active-trace.bin').read_bytes()).hexdigest(),
                  normal_LSan_and_failfast_ASan_UBSan=True,
                  logical_PM_regulator_lock_RPMsg_allocation_and_completion_services=True,
                  deterministic_reply_ordering_not_kernel_concurrency_or_firmware_acceptance=True,
                  no_phone_QMI_DMA_audio_or_network_execution=True,
                  full_CPU_MX_SPM_RPM_sleep_handoff_and_physical_acceptance_qualified=False)
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['failures'] > 0 if baseline else report['failures'] == 0, report
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--transport-source', required=True, type=Path)
    p.add_argument('--baseline', action='store_true')
    a = p.parse_args()
    r = run(a.source, a.transport_source, a.output, a.baseline)
    print(json.dumps({k: r[k] for k in ['cases', 'checks', 'failures', 'active_trace_bytes', 'active_trace_SHA256']}))
