# SPDX-License-Identifier: GPL-2.0-only
"""Execute only the public example's scan definition and pure decoder."""
import argparse, ast, hashlib, json, struct
from pathlib import Path
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
tree = ast.parse(a.source.read_text())
selected = [n for n in tree.body if
    (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SCAN' for t in n.targets))
    or (isinstance(n, ast.FunctionDef) and n.name == 'decode_scan')]
assert len(selected) == 2
assert ast.unparse(selected[0].value) == "struct.Struct('=iiiiq8x')"
assert ast.unparse(selected[1].body[0]) == 'return SCAN.unpack_from(data)'
ns = {'struct': struct, '__builtins__': {}}
exec(compile(ast.Module(body=selected, type_ignores=[]), '<pure-decoder>', 'exec'), ns)
cases = [(0, 0, 0, 0, 0), (1 << 30, 0, 0, 0, 123456789),
         (-(1 << 30), 1, -1, 17, 987654321),
         (2**31-1, -2**31, 123, -456, 2**63-1),
         (5, 6, 7, 8, -2**63), (1, 2, 3, 4, -1),
         (-1, -2, -3, -4, 16), (123, 456, 789, 1000, 24),
         (111, -222, 333, -444, 31415926535)]
for values in cases:
    record = bytearray(struct.pack('=iiiiq8x', *values))
    record[24:] = b'\xa5' * 8
    assert len(record) == ns['SCAN'].size == 32
    assert ns['decode_scan'](record) == values
a.output.mkdir()
(a.output / 'qualification.json').write_text(json.dumps(dict(passed=True, cases=len(cases),
    source_example_SHA256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
    only_SCAN_definition_and_decode_function_executed=True,
    capture_main_restore_and_device_operations_not_executed=True,
    timestamp_offset=16, nonzero_tail_padding=True,
    normal_package_reader_update_required=True, phone_access=False), indent=2) + '\n')
print(json.dumps(dict(passed=True, synthetic_records=len(cases))))
