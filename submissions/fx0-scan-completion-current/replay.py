# SPDX-License-Identifier: GPL-2.0-only
"""Replay the scan completion port using synthetic requests and work scheduling."""
from pathlib import Path
import argparse
import hashlib
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
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1',
                    'PYTHONDONTWRITEBYTECODE': '1'}
env.pop('LSAN_OPTIONS', None)


def command(label, argv, *, cwd=None):
    r = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=240)
    (out / (label + '.stdout')).write_text(r.stdout)
    (out / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-2000:], r.stderr[-2000:])
    if '-patch-' in label:
        assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()


topics = json.loads((packet / 'source-topics.json').read_text())
count = 0
for name, topic in topics.items():
    tree = out / name
    shutil.copytree(packet / 'baseline' / name, tree)
    for i, patch in enumerate(sorted((packet / 'patches' / name).glob('*.patch'))):
        command(name + '-patch-' + str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=tree)
        count += 1
    assert (tree / 'net/wireless/scan.c').read_bytes() == (packet / 'candidate' / name / 'net/wireless/scan.c').read_bytes()
assert count == 4
assert (out / 'maintainer/net/wireless/scan.c').read_bytes() == (out / 'runtime/net/wireless/scan.c').read_bytes()
results = {}
for label, source, mutation, failures, delivered in [
    ('before', packet / 'baseline/maintainer/net/wireless/scan.c', None, 52, 2),
    ('candidate', out / 'maintainer/net/wireless/scan.c', None, 0, 28),
    ('no-work', out / 'maintainer/net/wireless/scan.c', 'no-deferred-work', 52, 2),
    ('retained-message', out / 'maintainer/net/wireless/scan.c', 'retain-delivered-message', 26, 28),
]:
    destination = out / ('scan-' + label)
    argv = [sys.executable, '-B', str(packet / 'tools/check-scan-lifecycle.py'), str(source), str(destination)]
    if mutation:
        argv += ['--mutation', mutation]
    command(label, argv)
    j = json.loads((destination / 'qualification.json').read_text())
    assert j['cases'] == 30 and j['checks'] == 146 and j['failures'] == failures
    assert j['delivered'] == delivered and j['requests_freed'] == 43 and not j['sanitizer_diagnostics']
    results[label] = j
report = dict(passed=True, patches=4, source_topics=2, actual_functions=4, lifecycle_cases=30,
              lifecycle_checks=146, before_failures=52, candidate_failures=0, regression_controls_rejected=2,
              requests_freed=43, candidate_completion_messages_delivered=28,
              standalone_sanitizers='address,undefined,leak', work_messages_and_driver_timing_synthetic=True,
              native_full_kernel_or_module_builds_repeated=False, physical_wireless_or_concurrency_acceptance=False,
              real_wireless_devices_or_RF_used=False, Git_required=False, network_or_phone_access=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
