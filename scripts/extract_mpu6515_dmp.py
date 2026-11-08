#!/usr/bin/env python3
"""Extract the pinned AOSP/InvenSense MPU-6515 image into a new private directory.

No device access. Firmware and its accompanying license remain local; the
public repository contains only this extraction recipe and provenance.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import zlib

COMMIT = 'd411d613f60e6305d48ade617c848262b62a582a'
SOURCE_URL = f'https://android.googlesource.com/platform/hardware/invensense/+/{COMMIT}/6515/libsensors_iio/software/core/mllite/linux/ml_load_dmp.c'
SOURCE_SHA256 = 'af94aecf908676765e48c629a0b146f4af95c0245bb2b51dc05ae3525e4d3f3f'
LICENSE_SHA256 = 'f358932599499c93dfbbabd5c87064f77f48efad6798d7c102975d8c32920299'
IMAGE_SHA256 = 'eabe2b79d93565358cca83864fece47d7dca5d5826bfbdab2d79ed75996076aa'
IMAGE_SIZE = 2943
IMAGE_CRC32 = 0xa7e2110d


def linux_crc32(data):
    """Linux crc32_le(seed=0), without zlib's initial/final complements."""
    return zlib.crc32(data, 0xffffffff) ^ 0xffffffff


def parse_array(source):
    marker = 'static const unsigned char dmpMemory[DMP_CODE_SIZE] = {'
    if source.count(marker) != 1:
        raise ValueError('expected exactly one dmpMemory array')
    rest = source.split(marker, 1)[1]
    if '};' not in rest:
        raise ValueError('unterminated dmpMemory array')
    body = rest.split('};', 1)[0]
    body = re.sub(r'/\*.*?\*/', '', body, flags=re.S)
    tokens = [token.strip() for token in body.split(',')]
    if tokens and not tokens[-1]:
        tokens.pop()
    if not tokens or any(not re.fullmatch(r'0[xX][0-9a-fA-F]{1,2}', t) for t in tokens):
        raise ValueError('array must contain only comma-separated byte literals')
    return bytes(int(token, 16) for token in tokens)


def extract(source, license_text):
    if hashlib.sha256(source).hexdigest() != SOURCE_SHA256:
        raise ValueError('source is not the pinned AOSP file')
    if hashlib.sha256(license_text).hexdigest() != LICENSE_SHA256:
        raise ValueError('license is not the accompanying pinned agreement')
    image = parse_array(source.decode('utf-8'))
    if len(image) != IMAGE_SIZE or linux_crc32(image) != IMAGE_CRC32:
        raise ValueError('image does not match the MPU-6515 driver size/CRC')
    if hashlib.sha256(image).hexdigest() != IMAGE_SHA256:
        raise ValueError('image digest mismatch')
    return image


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--license', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='new private directory')
    args = parser.parse_args()
    try:
        source = args.source.read_bytes()
        agreement = args.license.read_bytes()
        image = extract(source, agreement)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.mkdir(mode=0o700)  # Existing output is never overwritten.
        for name, data in [('mpu6515-dmp.bin', image), ('LICENSE', agreement)]:
            with (args.output / name).open('xb') as f:
                os.chmod(f.name, 0o600)
                f.write(data)
        info = {'source': SOURCE_URL, 'source_sha256': SOURCE_SHA256,
                'license_sha256': LICENSE_SHA256, 'firmware_sha256': IMAGE_SHA256,
                'firmware_bytes': IMAGE_SIZE, 'linux_crc32_seed0': hex(IMAGE_CRC32),
                'load_address': '0x20', 'entry_point': '0x400',
                'qualification': 'Reference image extracted; no device or execution test.'}
        with (args.output / 'manifest.json').open('x') as f:
            os.chmod(f.name, 0o600)
            json.dump(info, f, indent=2)
            f.write('\n')
        print(json.dumps(info, indent=2))
    except (OSError, ValueError, UnicodeError) as exc:
        parser.exit(2, f'{exc}\n')


if __name__ == '__main__':
    main()
