#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Independently parse the built Android v0 images and their shared RAM archive."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import stat
import struct


def sha(data):
    return hashlib.sha256(data).hexdigest()


def unpack_image(data, kernel_size):
    assert data.startswith(b'ANDROID!')
    ksize, kaddr, rsize, raddr, ssize, saddr, tags, page, version, unused = struct.unpack_from('<10I', data, 8)
    assert (kaddr, raddr, ssize, saddr, tags, page, version, unused) == (
        0x8000, 0x02000000, 0, 0x00f00000, 0x01e00000, 2048, 0, 0)
    assert 48 <= kernel_size < ksize
    command_line = data[64:576].split(b'\0', 1)[0].decode('ascii')
    kernel_payload = data[page:page + ksize]
    rstart = page + ((ksize + page - 1) // page) * page
    ramdisk = data[rstart:rstart + rsize]
    assert len(data) == rstart + ((rsize + page - 1) // page) * page
    assert not any(data[page + ksize:rstart]) and not any(data[rstart + rsize:])
    digest = hashlib.sha1()
    for part in (kernel_payload, ramdisk, b''):
        digest.update(part)
        digest.update(struct.pack('<I', len(part)))
    assert digest.digest() == data[576:596]
    kernel, dtb = kernel_payload[:kernel_size], kernel_payload[kernel_size:]
    assert struct.unpack_from('<I', kernel, 36)[0] == 0x016f2818
    assert dtb[:4] == b'\xd0\x0d\xfe\xed' and len(dtb) == int.from_bytes(dtb[4:8], 'big')
    return kernel, dtb, ramdisk, command_line


def unpack_cpio(raw):
    at = 0
    entries = {}
    while True:
        header = raw[at:at + 110]
        assert len(header) == 110 and header[:6] == b'070701'
        fields = [int(header[pos:pos + 8], 16) for pos in range(6, 110, 8)]
        mode, size, namelen = fields[1], fields[6], fields[11]
        name_bytes = raw[at + 110:at + 110 + namelen]
        assert name_bytes.endswith(b'\0')
        name = name_bytes[:-1].decode('ascii')
        payload_at = (at + 110 + namelen + 3) & ~3
        assert name not in entries and len(raw) >= payload_at + size
        if name == 'TRAILER!!!':
            assert size == 0 and payload_at == len(raw)
            return entries
        entries[name] = (mode, raw[payload_at:payload_at + size])
        at = (payload_at + size + 3) & ~3


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    args = parser.parse_args()
    directory = args.directory.resolve()
    manifest = json.loads((directory / 'images.json').read_text())
    result = {}
    for label in ['control', 'managed']:
        expected = manifest['images'][label]
        assert expected['file'] == f'fx0-usb-budget-{label}-ram.img'
        data = (directory / expected['file']).read_bytes()
        assert sha(data) == expected['sha256'] and len(data) == expected['bytes']
        result[label] = unpack_image(data, manifest['kernel_bytes'])
        kernel, dtb, ramdisk, command_line = result[label]
        assert sha(kernel) == manifest['kernel_sha256'] and sha(dtb) == expected['DTB_sha256']
        assert dtb == (directory / (label + '.dtb')).read_bytes()
        assert sha(ramdisk) == manifest['ramdisk_sha256'] and command_line == manifest['command_line']

    kernel, _, ramdisk, command_line = result['control']
    assert (kernel, ramdisk, command_line) == (result['managed'][0], result['managed'][2], result['managed'][3])
    assert result['control'][1] != result['managed'][1]
    raw = gzip.decompress(ramdisk)
    assert sha(raw) == manifest['raw_ramdisk_sha256']
    entries = unpack_cpio(raw)
    directories = {'bin', 'dev', 'proc', 'sys', 'tmp', 'www'}
    executables = {'bin/busybox', 'bin/usb-budget-registers', 'bin/usb-budget-sample', 'bin/serve-http', 'init'}
    assert set(entries) == directories | executables | {'bin/sh'}
    assert all(entries[name] == (stat.S_IFDIR | 0o755, b'') for name in directories)
    assert entries['bin/sh'] == (stat.S_IFLNK | 0o777, b'busybox')
    assert all(entries[name][0] == stat.S_IFREG | 0o755 for name in executables)
    assert {name: sha(content) for name, (_mode, content) in entries.items()} == manifest['entries_sha256']
    init = entries['init'][1]
    timer = b'(sleep 180; return_native timer) &'
    assert init.count(timer) == 1 and init.index(timer) < init.index(b'mount -t proc')
    assert b'blockdev --setro' in init and b'reboot -f' in init
    assert b'insmod ' not in init and b'modprobe ' not in init and b'mount /dev/' not in init
    print(json.dumps({'independently_parsed_images': 2, 'android_header_digest_verified': True,
                      'same_kernel_initramfs_and_cmdline': True, 'initramfs_entries': len(entries),
                      'early_independent_return_timer_seconds': 180,
                      'module_or_filesystem_payloads': False, 'staged_or_booted': False}, indent=2))


if __name__ == '__main__':
    main()
