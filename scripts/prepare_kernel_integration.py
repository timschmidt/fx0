#!/usr/bin/env python3
"""Prepare a pristine pinned kernel checkout from reviewed integration patches.

Reads local sources only. Verifies all input hashes and simulates the complete
series before modifying the checkout. Does not build or access a device.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(argv, cwd):
    result = subprocess.run([str(arg) for arg in argv], cwd=cwd,
                            capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"{' '.join(map(str, argv))}\n{result.stdout}{result.stderr}")
    return result.stdout


def relative_path(path):
    candidate = Path(path)
    if candidate.is_absolute() or '..' in candidate.parts or not candidate.parts:
        raise ValueError(f'Unsafe manifest path: {path}')
    return candidate


def prepare(source, profile, manifest_path, root=ROOT):
    source, root = Path(source).resolve(), Path(root).resolve()
    manifest = json.loads(Path(manifest_path).read_text())
    if manifest.get('schema') != 1:
        raise ValueError('Unsupported integration manifest schema')
    selected = manifest['profiles'][profile]
    paths = selected['patches']
    if len(set(paths)) != len(paths):
        raise ValueError('Duplicate patch in profile')
    patches, changed = [], set()
    for path in paths:
        patch = root / relative_path(path)
        if digest(patch) != manifest['sha256'][path]:
            raise ValueError(f'Patch checksum mismatch: {path}')
        headers = re.findall(r'^diff --git a/(\S+) b/(\S+)$', patch.read_text(), re.M)
        if not headers:
            raise ValueError(f'No file changes in patch: {path}')
        for before, after in headers:
            if before != after:
                raise ValueError(f'Renames are not supported: {path}')
            changed.add(relative_path(after))
        patches.append(patch)

    config = manifest['configuration']
    if digest(root / relative_path(config['path'])) != config['sha256']:
        raise ValueError('Reference configuration checksum mismatch')
    base = manifest['base']['commit']
    if run(['git', 'rev-parse', 'HEAD'], source).strip() != base:
        raise ValueError(f'Checkout must be at pinned base {base}')
    if run(['git', 'status', '--porcelain', '--untracked-files=all'], source).strip():
        raise ValueError('Checkout must have no tracked changes or untracked files')

    scratch = root/'local/kernel-preparation'
    scratch.mkdir(parents=True, exist_ok=True)
    commands = [['patch', '--batch', '--forward', '-p1', '--fuzz=0',
                 '--no-backup-if-mismatch', '-i', patch] for patch in patches]
    # Use workspace scratch: /tmp may have a separate filesystem/user quota.
    with tempfile.TemporaryDirectory(prefix='preflight-', dir=scratch) as temporary:
        target = Path(temporary)
        for path in changed:
            original = source/path
            if not original.resolve().is_relative_to(source):
                raise ValueError(f'Source path escapes checkout: {path}')
            if original.is_file():
                copied = target/path
                copied.parent.mkdir(parents=True, exist_ok=True)
                copied.write_bytes(original.read_bytes())
        for command in commands:
            run(command, target)
        expected = {str(path): digest(target/path) for path in sorted(changed)}

    # Preflight has passed. A filesystem error can still leave a partial tree;
    # keep it for inspection, rather than resetting or deleting caller files.
    for command in commands:
        run(command, source)
    for path, sha256 in expected.items():
        if digest(source/path) != sha256:
            raise RuntimeError(f'Prepared source differs from preflight: {path}')
    return {
        'profile': profile,
        'base': base,
        'manifest_sha256': digest(Path(manifest_path)),
        'configuration': config,
        'patches': {path: manifest['sha256'][path] for path in paths},
        'files_sha256': expected,
        'status': 'prepared and byte-verified; no build or device operation',
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True,
                        help='Existing pristine checkout at the manifest base commit')
    parser.add_argument('--profile', choices=['r50', 'cpr'], required=True)
    parser.add_argument('--manifest', type=Path,
                        default=ROOT/'manifests/kernel-integration.json')
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report already exists; choose a new destination')
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = prepare(args.source, args.profile, args.manifest)
    args.report.write_text(json.dumps(report, indent=2)+'\n')
    print(f"Prepared {args.profile}: {len(report['patches'])} patches, "
          f"{len(report['files_sha256'])} verified files")


if __name__ == '__main__':
    main()
