# SPDX-License-Identifier: GPL-2.0-only
"""Replay NGD resource ownership and earlier transport prerequisites offline."""
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
        if name == 'maintainer' and i == 4:
            command('ownership-IRQ-prefix', [sys.executable, '-B', str(packet / 'tools/ownership/check-ownership.py'),
                str(tree), str(out / 'ownership-IRQ-prefix'), '--baseline'])
            prefix = json.loads((out / 'ownership-IRQ-prefix/qualification.json').read_text())
            assert prefix['cases'] == 10 and prefix['checks'] == 114 and prefix['failures'] == 31
    for path in topic['snapshot_paths']:
        assert (tree / path).read_bytes() == (packet / 'candidate' / name / path).read_bytes(), path
assert patch_count == 8
expected = {'ownership': (10, 114, 34, [5, 18, 14, 15, 12, 3]),
            'parent': (12, 72, 20, [10, 7, 6, 6]),
            'bookkeeping': (21, 152, 48, [6, 24, 2, 4, 6, 12, 2])}
for name, script in [('ownership', 'check-ownership.py'), ('parent', 'check-parent.py'), ('bookkeeping', 'check-lifecycle.py')]:
    tools = packet / 'tools' / name
    spec = importlib.util.spec_from_file_location(name, tools / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.model(out / 'maintainer')[0] == module.model(out / 'runtime')[0]
    for label, source, before in [('before', packet / 'baseline/maintainer', True), ('candidate', out / 'maintainer', False)]:
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
report = dict(passed=True, source_topics=2, patches=8, ownership_cases=10, ownership_checks=114,
    ownership_before_failures=34, ownership_IRQ_prefix_remaining_failures=31,
    ownership_candidate_failures=0, ownership_controls_rejected=6,
    parent_cases=12, parent_checks=72, parent_candidate_failures=0, parent_controls_rejected=4,
    bookkeeping_cases=21, bookkeeping_checks=152, bookkeeping_candidate_failures=0, bookkeeping_controls_rejected=7,
    runtime_and_maintainer_generated_models_byte_identical=True,
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_services_synthetic=True,
    actual_Linux_devres_device_refs_workqueue_IRQ_DMA_or_hardware_execution=False,
    notification_admission_master_DMA_full_startup_power_failure_and_physical_acceptance=False,
    native_full_kernel_module_or_schema_builds_repeated=False,
    audio_network_or_phone_operations=False, Git_required=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
