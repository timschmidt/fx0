# SPDX-License-Identifier: GPL-2.0-only
"""Replay a pinned QMI error-path patch offline with synthetic services."""
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
for name, digest in manifest['inputs'].items():
    path = PACKET / name
    assert not path.is_symlink() and path.is_file()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
source = a.output / 'source'
shutil.copytree(PACKET / 'source-before', source)
fixture_dir = PACKET / 'fixtures'
spec = importlib.util.spec_from_file_location('qmi', fixture_dir / 'check-qmi.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
baseline = fixture.run(source, a.output / 'baseline', baseline=True)
result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / 'qmi-01.patch')],
                        cwd=source, capture_output=True, text=True, timeout=30)
(a.output / 'apply.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0, result.stderr
assert 'offset' not in result.stdout and 'fuzz' not in result.stdout
path = 'drivers/slimbus/qcom-ngd-ctrl.c'
assert hashlib.sha256((source / path).read_bytes()).hexdigest() == manifest['source_after_SHA256']
candidate = fixture.run(source, a.output / 'candidate')
control = subprocess.run(['python3', '-B', str(fixture_dir / 'check-controls.py'), str(source),
                          str(a.output / 'controls')], capture_output=True, text=True, timeout=120)
(a.output / 'controls.stdout').write_text(control.stdout)
(a.output / 'controls.stderr').write_text(control.stderr)
assert control.returncode == 0, control.stderr
controls = json.loads((a.output / 'controls/qualification.json').read_text())
assert controls['passed'] and len(controls['controls']) == 5
runtime = a.output / 'runtime'
shutil.copytree(PACKET / 'source-before', runtime)
shutil.copyfile(PACKET / 'runtime-before.c', runtime / path)
result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / 'runtime-01.patch')],
                        cwd=runtime, capture_output=True, text=True, timeout=30)
(a.output / 'runtime-apply.log').write_text(result.stdout + result.stderr)
assert result.returncode == 0 and 'offset' not in result.stdout and 'fuzz' not in result.stdout
assert hashlib.sha256((runtime / path).read_bytes()).hexdigest() == manifest['runtime_after_SHA256']
assert fixture.model(source) == fixture.model(runtime)
assert (candidate['cases'], candidate['checks'], candidate['failures'], baseline['failures']) == (576, 7008, 0, 896)
report = dict(passed=True, cases=576, checks=7008, before_failures=896, candidate_failures=0,
              exact_functions=6, controls_rejected=5, source_and_runtime_patch_applied_exactly=True,
              standalone_and_runtime_generated_C_byte_identical=True,
              all_inputs_hash_verified=True, all_services_synthetic=True,
              normal_LSan_and_failfast_ASan_UBSan=True,
              no_Git_or_network_or_real_QMI_device_execution=True,
              hardware_stop_and_suspend_rollback_qualified=False)
(a.output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
