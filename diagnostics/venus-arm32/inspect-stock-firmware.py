# SPDX-License-Identifier: GPL-2.0-only
"""Read Venus ELF geometry from a verified stock Fx0 system filesystem."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess


ELF = struct.Struct('<16sHHIIIIIHHHHHH')
PROGRAM = struct.Struct('<8I')
LOAD = 1
HASH_TYPE = 2 << 24
TYPE_MASK = 7 << 24
RELOCATABLE = 1 << 27
PAGE_SIZE = 4096
VENUS_MAX_FIRMWARE_SIZE = 6 * 1024 * 1024
VENUS_FILE = re.compile(r'venus\.(?:mdt|mbn|b\d\d)')


def debugfs(image, command):
    descriptor = image.fileno()
    result = subprocess.run(['debugfs', '-R', command, f'/proc/self/fd/{descriptor}'],
                            pass_fds=(descriptor,), capture_output=True, timeout=15, check=True)
    return result.stdout


def file_sizes(image):
    sizes = {}
    for line in debugfs(image, 'ls -p /etc/firmware').decode().splitlines():
        fields = line.split('/')
        if len(fields) == 8 and VENUS_FILE.fullmatch(fields[5]):
            name, size = fields[5:7]
            if name in sizes or not size.isdecimal() or int(fields[2], 8) & 0o170000 != 0o100000:
                raise ValueError(f'invalid stock directory entry for {name}')
            sizes[name] = int(size)
    return sizes


def describe_mdt(preamble, sizes):
    if len(preamble) != sizes.get('venus.mdt') or len(preamble) < ELF.size:
        raise ValueError('incomplete MDT payload')
    (ident, file_type, machine, version, entry, phoff, shoff, _, ehsize,
     phsize, phnum, shsize, shnum, _) = ELF.unpack_from(preamble)
    if (ident[:7] != b'\x7fELF\x01\x01\x01' or (file_type, machine, version) != (2, 40, 1)
            or ehsize != ELF.size or phsize != PROGRAM.size or phoff < ELF.size
            or not 2 < phnum <= 100 or phoff + phnum * phsize > len(preamble)
            or shoff or shnum or shsize not in (0, 40)):
        raise ValueError('unexpected stock ELF32 ARM header')

    segments = []
    header_size = hash_size = 0
    for index in range(phnum):
        kind, offset, _, address, filesz, memsz, flags, align = PROGRAM.unpack_from(
            preamble, phoff + index * phsize)
        name = f'venus.b{index:02d}'
        if sizes.get(name) != filesz:
            raise ValueError(f'split segment size mismatch for {name}')
        if index == 0:
            if kind != 0 or offset or filesz < phoff + phnum * phsize:
                raise ValueError('invalid MDT header segment')
            header_size = filesz
        if flags & TYPE_MASK == HASH_TYPE:
            if index != 1 or not filesz or hash_size:
                raise ValueError('invalid MDT hash segment')
            hash_size = filesz
        if kind != LOAD or not memsz or flags & TYPE_MASK == HASH_TYPE:
            continue
        if (not 0 < filesz <= memsz or offset < len(preamble)
                or address + memsz >= 1 << 32 or not flags & RELOCATABLE):
            raise ValueError(f'invalid relocatable segment {name}')
        segments.append(dict(index=index, paddr=address, filesz=filesz,
                             memsz=memsz, file_offset=offset, alignment=align))

    if not header_size or not hash_size or header_size + hash_size != len(preamble):
        raise ValueError('inconsistent contiguous header and hash lengths')
    ordered = sorted(segments, key=lambda item: item['paddr'])
    if not ordered or any(a['paddr'] + a['memsz'] > b['paddr'] for a, b in zip(ordered, ordered[1:])):
        raise ValueError('missing or overlapping loadable segments')
    start = ordered[0]['paddr']
    last = ordered[-1]
    end = (last['paddr'] + last['memsz'] + PAGE_SIZE - 1) & -PAGE_SIZE
    if start % PAGE_SIZE or not start <= entry < end or end - start > VENUS_MAX_FIRMWARE_SIZE:
        raise ValueError('firmware entry or page-aligned memory span is outside the expected range')
    return dict(ELF_class='ELF32 little-endian ARM', header_and_hash_bytes=header_size + hash_size,
                entry=entry, load_segments=segments, link_address=start, aligned_end=end,
                resident_span_bytes=end - start, relocatable=True, split_file_sizes=sizes,
                loadable_segments_individually_opened=False, signature_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock_system', type=Path, help='unchanged private ext4 system image')
    parser.add_argument('--sha256', required=True, help='expected image hash from the verified manifest')
    args = parser.parse_args()
    with args.stock_system.open('rb') as image:
        initial = os.fstat(image.fileno())
        if hashlib.file_digest(image, 'sha256').hexdigest() != args.sha256.lower():
            raise ValueError('stock image hash differs from the manifest')
        sizes = file_sizes(image)
        if not ELF.size <= sizes.get('venus.mdt', 0) <= 65536:
            raise ValueError('missing or unexpected Venus MDT size')
        summary = describe_mdt(debugfs(image, 'cat /etc/firmware/venus.mdt'), sizes)
        final = os.fstat(image.fileno())
        if (initial.st_size, initial.st_mtime_ns) != (final.st_size, final.st_mtime_ns):
            raise ValueError('stock image changed during inspection')
    print(json.dumps(summary | {'verified_stock_image_bytes': initial.st_size,
                                'stock_image_sha256_matched': True}, indent=2))


if __name__ == '__main__':
    main()
