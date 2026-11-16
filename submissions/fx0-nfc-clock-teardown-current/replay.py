# SPDX-License-Identifier: GPL-2.0-only
"""Replay attributed NFC patches and synthetic lifecycle/clock qualifications."""
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
for name, f in files.items():
    assert not f.is_symlink() and hashlib.sha256(f.read_bytes()).hexdigest() == manifest[name], name
out.mkdir(mode=0o700)
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1', 'PYTHONDONTWRITEBYTECODE': '1'}
env.pop('LSAN_OPTIONS', None)


def command(label, argv, cwd=None, extra=None):
    r = subprocess.run(argv, cwd=cwd, env=env | (extra or {}), capture_output=True, text=True, timeout=180)
    (out / (label + '.stdout')).write_text(r.stdout)
    (out / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-1800:], r.stderr[-1800:])
    if '-patch-' in label:
        assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()


topics = json.loads((packet / 'source-topics.json').read_text())
patches = 0
for name, topic in topics.items():
    tree = out / name
    shutil.copytree(packet / 'baseline' / name, tree)
    for i, patch in enumerate(sorted((packet / 'patches' / name).glob('*.patch'))):
        command(name + '-patch-' + str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=tree)
        patches += 1
    for path in topic['snapshot_paths']:
        assert (tree / path).read_bytes() == (packet / 'candidate' / name / path).read_bytes(), path
assert patches == 10
spec = importlib.util.spec_from_file_location('lifecycle', packet / 'tools/check-nfc-lifecycle.py')
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)
assert model.model(out / 'maintainer') == model.model(out / 'runtime')
for label, source, baseline in [('before', packet / 'baseline/maintainer', True), ('candidate', out / 'maintainer', False)]:
    argv = [sys.executable, '-B', str(packet / 'tools/check-nfc-lifecycle.py'), str(source), str(out / label)]
    command(label, argv + (['--baseline'] if baseline else []))
before = json.loads((out / 'before/verification.json').read_text())
after = json.loads((out / 'candidate/verification.json').read_text())
assert before['modeled_cases'] == before['failures'] == 9
assert after['modeled_cases'] == 10 and after['failures'] == 0
command('lifecycle-controls', [sys.executable, '-B', str(packet / 'tools/check-nfc-controls.py'),
    'NxpNciRemoveUpstreamTests.test_ordering_lock_wiring_and_ownership_controls_are_rejected', '-v'],
    extra={'FX0_NFC_REMOVE_SOURCE': str(out / 'maintainer'), 'FX0_NFC_REMOVE_OUTPUT': str(out / 'lifecycle-controls')})
command('clock', [sys.executable, '-B', str(packet / 'tools/check-nfc-clock.py'),
                  str(out / 'maintainer'), str(out / 'clock')])
report = dict(passed=True, patches=10, source_topics=2, baseline_cases=9, baseline_failures=9,
    lifecycle_positive_cases=10, clock_positive_cases=9, independent_controls=9,
    runtime_and_maintainer_generated_model_bytes_identical=True,
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_services_synthetic=True,
    concurrent_firmware_timing_modeled=False, physical_NFC_acceptance=False,
    native_full_kernel_module_or_schema_checks_repeated=False,
    Git_required=False, network_or_phone_access=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
