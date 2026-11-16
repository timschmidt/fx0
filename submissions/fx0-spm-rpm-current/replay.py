# SPDX-License-Identifier: GPL-2.0-only
"""Replay SPM/RPM source, actual-function models and regression controls."""
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
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1',
                    'PYTHONDONTWRITEBYTECODE': '1'}
env.pop('LSAN_OPTIONS', None)


def command(label, argv, *, cwd=None, environment=env):
    r = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, text=True, timeout=240)
    (out / (label + '.stdout')).write_text(r.stdout)
    (out / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-2000:], r.stderr[-2000:])
    if '-patch-' in label:
        assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()


topics = json.loads((packet / 'source-topics.json').read_text())
patch_count = 0
for name, topic in topics.items():
    tree = out / name
    shutil.copytree(packet / 'baseline' / name, tree)
    for i, patch in enumerate(sorted((packet / 'patches' / name).glob('*.patch')), 1):
        command(name + '-patch-' + str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=tree)
        patch_count += 1
        if name == 'maintainer' and i == 2:
            shutil.copyfile(tree / 'drivers/soc/qcom/spm.c', out / 'SPM-before-raw.c')
    for path in topic['paths']:
        assert (tree / path).read_bytes() == (packet / 'candidate' / name / path).read_bytes(), (name, path)
assert patch_count == 6
source = out / 'maintainer'
assert (source / 'drivers/soc/qcom/spm.c').read_bytes() == (out / 'runtime/drivers/soc/qcom/spm.c').read_bytes()

rpm_results = {}
for label, path, mutation, failures in [
    ('original', packet / 'baseline/maintainer/drivers/soc/qcom/smd-rpm.c', None, 10),
    ('candidate', source / 'drivers/soc/qcom/smd-rpm.c', None, 0),
    ('wrong-id', source / 'drivers/soc/qcom/smd-rpm.c', 'accept-wrong-id', 2),
    ('retained-completion', source / 'drivers/soc/qcom/smd-rpm.c', 'retain-completion', 1),
]:
    destination = out / ('rpm-' + label)
    argv = [sys.executable, '-B', str(packet / 'tools/check-rpm-correlation.py'), str(path),
            str(destination), '--fixture', str(packet / 'tests/test_smd_rpm_ack.py')]
    if mutation:
        argv += ['--mutation', mutation]
    command('rpm-' + label, argv)
    j = json.loads((destination / 'qualification.json').read_text())
    assert j['checks'] == 18 and j['failures'] == failures and not j['sanitizer_diagnostics']
    rpm_results[label] = j

raw_results = {}
for label, path, mutation, failures in [
    ('before', out / 'SPM-before-raw.c', None, 9),
    ('candidate', source / 'drivers/soc/qcom/spm.c', None, 0),
    ('ignored-raw', source / 'drivers/soc/qcom/spm.c', 'ignore-raw', 27),
    ('no-owner-lock', source / 'drivers/soc/qcom/spm.c', 'disable-owner-locking', 12),
]:
    destination = out / ('raw-' + label)
    argv = [sys.executable, '-B', str(packet / 'tools/check-raw-locks.py'), str(path),
            str(packet / 'support/drivers/regulator/qcom_spmi-regulator.c'),
            str(packet / 'support/drivers/base/regmap/regmap.c'), str(destination),
            '--pmic', str(packet / 'support/drivers/mfd/qcom-spmi-pmic.c')]
    if mutation:
        argv += ['--mutation', mutation]
    command('raw-' + label, argv)
    j = json.loads((destination / 'qualification.json').read_text())
    assert j['cases'] == 20 and j['failures'] == failures and not j['sanitizer_diagnostics']
    raw_results[label] = j

toolchain = out / 'toolchain'
toolchain.mkdir()
compiler = toolchain / 'cc'
compiler.write_text('#!/bin/sh\nexec clang-21 -fsanitize=address,undefined -fno-omit-frame-pointer -g "$@"\n')
compiler.chmod(0o700)
runner = out / 'run-existing.py'
runner.write_text('''from pathlib import Path
import sys,json,unittest
packet=Path(sys.argv[1]);out=Path(sys.argv[2]);sys.path.insert(0,str(packet/'tests'))
suite=unittest.TestLoader().loadTestsFromNames(['test_spm_l2_master','test_smd_rpm_ack'])
r=unittest.TextTestRunner(verbosity=2).run(suite)
j=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),passed=r.wasSuccessful())
(out/'existing-models.json').write_text(json.dumps(j,indent=2)+'\\n')
assert r.wasSuccessful() and r.testsRun==2 and not r.skipped,j
''')
model_env = env | {'PATH': str(toolchain) + os.pathsep + env['PATH'], 'FX0_KERNEL_SOURCE': str(source)}
command('existing-models', [sys.executable, '-B', str(runner), str(packet), str(out)], environment=model_env)
report = dict(passed=True, patches=6, source_trees=2, existing_model_methods=2,
              RPM_checks=18, RPM_original_failures=10, RPM_candidate_failures=0,
              RPM_controls_rejected=2, raw_lock_cases=20, raw_lock_checks=149,
              raw_lock_before_failures=9, raw_lock_candidate_failures=0, raw_lock_controls_rejected=2,
              standalone_sanitizers='address,undefined,leak', services_and_scheduling_synthetic=True,
              hardware_firmware_concurrency_or_physical_RT_acceptance=False,
              native_schema_kernel_module_builds_repeated=False, Git_required=False, network_or_phone_access=False)
(out / 'replay.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
