# SPDX-License-Identifier: GPL-2.0-only
"""Offline replay of the boot APC hold, its pre-change gap and retained paths."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess

PACKET = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__); p.add_argument('output', type=Path)
a = p.parse_args(); assert not a.output.exists(); a.output.mkdir()
manifest = json.loads((PACKET / 'manifest.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name, digest in manifest['inputs'].items():
    path = PACKET / name
    assert path.is_file() and not path.is_symlink() and sha(path) == digest, name
source = a.output / 'source'; runtime = a.output / 'runtime'
shutil.copytree(PACKET / 'source-before', source); shutil.copytree(PACKET / 'runtime-before', runtime)
fixtures = PACKET / 'fixtures'
spec = importlib.util.spec_from_file_location('boot', fixtures / 'check-boot.py')
boot = importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
pair = boot.pair; legacy = pair.legacy
before = boot.run(source, source, source, a.output / 'boot-before', baseline=True)
legacy_before = legacy.run(source, source, a.output / 'legacy-before')
for tree, patches, expected in [(source, ['binding-01.patch', 'provider-01.patch'], manifest['source_after']),
    (runtime, ['runtime-01.patch', 'runtime-02.patch', 'runtime-03.patch'], manifest['runtime_after'])]:
    for patch in patches:
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / patch)],
            cwd=tree, capture_output=True, text=True, timeout=30)
        (a.output / (tree.name + '-' + patch + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0 and 'offset' not in result.stdout and 'fuzz' not in result.stdout, (patch, result.stdout, result.stderr)
    for path, digest in expected.items():
        assert sha(tree / path) == digest, path
candidate = boot.run(source, source, source, a.output / 'boot-after')
integrated = boot.run(runtime, runtime, runtime, a.output / 'boot-runtime')
unguarded = pair.run(source, source, source, a.output / 'pair')
legacy_after = legacy.run(source, source, a.output / 'legacy-after')
sc, sb = boot.model(source, source, source); rc, rb = boot.model(runtime, runtime, runtime)
assert sc.replace('devm_kzalloc_obj(&pdev->dev, *vreg)', 'devm_kzalloc(&pdev->dev, sizeof(*vreg), GFP_KERNEL)') == rc
assert {k:v for k,v in sb.items() if k != 'rpm_reg_probe'} == {k:v for k,v in rb.items() if k != 'rpm_reg_probe'}
assert legacy.model(source, source) == legacy.model(runtime, runtime)
assert (before['cases'], before['checks'], before['failures']) == (317, 34699, 2180)
for j in [candidate, integrated]:
    assert (j['cases'], j['checks'], j['failures']) == (317, 57600, 0)
assert (unguarded['cases'], unguarded['checks'], unguarded['failures']) == (3726, 202962, 0)
for j in [legacy_before, legacy_after]:
    assert (j['cases'], j['checks'], j['failures']) == (6310, 77934, 0)
    assert j['active_trace_bytes'] == 1280
    assert j['active_trace_SHA256'] == 'b340d70e72a641884eccb247c8b823715a5e38e54974d430f5d800343452708a'
counts = []
for suite, script, count, extra in [('boot-controls', fixtures / 'check-boot-controls.py', 11, ['--cpu-source', str(source)]),
    ('pair-controls', fixtures / 'check-pair-controls.py', 16, ['--cpu-source', str(source)]),
    ('legacy-controls', fixtures / 'legacy/check-controls.py', 14, [])]:
    result = subprocess.run(['python3', '-B', str(script), str(source), str(a.output / suite),
        '--transport-source', str(source), *extra], capture_output=True, text=True, timeout=240)
    (a.output / (suite + '.stdout')).write_text(result.stdout)
    (a.output / (suite + '.stderr')).write_text(result.stderr)
    assert result.returncode == 0, result.stderr
    j = json.loads((a.output / suite / 'qualification.json').read_text())
    assert j['passed'] and len(j['controls']) == count; counts.append(count)
report = dict(passed=True, boot_cases=317, boot_checks=57600, boot_failures=0, before_checks=34699, before_failures=2180,
    pair_cases=3726, pair_checks=202962, legacy_cases=6310, legacy_checks=77934,
    unique_cases=10353, unique_checks=338496, controls_rejected=sum(counts),
    actual_boot_functions=28, actual_ops_tables=5, actual_catalogues=1,
    all_inputs_hash_verified=True, source_and_runtime_patches_applied_without_fuzz_or_offset=True,
    callbacks_and_catalogue_byte_identical=True, actual_probe_difference_only_existing_allocator=True,
    active_trace_bytes_preserved=1280, normal_LSan_and_failfast_ASan_UBSan=True,
    only_deterministic_logical_services=True, no_Git_network_phone_firmware_radio_audio_or_hardware_execution=True,
    full_deep_PM_hardware_firmware_and_kernel_concurrency_qualified=False)
(a.output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n'); print(json.dumps(report))
