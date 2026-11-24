#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect firmware on its existing filesystem; emit numbers/digests, never bytes.

For the Fx0, run this on the phone. It does not request kernel firmware loading,
map device memory, open modem controls, or write files. This checks layout only;
MBA authentication and successful operation remain untested.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct

TYPE_MASK = 7 << 24
TYPE_HASH = 2 << 24
RELOCATABLE = 1 << 27


def require(condition, message):
    if not condition:
        raise ValueError(message)


def elf_headers(path):
    size = path.stat().st_size
    require(52 <= size <= 65536, 'MDT size outside inspection bound')
    with path.open('rb') as stream:
        header = stream.read(52)
        require(header[:7] == b'\x7fELF\x01\x01\x01', 'ELF32 little-endian version1 required')
        fields = struct.unpack('<16sHHIIIIIHHHHHH', header)
        _, kind, machine, version, entry, phoff, shoff, flags, ehsize, phsize, phnum, shsize, shnum, _ = fields
        require(kind == 2 and machine == 164 and version == 1, 'Expected executable Hexagon ELF')
        require(ehsize == phoff == 52 and phsize == 32, 'MSS loader expects adjacent ELF32 program headers')
        require(1 <= phnum <= 100 and phoff + phnum * phsize <= size, 'Truncated/oversized program header table')
        require(shsize in [0, 40] and (not shnum or shsize == 40), 'Invalid section header width')
        require(shoff + shsize * shnum <= size, 'Truncated section header table')
        stream.seek(phoff)
        table = stream.read(phsize * phnum)
    keys = ['type', 'offset', 'vaddr', 'paddr', 'filesz', 'memsz', 'flags', 'align']
    rows = [dict(zip(keys, struct.unpack_from('<8I', table, i * phsize)), index=i) for i in range(phnum)]
    return {'bytes': size, 'entry': entry, 'flags': flags, 'phnum': phnum,
            'header_table_bytes': phoff + phnum * phsize, 'program_headers': rows}


