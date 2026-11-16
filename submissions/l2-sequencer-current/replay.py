# SPDX-License-Identifier: GPL-2.0-only
"""Replay the pinned L2 backend without Git, network or hardware services."""
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
before = a.output / 'before'
source = a.output / 'source'
runtime = a.output / 'runtime'
shutil.copytree(PACKET / 'source-before', before)
shutil.copytree(PACKET / 'source-before', source)
shutil.copytree(PACKET / 'source-before', runtime)
r = subprocess.run(['python3', '-B', str(PACKET / 'check-before.py'), str(before), str(a.output / 'before-model')],
    capture_output=True, text=True, timeout=60)
(a.output / 'before.stdout').write_text(r.stdout)
(a.output / 'before.stderr').write_text(r.stderr)
assert r.returncode == 0, r.stderr
baseline = json.loads((a.output / 'before-model/qualification.json').read_text())
assert baseline['cases'] == 1 and baseline['failures'] == 21
for tree, patch in [(source, 'SPM-01.patch'), (runtime, 'runtime-01.patch')]:
    r = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / patch)],
        cwd=tree, capture_output=True, text=True, timeout=30)
    (a.output / (tree.name + '-patch.log')).write_text(r.stdout + r.stderr)
    assert r.returncode == 0 and 'offset' not in r.stdout and 'fuzz' not in r.stdout, (patch, r.stdout, r.stderr)
    for path, digest in manifest['source_after'].items():
        assert sha(tree / path) == digest, path
spec = importlib.util.spec_from_file_location('l2_model', PACKET / 'check-model.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
bindings = None
for label, tree in [('source-model', source), ('runtime-model', runtime)]:
    code, actual = m.model(tree)
    if bindings is None:
        bindings = actual
    else:
        assert actual == bindings
    report = m.run_code(code, a.output / label)
    assert (report['cases'], report['checks'], report['failures']) == (1259, 110383, 0)
    assert len(actual) == 7
r = subprocess.run(['python3', '-B', str(PACKET / 'check-controls.py'), str(source), str(a.output / 'controls')],
    capture_output=True, text=True, timeout=240)
(a.output / 'controls.stdout').write_text(r.stdout)
(a.output / 'controls.stderr').write_text(r.stderr)
assert r.returncode == 0, r.stderr
controls = json.loads((a.output / 'controls/qualification.json').read_text())
assert controls['passed'] and len(controls['controls']) == 14
report = dict(passed=True, unique_cases=1259, unique_checks=110383, failures=0,
    controls_rejected=14, before_cases=1, before_failures=21,
    full_new_feature_suite_not_claimed_on_parent=True, actual_functions=7,
    all_vendor_sequence_bytes_and_padding_verified=True,
    all_inputs_verified=True, source_runtime_patch_application_without_fuzz_or_offset=True,
    source_and_runtime_bytes_identical=True, normal_LSan_and_failfast_ASan_UBSan=True,
    only_synthetic_regmap_MMIO_context_devres_and_syscon_services=True,
    no_Git_network_phone_radio_audio_firmware_or_hardware_execution=True,
    full_CPU_APC_cache_SCM_RPM_MPM_entry_abort_and_physical_acceptance_qualified=False)
(a.output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
