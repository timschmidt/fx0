#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Extract and authenticate only the standalone QRTR core from the retained r50 backup."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import tarfile
import tempfile

from importlib.util import module_from_spec, spec_from_file_location

ROOT = Path(__file__).resolve().parents[2]
PREFIX = 'usr/lib/modules/6.18.59-fx0-dmp/'
QRTR = 'kernel/net/qrtr/qrtr.ko.zst'
R50_BACKUP_SHA = 'abbaed40f197afa6fd49d0eead6f68b62479ae7e7422faffb500032ea18ac5cb'


def load(name, path):
    spec = spec_from_file_location(name, path)
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def extract(backup, output):
    with backup.open('rb') as file:
        assert hashlib.file_digest(file, 'sha256').hexdigest() == R50_BACKUP_SHA
    with tarfile.open(backup) as archive:
        dependencies = archive.extractfile(PREFIX + 'modules.dep').read().decode().splitlines()
        assert [line for line in dependencies if line.startswith(QRTR + ':')] == [QRTR + ':']
        member = archive.getmember(PREFIX + QRTR)
        assert member.isfile()
        compressed = archive.extractfile(member).read()
    path = output / 'qrtr.ko.zst'
    path.write_bytes(compressed)
    return path, sha(compressed)


def verify(qrtr, retained, output):
    family = load('native_family', ROOT / 'diagnostics/modem-control/verify-native-family.py')
    verifier = load('module_verifier', ROOT / 'scripts/verify_kernel_modules.py')
    metadata = json.loads((retained / 'native-family-verification.json').read_text())
    pinned = json.loads((retained / 'retained-inputs.json').read_text())
    assert pinned['archive_sha256'] == R50_BACKUP_SHA
    assert metadata['certificate_is_entire_exact_kernel_trust_list']
    image = (retained / 'native-Image').read_bytes()
    assert sha(image) == metadata['runtime_Image_sha256'] == '7f355ca46d02521e939d8dffb8c180058b254c2aa87fc4199233c1d151e1b2d6'
    files = retained / 'retained-r50/boot'
    config = (files / 'config').read_bytes()
    symbol_map = (files / 'System.map').read_bytes()
    assert sha(config) == pinned['files']['boot/config']['sha256']
    assert sha(symbol_map) == pinned['files']['boot/System.map']['sha256']
    assert all(option in config.splitlines() for option in
               [b'CONFIG_QRTR=m', b'CONFIG_QRTR_SMD=m', b'CONFIG_QCOM_RMTFS_MEM=y',
                b'CONFIG_MODVERSIONS=y', b'CONFIG_MODULE_SIG=y'])
    symbols = {row.split()[2]: int(row.split()[0], 16)
               for row in symbol_map.decode().splitlines() if len(row.split()) == 3}
    start = symbols['_text']
    certificate = image[symbols['__cert_list_start'] - start:symbols['__cert_list_end'] - start]
    assert certificate == (retained / 'native-kernel-certificate.der').read_bytes()
    assert len(certificate) == struct.unpack_from('<I', image, symbols['system_certificate_list_size'] - start)[0]
    assert sha(certificate) == '0f5e9ed13fb5e85bca920e4900226a7786b05619f20b6791b29618df34fec98a'
    notes = image[symbols['__start_notes'] - start:symbols['__stop_notes'] - start]
    assert sha(notes) == 'cb8ff4d80009dbd0b4542ce5d28d7ce10e4d84e0db4e332c749ff8ae18a08269'
    exports = family.kernel_exports(image, symbols)
    assert len(exports) == metadata['kernel_exports_checked_against_System_map'] == 11709

    raw = verifier.run(['zstd', '-q', '-d', '-c', qrtr])
    payload, signature = verifier.split_module(raw)
    imports, provided = family.module_versions(payload)
    family.check_imports(imports, exports)
    wrong = dict(imports)
    wrong['module_layout'] ^= 1
    try:
        family.check_imports(wrong, exports)
    except ValueError:
        pass
    else:
        raise AssertionError('Wrong module_layout accepted')
    with tempfile.TemporaryDirectory(dir=output) as directory:
        scratch = Path(directory)
        pem = scratch / 'r50.pem'
        pem.write_bytes(verifier.run(['openssl', 'x509', '-inform', 'DER', '-in',
                                     retained / 'native-kernel-certificate.der', '-outform', 'PEM']))
        assert verifier.check_cms(payload, signature, pem, scratch)
        changed = bytearray(payload)
        changed[len(changed) // 2] ^= 1
        assert not verifier.check_cms(bytes(changed), signature, pem, scratch)
    module = output / 'qrtr.ko'
    module.write_bytes(raw)
    vermagic = verifier.run(['modinfo', '-F', 'vermagic', module]).decode().strip()
    assert vermagic.split()[0] == '6.18.59-fx0-dmp'
    assert verifier.run(['modinfo', '-F', 'depends', module]).strip() == b''
    assert verifier.run(['modinfo', '-F', 'name', module]).strip() == b'qrtr'
    return {'sha256': sha(raw), 'bytes': len(raw), 'vermagic': vermagic,
            'imports_verified': len(imports), 'exports': len(provided),
            'exact_r50_kernel_certificate_CMS': True, 'changed_payload_rejected': True,
            'changed_module_layout_rejected': True, 'kernel_exports_checked': len(exports),
            'kernel_notes_sha256': sha(notes), 'depends': [], 'QRTR_transport_modules': []}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['backup', 'retained', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    module, compressed_hash = extract(args.backup, output)
    result = verify(module, args.retained.resolve(), output)
    result['compressed_sha256'] = compressed_hash
    result['archive_sha256'] = R50_BACKUP_SHA
    (output / 'qrtr-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
