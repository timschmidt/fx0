# SPDX-License-Identifier: GPL-2.0-only
"""Compare a public Linux source export to every file in its pinned archive."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tarfile

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('--archive', type=Path, required=True)
p.add_argument('--source', type=Path, required=True)
p.add_argument('--expected-archive-sha256', required=True)
p.add_argument('--report', type=Path, required=True)
a = p.parse_args()
assert not a.report.exists()
def file_sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
assert file_sha(a.archive) == a.expected_archive_sha256
source = a.source.resolve()
actual = set()
for root, directories, files in os.walk(source, followlinks=False):
    for name in directories + files:
        path = Path(root) / name
        if path.is_symlink() or path.is_file():
            actual.add(str(path.relative_to(source)))
rows = []
total = 0
regular = symlinks = 0
with tarfile.open(a.archive) as archive:
    members = [m for m in archive if m.isfile() or m.issym()]
    assert actual == {m.name for m in members}, 'Export path set differs from archive'
    for member in members:
        path = source / member.name
        if member.issym():
            assert path.is_symlink() and os.readlink(path) == member.linkname, member.name
            rows.append(dict(path=member.name, type='symlink', target=member.linkname))
            symlinks += 1
        else:
            assert path.is_file() and not path.is_symlink(), member.name
            with archive.extractfile(member) as stream:
                expected = hashlib.file_digest(stream, 'sha256').hexdigest()
            assert file_sha(path) == expected, member.name
            executable = bool(member.mode & 0o111)
            assert bool(path.stat().st_mode & 0o111) == executable, member.name
            rows.append(dict(path=member.name, type='file', SHA256=expected, executable=executable))
            regular += 1
            total += member.size
rows.sort(key=lambda r: r['path'])
report = dict(passed=True, checked_UTC=datetime.now(timezone.utc).isoformat(),
    archive_SHA256=a.expected_archive_sha256, regular_files=regular, symlinks=symlinks,
    verified_paths=len(rows), regular_file_bytes=total, no_extra_paths=True,
    all_file_bytes_executable_flags_and_symlink_targets_exact=True,
    canonical_source_manifest_SHA256=hashlib.sha256(json.dumps(rows, sort_keys=True,
        separators=(',', ':')).encode()).hexdigest(), source_directory=str(source),
    source_only_no_build_outputs=True, phone_access=False)
a.report.parent.mkdir(parents=True, exist_ok=True)
a.report.write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
