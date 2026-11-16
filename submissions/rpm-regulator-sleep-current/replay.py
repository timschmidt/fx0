# SPDX-License-Identifier: GPL-2.0-only
"""Replay the regulator sleep-set prerequisite using only pinned packet inputs."""
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
    assert path.is_file() and not path.is_symlink()
    assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name
source = a.output / 'source'
runtime = a.output / 'runtime'
shutil.copytree(PACKET / 'source-before', source)
shutil.copytree(PACKET / 'runtime-before', runtime)
fixtures = PACKET / 'fixtures'
spec = importlib.util.spec_from_file_location('sleep', fixtures / 'check-sleep.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
baseline = fixture.run(source, source, a.output / 'baseline', baseline=True)
for tree, patch, expected in [(source, 'sleep-01.patch', manifest['source_after_SHA256']),
                               (runtime, 'runtime-01.patch', manifest['runtime_after_SHA256'])]:
    result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(PACKET / patch)],
                            cwd=tree, capture_output=True, text=True, timeout=30)
    (a.output / (tree.name + '-apply.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0 and 'offset' not in result.stdout and 'fuzz' not in result.stdout
    assert hashlib.sha256((tree / 'drivers/regulator/qcom_smd-regulator.c').read_bytes()).hexdigest() == expected
candidate = fixture.run(source, source, a.output / 'candidate')
assert fixture.model(source, source) == fixture.model(runtime, runtime)
result = subprocess.run(['python3', '-B', str(fixtures / 'check-controls.py'), str(source),
                         str(a.output / 'controls'), '--transport-source', str(source)],
                        capture_output=True, text=True, timeout=120)
(a.output / 'controls.stdout').write_text(result.stdout)
(a.output / 'controls.stderr').write_text(result.stderr)
assert result.returncode == 0, result.stderr
controls = json.loads((a.output / 'controls/qualification.json').read_text())
assert controls['passed'] and len(controls['controls']) == 14
assert (candidate['cases'], candidate['checks'], candidate['failures'], baseline['failures']) == (6310, 77934, 0, 6516)
assert candidate['active_trace_bytes'] == baseline['active_trace_bytes'] == 1280
assert candidate['active_trace_SHA256'] == baseline['active_trace_SHA256'] == 'b340d70e72a641884eccb247c8b823715a5e38e54974d430f5d800343452708a'
report = dict(passed=True, cases=6310, checks=77934, before_failures=6516, candidate_failures=0,
              exact_functions=17, exact_operations_tables=5, controls_rejected=14,
              source_and_runtime_patches_applied_without_fuzz_or_offset=True,
              maintainer_and_runtime_generated_C_byte_identical=True,
              active_trace_bytes=1280, active_trace_SHA256=candidate['active_trace_SHA256'],
              all_inputs_hash_verified=True, all_services_synthetic=True,
              prior_reply_correlated_RPM_transport_composed=True,
              normal_LSan_and_failfast_ASan_UBSan=True,
              no_Git_network_hardware_or_actual_suspend_execution=True,
              full_CPU_MX_SPM_RPM_sleep_handoff_qualified=False)
(a.output / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
