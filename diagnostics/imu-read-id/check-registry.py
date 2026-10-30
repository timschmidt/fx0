#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Validate the real private SSI decode, boundaries and output insensitivity."""
import argparse
import importlib.util
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
for name in ['registry', 'defaults', 'map']:
    parser.add_argument('--'+name, type=Path, required=True)
args = parser.parse_args()
spec = importlib.util.spec_from_file_location('inspector', Path(__file__).resolve().parents[2]/'scripts/inspect_fx0_sensor_registry.py')
inspector = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inspector)
raw, defaults, mapping = args.registry.read_bytes(), args.defaults.read_text(), args.map.read_text()
expected = inspector.inspect(raw, defaults, mapping)
assert expected['shared_static_keys_checked'] == 72
assert not expected['calibration_or_driver_UUIDs_exported']
assert not expected['silicon_identity_or_DMP_execution_verified']
base, size = (int(value, 16) for value in re.findall(r'\{\s*2690\s*,\s*(0x[\da-fA-F]+)\s*,\s*(0x[\da-fA-F]+)\s*\}', mapping)[0])
cases = 1
for length in [0, 1, base, base+size-1]:
    try:
        inspector.inspect(raw[:length], defaults, mapping)
    except ValueError:
        cases += 1
    else:
        raise AssertionError('accepted truncated SSI group')
assert inspector.inspect(raw[:base+size], defaults, mapping) == expected
cases += 1
for offset in [0, 1, 255, base-1, base+size, len(raw)-1]:
    data = bytearray(raw); data[offset] ^= 0xff
    assert inspector.inspect(data, defaults, mapping) == expected
    cases += 1
for offset in range(base, base+size):
    data = bytearray(raw); data[offset] ^= 0xff
    try:
        result = inspector.inspect(data, defaults, mapping)
    except ValueError:
        pass  # A changed verified key must not produce an unchecked topology.
    else:
        assert result == expected  # Padding/unexported data cannot affect output.
    cases += 1
conditional, count = re.subn(r'(?m)^([ \t]*1900[ \t])', r':property unverified selector\n\1', defaults)
assert count == 1
for definition in [conditional, defaults.replace('1902', '61902')]:
    try:
        inspector.inspect(raw, definition, mapping)
    except ValueError:
        cases += 1
    else:
        raise AssertionError('accepted unresolved selector or missing static key')
print('PASS:', cases, 'private-registry/boundary/selector/output-isolation cases; no calibration values printed')
