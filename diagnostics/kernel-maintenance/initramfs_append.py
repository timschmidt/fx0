# SPDX-License-Identifier: MIT
"""Check canonical parent directories before appending initramfs entries.

Linux's initramfs unpacker does not create omitted parent directories. Callers
provide the already parsed layout and additions in archive order. Symlink
parents are deliberately rejected: additions must use canonical directory paths.
This check does not replace header, payload, signature or boot-image validation.
"""
from pathlib import PurePosixPath
import stat


def require_append_parents(existing_modes, additions):
    """Raise ValueError if an addition lacks a preceding directory parent."""
    directories = {name for name, mode in existing_modes.items()
                   if stat.S_ISDIR(mode)}
    seen = set()
    for name, mode, _body in additions:
        path = PurePosixPath(name)
        if (not name or path.is_absolute() or str(path) != name
                or name == "." or ".." in path.parts or name in seen):
            raise ValueError("Invalid or duplicate appended path: " + name)
        for parent in path.parents:
            if str(parent) != "." and str(parent) not in directories:
                raise ValueError("Missing canonical parent for " + name
                                 + ": " + str(parent))
        seen.add(name)
        if stat.S_ISDIR(mode):
            directories.add(name)
        else:
            directories.discard(name)
