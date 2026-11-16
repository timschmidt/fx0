# SPDX-License-Identifier: GPL-2.0-only
"""Replay controller bookkeeping patches using synthetic services only."""
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
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=180)
    (out / (label + '.stdout')).write_text(result.stdout)
    (out / (label + '.stderr')).write_text(result.stderr)
    assert result.returncode == 0, (label, result.stdout[-1600:], result.stderr[-1600:])
    if '-patch-' in label:
        assert 'fuzz' not in result.stdout.lower() and 'offset' not in result.stdout.lower()


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
assert patch_count == 4
spec = importlib.util.spec_from_file_location('lifecycle', packet / 'tools/check-lifecycle.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
assert module.model(out / 'maintainer')[0] == module.model(out / 'runtime')[0]
for label, source, before in [('before', packet / 'baseline/maintainer', True), ('candidate', out / 'maintainer', False)]:
    command(label, [sys.executable, '-B', str(packet / 'tools/check-lifecycle.py'), str(source), str(out / label)] + (['--baseline'] if before else []))
before = json.loads((out / 'before/qualification.json').read_text())
after = json.loads((out / 'candidate/qualification.json').read_text())
assert before['cases'] == after['cases'] == 21
assert before['checks'] == after['checks'] == 152
assert before['failures'] == 48 and after['failures'] == 0
command('controls', [sys.executable, '-B', str(packet / 'tools/check-controls.py'),
                    str(out / 'maintainer'), str(out / 'controls')])
controls = json.loads((out / 'controls/qualification.json').read_text())
assert controls['passed'] and len(controls['controls']) == 7
assert [x['failures'] for x in controls['controls']] == [6, 24, 2, 4, 6, 12, 2]
report = dict(passed=True, patches=4, source_topics=2, actual_functions=10,
    cases=21, checks=152, before_failures=48, candidate_failures=0, controls_rejected=7,
    runtime_and_maintainer_generated_model_bytes_identical=True,
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_services_synthetic=True,
    startup_scheduling_teardown_firmware_concurrency_power_failure_and_physical_acceptance=False,
    native_full_kernel_module_or_schema_builds_repeated=False,
    audio_device_network_or_phone_operations=False, Git_required=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
