# SPDX-License-Identifier: GPL-2.0-only
"""Audit extractor variants without treating normalized links as literal matches."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--reference',type=Path,required=True)
p.add_argument('--variant',type=Path,action='append',required=True)
p.add_argument('--report',type=Path,required=True)
a=p.parse_args();assert not a.report.exists()
reference=a.reference.resolve();variants=[p.resolve() for p in a.variant]
def paths(root):
    result=set()
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files:
            path=Path(parent)/name
            if path.is_symlink() or path.is_file():result.add(str(path.relative_to(root)))
    return result
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
names=paths(reference)
assert all(paths(root)==names for root in variants)
differences=[[] for root in variants];regular=symlinks=0
for name in sorted(names):
    expected=reference/name
    if expected.is_symlink():
        symlinks+=1;target=os.readlink(expected)
        for i,root in enumerate(variants):
            path=root/name;assert path.is_symlink(),name;actual=os.readlink(path)
            if target!=actual:
                # The observed filter change removes '.' path components only.
                assert actual=='/'.join(p for p in target.split('/') if p!='.'),name
                assert path.resolve().relative_to(root)==expected.resolve().relative_to(reference),name
                differences[i].append(dict(path=name,archive_target=target,extracted_target=actual,
                    only_redundant_dot_components_removed=True,resolved_target_identical=True))
    else:
        regular+=1;digest=sha(expected)
        for root in variants:
            path=root/name;assert not path.is_symlink() and path.is_file(),name
            assert sha(path)==digest,name
            assert bool(path.stat().st_mode&0o111)==bool(expected.stat().st_mode&0o111),name
report=dict(passed=True,checked_UTC=datetime.now(timezone.utc).isoformat(),verified_paths=len(names),
    regular_files_compared=regular,symlinks_compared=symlinks,all_regular_file_bytes_and_executable_flags_identical=True,
    variants=[dict(source_directory=str(root),literal_symlink_targets_exact=not differences[i],
        normalization_differences=differences[i],all_symlinks_resolve_to_same_source_objects=True)
        for i,root in enumerate(variants)],
    does_not_replace_or_pass_the_initial_strict_literal_source_check=True,phone_access=False)
a.report.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(passed=True,verified_paths=len(names),regular_files=regular,symlinks=symlinks,
    normalization_differences=[len(x) for x in differences])))
