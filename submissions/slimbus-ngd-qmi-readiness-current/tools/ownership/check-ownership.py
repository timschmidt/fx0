# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact driver/device wrappers with modeled parent devres and references."""
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
    return block(text, r'^(?:(?:static|inline) )*(?:int|void) ' + re.escape(name) + r'\([^;{}]*\)\n\{')


def model(source):
    driver = (source / 'drivers/slimbus/qcom-ngd-ctrl.c').read_text()
    platform = (source / 'drivers/base/platform.c').read_text()
    devres = (source / 'include/linux/device/devres.h').read_text()
    code = (B / 'ownership-model.c').read_text()
    groups = {
        'NGD_TYPE': block(driver, r'^struct qcom_slim_ngd \{'),
        'ACTION_OR_RESET': function(devres, '__devm_add_action_or_reset'),
        'PLATFORM_WRAPPERS': ''.join(function(platform, n) for n in ['platform_device_put', 'platform_device_unregister']),
    }
    names = ['of_qcom_slim_ngd_register', 'qcom_slim_ngd_unregister', 'qcom_slim_ngd_probe',
             'qcom_slim_ngd_remove', 'qcom_slim_ngd_ctrl_remove']
    if 'static void qcom_slim_ngd_put_device(' in driver:
        names.insert(0, 'qcom_slim_ngd_put_device')
    if 'static void qcom_slim_ngd_stop_up(' in driver:
        names.insert(0, 'qcom_slim_ngd_stop_up')
    groups['DRIVER'] = ''.join(function(driver, n) for n in names)
    for marker, value in groups.items():
        assert code.count('/* ACTUAL_' + marker + ' */') == 1
        code = code.replace('/* ACTUAL_' + marker + ' */', value)
    bindings = {n: hashlib.sha256(function(driver, n).encode()).hexdigest() for n in names}
    for n in names:
        assert function(driver, n) == function(code, n)
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
        '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
        str(src), '-o', str(binary)], capture_output=True, text=True, timeout=60)
    (a.output / 'build.log').write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    r = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
    (a.output / 'run.stdout').write_text(r.stdout)
    (a.output / 'run.stderr').write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'fixture invariant']), r.stderr
    j = json.loads(r.stdout)
    j.update(actual_driver_wrapper_and_devm_reset_bodies_preserved=True, actual_function_bindings=bindings,
        generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        normal_LSan_and_failfast_ASan_UBSan=True, devres_refcount_device_IRQ_and_PM_services_synthetic=True,
        fixture_keeps_all_memory_alive_until_resource_audit=True,
        concurrency_physical_bus_audio_firmware_or_phone_execution=False)
    (a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
    assert j['failures'] > 0 if a.baseline else j['failures'] == 0, j
    print(json.dumps({k: j[k] for k in ['cases', 'checks', 'failures']}))
