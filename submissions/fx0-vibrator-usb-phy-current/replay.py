#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay the two driver series and actual-source models without Git."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
a = p.parse_args()
base = Path(__file__).resolve().parent
out = a.output.resolve()
assert not out.is_relative_to(base)
manifest = json.loads((base/'files.json').read_text())
files = {str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()}
assert files == set(manifest) | {'files.json'}
for name, digest in manifest.items():
    assert hashlib.sha256((base/name).read_bytes()).hexdigest() == digest, name
out.mkdir(mode=0o700)


def run(label, cmd, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=90)
    (out/(label+'.stdout')).write_text(r.stdout)
    (out/(label+'.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.returncode, r.stderr[-2000:])


baseline = base/'sources/baseline'
candidate = out/'candidate'
shutil.copytree(baseline, candidate)
patches = sorted((base/'patches/vibrator').glob('*.patch')) + sorted((base/'patches/usb').glob('*.patch'))
assert len(patches) == 5
for i, patch in enumerate(patches):
    run('apply-'+str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], candidate)
for path in (base/'sources/candidate').rglob('*'):
    if path.is_file():
        name = path.relative_to(base/'sources/candidate')
        assert path.read_bytes() == (candidate/name).read_bytes(), str(name)
integration = out/'integration'
shutil.copytree(candidate, integration)
for path in (base/'sources/integration').rglob('*'):
    if path.is_file():
        name = path.relative_to(base/'sources/integration')
        (integration/name).write_bytes(path.read_bytes())
expected = json.loads((base/'model-qualification.json').read_text())
results = {}
vib = 'drivers/input/misc/pm8xxx-vibrator.c'
usb = 'drivers/phy/qualcomm/phy-qcom-usb-hs.c'
jobs = [('vibrator-baseline-01', 'vibrator', baseline/vib, None),
        ('vibrator-three-fixes-01', 'vibrator', base/'sources/three-fixes'/vib, None),
        ('vibrator-candidate-01', 'vibrator', candidate/vib, None),
        ('vibrator-wrong-range-01', 'vibrator', candidate/vib, 'wrong-range'),
        ('vibrator-missing-limit-01', 'vibrator', candidate/vib, 'missing-limit'),
        ('vibrator-stale-drive-01', 'vibrator', candidate/vib, 'stale-drive'),
        ('vibrator-upper-left-01', 'vibrator', candidate/vib, 'upper-left'),
        ('vibrator-integration-01', 'vibrator', integration/vib, None),
        ('usb-baseline-02', 'usb', baseline/usb, None),
        ('usb-candidate-02', 'usb', candidate/usb, None),
        ('usb-zero-sentinel-02', 'usb', candidate/usb, 'zero-sentinel'),
        ('usb-no-odd-check-02', 'usb', candidate/usb, 'no-odd-check'),
        ('usb-short-count-02', 'usb', candidate/usb, 'short-count'),
        ('usb-integration-01', 'usb', integration/usb, None)]
for label, kind, source, mutation in jobs:
    output = out/label
    cmd = [sys.executable, '-B', str(base/('check-'+kind+'.py')), str(source), str(output)]
    if mutation:
        cmd += ['--mutation', mutation]
    run(label, cmd)
    data = json.loads((output/'qualification.json').read_text())
    for field in ['cases', 'checks', 'failures', 'body_SHA256', 'program_SHA256']:
        assert data[field] == expected[label][field], (label, field)
    assert data['sanitizer_diagnostics'] is False
    results[label] = {key: data[key] for key in ['cases', 'checks', 'failures', 'body_SHA256']}
result = dict(passed=True, packet_manifest_verified=True,
              five_patches_applied_without_fuzz=True, actual_source_models=results,
              Git_used=False, phone_access=False, native_builds_repeated=False,
              physical_current_source_acceptance=False)
(out/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(dict(passed=True, models=len(results), Git_used=False)))
