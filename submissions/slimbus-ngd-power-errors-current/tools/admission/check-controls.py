# SPDX-License-Identifier: GPL-2.0-only
"""Reject deliberate child admission and PM ownership regressions in synthetic services."""
from pathlib import Path
import argparse
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ownership_model', B / 'check-admission.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
code, _ = module.model(a.source)
worker = module.function(code, 'qcom_slim_ngd_up_worker')
notify = module.function(code, 'qcom_slim_ngd_ssr_pdr_notify')
probe = module.function(code, 'qcom_slim_ngd_probe')
remove = module.function(code, 'qcom_slim_ngd_remove')
controls = []
def change(label, old, new, expected):
    assert code.count(old) == 1, (label, code.count(old))
    controls.append((label, code.replace(old, new), expected))
change('missing-worker-precheck', worker, worker.replace(
    '\tif (!ctrl->child_ready || !ctrl->up_requested) {\n\t\tmutex_unlock(&ctrl->ssr_lock);\n\t\treturn;\n\t}\n', ''), 'DOWN-before-queued-UP-runs')
change('missing-worker-postcheck', worker, worker.replace(
    '\tif (ctrl->child_ready && ctrl->up_requested)\n\t\tqcom_slim_ngd_enable(ctrl, true);',
    '\tqcom_slim_ngd_enable(ctrl, true);'), 'interleave-action-0-worker-waiting')
change('UP-queues-unbound', notify, notify.replace(
    '\t\tif (ctrl->child_ready)\n\t\t\tschedule_work(&ctrl->ngd_up_work);',
    '\t\tschedule_work(&ctrl->ngd_up_work);'), 'UP-before-bind')
change('child-remove-leaves-admission-open', remove, remove.replace('\tctrl->child_ready = false;\n', ''), 'interleave-action-0-worker-waiting')
change('child-remove-skips-cancel', remove, remove.replace('\tcancel_work_sync(&ctrl->ngd_up_work);\n', ''), 'remove-queued-UP')
change('rebind-loses-UP', probe, probe.replace('\tif (ctrl->up_requested)\n\t\tschedule_work(&ctrl->ngd_up_work);\n', ''), 'rebind-retains-last-UP')
change('probe-failure-leaks-PM-reference', probe, probe.replace('\t\tpm_runtime_put_noidle(dev);\n', ''), 'discovery-failure')
change('remove-leaks-PM-reference', remove, remove.replace('\t\tpm_runtime_put_noidle(&pdev->dev);\n', ''), 'bound-idle-remove')
enable = module.function(code, 'qcom_slim_ngd_enable')
change('registration-retains-PM-ownership', enable, enable.replace('\t\tctrl->pm_ref_held = false;\n', ''), 'repeated-DOWN-after-UP')
change('DOWN-skips-registered-failed-powerup', notify, notify.replace('ctrl->state != QCOM_SLIM_NGD_CTRL_DOWN || ctrl->registered', 'ctrl->state != QCOM_SLIM_NGD_CTRL_DOWN'), 'DOWN-after-registered-power-failure')
change('probe-keeps-stale-completions', probe, probe.replace('\treinit_completion(&ctrl->qmi_up);\n\treinit_completion(&ctrl->qmi.qmi_comp);\n', ''), 'rebind-retains-last-UP')
controls.append(('rebind-keeps-old-power-state', code.replace(probe, probe.replace('\tctrl->state = QCOM_SLIM_NGD_CTRL_DOWN;\n', '')).replace(remove, remove.replace('\tctrl->state = QCOM_SLIM_NGD_CTRL_DOWN;\n', '')), 'UP-while-unbound-rebind'))

env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
env.pop('LSAN_OPTIONS', None)
records = []
for label, text, expected_case in controls:
    assert text != code
    src = a.output / (label + '.c'); src.write_text(text)
    binary = a.output / label
    c = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
        '-Wno-unused-parameter', '-Wno-unused-function', '-Wno-sign-compare', '-pthread',
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
    assert j['cases'] == 42 and j['checks'] == 462 and j['failures'] > 0
    assert expected_case + ':' in r.stderr
    records.append(dict(control=label, failures=j['failures'], expected_case=expected_case,
                        rejected=True, sanitizer_diagnostics=False))
(a.output / 'qualification.json').write_text(json.dumps(dict(passed=True, controls=records,
    normal_LSan_and_failfast_ASan_UBSan=True, all_services_synthetic=True,
    hardware_audio_firmware_or_phone_execution=False), indent=2) + '\n')
print(json.dumps(records))
