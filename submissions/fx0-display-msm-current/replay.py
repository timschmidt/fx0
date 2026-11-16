#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify this source-only packet and replay its actual-source host models."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('output', type=Path, help='fresh output directory outside this packet')
args = parser.parse_args()
base = Path(__file__).resolve().parent
out = args.output.resolve()
assert not out.is_relative_to(base)
manifest = json.loads((base/'files.json').read_text())
actual = {str(p.relative_to(base)) for p in base.rglob('*') if p.is_file()}
assert actual == set(manifest) | {'files.json'}, 'packet contains missing or unexpected files'
for name, digest in manifest.items():
    assert hashlib.sha256((base/name).read_bytes()).hexdigest() == digest, name
out.mkdir(mode=0o700)


def run(label, command, cwd=None):
    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True, timeout=90)
    (out/(label+'.stdout')).write_text(proc.stdout)
    (out/(label+'.stderr')).write_text(proc.stderr)
    assert proc.returncode == 0, (label, proc.returncode, proc.stderr[-2000:])
    return proc


baseline = base/'sources/baseline'
candidate = out/'candidate'
shutil.copytree(baseline, candidate)
patches = sorted((base/'patches').glob('*.patch'))
assert len(patches) == 5
for i, patch in enumerate(patches):
    run('apply-'+str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], candidate)
for p in (base/'sources/candidate').rglob('*'):
    if p.is_file():
        name = p.relative_to(base/'sources/candidate')
        assert p.read_bytes() == (candidate/name).read_bytes(), str(name)
integration = out/'integration'
shutil.copytree(candidate, integration)
for p in (base/'sources/integration').rglob('*'):
    if p.is_file():
        name = p.relative_to(base/'sources/integration')
        (integration/name).write_bytes(p.read_bytes())

generator = 'drivers/gpu/drm/msm/registers/gen_header.py'
regenerated = out/'regenerated'
regenerated.mkdir()
for name in ['dsi_phy_28nm', 'mdp5', 'mdp_common']:
    proc = run('header-'+name, [sys.executable, '-B', str(candidate/generator), '--no-validate',
                              '--rnn', str(base/'registers'), '--xml',
                              str(base/'registers/display'/(name+'.xml')), 'c-defines'])
    data = proc.stdout.encode()
    (regenerated/(name+'.xml.h')).write_bytes(data)
    assert data == (base/'generated'/(name+'.xml.h')).read_bytes(), name

expected = json.loads((base/'model-qualification.json').read_text())
results = {}


def check(label, command):
    dest = out/label
    run(label, command+[str(dest)])
    data = json.loads((dest/'qualification.json').read_text())
    previous = expected[label]
    for field in ['cases', 'checks', 'failures', 'body_SHA256']:
        assert data[field] == previous[field], (label, field, data[field], previous[field])
    assert data['sanitizer_diagnostics'] is False
    results[label] = {key: data[key] for key in ['cases', 'checks', 'failures', 'body_SHA256']}


phy = 'drivers/gpu/drm/msm/dsi/phy/dsi_phy_28nm.c'
vendor = base/'sources/vendor/msm8226-mdss.dtsi'
for label, source, mutation in [('phy-baseline-01', baseline, None),
                                ('phy-candidate-01', candidate, None),
                                ('phy-unconditional-01', candidate, 'unconditional'),
                                ('phy-lane-value-01', candidate, 'lane-value')]:
    command = [sys.executable, '-B', str(base/'check-phy.py'), str(source/phy), str(baseline/phy), str(vendor)]
    # argparse accepts the optional mutation before the final positional output.
    if mutation:
        command += ['--mutation', mutation]
    check(label, command)
for label, source, mutation in [('encoder-baseline-03', baseline, None),
                                ('encoder-candidate-03', candidate, None),
                                ('encoder-late-flush-03', candidate, 'late-flush'),
                                ('encoder-no-start-03', candidate, 'no-start'),
                                ('encoder-integration-01', integration, None)]:
    command = [sys.executable, '-B', str(base/'check-encoder.py'), str(source)]
    if mutation:
        command += ['--mutation', mutation]
    check(label, command)
for label, source, mutation in [('plane-baseline-final-01', baseline, None),
                                ('plane-candidate-final-01', candidate, None),
                                ('plane-left-only-final-01', candidate, 'left-only'),
                                ('plane-ignore-error-final-01', candidate, 'ignore-error'),
                                ('plane-drop-owned-final-01', candidate, 'drop-owned'),
                                ('plane-right-old-only-final-01', candidate, 'right-old-only'),
                                ('plane-right-new-only-02', candidate, 'right-new-only'),
                                ('plane-integration-01', integration, None)]:
    command = [sys.executable, '-B', str(base/'check-plane.py'), str(source)]
    if mutation:
        command += ['--mutation', mutation]
    check(label, command)
run('generator', [sys.executable, '-B', str(base/'verify-generator.py'),
                  '--before', str(baseline/generator), '--after', str(candidate/generator),
                  '--registers', str(base/'registers'), '--output', str(out/'generator.json')])
gen = json.loads((out/'generator.json').read_text())
oldgen = json.loads((base/'generator-qualification.json').read_text())
for field in ['records', 'distinct_baseline_outputs', 'distinct_fixed_outputs',
              'usage_array_count', 'every_usage_array_key_and_value_preserved',
              'every_non_usage_declaration_preserved']:
    assert gen[field] == oldgen[field], field
result = dict(passed=True, packet_manifest_verified=True, five_patches_applied_without_fuzz=True,
              generated_headers_recreated_exactly=True, actual_source_models=results,
              generator_passed=True, Git_used=False, phone_access=False,
              native_builds_repeated=False, full_physical_acceptance=False)
(out/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(dict(passed=True, models=len(results), generated_headers=3, Git_used=False)))
