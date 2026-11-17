# SPDX-License-Identifier: GPL-2.0-only
"""Run exact driver mode/open/close/probe callbacks against synthetic services."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import os
import subprocess

B = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('clock_fixture', B / 'fixtures/test_nxp_nci_clock.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir()
(a.output / "tmp").mkdir(mode=0o700)
i2c = (a.source / 'drivers/nfc/nxp-nci/i2c.c').read_text()
core = (a.source / 'drivers/nfc/nxp-nci/core.c').read_text()
functions = [(i2c, 'nxp_nci_i2c_set_mode'), (core, 'nxp_nci_open'), (core, 'nxp_nci_close')]
code = fixture.HARNESS + ''.join(fixture.function(s, n) for s, n in functions)
code += fixture.PROBE
code += '#define devm_kzalloc_obj(dev, type) devm_kzalloc(dev, sizeof(type), GFP_KERNEL)\n'
code += fixture.function(i2c, 'nxp_nci_i2c_probe') + fixture.MAIN
for source, name in functions + [(i2c, 'nxp_nci_i2c_probe')]:
    assert fixture.function(source, name) == fixture.function(code, name)
records = []


def run(label, text, modes, succeeds):
    src = a.output / (label + '.c'); src.write_text(text)
    binary = a.output / label
    cmd = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-Wno-unused-function', '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
           '-fno-omit-frame-pointer', str(src), '-o', str(binary)]
    c = subprocess.run(cmd, capture_output=True, text=True)
    (a.output / (label + '-build.log')).write_text(c.stdout + c.stderr)
    assert c.returncode == 0, c.stderr
    for mode in modes:
        r = subprocess.run([str(binary), mode], capture_output=True, text=True, timeout=10,
                           env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1',
                                             'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1', 'TMPDIR':str(a.output / 'tmp')})
        (a.output / (label + '-' + mode + '.log')).write_text(r.stdout + r.stderr)
        assert not any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:']), r.stderr
        assert (r.returncode == 0 and not r.stderr) if succeeds else (r.returncode == 1 and 'CHECK' not in r.stderr and r.stderr.strip()), (label, mode, r.returncode, r.stderr)
        records.append(dict(label=label, mode=mode, returncode=r.returncode, expected_success=succeeds))


run('candidate', code, ['cycle', 'failure_retry', 'legacy_no_clock', 'missing_firmware_pin',
                       'firmware_clock_failure', 'probe_defer', 'probe_irq_failure', 'probe_DT', 'probe_ACPI'], True)
changes = [
    ('open-error-lost', '\t\tif (r)\n\t\t\tgoto open_exit;\n', '', 'failure_retry'),
    ('clock-error-lost', '\t\tif (r)\n\t\t\treturn r;\n', '\t\tif (r)\n\t\t\treturn 0;\n', 'firmware_clock_failure'),
    ('clock-disable-missing', '\t\t\tclk_disable_unprepare(phy->ref_clk);', '', 'cycle'),
]
for label, old, new, mode in changes:
    assert code.count(old) == 1
    run(label, code.replace(old, new), [mode], False)
(a.output / 'verification.json').write_text(json.dumps(dict(
    actual_callback_bodies_preserved=True, normal_LSan_and_failfast_ASan_UBSan=True,
    positive_cases=9, independent_controls=3, fixture_SHA256=hashlib.sha256(code.encode()).hexdigest(),
    results=records, services_synthetic=True, phone_access=False), indent=2) + '\n')
print(json.dumps(dict(positive_cases=9, independent_controls=3, passed=True)))
