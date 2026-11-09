#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify retained r50 kernel/module inputs without loading code or reading a phone."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import re
import struct
import subprocess
import tempfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def elf_sections(payload):
    assert payload[:6] == b'\x7fELF\x01\x01'
    offset = struct.unpack_from('<I', payload, 32)[0]
    size, count, strings = struct.unpack_from('<HHH', payload, 46)
    assert size == 40 and offset + count * size <= len(payload)
    sections = [struct.unpack_from('<10I', payload, offset + index * size) for index in range(count)]
    names = payload[sections[strings][4]:sum(sections[strings][4:6])]
    return sections, {names[s[0]:].split(b'\0', 1)[0].decode(): s for s in sections}


def module_versions(payload):
    sections, by_name = elf_sections(payload)
    section = by_name['__versions']
    data = payload[section[4]:sum(section[4:6])]
    assert data and len(data) % 64 == 0
    imports = {}
    for offset in range(0, len(data), 64):
        name = data[offset + 4:offset + 64].split(b'\0', 1)[0].decode()
        assert name and name not in imports
        imports[name] = struct.unpack_from('<I', data, offset)[0]
    assert 'module_layout' in imports
    exports = {}
    for section in sections:
        if section[1] != 2:
            continue
        strings = sections[section[6]]
        names = payload[strings[4]:sum(strings[4:6])]
        assert section[9] == 16
        for offset in range(section[4], sum(section[4:6]), 16):
            name, value, _, _, _, index = struct.unpack_from('<IIIBBH', payload, offset)
            name = names[name:].split(b'\0', 1)[0].decode()
            if not name.startswith('__crc_'):
                continue
            assert 0 < index < len(sections)
            target = sections[index]
            assert value + 4 <= target[5]
            exports[name[6:]] = struct.unpack_from('<I', payload, target[4] + value)[0]
    return imports, exports


