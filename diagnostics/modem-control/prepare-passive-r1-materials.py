#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Select the locked passive-r1 materials from exact APKs and public helper builds."""
import argparse
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tarfile
import zlib

ROOT = Path(__file__).resolve().parents[2]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('apk-dir', 'helpers', 'passive-dtb', 'output-dir'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    require(not sys.flags.optimize, 'Optimized Python is forbidden')
    spec = importlib.util.spec_from_file_location(
        'passive_r1_material_lock', ROOT / 'diagnostics/modem-control/build-passive-r1-image.py')
    builder = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(builder)
    profile = json.loads(builder.LOCK.read_text())
    lock = json.loads((ROOT / 'manifests/passive-r1-materials.json').read_text())
    require(lock['format'] == 1, 'Unexpected archive lock')
    require(set(lock['members']) == builder.MATERIALS - {'native-return', 'qrtr-local-rmtfs', 'passive.dtb'},
            'Unexpected selected member roster')
    material = {}
    for name, expected in lock['archives'].items():
        require(Path(name).name == name and name.endswith('.apk'), 'Invalid locked APK basename')
        raw = builder.locked_file(args.apk_dir / name, expected)
        chunks, compressed = [], []
        while raw:
            decoder = zlib.decompressobj(31)
            body = decoder.decompress(raw)
            require(decoder.eof and len(chunks) < 3, 'Expected APK v2 gzip streams')
            consumed = len(raw) - len(decoder.unused_data)
            compressed.append(raw[:consumed])
            chunks.append(body)
            raw = decoder.unused_data
        require(len(chunks) == 3, 'Expected three APK streams')
        with tarfile.open(fileobj=io.BytesIO(chunks[1]), mode='r:') as control:
            member = control.getmember('.PKGINFO')
            require(member.isfile(), 'Missing regular package metadata')
            metadata = control.extractfile(member).read().decode().splitlines()
            require('datahash = ' + sha(compressed[2]) in metadata, 'APK data hash mismatch')
        # Never tar-extract a tree: read only exact locked regular members into memory.
        with tarfile.open(fileobj=io.BytesIO(chunks[2]), mode='r:') as payload:
            for destination, item in lock['members'].items():
                if item['archive'] != name:
                    continue
                matches = [m for m in payload.getmembers() if m.name == item['member']]
                require(len(matches) == 1 and matches[0].isfile(), 'Missing/duplicate/nonregular selected member')
                body = payload.extractfile(matches[0]).read()
                if item['zstd']:
                    body = subprocess.check_output(['zstd', '-q', '-d', '-c'], input=body, timeout=15)
                material[destination] = body
    for name in ('native-return', 'qrtr-local-rmtfs'):
        material[name] = builder.locked_file(args.helpers / 'one' / name, profile['materials'][name])
    material['passive.dtb'] = builder.locked_file(args.passive_dtb, profile['materials']['passive.dtb'])
    require(set(material) == builder.MATERIALS, 'Incomplete material selection')
    for name, body in material.items():
        expected = profile['materials'][name]
        require(len(body) == expected['bytes'] and sha(body) == expected['SHA256'], 'Selected material differs')
    args.output_dir.mkdir(mode=0o700, exist_ok=False)
    for name, body in material.items():
        fd = os.open(args.output_dir / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
    print(json.dumps({'selected_materials': len(material), 'exact_APKs': len(lock['archives']),
                      'private_keys_read': False, 'phone_access': False}))


if __name__ == '__main__':
    main()
