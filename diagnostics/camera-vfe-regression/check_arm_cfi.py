#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check LLVM22 A32 guards, real old callers and corrupt-instruction controls."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

from arm_cfi import require_type, xor_guards


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--object', action='append', type=Path, required=True)
    parser.add_argument('--baseline-object', action='append', type=Path, default=[])
    parser.add_argument('--type-word', type=lambda value: int(value, 0), default=0xe8f4cf55)
    parser.add_argument('--baseline-word', type=lambda value: int(value, 0), default=0xf0f6e568)
    parser.add_argument('--guards-per-object', type=int, default=1)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert not args.output.exists() and args.guards_per_object > 0
    rows = []
    controls = []
    for path in args.object:
        data = path.read_bytes()
        matches = require_type(data, args.type_word, args.guards_per_object)
        for match in matches:
            mutations = [
                ('altered XOR immediate', match['xor_instruction_file_offsets'][0], None),
                ('NE instead of EQ skip', match['branch_file_offset'], 0x1a000000),
                ('missing UDF trap', match['trap_file_offset'], 0xe1a00000),
                ('different BLX target', match['call_file_offset'], None),
            ]
            for label, offset, replacement in mutations:
                altered = bytearray(data)
                word = struct.unpack_from('<I', altered, offset)[0]
                struct.pack_into('<I', altered, offset, word ^ 1 if replacement is None else replacement)
                try:
                    require_type(altered, args.type_word, args.guards_per_object)
                except ValueError:
                    controls.append(dict(object=path.name, rejected=label))
                else:
                    raise ValueError('Accepted corrupt guard: ' + label)
        rows.append(dict(object=path.name, SHA256=hashlib.sha256(data).hexdigest(), guards=matches))
    for path in args.baseline_object:
        data = path.read_bytes()
        assert any(row['type_word'] == args.baseline_word for row in xor_guards(data))
        try:
            require_type(data, args.type_word, args.guards_per_object)
        except ValueError:
            controls.append(dict(object=path.name, rejected='real old void-return caller'))
        else:
            raise ValueError('Accepted old callback type')
    result = dict(scope='Static LLVM22 A32 guard encoding; not runtime CFI or hardware qualification',
                  type_word=f'0x{args.type_word:08x}', objects=rows,
                  negative_controls=controls, negative_control_count=len(controls), passed=True)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(objects=len(rows), negative_controls=len(controls), passed=True)))


if __name__ == '__main__':
    main()
