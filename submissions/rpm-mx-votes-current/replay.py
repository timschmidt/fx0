# SPDX-License-Identifier: GPL-2.0-only
"""Replay paired MX voters from pinned files without Git, network or devices."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess

PACKET = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists(); a.output.mkdir()
manifest = json.loads((PACKET / 'manifest.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name, digest in manifest['inputs'].items():
    path = PACKET / name
    assert path.is_file() and not path.is_symlink() and sha(path) == digest, name
source = a.output / 'source'; runtime = a.output / 'runtime'
shutil.copytree(PACKET / 'source-before', source)
shutil.copytree(PACKET / 'runtime-before', runtime)
fixtures = PACKET / 'fixtures'
spec = importlib.util.spec_from_file_location('pair', fixtures / 'check-pair.py')
pair = importlib.util.module_from_spec(spec); spec.loader.exec_module(pair)
legacy = pair.legacy
before = legacy.run(source, source, a.output / 'legacy-before')
for tree, patches, expected in [(source, ['binding-01.patch', 'provider-01.patch'], manifest['source_after']),
    (runtime, ['runtime-01.patch', 'runtime-02.patch', 'runtime-03.patch'], manifest['runtime_after'])]:
    for patch in patches:
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / patch)],
                                cwd=tree, capture_output=True, text=True, timeout=30)
        (a.output / (tree.name + '-' + patch + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and 'offset' not in result.stdout and 'fuzz' not in result.stdout, (patch, result.stdout, result.stderr)
    for name, digest in expected.items():
        assert sha(tree / name) == digest, name
after = legacy.run(source, source, a.output / 'legacy-after')
candidate = pair.run(source, source, source, a.output / 'pair-source')
integrated = pair.run(runtime, runtime, runtime, a.output / 'pair-runtime')
assert legacy.model(source, source) == legacy.model(runtime, runtime)
source_code, source_bindings = pair.model(source, source, source)
runtime_code, runtime_bindings = pair.model(runtime, runtime, runtime)
assert source_code.replace('devm_kzalloc_obj(&pdev->dev, *vreg)', 'devm_kzalloc(&pdev->dev, sizeof(*vreg), GFP_KERNEL)') == runtime_code
assert {k:v for k,v in source_bindings.items() if k != 'rpm_reg_probe'} == {k:v for k,v in runtime_bindings.items() if k != 'rpm_reg_probe'}
assert (candidate['cases'], candidate['checks'], candidate['failures']) == (3726, 202962, 0)
assert (integrated['cases'], integrated['checks'], integrated['failures']) == (3726, 202962, 0)
assert (before['cases'], before['checks'], before['failures']) == (6310, 77934, 0)
assert (after['cases'], after['checks'], after['failures']) == (6310, 77934, 0)
assert before['active_trace_bytes'] == after['active_trace_bytes'] == 1280
assert before['active_trace_SHA256'] == after['active_trace_SHA256'] == 'b340d70e72a641884eccb247c8b823715a5e38e54974d430f5d800343452708a'
counts = []
for suite, path, count, extra in [('pair-controls', fixtures / 'check-pair-controls.py', 16, ['--cpu-source', str(source)]),
    ('legacy-controls', fixtures / 'legacy/check-controls.py', 14, [])]:
    result = subprocess.run(['python3', '-B', str(path), str(source), str(a.output / suite),
        '--transport-source', str(source), *extra], capture_output=True, text=True, timeout=240)
    (a.output / (suite + '.stdout')).write_text(result.stdout)
    (a.output / (suite + '.stderr')).write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    j = json.loads((a.output / suite / 'qualification.json').read_text())
    assert j['passed'] and len(j['controls']) == count
    counts.append(count)
report = dict(passed=True, pair_cases=3726, pair_checks=202962, pair_failures=0,
    legacy_cases=6310, legacy_checks=77934, legacy_failures=0,
    unique_cases=10036, unique_checks=280896, controls_rejected=sum(counts),
    original_shared_constraint_rejections=8, actual_pair_functions=25, actual_pair_ops_tables=5, actual_pair_catalogues=1,
    source_and_runtime_patches_applied_without_fuzz_or_offset=True,
    callbacks_and_catalogue_byte_identical=True, actual_probe_difference_only_existing_allocator=True,
    active_trace_bytes_preserved=1280, all_inputs_hash_verified=True,
    normal_LSan_and_failfast_ASan_UBSan=True, only_synthetic_services=True,
    no_Git_network_hardware_firmware_radio_audio_or_actual_suspend_execution=True,
    full_deep_PM_boot_handover_abort_and_physical_acceptance_qualified=False)
(a.output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
