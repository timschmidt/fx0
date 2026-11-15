#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Copy this fixture to a new workspace and pin its public tool inputs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-root', type=Path, required=True)
    parser.add_argument('--runtime-root', type=Path, required=True,
                        help='Existing rootless Podman runtime with podman-storage and podman-run')
    parser.add_argument('--expected-native-db-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = args.native_root.resolve()
    runtime = args.runtime_root.resolve()
    output = args.output.resolve()
    expected = args.expected_native_db_sha256
    assert re.fullmatch('[0-9a-f]{64}', expected)
    database = native / 'lib/apk/db/installed'
    assert sha(database) == expected
    matches = [stanza for stanza in database.read_text().split('\n\n')
               if '\nP:fakeroot\n' in '\n' + stanza + '\n']
    assert len(matches) == 1
    version = next(line[2:] for line in matches[0].splitlines() if line.startswith('V:'))
    for path in [native / 'usr/bin/python3', native / 'usr/bin/fakeroot',
                 runtime / 'podman-storage', runtime / 'podman-run']:
        assert path.exists(), path
    tracer = Path(shutil.which('strace')).resolve()
    tracer_version = subprocess.check_output([str(tracer), '--version'], text=True).splitlines()[0]
    assert not output.exists()
    output.mkdir(mode=0o700)
    (output / 'inputs').mkdir(mode=0o755)
    source = Path(__file__).resolve().parent
    names = ['run.py', 'verify.py', 'inputs/fixture.py', 'inputs/dispatch.py']
    for name in names:
        shutil.copyfile(source / name, output / name)
    plan = dict(recorded_UTC=datetime.now(timezone.utc).isoformat(),
                purpose='Paired owned-client receive control and one EINTR; no daemon injection',
                native_root=str(native), runtime_root=str(runtime),
                expected_native_database_SHA256=expected, native_fakeroot_version=version,
                strace_path=str(tracer), strace_SHA256=sha(tracer), strace_version=tracer_version,
                input_SHA256={name: sha(output / name) for name in names},
                phone_access=False, signers_mounted=False)
    (output / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
    print(json.dumps(dict(workspace=str(output), native_fakeroot=version,
                          source_files_copied=len(names), signers_mounted=False)))


if __name__ == '__main__':
    main()
