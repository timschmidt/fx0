#!/usr/bin/env python3
# SPDX-License-Identifier: 0BSD
"""Compare treescan's output with independent file metadata, including time64."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve(strict=True)


def scan(directory):
    result = subprocess.run([str(binary), str(directory)], capture_output=True, check=True)
    assert not result.stderr
    rows = {}
    for line in result.stdout.decode().splitlines():
        name, kind, timestamp = line.rsplit(' ', 2)
        assert name not in rows
        assert kind.startswith('type=') and timestamp.startswith('mtime=')
        rows[name] = (kind.removeprefix('type='), int(timestamp.removeprefix('mtime=')))
    return rows


def expected(directory):
    rows = {}
    for parent, directories, files in os.walk(directory, followlinks=False):
        for leaf in directories + files:
            path = Path(parent) / leaf
            kind = 'symlink' if path.is_symlink() else 'dir' if path.is_dir() else 'file'
            rows[str(path)] = (kind, path.stat().st_mtime_ns // 10**9)
    return rows


with tempfile.TemporaryDirectory(prefix='treescan-check-') as temporary:
    root = Path(temporary)
    timestamps = [-1, 0, 1, 2147483647, 2147483648, 4102444800]
    for index, value in enumerate(timestamps):
        path = root / f'file {index}'
        path.write_bytes(b'fixture\n')
        os.utime(path, ns=(value * 10**9, value * 10**9))
        assert path.stat().st_mtime_ns == value * 10**9
    (root / 'directory').mkdir()
    (root / 'directory' / 'nested').write_bytes(b'nested\n')
    (root / 'symlink').symlink_to('file 4')
    wanted = expected(root)
    for _ in range(3):
        assert scan(root) == wanted
    missing = subprocess.run([str(binary), str(root / 'missing')], capture_output=True)
    assert missing.returncode != 0 and missing.stderr
print('Timestamp, recursion, symlink and missing-directory checks passed')
