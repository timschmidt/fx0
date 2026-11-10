#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare two Fx0 diagnostic images that differ in kernel compression."""
import argparse
import hashlib
import json
import lzma
from pathlib import Path
import struct


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def unpack_image(data):
    require(data[:8] == b'ANDROID!' and len(data) >= 2048, 'Expected an Android boot image')
    payload_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size, second_addr, tags, page, version, _ = (
        struct.unpack_from('<10I', data, 8))
    require((kernel_addr, ramdisk_addr, second_size, second_addr, tags, page, version) ==
            (0x8000, 0x2000000, 0, 0xf00000, 0x1e00000, 2048, 0), 'Unexpected Fx0 image layout')
    align = lambda size: (size + page - 1) // page * page
    ramdisk_start = page + align(payload_size)
    require(len(data) == ramdisk_start + align(ramdisk_size), 'Unexpected boot image size')
    payload = data[page:page + payload_size]
    ramdisk = data[ramdisk_start:ramdisk_start + ramdisk_size]
    require(not any(data[page + payload_size:ramdisk_start]) and
            not any(data[ramdisk_start + ramdisk_size:]), 'Nonzero boot image padding')
    require(len(payload) >= 48 and len(ramdisk) == ramdisk_size, 'Truncated image components')
    magic, start, end = struct.unpack_from('<3I', payload, 0x24)
    kernel_size = end - start
    require(magic == 0x016f2818 and 48 <= kernel_size <= len(payload) - 8, 'Invalid zImage extent')
    kernel, dtb = payload[:kernel_size], payload[kernel_size:]
    require(struct.unpack_from('>2I', dtb) == (0xd00dfeed, len(dtb)), 'Invalid appended DTB')
    digest = hashlib.sha1()
    for part in [payload, ramdisk, b'']:
        digest.update(part)
        digest.update(struct.pack('<I', len(part)))
    require(data[576:608] == digest.digest().ljust(32, b'\0'), 'Boot image checksum differs')
    return kernel, dtb, ramdisk


def check_stream(kernel, piggy, runtime):
    require(len(piggy) > 4 and piggy.startswith(b'\xfd7zXZ\0'), 'Expected a single XZ payload')
    require(struct.unpack('<I', piggy[-4:])[0] == len(runtime), 'Uncompressed size trailer differs')
    require(kernel.count(piggy) == 1, 'Packed stream not found exactly once in zImage')
    decoder = lzma.LZMADecompressor(format=lzma.FORMAT_XZ, memlimit=256 * 1024 * 1024)
    decoded = decoder.decompress(piggy[:-4], max_length=len(runtime) + 1)
    require(decoder.eof and not decoder.unused_data and decoder.check == lzma.CHECK_CRC32,
            'Unexpected XZ framing or checksum type')
    require(decoded == runtime, 'Decoded runtime Image differs')
    return 2048 + kernel.index(piggy)


def verify(reference, candidate, reference_piggy, candidate_piggy, runtime, offset, chunk):
    old_kernel, old_dtb, old_ramdisk = unpack_image(reference)
    new_kernel, new_dtb, new_ramdisk = unpack_image(candidate)
    require(old_dtb == new_dtb, 'Appended DTB differs')
    require(old_ramdisk == new_ramdisk, 'Compressed initramfs differs')
    require(reference[:8] == candidate[:8] and reference[12:576] == candidate[12:576] and
            reference[608:2048] == candidate[608:2048], 'Unexpected boot header change')
    old_start = check_stream(old_kernel, reference_piggy, runtime)
    new_start = check_stream(new_kernel, candidate_piggy, runtime)
    end = offset + chunk
    require(chunk > 0 and old_start <= offset and end <= old_start + len(reference_piggy) - 4 and
            new_start <= offset and end <= new_start + len(candidate_piggy) - 4,
            'Transfer frame lies outside the compressed kernel streams')
    old_frame, new_frame = reference[offset:end], candidate[offset:end]
    changed = sum(a != b for a, b in zip(old_frame, new_frame))
    require(changed > 0, 'Transfer frame bytes are unchanged')
    return {'reference_image_sha256': sha(reference), 'reference_image_bytes': len(reference),
            'candidate_image_sha256': sha(candidate), 'candidate_image_bytes': len(candidate),
            'reference_zImage_sha256': sha(old_kernel), 'candidate_zImage_sha256': sha(new_kernel),
            'candidate_zImage_bytes': len(new_kernel), 'runtime_Image_sha256': sha(runtime),
            'runtime_Image_bytes': len(runtime), 'DTB_sha256': sha(old_dtb),
            'compressed_initramfs_sha256': sha(old_ramdisk),
            'same_header_except_kernel_size_and_digest': True,
            'same_runtime_Image_DTB_and_compressed_initramfs': True,
            'first_unconfirmed_host_frame': {'offset': offset, 'bytes': chunk, 'changed_bytes': changed,
                'reference_sha256': sha(old_frame), 'candidate_sha256': sha(new_frame),
                'reference_frame_occurs_in_candidate': old_frame in candidate}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['reference', 'candidate', 'reference-piggy', 'candidate-piggy', 'runtime', 'output']:
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--reference-sha256', required=True)
    parser.add_argument('--offset', type=int, required=True)
    parser.add_argument('--chunk', type=int, required=True)
    args = parser.parse_args()
    reference = args.reference.read_bytes()
    require(sha(reference) == args.reference_sha256, 'Reference image hash differs')
    result = verify(reference, args.candidate.read_bytes(), args.reference_piggy.read_bytes(),
                    args.candidate_piggy.read_bytes(), args.runtime.read_bytes(), args.offset, args.chunk)
    with args.output.open('x') as file:
        json.dump(result, file, indent=2)
        file.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
