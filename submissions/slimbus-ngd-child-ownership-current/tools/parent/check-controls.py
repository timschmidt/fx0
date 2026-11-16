# SPDX-License-Identifier: GPL-2.0-only
"""Reject parent cleanup ordering regressions using synthetic pthread services."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('parent_model', B / 'check-parent.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = module.model(a.source)
remove = module.function(code, 'qcom_slim_ngd_ctrl_remove')
probe = module.function(code, 'qcom_slim_ngd_ctrl_probe')
cancel = '\tcancel_work_sync(&ctrl->ngd_up_work);\n'
assert remove.count(cancel) == 1
old = '\tpdr_handle_release(ctrl->pdr);\n' + cancel + '\tqcom_slim_ngd_unregister(ctrl);\n\tgoto err_destroy_mwq;'
assert probe.count(old) == 1
controls = [
    ('missing-detach-drain', code.replace(remove, remove.replace(cancel, '')), 'remove-queued'),
    ('late-detach-drain', code.replace(remove, remove.replace(cancel, '').replace(
        '\tqcom_slim_ngd_unregister(ctrl);', '\tqcom_slim_ngd_unregister(ctrl);\n' + cancel.rstrip())), 'remove-running'),
    ('missing-probe-drain', code.replace(probe, probe.replace(old, old.replace(cancel, ''))), 'probe-SSR-error-queued'),
    ('late-probe-provider-stop', code.replace(probe, probe.replace(old,
        cancel + '\tqcom_slim_ngd_unregister(ctrl);\n\tpdr_handle_release(ctrl->pdr);\n\tgoto err_destroy_mwq;')), 'probe-SSR-error-PDR-inflight'),
]
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
env.pop('LSAN_OPTIONS', None)
records = []
for label, text, expected_case in controls:
    assert text != code
    src = a.output / (label + '.c'); src.write_text(text)
    binary = a.output / label
    c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-unused-function', '-pthread',
        '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-fno-omit-frame-pointer',
        str(src), '-o', str(binary)], capture_output=True, text=True, timeout=60)
    (a.output / (label + '-build.log')).write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    r = subprocess.run([str(binary)], env=env, capture_output=True, text=True, timeout=30)
    (a.output / (label + '.stdout')).write_text(r.stdout)
    (a.output / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'fixture invariant']), r.stderr
    j = json.loads(r.stdout)
    assert j['cases'] == 12 and j['checks'] == 72 and j['failures'] > 0
    assert expected_case + ':' in r.stderr
    records.append(dict(control=label, failures=j['failures'], expected_case=expected_case,
                        rejected=True, sanitizer_diagnostics=False))
(a.output / 'qualification.json').write_text(json.dumps(dict(passed=True, controls=records,
    normal_LSan_and_failfast_ASan_UBSan=True, pthread_services_synthetic=True,
    hardware_audio_firmware_or_phone_execution=False), indent=2) + '\n')
print(json.dumps(records))
