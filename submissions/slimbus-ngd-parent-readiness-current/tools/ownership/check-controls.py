# SPDX-License-Identifier: GPL-2.0-only
"""Reject descriptor/reference/IRQ ownership regressions in synthetic services."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ownership_model', B / 'check-ownership.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = module.model(a.source)
child = module.function(code, 'qcom_slim_ngd_remove')
register = module.function(code, 'of_qcom_slim_ngd_register')
initial_put = '\t\tif (ret) {\n\t\t\tplatform_device_put(ngd->pdev);\n\t\t\treturn ret;\n\t\t}'
assert register.count(initial_put) == 3
controls = [
    ('parent-IRQ-left-enabled', code.replace('\tdisable_irq(ctrl->irq);\n', ''), 'parent-detach-bound'),
    ('unmanaged-descriptor', code.replace('devm_kzalloc_obj(parent, *ngd)', 'kzalloc_obj(*ngd)'), 'parent-detach-unbound'),
    ('child-frees-parent-descriptor', code.replace(child, child.replace('\tqcom_slim_ngd_qmi_svc_event_deinit(&ctrl->qmi);',
        '\tqcom_slim_ngd_qmi_svc_event_deinit(&ctrl->qmi);\n\tkfree(ctrl->ngd);\n\tctrl->ngd = NULL;')), 'child-unbind-rebind'),
    ('initial-device-reference-leaked', code.replace('\tplatform_device_unregister(ngd->pdev);', '\tplatform_device_del(ngd->pdev);'), 'parent-detach-bound'),
    ('extra-device-reference-missing', code.replace('get_device(&ngd->pdev->dev)', '&ngd->pdev->dev'), 'parent-detach-bound'),
    ('initial-reference-leaked-on-action-error', code.replace(register, register.replace(initial_put,
        '\t\tif (ret)\n\t\t\treturn ret;', 1)), 'managed-action-allocation-error'),
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
        '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare',
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
    assert j['cases'] == 10 and j['checks'] == 114 and j['failures'] > 0
    assert expected_case + ':' in r.stderr
    records.append(dict(control=label, failures=j['failures'], expected_case=expected_case,
                        rejected=True, sanitizer_diagnostics=False))
(a.output / 'qualification.json').write_text(json.dumps(dict(passed=True, controls=records,
    normal_LSan_and_failfast_ASan_UBSan=True, all_services_synthetic=True,
    hardware_audio_firmware_or_phone_execution=False), indent=2) + '\n')
print(json.dumps(records))
