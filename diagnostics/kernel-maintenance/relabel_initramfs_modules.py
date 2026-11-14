# SPDX-License-Identifier: MIT
"""Relabel one newc module tree while preserving unrelated records verbatim."""
from pathlib import PurePosixPath
import stat


def require(condition, message):
    if not condition:
        raise ValueError(message)


def relabel(raw, old_release, new_release, replacements):
    """Return a single archive with exact caller-supplied regular module files.

    Headers retain every byte except changed size/name-length fields. Only module
    tree names and regular bodies change; all other records remain byte exact.
    No filesystem or device access occurs here.
    """
    for release in (old_release, new_release):
        require(release and '/' not in release and release not in ('.', '..'), 'Invalid release')
    require(old_release != new_release, 'Distinct module releases required')
    old = 'usr/lib/modules/' + old_release
    new = 'usr/lib/modules/' + new_release
    at, output, seen, replaced, renamed = 0, bytearray(), set(), set(), []
    while at < len(raw):
        require(at % 4 == 0 and raw[at:at + 6] == b'070701', 'Expected aligned newc record')
        header = raw[at:at + 110]
        require(len(header) == 110, 'Truncated newc header')
        fields = [int(header[n:n + 8], 16) for n in range(6, 110, 8)]
        size, length = fields[6], fields[11]
        require(0 < length < 4096, 'Invalid newc name length')
        encoded = raw[at + 110:at + 110 + length]
        require(len(encoded) == length and encoded.endswith(b'\0') and b'\0' not in encoded[:-1],
                'Invalid newc name')
        name = encoded[:-1].decode()
        path = PurePosixPath(name)
        require(name and not path.is_absolute() and '..' not in path.parts and str(path) == name,
                'Unsafe or noncanonical newc path')
        start = (at + 110 + length + 3) & ~3
        end = (start + size + 3) & ~3
        require(end <= len(raw), 'Truncated newc body/padding')
        if name == 'TRAILER!!!':
            require(size == 0 and not any(raw[end:]), 'Expected exactly one archive')
            require(replaced == set(replacements), 'Replacement roster differs from module files')
            require(renamed, 'Module tree absent')
            output += raw[at:]
            output += bytes((-len(output)) % 512)
            return bytes(output), {'renamed_paths': renamed, 'replaced_relative_files': sorted(replaced)}
        require(name not in seen, 'Duplicate newc path')
        seen.add(name)
        require(name != new and not name.startswith(new + '/'), 'Destination module tree already exists')
        if name == old or name.startswith(old + '/'):
            replacement_name = new + name[len(old):]
            body = raw[start:start + size]
            if stat.S_ISREG(fields[1]):
                relative = name[len(old) + 1:]
                require(relative in replacements and fields[4] == 1, 'Unexpected/hardlinked module file')
                body = replacements[relative]
                require(isinstance(body, bytes), 'Replacement body must be bytes')
                replaced.add(relative)
            else:
                require(stat.S_ISDIR(fields[1]) and size == 0, 'Unexpected nonregular module entry')
            updated_header = bytearray(header)
            if len(body) != size:
                updated_header[54:62] = f'{len(body):08x}'.encode()
            encoded = replacement_name.encode() + b'\0'
            if len(encoded) != length:
                updated_header[94:102] = f'{len(encoded):08x}'.encode()
            output += updated_header + encoded
            output += bytes((-len(output)) % 4)
            output += body
            output += bytes((-len(output)) % 4)
            renamed.append(name)
        else:
            output += raw[at:end]
        at = end
    raise ValueError('Missing newc trailer')
