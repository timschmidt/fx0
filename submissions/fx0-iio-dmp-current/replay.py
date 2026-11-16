# SPDX-License-Identifier: GPL-2.0-only
"""Verify and replay this source-review packet without Git or a device."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
p.add_argument('--firmware', type=Path, help='optional owner-supplied pinned image; stays private')
a = p.parse_args()
packet = Path(__file__).resolve().parent
out = a.output.resolve()
assert not out.exists() and not out.is_relative_to(packet)
manifest = json.loads((packet/'manifest.json').read_text())
files = {str(f.relative_to(packet)): f for f in packet.rglob('*') if f.is_file() and f.name != 'manifest.json'}
assert set(files) == set(manifest)
for name, f in files.items():
    assert not f.is_symlink() and hashlib.sha256(f.read_bytes()).hexdigest() == manifest[name], name
out.mkdir(mode=0o700); source = out/'source'
shutil.copytree(packet/'baseline', source)
records = {}

def command(label, cmd, *, cwd=None, env=None):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)
    (out/(label+'.stdout')).write_text(r.stdout)
    (out/(label+'.stderr')).write_text(r.stderr)
    assert r.returncode == 0, (label, r.stdout[-3000:], r.stderr[-3000:])
    return r

for i, patch in enumerate(sorted((packet/'patches').glob('*.patch'))):
    r = command('patch-'+str(i), ['patch', '--batch', '--forward', '--fuzz=0', '-p1', '-i', str(patch)], cwd=source)
    assert 'fuzz' not in r.stdout.lower()
for f in (packet/'candidate').rglob('*'):
    if f.is_file():
        assert (source/f.relative_to(packet/'candidate')).read_bytes() == f.read_bytes(), f

def model(label, script, args, *, file_source=False, expected=0):
    target = source/'drivers/iio/adc/qcom-spmi-iadc.c' if file_source else source
    directory = out/label
    command(label, [sys.executable, '-B', str(packet/script), str(target), str(directory)]+[str(x) for x in args])
    j = json.loads((directory/'qualification.json').read_text())
    assert j['returncode'] == expected and not j['sanitizer_diagnostics'], label
    records[label] = j

model('iadc', 'check-iadc.py', [], file_source=True)
command('iadc-baseline', [sys.executable, '-B', str(packet/'check-iadc.py'),
        str(packet/'baseline/drivers/iio/adc/qcom-spmi-iadc.c'), str(out/'iadc-baseline')])
j = json.loads((out/'iadc-baseline/qualification.json').read_text())
assert j['returncode'] == 1 and not j['sanitizer_diagnostics']; records['iadc-baseline'] = j
for mutation in ['unsigned-difference', 'missing-units', 'missing-range']:
    model('iadc-'+mutation, 'check-iadc.py', ['--mutation', mutation], file_source=True, expected=1)
model('calibbias', 'check-calibbias.py', [])
for part in ['offset', 'pm']:
    model('calibbias-baseline-'+part, 'check-calibbias.py',
          ['--baseline', packet/'baseline/drivers/iio/imu/inv_mpu6050/inv_mpu_core.c', '--part', part], expected=1)
for mutation in ['gyro-stride', 'missing-put']:
    model('calibbias-'+mutation, 'check-calibbias.py', ['--mutation', mutation], expected=1)
model('scan-current', 'check-scan.py', [])
model('scan-legacy', 'check-scan.py', ['--legacy-core', packet/'legacy-IIO'])
model('scan-old-reader-control', 'check-scan.py', ['--mutation', 'legacy-reader'], expected=1)
for kind in ['transport', 'packet', 'lifecycle', 'recovery', 'smd']:
    model('dmp-'+kind, 'check-dmp.py', [kind])
for kind, mutation in [('transport', 'cursor'), ('packet', 'packet-error'),
                       ('lifecycle', 'restore-flag'), ('smd', 'status-bit'), ('smd', 'suspended-bus')]:
    model('dmp-control-'+mutation, 'check-dmp.py', [kind, '--mutation', mutation], expected=1)
if a.firmware:
    model('dmp-loader-private', 'check-dmp.py', ['loader', '--firmware', a.firmware.resolve()])
command('precision', [sys.executable, '-B', str(packet/'test_precision.py'), '-v'],
        env=os.environ | {'FX0_KERNEL_SOURCE': str(source)})
spec = importlib.util.spec_from_file_location('reader', packet/'read-quaternion-current.py')
reader = importlib.util.module_from_spec(spec); spec.loader.exec_module(reader)
count = 0
for q in [(1 << 30, 0, 0, 0), (0, -(1 << 30), 0, 0), (0, 0, (1 << 30)-1, -17)]:
    for t in [1, 1000000007, 2**60+73]:
        assert reader.decode_scan(struct.pack('=iiiiqq', *q, t, -123456789)) == (*q, t)
        count += 1
report = dict(passed=True, model_variants=len(records), precision_test_methods=3,
              reader_synthetic_scans=count, models=records, Git_required=False,
              network_or_phone_access=False, native_builds_repeated=False,
              real_KUnit_repeated=False, private_loader_repeated=bool(a.firmware))
(out/'replay.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k: v for k, v in report.items() if k != 'models'}))
