# SPDX-License-Identifier: GPL-2.0-only
"""Replay the atomic-regmap fixes and current regulator port without Git/device."""
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
files = {str(f.relative_to(packet)): f for f in packet.rglob('*')
         if f.is_file() and f.name != 'manifest.json'}
assert set(files) == set(manifest)
for name, file in files.items():
    assert not file.is_symlink() and hashlib.sha256(file.read_bytes()).hexdigest() == manifest[name], name
out.mkdir(mode=0o700)
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1',
                    'PYTHONDONTWRITEBYTECODE': '1'}
env.pop('LSAN_OPTIONS', None)
def command(label, argv, cwd=None, environment=env):
    r = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, text=True, timeout=240)
    (out / (label + '.stdout')).write_text(r.stdout)
    (out / (label + '.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-1500:], r.stderr[-1500:])
    return r

trees = {}
runtime_support = ['drivers/soc/qcom/spm-msm8226-l2.h',
                   'drivers/regulator/qcom-spmi-saw-fts2.h',
                   'drivers/regulator/core.c', 'drivers/base/regmap/regmap.c']
for group in ['runtime', 'regulator', 'MFD']:
    source = out / group
    shutil.copytree(packet / 'baseline' / group, source)
    support = runtime_support if group == 'runtime' else ['drivers/regulator/core.c'] if group == 'regulator' else []
    for name in support:
        file = source / name
        assert not file.exists()
        file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(packet / 'candidate' / group / name, file)
    for i, patch in enumerate(sorted((packet / 'patches' / group).glob('*.patch'))):
        r = command(group + '-patch-' + str(i), ['patch', '--batch', '--forward', '--fuzz=0',
                    '-p1', '-i', str(patch)], cwd=source)
        assert 'fuzz' not in r.stdout.lower()
    for file in (packet / 'candidate' / group).rglob('*'):
        if file.is_file():
            assert (source / file.relative_to(packet / 'candidate' / group)).read_bytes() == file.read_bytes(), file
    trees[group] = source
assert (trees['MFD'] / 'drivers/mfd/qcom-spmi-pmic.c').read_bytes() == (trees['runtime'] / 'drivers/mfd/qcom-spmi-pmic.c').read_bytes()
assert (trees['regulator'] / 'drivers/regulator/qcom_spmi-regulator.c').read_bytes() == (trees['runtime'] / 'drivers/regulator/qcom_spmi-regulator.c').read_bytes()

raw_results = {}
spm = 'drivers/soc/qcom/spm.c'
pmic = 'drivers/mfd/qcom-spmi-pmic.c'
regulator = trees['regulator'] / 'drivers/regulator/qcom_spmi-regulator.c'
core = trees['runtime'] / 'drivers/base/regmap/regmap.c'
for label, owner, parent, mutation, failures in [
    ('baseline', packet/'baseline/runtime'/spm, packet/'baseline/runtime'/pmic, None, 18),
    ('owner-only', trees['runtime']/spm, packet/'baseline/runtime'/pmic, None, 9),
    ('candidate', trees['runtime']/spm, trees['MFD']/pmic, None, 0),
    ('ignored-raw', trees['runtime']/spm, trees['MFD']/pmic, 'ignore-raw', 27),
    ('no-lock', trees['runtime']/spm, trees['MFD']/pmic, 'disable-owner-locking', 12),
]:
    target = out / ('raw-' + label)
    argv = [sys.executable, '-B', str(packet/'tools/check-raw-locks.py'),
            str(owner), str(regulator), str(core), str(target), '--pmic', str(parent)]
    if mutation:
        argv += ['--mutation', mutation]
    command('raw-' + label, argv)
    j = json.loads((target/'qualification.json').read_text())
    assert j['failures'] == failures and not j['sanitizer_diagnostics']
    raw_results[label] = j

mapping_results = {}
for label, mutation, failures in [('candidate', None, 0), ('all-shared', 'all-shared', 67),
                                  ('no-defer', 'no-defer', 2), ('drop-error', 'drop-map-error', 12),
                                  ('legacy-spinlock', 'legacy-spinlock', 20)]:
    target = out / ('mapping-' + label)
    argv = [sys.executable, '-B', str(packet/'tools/check-saw-mapping.py'), str(regulator), str(target)]
    if mutation:
        argv += ['--mutation', mutation]
    command('mapping-' + label, argv)
    j = json.loads((target/'qualification.json').read_text())
    assert j['failures'] == failures and not j['sanitizer_diagnostics']
    mapping_results[label] = j

toolchain = out/'toolchain'
toolchain.mkdir()
compiler = toolchain/'cc'
compiler.write_text('#!/bin/sh\nexec clang-21 -fsanitize=address,undefined -fno-omit-frame-pointer -g "$@"\n')
compiler.chmod(0o700)
runner = out/'run-existing.py'
runner.write_text('''from pathlib import Path
import json,sys,unittest
packet=Path(sys.argv[1]);target=Path(sys.argv[2]);sys.path.insert(0,str(packet/'tests'))
suite=unittest.TestLoader().loadTestsFromNames(sys.argv[3:])
r=unittest.TextTestRunner(verbosity=2).run(suite)
j=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),passed=r.wasSuccessful())
target.write_text(json.dumps(j,indent=2)+'\\n')
assert r.wasSuccessful() and not r.skipped,j
''')
existing = {}
for label, group, module, count in [('SPM', 'runtime', 'test_spm_l2_master', 1),
                                   ('runtime-FTS2', 'runtime', 'test_saw_fts2', 3),
                                   ('standalone-FTS2', 'regulator', 'test_saw_fts2', 3)]:
    target = out/(label+'.json')
    e = env | {'PATH': str(toolchain)+os.pathsep+env['PATH'], 'FX0_KERNEL_SOURCE': str(trees[group])}
    command(label, [sys.executable, '-B', str(runner), str(packet), str(target), module], environment=e)
    j = json.loads(target.read_text())
    assert j['tests'] == count
    existing[label] = j
report = dict(passed=True, patches=6, source_trees=3, existing_test_methods=7,
              actual_core_lock_cases=raw_results['candidate']['cases'],
              actual_core_lock_checks=raw_results['candidate']['checks'],
              full_baseline_lock_failures=18, partial_owner_only_failures=9,
              lock_controls_rejected=2, map_cases=47, map_checks=407,
              mapping_controls_rejected=4, sanitizers='address,undefined,leak',
              raw_models=raw_results, mapping_models=mapping_results, existing_methods=existing,
              lock_IPI_OF_and_hardware_services_synthetic=True,
              native_schema_full_kernel_or_module_checks_repeated=False,
              physical_voltage_RT_lockdep_or_power_acceptance=False,
              Git_required=False, network_or_phone_access=False)
(out/'replay.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['raw_models','mapping_models','existing_methods']}))
