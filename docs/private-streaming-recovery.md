# Streaming cold replay for private fixtures

[`StreamRollback`](../diagnostics/stable-update/stream_restore.py) restores an
owned, stopped private directory from a complete file manifest and its verified
base and delta archives. It streams file bodies with a one-MiB buffer, rehashes
reused bodies, restores nanosecond metadata and attributes, reconstructs complete
hardlink groups, and checks every recorded directory membership.

The caller establishes exclusive ownership of the fixture and keeps both input
archives read-only throughout replay. Use a bounded service whose writable paths
are the fixture and a separate controller workspace. The native qualification
also masks original credentials, hides raw devices and isolates networking and
processes. Original backup and quarantine directories remain read-only.

## Inputs and invocation

The `fx0-stable-file-delta-v2` manifest records canonical absolute names beneath
the private root. Each row records its type, ownership, mode, nanosecond mtime and
complete extended attributes. Regular-file leaders include size, SHA256,
hardlink count and one authenticated base/delta archive member reference.
Aliases identify a captured leader. Symlinks record their exact targets.
`directory_membership` records the complete expected child names of each guarded
directory. Explicit absent rows record names that recovery must remove.

An invocation using private operator-provided paths is:

```python
import json
from pathlib import Path
from stream_restore import StreamRollback

fixture = Path("/var/lib/fx0-owned-fixture/root")
backups = Path("/var/lib/fx0-owned-backups")
manifest = json.loads((backups / "manifest.private.json").read_text())

with StreamRollback(
    fixture,
    manifest,
    backups / "base.private.tar.gz",
    backups / "delta.private.tar.gz",
    manifest["delta_archive_sha256"],
) as replay:
    replay.restore()
    replay.verify()
```

Use `PYTHONPATH=diagnostics/stable-update` from the repository root. Constructing
the object validates archive checksums, referenced bodies and the closed
manifest before replay writes. Changed source archives, symlink parents, nested
mounts and hardlinks crossing the captured scope cause refusal. Unknown children
are preserved; complete directory verification requires resolving them through a
separately reviewed preservation and namespace-closure step.

## Interrupted replay and capture boundaries

An interrupted caller opens a new `StreamRollback` with the same sealed inputs.
Recognized partial files must have the expected ownership, mode, link count,
name and an authenticated prefix of the archived body. Replay validates the
prefix before continuing and atomically replaces the destination only after
checking the complete body. Unexpected partials are retained and refused.

Credential and opaque file bodies are excluded by the capture policy. Their
presence in recorded directory membership does not provide recoverable contents.
The qualification fixture represents excluded names with explicit empty
placeholders and remains unprovisioned. Its recovery result covers the complete
captured safe namespace. It makes no claim of preserving a live APK lock inode.

SELinux attributes are verified by default. The host tests explicitly skip
SELinux comparison in their synthetic unprivileged fixtures; native qualification
restores and verifies the actual labels without that override.

## Validation

Run the focused suite from the repository root:

```sh
python3 -B -m unittest discover -s tests -p test_stream_restore.py
```

The 14 cases cover body/metadata/attribute recovery, hardlinks, full membership,
interruption and resume, actual owned-process SIGKILL before rename, source
corruption/change, parent escapes, unknown partials and bounded body buffering.

The [native qualification](../evidence/2026-11-13-full-cold-private-replay.json)
verifies all 26,582 captured paths, 2,438 directory memberships, 255 hardlink
aliases and the exact 775-package database. It includes interruption after 5,000
changes and resume in a fresh process. The separately running post-edge return
requires its own completion and independent verification before acceptance.
