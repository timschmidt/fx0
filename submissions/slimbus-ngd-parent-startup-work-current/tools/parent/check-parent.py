# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact parent cleanup and startup callbacks with pthread-backed services."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess

B = Path(__file__).resolve().parent


def function(text, name):
    m = re.search(r'^(?:static )?(?:int|void) ' + re.escape(name) + r'\([^;{}]*\)\n\{', text, re.M)
    assert m, name
    end = text.index('{', m.start()) + 1
    depth = 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[m.start():end] + '\n'


def model(source):
    text = (source / 'drivers/slimbus/qcom-ngd-ctrl.c').read_text()
    code = (B / 'parent-model.c').read_text()
    groups = {
        'CALLBACKS': ['qcom_slim_ngd_up_worker', 'qcom_slim_ngd_ssr_pdr_notify', 'qcom_slim_ngd_ssr_notify', 'slim_pd_status'],
        'PARENT': ['qcom_slim_ngd_unregister', 'qcom_slim_ngd_ctrl_probe', 'qcom_slim_ngd_ctrl_remove'],
    }
    bindings = {}
    for marker, names in groups.items():
        bodies = ''.join(function(text, name) for name in names)
        assert code.count('/* ACTUAL_' + marker + ' */') == 1
        code = code.replace('/* ACTUAL_' + marker + ' */', bodies)
        for name in names:
            assert function(code, name) == function(text, name)
            bindings[name] = hashlib.sha256(function(text, name).encode()).hexdigest()
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
        '-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-unused-function', '-pthread',
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
    j.update(actual_callback_bodies_preserved=True, actual_function_bindings=bindings,
        generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),
        normal_LSan_and_failfast_ASan_UBSan=True, pthread_interleavings_with_synthetic_services=True,
        real_kernel_workqueue_or_hardware_acceptance=False, child_master_DMA_IRQ_admission_qualified=False,
        audio_execution=False, phone_access=False)
    (a.output / 'qualification.json').write_text(json.dumps(j, indent=2) + '\n')
    assert j['failures'] > 0 if a.baseline else j['failures'] == 0, j
    print(json.dumps({k: j[k] for k in ['cases', 'checks', 'failures']}))
