#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Verify and attach a previously issued public module signature.

This program never signs new content and never accepts a private-key argument.
The kernel's sign-file -s operation performs the actual attachment.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

MAGIC = b'~Module signature appended~\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def attach(module, manifest, sign_file):
    module, manifest, sign_file = map(Path, (module, manifest, sign_file))
    inputs = manifest.resolve().parent
    spec = json.loads(manifest.read_text())
    if spec.get('schema') != 1 or spec.get('signature_hash') != 'sha512':
        raise ValueError('Unsupported signature input schema')
    payload = module.read_bytes()
    if payload.endswith(MAGIC):
        raise ValueError('Refusing to attach a second module signature')
    if payload[:6] != b'\x7fELF\x01\x01' or int.from_bytes(payload[18:20], 'little') != 40:
        raise ValueError('Expected a little-endian ELF32 ARM module')
    entry = spec['payloads'].get(digest(payload))
    if entry is None:
        raise ValueError('No issued signature for this exact module payload')
    name = entry['signature']
    if not re.fullmatch(r'module-signatures/[0-9a-f]{64}\.p7s', name):
        raise ValueError('Invalid signature path')
    signature_file = inputs / name
    signature = signature_file.read_bytes()
    if digest(signature) != entry['signature_SHA256']:
        raise ValueError('Detached signature checksum mismatch')
    certificate = inputs / 'module-verification.pem'
    certificate_der = inputs / 'module-verification.der'
    if digest(certificate.read_bytes()) != spec['certificate_PEM_SHA256']:
        raise ValueError('Certificate PEM checksum mismatch')
    if digest(certificate_der.read_bytes()) != spec['certificate_DER_SHA256']:
        raise ValueError('Certificate DER checksum mismatch')
    # Verify with this explicit certificate, ignoring any embedded CMS certs.
    verified = subprocess.run(['openssl', 'cms', '-verify', '-binary', '-inform', 'DER',
        '-in', str(signature_file), '-content', str(module), '-noverify', '-nointern',
        '-certfile', str(certificate), '-out', '/dev/null'], capture_output=True)
    if verified.returncode:
        raise ValueError('Detached CMS signature does not verify for this payload')
    trailer = bytes([0, 0, 2, 0, 0, 0, 0, 0]) + len(signature).to_bytes(4, 'big')
    expected = digest(payload + signature + trailer + MAGIC)
    if expected != entry['signed_module_SHA256']:
        raise ValueError('Expected signed module checksum mismatch')
    subprocess.run([str(sign_file), '-s', str(signature_file), 'sha512',
                    str(certificate_der), str(module)], check=True)
    if digest(module.read_bytes()) != expected:
        raise ValueError('Kernel sign-file attachment produced unexpected bytes')
    return expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--module', type=Path, required=True)
    parser.add_argument('--sign-file', type=Path, required=True)
    args = parser.parse_args()
    attach(args.module, args.manifest, args.sign_file)


if __name__ == '__main__':
    main()