def check_imports(imports, exports):
    for name, crc in imports.items():
        if exports.get(name) != crc:
            raise ValueError('Missing or mismatched imported CRC: ' + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    args = parser.parse_args()
    base = args.inputs.resolve()
    assert not (base / 'native-family-verification.json').exists()
    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location('module_verifier', root / 'scripts/verify_kernel_modules.py')
    verifier = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(verifier)
    retained = json.loads((base / 'retained-inputs.json').read_text())
    inputs = base / 'retained-r50'
    for name, info in retained['files'].items():
        assert sha((inputs / name).read_bytes()) == info['sha256'], name
    kernel = (inputs / 'boot/vmlinuz').read_bytes()
    assert sha(kernel) == '7e896bb7c3fc80d7d8c8306a659fa57c1bcb3924ec2aaf37b77924e23c274417'
    config = (inputs / 'boot/config').read_text()
    for required in ['CONFIG_KERNEL_XZ=y', 'CONFIG_MODVERSIONS=y', 'CONFIG_BASIC_MODVERSIONS=y',
                     '# CONFIG_FW_LOADER_USER_HELPER is not set', '# CONFIG_QCOM_SYSMON is not set']:
        assert required + '\n' in config
    assert 'CONFIG_HAVE_ARCH_PREL32_RELOCATIONS=y\n' not in config and 'CONFIG_64BIT=y\n' not in config
    symbols = {row.split()[2]: int(row.split()[0], 16) for row in
               (inputs / 'boot/System.map').read_text().splitlines() if len(row.split()) == 3}
    start = symbols['_text']
    candidates = []
    for match in re.finditer(re.escape(b'\xfd7zXZ\0'), kernel):
        try:
            decoder = lzma.LZMADecompressor()
            image = decoder.decompress(kernel[match.start():])
        except lzma.LZMAError:
            continue
        if decoder.eof and len(image) == symbols['_edata'] - start:
            candidates.append(image)
    assert len(candidates) == 1
    image = candidates[0]
    banner = image[symbols['linux_banner'] - start:].split(b'\0', 1)[0]
    assert banner.startswith(b'Linux version 6.18.59-fx0-dmp ')
    certificate = image[symbols['__cert_list_start'] - start:symbols['__cert_list_end'] - start]
    assert len(certificate) == struct.unpack_from('<I', image, symbols['system_certificate_list_size'] - start)[0] == 1324
    assert sha(certificate) == '0f5e9ed13fb5e85bca920e4900226a7786b05619f20b6791b29618df34fec98a'
    for name, data in [('native-Image', image), ('native-kernel-certificate.der', certificate),
                       ('native-kernel-notes', image[symbols['__start_notes'] - start:symbols['__stop_notes'] - start])]:
        path = base / name
        if path.exists():
            assert path.read_bytes() == data
        else:
            path.write_bytes(data)
    exports = {}
    for suffix in ['', '_gpl']:
        table, end = symbols['__start___ksymtab' + suffix], symbols['__stop___ksymtab' + suffix]
        crcs, crcs_end = symbols['__start___kcrctab' + suffix], symbols['__stop___kcrctab' + suffix]
        assert (end - table) % 12 == 0 and (end - table) // 12 == (crcs_end - crcs) // 4
        for index in range((end - table) // 12):
            address = table + index * 12
            name_pointer = struct.unpack_from('<I', image, address - start + 4)[0] - start
            assert 0 <= name_pointer < len(image)
            name = image[name_pointer:].split(b'\0', 1)[0].decode()
            assert re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name) and name not in exports
            assert symbols['__ksymtab_' + name] == address
            exports[name] = struct.unpack_from('<I', image, crcs - start + index * 4)[0]
    kernel_exports_count = len(exports)
    modules = base / 'modules'
    modules.mkdir(exist_ok=False)
    report = {}
    with tempfile.TemporaryDirectory(dir=base) as directory:
        scratch = Path(directory)
        pem = scratch / 'kernel.pem'
        pem.write_bytes(verifier.run(['openssl', 'x509', '-inform', 'DER', '-in',
                                     base / 'native-kernel-certificate.der', '-outform', 'PEM']))
        for name in retained['dependency_order']:
            compressed = inputs / 'usr/lib/modules/6.18.59-fx0-dmp' / name
            raw = verifier.run(['zstd', '-q', '-d', '-c', compressed])
            payload, signature = verifier.split_module(raw)
            assert verifier.check_cms(payload, signature, pem, scratch), name
            imports, provided = module_versions(payload)
            check_imports(imports, exports)
            bad = dict(imports)
            bad['module_layout'] ^= 1
            try:
                check_imports(bad, exports)
            except ValueError:
                pass
            else:
                raise AssertionError('Corrupt CRC control accepted')
            corrupt = bytearray(payload)
            corrupt[len(corrupt) // 2] ^= 1
            assert not verifier.check_cms(bytes(corrupt), signature, pem, scratch)
            corrupt = bytearray(signature)
            corrupt[-1] ^= 1
            assert not verifier.check_cms(payload, bytes(corrupt), pem, scratch)
            exports.update(provided)
            path = modules / Path(name).name.removesuffix('.zst')
            path.write_bytes(raw)
            vermagic = verifier.run(['modinfo', '-F', 'vermagic', path]).decode().strip()
            assert vermagic.split()[0] == '6.18.59-fx0-dmp'
            report[path.name] = {'sha256': sha(raw), 'bytes': len(raw), 'imported_CRCs_checked': len(imports),
                                 'provided_exports': len(provided), 'vermagic': vermagic,
                                 'CMS_checked_with_exact_kernel_certificate': True,
                                 'depends': verifier.run(['modinfo', '-F', 'depends', path]).decode().strip().split(',')}
    result = {'verified_UTC': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'kernel_sha256': sha(kernel), 'runtime_Image_sha256': sha(image),
              'certificate_sha256': sha(certificate), 'certificate_is_entire_exact_kernel_trust_list': True,
              'linked_notes_sha256': sha((base / 'native-kernel-notes').read_bytes()),
              'kernel_exports_checked_against_System_map': kernel_exports_count,
              'kernel_and_BSS_plus_load_offset_below_ramdisk': symbols['_end'] - start + 0x8000 < 0x02000000,
              'modules': report, 'module_count': len(report),
              'all_imported_CRCs_match_actual_kernel_or_earlier_signed_module': True,
              'imported_CRC_checks': sum(row['imported_CRCs_checked'] for row in report.values()),
              'controls': ['modified payload rejected for each module', 'modified CMS rejected for each module',
                           'modified module_layout CRC rejected for each module'],
              'proprietary_firmware_or_private_key_bytes_read': False,
              'no_module_loading_or_phone_access': True}
    assert len(report) == 5 and result['kernel_and_BSS_plus_load_offset_below_ramdisk']
    (base / 'native-family-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
