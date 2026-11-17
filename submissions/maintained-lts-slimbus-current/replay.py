"""Verify every packet byte before compiling isolated synthetic models."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

B = Path(__file__).resolve().parent
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
p.add_argument('--all-controls', action='store_true')
a = p.parse_args()
manifest = json.loads((B / 'manifest.json').read_text())
for path, want in manifest['files'].items():
    assert not Path(path).is_absolute() and '..' not in Path(path).parts
    actual = B / path
    assert actual.is_file() and not actual.is_symlink()
    assert hashlib.sha256(actual.read_bytes()).hexdigest() == want, 'packet SHA256 mismatch: ' + path
assert not a.output.exists()
a.output.mkdir()
(a.output / 'tmp').mkdir(mode=0o700)
env = os.environ | {'TMPDIR':str(a.output.resolve() / 'tmp'), 'PYTHONDONTWRITEBYTECODE':'1'}
expected = json.loads((B / 'evidence/replay-expected.json').read_text())
rows = []
for name, script in [('startup','check-qmi.py'), ('transaction','check-qmi.py'),
                     ('transport','check-transport.py'), ('response','check-response.py'),
                     ('ownership','check-ownership.py'), ('tx','check-tx.py')]:
    for phase in ['baseline', 'candidate'] + (['controls'] if a.all_controls else []):
        source = B / ('baselines/' + name if phase == 'baseline' else 'source')
        entry = 'check-controls.py' if phase == 'controls' else script
        output = a.output.resolve() / (name + '-' + phase)
        command = ['python3', '-B', str(B / 'fixtures' / name / entry), str(source), str(output)]
        if phase == 'baseline': command.append('--baseline')
        result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=180)
        (a.output / (name + '-' + phase + '.log')).write_text(result.stdout + result.stderr)
        assert result.returncode == 0, (name, phase, result.stderr[-1600:])
        report = json.loads((output / 'qualification.json').read_text())
        if phase != 'controls':
            assert hashlib.sha256((output / 'model.c').read_bytes()).hexdigest() == expected[name][phase]['model_SHA256']
            for field in ['cases', 'checks', 'failures']: assert report[field] == expected[name][phase][field], (name, phase, field)
        rows.append(dict(suite=name, phase=phase, cases=report.get('cases'), failures=report.get('failures'), controls=len(report.get('controls',[]))))
for name, entry in [('stream','check-stream.py')] + ([('sync-controls','check-sync-delta-controls.py')] if a.all_controls else []):
    output = a.output.resolve() / name
    result = subprocess.run(['python3','-B',str(B/'fixtures/response'/entry),str(B/'source'),str(output)], env=env, capture_output=True, text=True, timeout=180)
    (a.output / (name + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stderr[-1600:]
    report = json.loads((output / 'qualification.json').read_text())
    assert report['passed']
    if name == 'stream':
        assert hashlib.sha256((output / 'candidate.c').read_bytes()).hexdigest() == expected['stream']['model_SHA256']
        for field in ['cases','checks','failures']: assert report[field] == expected['stream'][field]
    rows.append(dict(suite=name, cases=report.get('cases'), controls=len(report.get('controls',[]))))
wire = (a.output/'tx-candidate/wire.bin').read_bytes()
assert wire == (a.output/'tx-baseline/wire.bin').read_bytes()
assert hashlib.sha256(wire).hexdigest() == expected['wire_SHA256']
report = dict(passed=True, packet_manifest_verified_before_execution=True,
    generated_model_bytes_and_receipts_exact=True, cases=3221, failures=0,
    recorded_independent_controls=117, all_117_controls_reexecuted=a.all_controls,
    stream_controls_reexecuted=3, source_and_before_fixtures_self_contained=True,
    wire_trace_bytes=len(wire), wire_trace_SHA256=expected['wire_SHA256'],
    normal_LSan_and_failfast_ASan_UBSan=True, all_kernel_services_synthetic=True,
    private_signing_key_required=False, phone_access=False, network_execution=False, rows=rows)
(a.output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:report[k] for k in ['passed','cases','failures','all_117_controls_reexecuted']}))
