# SPDX-License-Identifier: MIT
"""Read package-owned native toolchain bodies; exclude credential/key paths."""
from pathlib import Path, PurePosixPath
from datetime import datetime, timezone
import argparse, base64, hashlib, json, os

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--native-root', type=Path, required=True)
parser.add_argument('--report', type=Path, required=True)
args = parser.parse_args()
native = args.native_root.resolve()
if args.report.exists():
    parser.error('Report exists; choose a new output path')
database = (native / 'lib/apk/db/installed').read_bytes()

def parent_in_native(name):
    parts = list(PurePosixPath(name).parts)
    filename = parts.pop()
    current = []
    steps = 0
    while parts:
        part = parts.pop(0)
        if part in ('/', '.', ''):
            continue
        if part == '..':
            assert current, 'Virtual path escapes native root'
            current.pop()
            continue
        path = native.joinpath(*current, part)
        if path.is_symlink():
            steps += 1
            assert steps < 64, 'Symlink loop'
            target = os.readlink(path)
            if target.startswith('/'):
                current = []
            parts = list(PurePosixPath(target).parts) + parts
        else:
            current.append(part)
    return native.joinpath(*current, filename)

records = []
for paragraph in database.decode().split('\n\n'):
    package = folder = filename = None
    for line in paragraph.splitlines():
        if line.startswith('P:'):
            package = line[2:]
        elif line.startswith('F:'):
            folder = line[2:]
        elif line.startswith('R:'):
            filename = line[2:]
        elif line.startswith('Z:'):
            assert package and folder is not None and filename
            records.append((package, '/' + folder + '/' + filename, line[2:]))
checked = symlinks = 0
excluded = []
mismatches = []
for package, name, checksum in records:
    # The audit never opens private key or credential bodies, including ones
    # accidentally introduced into a package-owned path.
    if (name in ['/etc/shadow', '/etc/gshadow'] or '/ssl/private/' in name or
            name.startswith(('/root/', '/home/')) or name.endswith(('.key', '.rsa'))):
        excluded.append(name)
        continue
    path = parent_in_native(name)
    assert checksum.startswith('Q1'), checksum[:2]
    try:
        if path.is_symlink():
            digest = hashlib.sha1(os.fsencode(os.readlink(path))).digest()
            symlinks += 1
        else:
            with path.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha1').digest()
        actual = 'Q1' + base64.b64encode(digest).decode()
    except OSError as exc:
        mismatches.append(dict(package=package, path=name, error=type(exc).__name__))
        continue
    checked += 1
    if actual != checksum:
        mismatches.append(dict(package=package, path=name, expected=checksum, actual=actual))
result = dict(recorded_UTC=datetime.now(timezone.utc).isoformat(),
              installed_database_SHA256=hashlib.sha256(database).hexdigest(),
              packaged_checksum_paths=len(records), checked_paths=checked,
              symlink_target_bodies_checked=symlinks, credential_or_private_paths_excluded=excluded,
              mismatches=mismatches, private_key_or_credential_bodies_opened=False,
              read_only=True, phone_changes=False,
              scope='Native build-root package-owned bodies against retained installed DB; signatures and public-key fixture separate.')
args.report.parent.mkdir(parents=True, exist_ok=True)
with args.report.open('x') as stream:
    json.dump(result, stream, indent=2)
    stream.write('\n')
print(json.dumps({k: v for k, v in result.items() if k != 'mismatches'}))
print('Mismatch paths:', [row['path'] for row in mismatches])

# Differences require explicit source reconciliation; configuration paths are
# never waived by this checksum reader. The report retains every discrepancy.
if mismatches:
    raise SystemExit(1)
