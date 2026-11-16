# SPDX-License-Identifier: GPL-2.0-only
"""Replay NGD bookkeeping and parent startup-work cleanup with synthetic services."""
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
    for path in topic['snapshot_paths']:
        assert (tree / path).read_bytes() == (packet / 'candidate' / name / path).read_bytes(), path
assert patch_count == 6
for name, script in [('parent', 'check-parent.py'), ('bookkeeping', 'check-lifecycle.py')]:
    spec = importlib.util.spec_from_file_location(name, packet / 'tools' / name / script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.model(out / 'maintainer')[0] == module.model(out / 'runtime')[0]
    for label, source, before in [('before', packet / 'baseline/maintainer', True), ('candidate', out / 'maintainer', False)]:
        command(name + '-' + label, [sys.executable, '-B', str(packet / 'tools' / name / script),
            str(source), str(out / (name + '-' + label))] + (['--baseline'] if before else []))
    command(name + '-controls', [sys.executable, '-B', str(packet / 'tools' / name / 'check-controls.py'),
        str(out / 'maintainer'), str(out / (name + '-controls'))])
parent_before = json.loads((out / 'parent-before/qualification.json').read_text())
parent_after = json.loads((out / 'parent-candidate/qualification.json').read_text())
assert parent_before['cases'] == parent_after['cases'] == 12
assert parent_before['checks'] == parent_after['checks'] == 72
assert parent_before['failures'] == 20 and parent_after['failures'] == 0
parent_controls = json.loads((out / 'parent-controls/qualification.json').read_text())
assert [x['failures'] for x in parent_controls['controls']] == [10, 7, 6, 6]
book_before = json.loads((out / 'bookkeeping-before/qualification.json').read_text())
book_after = json.loads((out / 'bookkeeping-candidate/qualification.json').read_text())
assert book_before['cases'] == book_after['cases'] == 21
assert book_before['checks'] == book_after['checks'] == 152
assert book_before['failures'] == 48 and book_after['failures'] == 0
book_controls = json.loads((out / 'bookkeeping-controls/qualification.json').read_text())
assert [x['failures'] for x in book_controls['controls']] == [6, 24, 2, 4, 6, 12, 2]
report = dict(passed=True, source_topics=2, patches=6, parent_cases=12, parent_checks=72,
    parent_before_failures=20, parent_candidate_failures=0, parent_controls_rejected=4,
    bookkeeping_cases=21, bookkeeping_checks=152, bookkeeping_before_failures=48,
    bookkeeping_candidate_failures=0, bookkeeping_controls_rejected=7,
    runtime_and_maintainer_generated_models_byte_identical=True,
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_services_synthetic=True,
    actual_Linux_workqueue_PDR_SSR_IRQ_DMA_or_device_execution=False,
    whole_startup_child_unbind_master_work_power_failure_and_physical_acceptance=False,
    native_full_kernel_module_or_schema_builds_repeated=False,
    audio_network_or_phone_operations=False, Git_required=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
