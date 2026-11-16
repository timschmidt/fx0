# SPDX-License-Identifier: GPL-2.0-only
"""Reject deliberate bookkeeping regressions in the extracted callback model."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('lifecycle', B / 'check-lifecycle.py')
shared = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shared)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, bindings = shared.model(a.source)
early_put = '\t\tpm_runtime_mark_last_busy(ctrl->ctrl.dev);\n\t\tpm_runtime_put(ctrl->ctrl.dev);\n'
assert code.count(early_put) == 1
without_put = code.replace(early_put, '')
changes = [
    ('duplicate-registration', code.replace('\t\tif (ctrl->registered)\n\t\t\treturn 0;\n', ''), 'duplicate-up-pm-0'),
    ('unowned-unregister', code.replace('\t\tif (ctrl->registered) {\n\t\t\tslim_unregister_controller(&ctrl->ctrl);\n\t\t\tctrl->registered = false;\n\t\t}',
         '\t\tslim_unregister_controller(&ctrl->ctrl);\n\t\tctrl->registered = false;'), 'disable-without-registration'),
    ('early-PM-put', without_put.replace('\t\tret = slim_register_controller(&ctrl->ctrl);',
         early_put + '\n\t\tret = slim_register_controller(&ctrl->ctrl);'), 'registration-error--12'),
    ('missing-QMI-unwind', code.replace('\t\t\tqcom_slim_qmi_exit(ctrl);\n', ''), 'registration-error--12'),
    ('duplicate-QMI-client', code.replace('if (!ctrl->registered)', 'if (true)'), 'duplicate-up-pm-0'),
    ('runtime-wake-suppressed', code.replace('\t\tif (ctrl->registered)\n\t\t\treturn 0;\n', '').replace('\t\tif (!ctrl->registered)', '\t\tif (ctrl->registered)\n\t\t\treturn 0;\n\n\t\tif (!ctrl->registered)'), 'registered-runtime-resume-0'),
]
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
env.pop('LSAN_OPTIONS', None)
records = []
for label, text, expected_case in changes:
    assert text != code
    src = a.output / (label + '.c'); src.write_text(text)
    binary = a.output / label
    c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-Wno-sign-compare', '-fsanitize=address,undefined',
        '-fno-sanitize-recover=all', '-fno-omit-frame-pointer', str(src), '-o', str(binary)],
        capture_output=True, text=True, timeout=60)
    (a.output / (label + '-build.log')).write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    r = subprocess.run([str(binary), 'all'], env=env, capture_output=True, text=True, timeout=30)
    (a.output / (label + '.stdout')).write_text(r.stdout)
    (a.output / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, r.stderr
    assert not any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:', 'model invariant']), r.stderr
    j = json.loads(r.stdout)
    assert j['cases'] == 21 and j['checks'] == 152 and j['failures'] > 0
    assert expected_case + ':' in r.stderr
    records.append(dict(control=label, failures=j['failures'], expected_case=expected_case,
                        rejected=True, sanitizer_diagnostics=False))
(a.output / 'qualification.json').write_text(json.dumps(dict(passed=True, controls=records,
    normal_LSan_and_failfast_ASan_UBSan=True, all_services_synthetic=True,
    hardware_or_audio_execution=False), indent=2) + '\n')
print(json.dumps(records))
