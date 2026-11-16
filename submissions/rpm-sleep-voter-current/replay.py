# SPDX-License-Identifier: GPL-2.0-only
"""Replay source-bound CPU sleep-voter qualification without Git or a device."""
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
assert not a.output.exists()
a.output.mkdir()
manifest = json.loads((PACKET / 'manifest.json').read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
for name, digest in manifest['inputs'].items():
    path = PACKET / name
    assert path.is_file() and not path.is_symlink() and sha(path) == digest, name
source = a.output / 'source'
runtime = a.output / 'runtime'
shutil.copytree(PACKET / 'source-before', source)
shutil.copytree(PACKET / 'runtime-before', runtime)
fixtures = PACKET / 'fixtures'
spec = importlib.util.spec_from_file_location('sleep_voter', fixtures / 'check-sleep-voter.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def run_script(label, script, arguments, timeout=300):
    r = subprocess.run(['python3', '-B', str(script), *map(str, arguments)],
        capture_output=True, text=True, timeout=timeout)
    (a.output / (label + '.stdout')).write_text(r.stdout)
    (a.output / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stderr)


run_script('before-topology', fixtures / 'check-before.py', [source, a.output / 'before-topology'])
before = json.loads((a.output / 'before-topology/qualification.json').read_text())
assert before['cases'] == before['failures'] == 6
for tree, patches, expected in [
    (source, ['binding-01.patch', 'provider-01.patch', 'cpr-binding-01.patch', 'cpr-provider-01.patch'], manifest['source_after']),
    (runtime, ['runtime-%02d.patch' % i for i in range(1, 6)], manifest['runtime_after'])]:
    for patch in patches:
        r = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / patch)],
            cwd=tree, capture_output=True, text=True, timeout=30)
        (a.output / (tree.name + '-' + patch + '.log')).write_text(r.stdout + r.stderr)
        assert r.returncode == 0 and 'offset' not in r.stdout and 'fuzz' not in r.stdout, (patch, r.stdout, r.stderr)
    for path, digest in expected.items():
        assert sha(tree / path) == digest, path
candidate = m.run(source, source, source, a.output / 'sleep-voter-source')
integrated = m.run(runtime, runtime, runtime, a.output / 'sleep-voter-runtime')
boot = m.boot.run(source, source, source, a.output / 'boot')
pair = m.boot.pair.run(source, source, source, a.output / 'pair')
legacy = m.boot.pair.legacy.run(source, source, a.output / 'legacy')
for report in [candidate, integrated]:
    assert (report['cases'], report['checks'], report['failures']) == (1785, 175489, 0)
assert (boot['cases'], boot['checks'], boot['failures']) == (317, 57600, 0)
assert (pair['cases'], pair['checks'], pair['failures']) == (3726, 202962, 0)
assert (legacy['cases'], legacy['checks'], legacy['failures']) == (6310, 77934, 0)
assert legacy['active_trace_bytes'] == 1280
assert legacy['active_trace_SHA256'] == 'b340d70e72a641884eccb247c8b823715a5e38e54974d430f5d800343452708a'
sc, sb = m.model(source, source, source)
rc, rb = m.model(runtime, runtime, runtime)
assert sc.replace('devm_kzalloc_obj(&pdev->dev, *vreg)', 'devm_kzalloc(&pdev->dev, sizeof(*vreg), GFP_KERNEL)') == rc
assert {k:v for k,v in sb.items() if k != 'rpm_reg_probe'} == {k:v for k,v in rb.items() if k != 'rpm_reg_probe'}
counts = []
for label, script, count, extra in [
    ('sleep-controls', fixtures / 'check-sleep-voter-controls.py', 17, ['--cpu-source', source]),
    ('boot-controls', fixtures / 'check-boot-controls.py', 11, ['--cpu-source', source]),
    ('pair-controls', fixtures / 'check-pair-controls.py', 16, ['--cpu-source', source]),
    ('legacy-controls', fixtures / 'legacy/check-controls.py', 14, [])]:
    run_script(label, script, [source, a.output / label, '--transport-source', source, *extra])
    report = json.loads((a.output / label / 'qualification.json').read_text())
    assert report['passed'] and len(report['controls']) == count
    counts.append(count)
report = dict(passed=True, unique_cases=12138, unique_checks=513985, failures=0,
    sleep_voter_cases=1785, sleep_voter_checks=175489, controls_rejected=sum(counts),
    before_unsupported_topology_cases=6, before_failures=6,
    before_full_new_feature_suite_claimed=False, actual_functions=35, actual_ops_tables=5, actual_catalogues=1,
    all_inputs_hash_verified=True, patches_applied_without_fuzz_or_offset=True,
    source_and_runtime_callbacks_byte_identical=True, actual_probe_difference_only_existing_allocator=True,
    active_trace_bytes_preserved=1280, normal_LSan_and_failfast_ASan_UBSan=True,
    only_synthetic_OF_devres_reference_counts_locks_RPMsg_and_firmware_state=True,
    no_Git_network_phone_radio_audio_or_firmware_execution=True,
    firmware_KVP_atomicity_kernel_concurrency_and_full_deep_PM_qualified=False)
(a.output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
