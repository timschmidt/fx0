#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Inspect SSI topology only; never emit calibration, driver UUIDs or raw hashes."""
import argparse
import json
from pathlib import Path
import re


def inspect(registry, defaults, mapping):
    mapping = re.sub(r'/\*.*?\*/|//[^\n]*', '', mapping, flags=re.S)
    match = list(re.finditer(r'\{\s*2690\s*,\s*\{', mapping))
    if len(match) != 1:
        raise ValueError('expected exactly one group2690 key layout')
    start = match[0].end()-1
    end, depth = start+1, 1
    while depth and end < len(mapping):
        depth += (mapping[end] == '{')-(mapping[end] == '}')
        end += 1
    if depth:
        raise ValueError('incomplete group layout')
    body = mapping[start+1:end-1]
    pairs = re.findall(r'\{\s*(-?\d+)\s*,\s*(\d+)\s*\}', body)
    remainder = re.sub(r'\{\s*-?\d+\s*,\s*\d+\s*\}|\{\s*\}', '', body)
    if re.sub(r'[\s,]', '', remainder):
        raise ValueError('unsupported key layout syntax')
    location = re.findall(r'\{\s*2690\s*,\s*(0x[\da-fA-F]+)\s*,\s*(0x[\da-fA-F]+)\s*\}', mapping)
    if len(location) != 1:
        raise ValueError('expected exactly one group file location')
    base, size = (int(value, 16) for value in location[0])
    if size != 256 or base+size > len(registry):
        raise ValueError('unsupported group size or truncated registry')
    offset, values, widths = base, {}, {}
    for key, width in pairs:
        key, width = int(key), int(width)
        if key < -1 or width <= 0 or offset+width > base+size:
            raise ValueError('invalid key, padding or group boundary')
        if key >= 0:
            if key in values or width > 8:
                raise ValueError('duplicate key or unsupported scalar width')
            values[key] = int.from_bytes(registry[offset:offset+width], 'little')
            widths[key] = width
        offset += width
    if offset != base+size:
        raise ValueError('layout does not cover the complete group')

    expected = {}
    conditions = {}
    for line in defaults.splitlines():
        line = line.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith(':'):
            fields = line[1:].split()
            if fields[0] != 'version':
                conditions[fields[0]] = fields[1:]
            continue
        fields = line.split()
        if not fields[0].isdecimal() or int(fields[0]) not in values:
            continue
        if len(fields) != 3 or any(conditions.values()):
            raise ValueError('SSI defaults need explicit selector resolution')
        key = int(fields[0])
        if key in expected:
            raise ValueError('ambiguous repeated SSI default')
        expected[key] = int(fields[1], 0) & ((1 << (8*widths[key]))-1)
    if len(expected) != 72:
        raise ValueError('expected the Fx0 72-key static comparison set')
    mismatches = sorted(key for key in expected if values[key] != expected[key])
    if mismatches:
        raise ValueError('static SSI defaults differ; resolve layout or variant before interpreting topology')
    topology = {}
    for base_key, label, sensor_id in [(1902, 'accelerometer', 0), (1918, 'gyroscope', 10), (1934, 'magnetometer', 20)]:
        if values[base_key+9] != sensor_id:
            raise ValueError('unexpected sensor type assignment')
        topology[label] = {name: values[base_key+offset] for offset, name in
                           [(4, 'bus'), (7, 'gpio1'), (8, 'gpio2'), (10, 'address')]}
    return {'group': 2690, 'group_bytes': size, 'shared_static_keys_checked': len(expected),
            'mismatched_static_key_IDs': mismatches, 'topology': topology,
            'silicon_identity_or_DMP_execution_verified': False,
            'calibration_or_driver_UUIDs_exported': False,
            'other_registry_groups_qualified': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--registry', type=Path, required=True)
    parser.add_argument('--defaults', type=Path, required=True)
    parser.add_argument('--map', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.registry.read_bytes(), args.defaults.read_text(), args.map.read_text())
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
