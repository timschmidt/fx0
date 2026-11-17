# SPDX-License-Identifier: GPL-2.0-only
"""Run exact NGD power and QMI transaction bodies with logical service faults."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

B = Path(__file__).resolve().parent


def block(text, pattern):
    match = re.search(pattern, text, re.M)
    assert match, pattern
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    if text[end:end + 1] == ';':
        end += 1
    return text[match.start():end] + '\n'


def function(text, name):
    return block(text, r'^(?:static )?(?:int|void)\s+' + re.escape(name) + r'\([^;{}]*\)\n\{')


def model(source):
    driver = (source / 'drivers/slimbus/qcom-ngd-ctrl.c').read_text()
    core = (source / 'drivers/soc/qcom/qmi_interface.c').read_text()
    header = (source / 'include/linux/soc/qcom/qmi.h').read_text()
    code = (B / 'qmi-model.c').read_text()
    types = [block(header, r'^struct ' + name + r' \{') for name in ['qmi_response_type_v01', 'qmi_txn']]
    types += [block(driver, r'^(?:struct|enum) ' + name + r' \{') for name in [
        'slimbus_pm_enum_type_v01', 'slimbus_resp_enum_type_v01',
        'slimbus_power_req_msg_v01', 'slimbus_power_resp_msg_v01']]
    code = code.replace('/* ACTUAL_TYPES */', ''.join(types))
    defines = []
    for name in ['SLIMBUS_QMI_POWER_REQ_V01', 'SLIMBUS_QMI_POWER_REQ_MAX_MSG_LEN', 'SLIMBUS_QMI_RESP_TOUT']:
        defines.append(re.search(r'^#define[ \t]+' + name + r'[^\n]*', driver, re.M).group(0))
    code = code.replace('/* ACTUAL_DEFINES */', '\n'.join(defines))
    groups = {
        'CORE': (core, ['qmi_txn_init', 'qmi_txn_wait', 'qmi_txn_cancel']),
        'RESPONSE': (driver, ['qcom_slim_qmi_power_resp_cb']),
        'DRIVER': (driver, ['qcom_slim_qmi_send_power_request', 'qcom_slim_qmi_power_request']),
    }
    bindings = {}
    for marker, (text, names) in groups.items():
        bodies = ''.join(function(text, name) for name in names)
        code = code.replace('/* ACTUAL_' + marker + ' */', bodies)
        for name in names:
            assert function(code, name) == function(text, name)
            bindings[name] = hashlib.sha256(function(text, name).encode()).hexdigest()
    return code, bindings


def run(source, output, baseline=False):
    assert not output.exists()
    output.mkdir()
    code, bindings = model(source)
    (output / 'model.c').write_text(code)
    command = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
               '-Wno-unused-parameter', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
               '-fno-omit-frame-pointer', str(output / 'model.c'), '-o', str(output / 'model')]
    result = subprocess.run(command, capture_output=True, text=True, timeout=60)
    (output / 'build.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    result = subprocess.run([str(output / 'model')], capture_output=True, text=True, env=env, timeout=30)
    (output / 'run.stdout').write_text(result.stdout)
    (output / 'run.stderr').write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    assert not any(s in result.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:'])
    report = json.loads(result.stdout)
    report.update(actual_function_bindings=bindings, actual_callback_bodies_byte_exact=True,
                  logical_IDR_completion_mutex_and_socket_services=True,
                  no_real_QMI_DMA_audio_phone_or_network_execution=True,
                  normal_LSan_and_failfast_ASan_UBSan=True,
                  hardware_stop_and_suspend_rollback_qualified=False)
    (output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
    assert report['failures'] > 0 if baseline else report['failures'] == 0, report
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--baseline', action='store_true')
    args = p.parse_args()
    print(json.dumps(run(args.source, args.output, args.baseline)))
