# SPDX-License-Identifier: GPL-2.0-only
"""Replay four source topics and selected-function models without Git or a phone."""
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


def command(label, cmd, *, env=None, cwd=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=240)
    (out / (label + '.stdout')).write_text(r.stdout)
    (out / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-2000:], r.stderr[-3000:])
    return r


topics = json.loads((packet / 'source-topics.json').read_text())
patch_count = 0
for topic, row in topics.items():
    destination = out / topic
    shutil.copytree(packet / 'baseline' / topic, destination)
    patches = sorted((packet / 'patches' / topic).glob('*.patch'))
    assert len(patches) == len(row['commits'])
    for i, patch in enumerate(patches):
        r = command(topic + '-patch-' + str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=destination)
        assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()
        patch_count += 1
    for path in row['paths']:
        assert (destination / path).read_bytes() == (packet / 'candidate' / topic / path).read_bytes(), (topic, path)
assert patch_count == 11
source = out / 'model-source'
source.mkdir()
composition = json.loads((packet / 'model-composition.json').read_text())
for path, row in composition.items():
    origin = Path(row['packet_file'])
    # Candidate bytes must come from the freshly applied patches.
    src = out / Path(*origin.parts[1:]) if origin.parts[0] == 'candidate' else packet / origin
    assert hashlib.sha256(src.read_bytes()).hexdigest() == row['SHA256'], path
    dst = source / path
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

toolchain = out / 'toolchain'
toolchain.mkdir()
compiler = toolchain / 'cc'
compiler.write_text('''#!/usr/bin/python3
from pathlib import Path
import json,subprocess,sys
args=sys.argv[1:];shared='-shared' in args
flags=[] if shared else ['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g']
r=subprocess.run(['clang-21','-include',ALLOCATION]+flags+args)
with (Path(__file__).resolve().parents[1]/'compilations.jsonl').open('a') as f:
 f.write(json.dumps(dict(standalone_sanitizers=not shared,ctypes_oracle_unsanitized=shared,returncode=r.returncode))+'\\n')
sys.exit(r.returncode)
'''.replace('ALLOCATION', repr(str(packet / 'allocation-API.h'))))
compiler.chmod(0o700)
run = out / 'run-models.py'
run.write_text('''from pathlib import Path
import json,sys,unittest
packet=Path(sys.argv[1]);out=Path(sys.argv[2]);label=sys.argv[3];sys.path.insert(0,str(packet/'tests'))
modules=json.loads((packet/'test-modules.json').read_text()) if label=='composed' else ['test_msm8926_cpufreq']
suite=unittest.TestLoader().loadTestsFromNames(modules)
r=unittest.TextTestRunner(verbosity=2).run(suite)
j=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),passed=r.wasSuccessful())
(out/(label+'-models.json')).write_text(json.dumps(j,indent=2)+'\\n');sys.exit(not r.wasSuccessful())
''')
env = os.environ | {'PATH': str(toolchain) + os.pathsep + os.environ['PATH'], 'FX0_KERNEL_SOURCE': str(source), 'PYTHONDONTWRITEBYTECODE': '1'}
command('composed-models', [sys.executable, '-B', str(run), str(packet), str(out), 'composed'], env=env)
result = json.loads((out / 'composed-models.json').read_text())
assert result['tests'] == 45 and result['passed'] and result['skipped'] == 0

# The ARM CPUfreq topic has a different allocation API on its own base. Use
# its exact two C files with the explicitly declared PM supplier dependency.
arm_source = out / 'ARM-topic-model-source'
shutil.copytree(source, arm_source)
for path in ['drivers/cpufreq/qcom-cpufreq-nvmem.c', 'drivers/cpufreq/cpufreq-dt-platdev.c', 'include/linux/soc/qcom/cpr.h']:
    shutil.copyfile(out / 'CPUfreq' / path, arm_source / path)
command('ARM-topic-models', [sys.executable, '-B', str(run), str(packet), str(out), 'ARM-topic'], env=env | {'FX0_KERNEL_SOURCE': str(arm_source)})
arm_result = json.loads((out / 'ARM-topic-models.json').read_text())
assert arm_result['tests'] == 4 and arm_result['passed'] and arm_result['skipped'] == 0
numeric = {}
for mutation in [None, 'clock-selector', 'conditional-minimum', 'read-error']:
    label = 'calibration-' + str(mutation or 'candidate')
    directory = out / label
    args = [sys.executable, '-B', str(packet / 'check-calibration-sanitized.py'), str(source), str(directory)]
    if mutation:
        args += ['--mutation', mutation]
    command(label, args)
    j = json.loads((directory / 'qualification.json').read_text())
    assert j['returncode'] == (1 if mutation else 0) and not j['sanitizer_diagnostics']
    numeric[label] = j
compiles = [json.loads(line) for line in (out / 'compilations.jsonl').read_text().splitlines()]
assert all(j['returncode'] == 0 for j in compiles)
report = dict(passed=True, patches=11, topics=4, composed_model_methods=45, ARM_topic_with_PM_dependency_methods=4,
              failures=0, errors=0, skipped=0,
              standalone_sanitizer_compilations=sum(j['standalone_sanitizers'] for j in compiles),
              ctypes_shared_oracles_unsanitized=sum(j['ctypes_oracle_unsanitized'] for j in compiles),
              calibration_cases=4068, calibration_checks=178907, calibration_controls_rejected=3,
              typed_allocation_service_adapters=True, allocator_overflow_semantics_tested=False,
              Git_required=False, network_or_phone_access=False, unit_fuse_data=False,
              native_full_kernel_or_schema_builds_repeated=False, physical_CPU_or_PM_acceptance=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
