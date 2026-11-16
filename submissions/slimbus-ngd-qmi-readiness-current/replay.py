# SPDX-License-Identifier: GPL-2.0-only
"""Replay persistent QMI readiness, lifecycle and transport prerequisites offline."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
a = p.parse_args()
packet = Path(__file__).resolve().parent
out = a.output.resolve()
assert not out.exists() and not out.is_relative_to(packet)
manifest = json.loads((packet / 'manifest.json').read_text())
files = {str(f.relative_to(packet)): f for f in packet.rglob('*') if f.is_file() and f.name != 'manifest.json'}
assert set(files) == set(manifest)
for name, path in files.items():
    assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest() == manifest[name], name
out.mkdir(mode=0o700)
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1', 'PYTHONDONTWRITEBYTECODE': '1'}
env.pop('LSAN_OPTIONS', None)


def command(label, args, cwd=None):
    r = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
    (out / (label + '.stdout')).write_text(r.stdout)
    (out / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-1600:], r.stderr[-1600:])
    if '-patch-' in label:
        assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()


topics = json.loads((packet / 'source-topics.json').read_text())
patch_count = 0
for name, topic in topics.items():
    tree = out / name
    shutil.copytree(packet / 'baseline' / name, tree)
    for i, patch in enumerate(sorted((packet / 'patches' / name).glob('*.patch'))):
        command(name + '-patch-' + str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=tree)
        patch_count += 1
        if name == 'maintainer' and i == 6:
            for path in ['drivers/slimbus/qcom-ngd-ctrl.c', 'drivers/slimbus/core.c']:
                assert (tree / path).read_bytes() == (packet / 'DMA-baseline' / path).read_bytes(), path
        if name == 'maintainer' and i == 7:
            for path in ['drivers/slimbus/qcom-ngd-ctrl.c', 'drivers/slimbus/core.c', 'drivers/base/power/runtime.c']:
                assert (tree / path).read_bytes() == (packet / 'power-baseline' / path).read_bytes(), path
        if name == 'maintainer' and i == 8:
            for path in ['drivers/slimbus/qcom-ngd-ctrl.c', 'drivers/slimbus/core.c']:
                assert (tree / path).read_bytes() == (packet / 'QMI-baseline' / path).read_bytes(), path
    for path in topic['snapshot_paths']:
        assert (tree / path).read_bytes() == (packet / 'candidate' / name / path).read_bytes(), path
assert patch_count == 11
expected = {'QMI': (50, 625, 67, [28, 8, 3, 3, 1, 17, 4, 4, 3, 49, 9, 1, 1, 2, 1, 2]),
            'power': (626, 13284, 2435, [2427, 1818, 615, 915, 1184, 1220, 2433, 8, 915, 322, 16, 320]),
            'DMA': (85, 1150, 479, [79, 2, 83, 305, 151, 5, 124, 128, 16, 4, 4, 6, 1]),
            'ownership': (10, 114, 34, [5, 18, 14, 15, 12, 3]),
            'bookkeeping': (21, 152, 48, [24, 2, 4, 6, 12, 2])}
for name, script in [('QMI', 'check-qmi.py'), ('power', 'check-power.py'), ('DMA', 'check-dma.py'), ('ownership', 'check-ownership.py'), ('bookkeeping', 'check-lifecycle.py')]:
    tools = packet / 'tools' / name
    spec = importlib.util.spec_from_file_location(name, tools / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.model(out / 'maintainer')[0] == module.model(out / 'runtime')[0]
    baseline = packet / ('QMI-baseline' if name == 'QMI' else 'power-baseline' if name == 'power' else 'DMA-baseline' if name == 'DMA' else 'baseline/maintainer')
    for label, source, before in [('before', baseline, True), ('candidate', out / 'maintainer', False)]:
        command(name + '-' + label, [sys.executable, '-B', str(tools / script), str(source),
            str(out / (name + '-' + label))] + (['--baseline'] if before else []))
    command(name + '-controls', [sys.executable, '-B', str(tools / 'check-controls.py'),
        str(out / 'maintainer'), str(out / (name + '-controls'))])
    before = json.loads((out / (name + '-before/qualification.json')).read_text())
    after = json.loads((out / (name + '-candidate/qualification.json')).read_text())
    controls = json.loads((out / (name + '-controls/qualification.json')).read_text())
    cases, checks, failures, rejected = expected[name]
    assert before['cases'] == after['cases'] == cases
    assert before['checks'] == after['checks'] == checks
    assert before['failures'] == failures and after['failures'] == 0
    assert [c['failures'] for c in controls['controls']] == rejected
power_tools = packet / 'tools/power'
spec = importlib.util.spec_from_file_location('power_compat', power_tools / 'check-power.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
PM_source = packet / 'PM-compat-6.18.63'
assert module.model(out / 'maintainer', PM_source)[0] == module.model(out / 'runtime', PM_source)[0]
for label, source, before in [('before', packet / 'power-baseline', True), ('candidate', out / 'maintainer', False)]:
    command('power-LTS-PM-' + label, [sys.executable, '-B', str(power_tools / 'check-power.py'),
        str(source), str(out / ('power-LTS-PM-' + label)), '--PM-source', str(PM_source)] + (['--baseline'] if before else []))
    receipt = json.loads((out / ('power-LTS-PM-' + label) / 'qualification.json').read_text())
    assert receipt['PM_callback_latches_errors'] is True and receipt['cases'] == 626 and receipt['checks'] == 12708
    assert receipt['failures'] == (2652 if before else 0)
assert json.loads((out / 'power-candidate/qualification.json').read_text())['PM_callback_latches_errors'] is False
report = dict(passed=True, source_topics=2, patches=11, QMI_cases=50, QMI_checks=625, QMI_before_failures=67, QMI_candidate_failures=0, QMI_controls_rejected=16,
    power_cases_per_PM_profile=626, power_current_checks=13284, power_current_before_failures=2435,
    power_current_candidate_failures=0, power_LTS_PM_checks=12708, power_LTS_PM_before_failures=2652,
    power_LTS_PM_candidate_failures=0, power_controls_rejected=12,
    whole_LTS_driver_build_backport_or_recovery_qualified=False,
    DMA_cases=85, DMA_checks=1150, DMA_before_failures=479, DMA_candidate_failures=0, DMA_controls_rejected=13,
    ownership_cases=10, ownership_checks=114, ownership_candidate_failures=0, ownership_controls_rejected=6,
    bookkeeping_cases=21, bookkeeping_checks=152, bookkeeping_candidate_failures=0, bookkeeping_controls_rejected=6,
    actual_driver_core_PM_and_QMI_callbacks_composed=True, older_forced_wait_admission_fixture_superseded=True, total_controls_rejected=53,
    runtime_and_maintainer_generated_models_byte_identical=True,
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_services_synthetic=True,
    real_kernel_workqueue_device_DMA_firmware_or_physical_acceptance=False,
    native_full_kernel_module_or_schema_builds_repeated=False,
    audio_network_or_phone_operations=False, Git_required=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
