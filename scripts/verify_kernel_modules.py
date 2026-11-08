#!/usr/bin/env python3
"""Verify every staged ARM module against an explicit kernel certificate.

Checks count, ELF architecture, release and detached CMS signatures. Uses only
local files; never loads modules or accesses a device. Requires openssl, modinfo
and zstd (for .ko.zst). Set TMPDIR to suitable private workspace scratch.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

MAGIC = b'~Module signature appended~\n'


def run(argv):
    result = subprocess.run([str(arg) for arg in argv], capture_output=True)
    if result.returncode:
        raise RuntimeError(f'{argv[0]} failed: {result.stderr.decode(errors="replace")}')
    return result.stdout


def split_module(data):
    if not data.endswith(MAGIC) or len(data) < len(MAGIC)+12:
        raise ValueError('Missing module signature trailer')
    end = len(data)-len(MAGIC)
    info = data[end-12:end]
    # Modern sign-file uses PKCS#7 and no legacy signer/key-id strings.
    if info[:8] != bytes([0,0,2,0,0,0,0,0]):
        raise ValueError('Unexpected module signature format')
    size = int.from_bytes(info[8:], 'big')
    start = end-12-size
    if not size or start < 20:
        raise ValueError('Invalid signature length')
    payload, signature = data[:start], data[start:end-12]
    if payload[:6] != b'\x7fELF\x01\x01' or int.from_bytes(payload[18:20],'little') != 40:
        raise ValueError('Module is not a little-endian ELF32 ARM object')
    return payload, signature


def check_cms(payload, signature, certificate, scratch):
    content, cms = scratch/'content.ko', scratch/'signature.der'
    content.write_bytes(payload)
    cms.write_bytes(signature)
    result = subprocess.run(['openssl','cms','-verify','-binary','-inform','DER',
                             '-in',str(cms),'-content',str(content),'-noverify',
                             '-nointern','-certfile',str(certificate),'-out','/dev/null'],
                            capture_output=True)
    return result.returncode == 0


def verify(modules, release, certificate, expected_count):
    modules, certificate = Path(modules).resolve(), Path(certificate).resolve()
    files = sorted(p for p in modules.rglob('*') if p.is_file() and
                   (p.name.endswith('.ko') or '.ko.' in p.name))
    if expected_count <= 0 or len(files) != expected_count:
        raise ValueError(f'Expected {expected_count} modules, found {len(files)}')
    report = {'release':release,'certificate_sha256':hashlib.sha256(certificate.read_bytes()).hexdigest(),
              'modules':{},'signature_verification':'explicit certificate; CMS embedded certificates ignored',
              'chain_validation':'disabled for the local self-signed development certificate'}
    with tempfile.TemporaryDirectory(prefix='fx0-module-verification-') as temporary:
        scratch = Path(temporary)
        pem = scratch/'certificate.pem'
        run(['openssl','x509','-inform','DER','-in',certificate,'-out',pem])
        for index,path in enumerate(files):
            if path.name.endswith('.ko.zst'):
                data = run(['zstd','-q','-d','-c',path])
            elif path.name.endswith('.ko'):
                data = path.read_bytes()
            else:
                raise ValueError(f'Unsupported module compression: {path.name}')
            payload, signature = split_module(data)
            if not check_cms(payload,signature,pem,scratch):
                raise ValueError(f'Signature verification failed: {path}')
            vermagic = run(['modinfo','-F','vermagic',path]).decode().strip()
            if not vermagic or vermagic.split()[0] != release:
                raise ValueError(f'Unexpected module release: {path}: {vermagic}')
            if index == 0:
                corrupt = bytearray(payload)
                corrupt[len(corrupt)//2] ^= 1
                if check_cms(corrupt,signature,pem,scratch):
                    raise ValueError('Negative control accepted modified module contents')
                corrupt = bytearray(signature)
                corrupt[-1] ^= 1
                if check_cms(payload,corrupt,pem,scratch):
                    raise ValueError('Negative control accepted a modified signature')
            report['modules'][str(path.relative_to(modules))] = {
                'file_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                'signed_payload_sha256':hashlib.sha256(payload).hexdigest(),
            }
    report.update({'verified_modules':len(files),'negative_controls':['modified payload rejected','modified CMS signature rejected']})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--modules',type=Path,required=True)
    parser.add_argument('--release',required=True)
    parser.add_argument('--certificate',type=Path,required=True,help='Kernel build signing_key.x509 (DER)')
    parser.add_argument('--expected-count',type=int,required=True)
    parser.add_argument('--report',type=Path,required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Report already exists; choose a new destination')
    report = verify(args.modules,args.release,args.certificate,args.expected_count)
    args.report.parent.mkdir(parents=True,exist_ok=True)
    args.report.write_text(json.dumps(report,indent=2)+'\n')
    print(f"Verified {report['verified_modules']} signed ARM modules for {args.release}; corruption controls rejected")


if __name__ == '__main__':
    main()
