# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact NGD/core lifecycle and QMI readiness callbacks with logical wait/transport services."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

B = Path(__file__).resolve().parent


def function(text, name):
    match = re.search(r'^(?:static )?(?:int|void) ' + re.escape(name) + r'\([^;{}]*\)\n\{', text, re.M)
    assert match, name
    end = text.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end] + '\n'


def model(source):
    driver = (source / 'drivers/slimbus/qcom-ngd-ctrl.c').read_text()
    core = (source / 'drivers/slimbus/core.c').read_text()
    groups = {
        'QMI_CALLBACKS': (driver, ['qcom_slim_ngd_qmi_new_server', 'qcom_slim_ngd_qmi_del_server']),
        'DISCOVERY': (driver, ['qcom_slim_ngd_qmi_svc_event_init', 'qcom_slim_ngd_qmi_svc_event_deinit']),
        'CORE': (core, ['slim_register_controller', 'slim_remove_device', 'slim_ctrl_remove_device', 'slim_unregister_controller']),
        'RESUME': (driver, ['qcom_slim_ngd_runtime_resume']),
        'ENABLE': (driver, ['qcom_slim_ngd_enable']),
        'UP': (driver, ['qcom_slim_ngd_up_worker']),
        'NOTIFY': (driver, ['qcom_slim_ngd_update_device_status', 'qcom_slim_ngd_down', 'qcom_slim_ngd_ssr_pdr_notify']),
        'WRAPPERS': (driver, ['qcom_slim_ngd_ssr_notify', 'slim_pd_status']),
        'CHILD': (driver, ['qcom_slim_ngd_probe', 'qcom_slim_ngd_remove']),
        'PARENT': (driver, ['qcom_slim_ngd_unregister', 'qcom_slim_ngd_ctrl_probe', 'qcom_slim_ngd_ctrl_remove']),
    }
    code = (B / 'qmi-model.c').read_text()
    table = re.search(r'^static const struct qmi_ops qcom_slim_ngd_qmi_svc_event_ops = \{.*?^\};', driver, re.M | re.S)
    assert table
    code = code.replace('/* ACTUAL_QMI_OPS */', table.group(0) + '\n')
    stop = function(driver, 'qcom_slim_ngd_stop_up') if 'static void qcom_slim_ngd_stop_up(' in driver else ''
    code = code.replace('/* ACTUAL_STOP_UP */', stop)
    bindings = {}
    for marker, (text, names) in groups.items():
        value = ''.join(function(text, name) for name in names)
        assert code.count('/* ACTUAL_' + marker + ' */') == 1
        code = code.replace('/* ACTUAL_' + marker + ' */', value)
        for name in names:
            body = function(text, name)
            assert function(code, name) == body
            bindings[name] = hashlib.sha256(body.encode()).hexdigest()
    if stop:
        assert function(code, 'qcom_slim_ngd_stop_up') == stop
        bindings['qcom_slim_ngd_stop_up'] = hashlib.sha256(stop.encode()).hexdigest()
    return code, bindings


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--baseline', action='store_true')
    a = p.parse_args()
    assert not a.output.exists()
    a.output.mkdir()
    code, bindings = model(a.source)
    src = a.output / 'model.c'; src.write_text(code)
    binary = a.output / 'model'
    c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-unused-function', '-pthread', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(src), '-o', str(binary)],
        capture_output=True, text=True, timeout=60)
    (a.output / 'build.log').write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    r = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
    (a.output / 'run.stdout').write_text(r.stdout)
    (a.output / 'run.stderr').write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'model invariant']), r.stderr
    j = json.loads(r.stdout)
    j.update(actual_callback_bodies_preserved=True, actual_function_bindings=bindings,
        generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        normal_LSan_and_failfast_ASan_UBSan=True, QMI_PM_firmware_DMA_and_children_synthetic=True, logical_wait_predicates_and_consumable_completion_services=True,
        pthread_interleavings_with_synthetic_services=True, real_kernel_workqueue_or_physical_acceptance=False, audio_execution=False, phone_access=False)
    (a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
    assert j['failures'] > 0 if a.baseline else j['failures'] == 0, j
    print(json.dumps({k: j[k] for k in ['cases', 'checks', 'failures']}))