def inspect(root, mpss_base, mpss_size, mba_base, mba_size):
    root = Path(root)
    real_root = (root / 'modem.mdt').resolve(strict=True).parent
    files = {}

    def selected(name):
        path = (root / name).resolve(strict=True)
        require(path.parent == real_root, 'Selected firmware files must share one original directory')
        info = path.stat()
        require(stat.S_ISREG(info.st_mode), 'Regular firmware files required')
        return path

    def digest(name):
        if name not in files:
            path = selected(name)
            before = path.stat()
            require(before.st_size <= 128 * 1024 * 1024, 'Firmware file exceeds inspection bound')
            with path.open('rb') as stream:
                hasher = hashlib.sha256()
                for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                    hasher.update(chunk)
            after = path.stat()
            require((before.st_ino, before.st_size, before.st_mtime_ns) ==
                    (after.st_ino, after.st_size, after.st_mtime_ns), 'Firmware changed during read')
            files[name] = {'bytes': before.st_size, 'sha256': hasher.hexdigest()}
        return files[name]

    mdt = elf_headers(selected('modem.mdt'))
    digest('modem.mdt')
    headers = mdt['program_headers']
    hashes = [row for row in headers[1:] if row['flags'] & TYPE_MASK == TYPE_HASH]
    require(headers[0]['type'] != 1 and len(hashes) == 1, 'Expected one metadata hash segment and non-loadable first header')
    header_size, hash_size = headers[0]['filesz'], hashes[0]['filesz']
    require(header_size >= mdt['header_table_bytes'] and header_size <= mdt['bytes'] and hash_size > 0,
            'Invalid authenticated metadata sizes')
    if header_size + hash_size == mdt['bytes']:
        metadata = {'source': 'packed after ELF header', 'offset': header_size, 'bytes': hash_size}
    elif hashes[0]['offset'] + hash_size <= mdt['bytes']:
        metadata = {'source': 'embedded segment', 'offset': hashes[0]['offset'], 'bytes': hash_size}
    else:
        name = 'modem.b%02d' % hashes[0]['index']
        require(digest(name)['bytes'] == hash_size, 'Split metadata hash size mismatch')
        metadata = {'source': name, 'offset': 0, 'bytes': hash_size}
    loadable = [row for row in headers if row['type'] == 1 and row['memsz'] and row['flags'] & TYPE_MASK != TYPE_HASH]
    require(loadable, 'No loadable MPSS segments')
    relocate = any(row['flags'] & RELOCATABLE for row in loadable)
    minimum = min(row['paddr'] for row in loadable)
    maximum = max((row['paddr'] + row['memsz'] + 4095) & ~4095 for row in loadable)
    relocation_base = minimum if relocate else mpss_base
    require(0 < mpss_size and maximum <= 1 << 32 and maximum - minimum <= mpss_size,
            'MPSS span exceeds reserved memory or ELF32 address space')
    segments = []
    ranges = []
    for row in loadable:
        offset = row['paddr'] - relocation_base
        require(row['filesz'] <= row['memsz'], 'Segment filesz exceeds memsz')
        require(offset >= 0 and offset + row['memsz'] <= mpss_size, 'Segment outside MPSS carveout')
        if not row['filesz']:
            source = 'zero-fill only'
        elif row['offset'] < mdt['bytes']:
            require(row['offset'] + row['filesz'] <= mdt['bytes'], 'Truncated embedded segment')
            source = 'embedded in modem.mdt'
        else:
            source = 'modem.b%02d' % row['index']
            require(digest(source)['bytes'] == row['filesz'], 'Split segment size mismatch')
        segments.append(dict(row, source=source, carveout_offset=offset,
                             physical_start=mpss_base + offset, zero_fill_bytes=row['memsz'] - row['filesz']))
        ranges.append((offset, offset + row['memsz']))
    ranges.sort()
    require(all(a[1] <= z[0] for a, z in zip(ranges, ranges[1:])), 'Overlapping loadable segments need separate audit')
    mba = elf_headers(selected('mba.mdt'))
    digest('mba.mdt')
    raw_mba = digest('mba.b00')
    require(raw_mba['bytes'] <= min(mba_size, 1024 * 1024), 'MBA file exceeds loader/carveout bound')
    require(mba['phnum'] == 1 and mba['entry'] == mba_base, 'Unexpected MBA description')
    mba_segment = mba['program_headers'][0]
    require(mba_segment['type'] == 1 and mba_segment['paddr'] == mba_base and
            mba_segment['filesz'] == raw_mba['bytes'] and raw_mba['bytes'] <= mba_segment['memsz'] <= mba_size,
            'MBA metadata/raw file/carveout mismatch')
    return {'layout_checks_passed': True, 'MSS_loader_program_headers_adjacent_to_ELF_header': True,
            'MPSS': {'base': mpss_base, 'size': mpss_size, 'entry': mdt['entry'], 'phnum': mdt['phnum'],
                     'relocatable': relocate, 'relocation_base': relocation_base, 'aligned_span': maximum - minimum,
                     'metadata': metadata, 'loadable_segments': segments, 'nonoverlapping': True},
            'MBA': {'base': mba_base, 'size': mba_size, 'raw_file_bytes': raw_mba['bytes'],
                    'metadata_checked_but_loader_uses_raw_b00': True},
            'files': files, 'firmware_payload_exported': False, 'firmware_authentication_tested': False,
            'firmware_started': False, 'read_only': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--firmware-root', required=True, type=Path)
    parser.add_argument('--mpss-base', type=lambda s: int(s, 0), default=0x08000000)
    parser.add_argument('--mpss-size', type=lambda s: int(s, 0), default=0x05100000)
    parser.add_argument('--mba-base', type=lambda s: int(s, 0), default=0x0d100000)
    parser.add_argument('--mba-size', type=lambda s: int(s, 0), default=0x00100000)
    args = parser.parse_args()
    print(json.dumps(inspect(args.firmware_root, args.mpss_base, args.mpss_size, args.mba_base, args.mba_size), indent=2))


if __name__ == '__main__':
    main()
