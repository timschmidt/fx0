# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact NGD/core bookkeeping callbacks against synthetic services."""
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
        'CORE': (core, ['slim_register_controller', 'slim_remove_device', 'slim_ctrl_remove_device', 'slim_unregister_controller']),
        'RESUME': (driver, ['qcom_slim_ngd_runtime_resume']),
        'ENABLE': (driver, ['qcom_slim_ngd_enable']),
        'UP': (driver, ['qcom_slim_ngd_up_worker']),
        'NOTIFY': (driver, ['qcom_slim_ngd_update_device_status', 'qcom_slim_ngd_down', 'qcom_slim_ngd_ssr_pdr_notify']),
    }
    code = (B / 'lifecycle-model.c').read_text()
    code = '#define FIXTURE_USES_EVENT_WAIT ' + str(int('wait_event_interruptible_timeout(' in function(driver, 'qcom_slim_ngd_up_worker'))) + '\n' + code
    bindings = {}
    for marker, (text, names) in groups.items():
        value = ''.join(function(text, name) for name in names)
        assert code.count('/* ACTUAL_' + marker + ' */') == 1
        code = code.replace('/* ACTUAL_' + marker + ' */', value)
        for name in names:
            body = function(text, name)
            assert function(code, name) == body
            bindings[name] = hashlib.sha256(body.encode()).hexdigest()
    return code, bindings


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('output', type=Path)
    p.add_argument('--suite', choices=['all', 'wait', 'registration'], default='all')
    p.add_argument('--baseline', action='store_true')
    a = p.parse_args()
    assert not a.output.exists()
    a.output.mkdir()
    code, bindings = model(a.source)
    src = a.output / 'model.c'; src.write_text(code)
    binary = a.output / 'model'
    c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-Wno-sign-compare', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(src), '-o', str(binary)],
        capture_output=True, text=True, timeout=60)
    (a.output / 'build.log').write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                        'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
    env.pop('LSAN_OPTIONS', None)
    r = subprocess.run([str(binary), a.suite], env=env, capture_output=True, text=True, timeout=30)
    (a.output / 'run.stdout').write_text(r.stdout)
    (a.output / 'run.stderr').write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'model invariant']), r.stderr
    j = json.loads(r.stdout)
    j.update(actual_callback_bodies_preserved=True, actual_function_bindings=bindings,
        generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        normal_LSan_and_failfast_ASan_UBSan=True, QMI_PM_firmware_DMA_and_children_synthetic=True,
        concurrency_or_physical_acceptance=False, audio_execution=False, phone_access=False)
    (a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
    assert j['failures'] > 0 if a.baseline else j['failures'] == 0, j
    print(json.dumps({k: j[k] for k in ['cases', 'checks', 'failures']}))
