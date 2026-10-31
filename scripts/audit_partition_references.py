#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Record which stock components reference each original GPT entry.

Reads the original GPT, the stock boot-chain images, the stock boot/recovery
ramdisks and the vendor kernel source. It prints only partition names,
offsets, sizes, type GUIDs and reference sites, never partition contents.
"""
import argparse
import gzip
import json
import re
import struct
import subprocess
import uuid
from pathlib import Path

LOADERS = ['sbl1', 'aboot', 'rpm', 'tz', 'sdi']


def gpt_entries(path):
    data = Path(path).read_bytes()
    header = data[512:1024]
    assert header[:8] == b'EFI PART'
    lba, count, size = struct.unpack_from('<QII', header, 72)
    entries = []
    for i in range(count):
        e = data[1024 + i * size:1024 + (i + 1) * size]
        if not any(e[:16]):
            continue
        type_guid = str(uuid.UUID(bytes_le=e[:16]))
        first, last = struct.unpack_from('<QQ', e, 32)
        name = e[56:128].decode('utf-16le').rstrip('\0')
        entries.append({'index': i + 1, 'name': name, 'type_guid': type_guid,
                        'first_lba': first, 'last_lba': last,
                        'bytes': (last - first + 1) * 512, 'raw_type': e[:16]})
    return entries


def lz4_block(src):
    out = bytearray()
    i = 0
    while i < len(src):
        token = src[i]; i += 1
        lit = token >> 4
        if lit == 15:
            while True:
                b = src[i]; i += 1; lit += b
                if b != 255:
                    break
        out += src[i:i + lit]; i += lit
        if i >= len(src):
            break
        offset = src[i] | src[i + 1] << 8; i += 2
        match = (token & 15) + 4
        if token & 15 == 15:
            while True:
                b = src[i]; i += 1; match += b
                if b != 255:
                    break
        start = len(out) - offset
        for k in range(match):
            out.append(out[start + k])
    return bytes(out)


def lz4_legacy(data):
    assert data[:4] == b'\x02\x21\x4c\x18'
    out, i = bytearray(), 4
    while i + 4 <= len(data):
        size = struct.unpack_from('<I', data, i)[0]
        if size == 0x184C2102 or size == 0 or i + 4 + size > len(data):
            break
        out += lz4_block(data[i + 4:i + 4 + size]); i += 4 + size
    return bytes(out)


def ramdisk_files(image):
    data = Path(image).read_bytes()
    assert data[:8] == b'ANDROID!'
    ksize, _, rsize, _, _, _, _, page = struct.unpack_from('<8I', data, 8)
    pages = lambda n: (n + page - 1) // page * page
    ramdisk = data[page + pages(ksize):page + pages(ksize) + rsize]
    raw = gzip.decompress(ramdisk) if ramdisk[:2] == b'\x1f\x8b' else lz4_legacy(ramdisk)
    files, off = {}, 0
    while off + 110 <= len(raw) and raw[off:off + 6] in (b'070701', b'070702'):
        fields = [int(raw[off + 6 + i * 8:off + 14 + i * 8], 16) for i in range(13)]
        namesize, filesize = fields[11], fields[6]
        name = raw[off + 110:off + 110 + namesize - 1].decode(errors='replace')
        off = (off + 110 + namesize + 3) & ~3
        if name == 'TRAILER!!!':
            break
        files[name] = raw[off:off + filesize]
        off = (off + filesize + 3) & ~3
    return files


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--gpt', required=True)
    p.add_argument('--images', required=True, help='directory with <name>.img stock partition images')
    p.add_argument('--vendor-linux', required=True)
    a = p.parse_args()
    images = Path(a.images)
    entries = gpt_entries(a.gpt)
    names = [e['name'] for e in entries]

    loaders = {n: (images / f'{n}.img').read_bytes() for n in LOADERS if (images / f'{n}.img').exists()}
    ramdisks = {img: ramdisk_files(images / f'{img}.img') for img in ('boot', 'recovery')}
    text = {f'{img}:{path}': body.decode(errors='replace')
            for img, files in ramdisks.items() for path, body in files.items()
            if re.search(r'(fstab|\.rc$|\.sh$)', path) and len(body) < 2_000_000}

    def kernel_refs(name):
        if len(name) < 3:
            return []
        out = subprocess.run(['git', '-C', a.vendor_linux, 'grep', '-l', '-w', '-F', f'"{name}"', '--',
                              '*.c', '*.h', '*.dts', '*.dtsi'], capture_output=True, text=True).stdout.split()
        return sorted(out)[:6]

    result = []
    for e in entries:
        n = e['name']
        loader_hits = sorted(k for k, blob in loaders.items()
                             if re.search(rb'(?<![A-Za-z0-9_])' + re.escape(n.encode()) + rb'(?![A-Za-z0-9_])', blob)
                             or n.encode('utf-16le') in blob)
        guid_hits = sorted(k for k, blob in loaders.items() if e['raw_type'] in blob)
        ramdisk_hits = sorted(k for k, body in text.items()
                              if re.search(r'(by-name/|/dev/block/[^ ]*/)' + re.escape(n) + r'\b', body))
        result.append({k: v for k, v in e.items() if k != 'raw_type'} |
                      {'loader_name_refs': loader_hits, 'loader_type_guid_refs': guid_hits,
                       'stock_ramdisk_refs': ramdisk_hits, 'vendor_kernel_refs': kernel_refs(n)})
    print(json.dumps({'entries': result, 'loaders_scanned': sorted(loaders),
                      'ramdisk_text_files_scanned': len(text)}, indent=2))


if __name__ == '__main__':
    main()
