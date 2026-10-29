#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Decode this diagnostic's function names from private pmdebug1 retained RAM.

Output contains kernel addresses; keep it private alongside the input dump.
"""
import argparse
import bisect
import json
from pathlib import Path
import re
import struct
import subprocess

FIELDS = ('address', 'fsr', 'pc', 'cpsr')


def decode_names(events):
    """Consume (sequence, cpu, function name), keeping CPU streams separate."""
    events = list(events)
    results = []
    for cpu in range(4):
        values = None
        field = None
        last = None
        for sequence, _, name in sorted(e for e in events if e[1] == cpu):
            if name == 'fx0_abort_address':
                values = {key: '' for key in FIELDS}
                values.update(cpu=cpu, sequence=sequence)
                field = 'address'
            elif name.startswith('fx0_abort_digit_') and values is not None:
                if field is not None:
                    values[field] += name[-1]
            elif name.removeprefix('fx0_abort_') in FIELDS and values is not None:
                field = name.removeprefix('fx0_abort_')
            elif name == 'fx0_abort_end' and values is not None:
                values['complete'] = all(len(values[key]) == 8 for key in FIELDS)
                values['synthetic_selftest'] = False
                results.append(values)
                last, values, field = values, None, None
            elif name == 'fx0_abort_selftest_end' and last is not None:
                last['synthetic_selftest'] = True
        if values is not None:
            values.update(complete=False, synthetic_selftest=None)
            results.append(values)
    return sorted(results, key=lambda result: result['sequence'])


def symbols(module, base):
    sections = subprocess.check_output(['llvm-readelf', '-SW', module], text=True)
    match = re.search(r'\[\s*(\d+)\]\s+\.text\s', sections)
    if match is None:
        raise ValueError('Module has no .text section')
    index = match[1]
    table = subprocess.check_output(['llvm-readelf', '--symbols', '-W', module], text=True)
    result = []
    for line in table.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[3] == 'FUNC' and parts[6] == index:
            result.append((base + int(parts[1], 16), int(parts[2]), parts[7]))
    return sorted(result)


def retained_events(raw, table):
    if len(raw) != 524288:
        raise ValueError('Expected the full 512 KiB pmdebug1 retained region')
    starts = [item[0] for item in table]
    events = []
    signature = 0x43474244 ^ ((6 << 16) | (18 << 8) | 59)
    for cpu in range(4):
        offset = 262144 + cpu * 65536
        sig, start, size = struct.unpack_from('<III', raw, offset)
        if sig != signature or not 0 <= start <= size <= 65524:
            raise ValueError(f'Invalid retained ring header on CPU {cpu}')
        data = raw[offset + 12:offset + 12 + size]
        data = data[start:] + data[:start]
        data = data[len(data) % 16:]
        for offset in range(0, len(data), 16):
            ip, _, sequence = struct.unpack_from('<IIQ', data, offset)
            if ip & 3 != cpu:
                raise ValueError('Unexpected CPU bits in function record')
            ip &= ~3
            index = bisect.bisect_right(starts, ip) - 1
            if index >= 0:
                address, length, name = table[index]
                if address <= ip < address + length and name.startswith('fx0_abort_'):
                    events.append((sequence, cpu, name))
    return sorted(events)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('raw', type=Path)
    parser.add_argument('module', type=Path)
    parser.add_argument('module_text_base', type=lambda value: int(value, 0))
    args = parser.parse_args()
    events = retained_events(args.raw.read_bytes(), symbols(str(args.module), args.module_text_base))
    print(json.dumps({'marker_events': len(events), 'captures': decode_names(events)}, indent=2))


if __name__ == '__main__':
    main()
