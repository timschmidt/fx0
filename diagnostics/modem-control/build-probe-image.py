#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assemble a host-only, timer-return r50 offline-probe image from verified inputs."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import struct


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(data):
    return hashlib.sha256(data).hexdigest()


def cpio_entries(raw):
    entries, offset = [], 0
    while True:
        header = raw[offset:offset + 110]
        assert header[:6] == b'070701'
        size, namesize = int(header[54:62], 16), int(header[94:102], 16)
        name = raw[offset + 110:offset + 110 + namesize - 1].decode()
        start = (offset + 110 + namesize + 3) & ~3
        if name == 'TRAILER!!!':
            break
        entries.append((name, int(header[14:22], 16), raw[start:start + size]))
        offset = (start + size + 3) & ~3
    assert len({name for name, _, _ in entries}) == len(entries)
    return entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', required=True, type=Path)
    parser.add_argument('--probe-dtb', required=True, type=Path)
    parser.add_argument('--qualified-image', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    base = args.inputs.resolve()
    family = json.loads((base / 'native-family-verification.json').read_text())
    assert family['module_count'] == 5 and family['imported_CRC_checks'] == 197
    assert family['certificate_is_entire_exact_kernel_trust_list']
    assert family['kernel_and_BSS_plus_load_offset_below_ramdisk']
    kernel = (base / 'retained-r50/boot/vmlinuz').read_bytes()
    assert sha(kernel) == family['kernel_sha256']
    image = args.qualified_image.read_bytes()
    assert sha(image) == '349ab28ce8d8c48a9699d67e9b84ed53e9038baeac896f3a8fd923c96b1d853b'
    old_kernel, _, ramdisk_size, _, _, _, _, page, _, _ = struct.unpack_from('<10I', image, 8)
    offset = page + ((old_kernel + page - 1) // page) * page
    entries = cpio_entries(gzip.decompress(image[offset:offset + ramdisk_size]))
    assert len(entries) == 10
    original = {name: (mode, data) for name, mode, data in entries}
    assert b'(sleep 180;' in original['init'][1]
    assert sha(original['bin/busybox'][1]) == '2b6c948da829c4eb46084f947316d7439607fff47eb8687c45330adb273c4540'
    fdt = load_module('modem_fdt', root / 'diagnostics/modem-control/verify-description.py').Fdt(args.probe_dtb)
    node = '/soc/remoteproc@fc880000'
    s5 = fdt.supply(node, 'mss-supply')
    assert fdt.strings(node, 'compatible') == ['qcom,msm8926-mss-pil']
    assert fdt.strings(node, 'status') == fdt.strings(s5, 'status') == ['okay']
    assert fdt.strings(node + '/bam-dmux', 'status') == ['disabled']
    assert fdt.prop(node, 'qcom,ext-bhs-reg') is None
    assert fdt.cells(s5, 'regulator-min-microvolt') == fdt.cells(s5, 'regulator-max-microvolt') == [1150000]
    properties = [(node, key) for key in ['compatible', 'status', 'memory-region', 'mx-supply',
                                         'pll-supply', 'mss-supply', 'reg', 'clocks', 'interrupts-extended']]
    properties += [(s5, key) for key in ['regulator-min-microvolt', 'regulator-max-microvolt', 'status']]
    properties += [(node + '/bam-dmux', 'status')]
    properties += [(fdt.resolve(phandle), key) for phandle in fdt.cells(node, 'memory-region') for key in ['reg', 'no-map']]
    dt_manifest = ''
    for path, key in properties:
        data = fdt.prop(path, key)
        assert data is not None
        dt_manifest += sha(data) + '  sys/firmware/devicetree/base' + path + '/' + key + '\n'
    modules_manifest = ''
    entries += [('etc', stat.S_IFDIR | 0o755, b''), ('modules', stat.S_IFDIR | 0o755, b'')]
    for name, info in family['modules'].items():
        data = (base / 'modules' / name).read_bytes()
        assert sha(data) == info['sha256']
        entries.append(('modules/' + name, stat.S_IFREG | 0o600, data))
        modules_manifest += sha(data) + '  modules/' + name + '\n'
    additions = {'etc/fx0-modem-trial': b'native-r50-offline-probe\n',
                 'etc/fx0-modem-native-boot-id': b'c3ac8f04-888e-493c-bb5d-a1729a275f7d\n',
                 'etc/fx0-modem-notes.sha256': (family['linked_notes_sha256'] + '\n').encode(),
                 'etc/fx0-modem-modules.sha256': modules_manifest.encode(),
                 'etc/fx0-modem-DT.sha256': dt_manifest.encode(),
                 'bin/modem-probe': (root / 'diagnostics/modem-control/probe-only.sh').read_bytes()}
    entries += [(name, stat.S_IFREG | (0o755 if name.startswith('bin/') else 0o644), data)
                for name, data in additions.items()]
    assert len(entries) == 23 and len({name for name, _, _ in entries}) == 23
    assert all((mode, data) == original[name] for name, mode, data in entries if name in original)
    assert not any('firmware' in name or 'cpufreq' in name for name, _, _ in entries)
    builder = load_module('diagnostic_builder', root / 'scripts/make_diagnostic_image.py')
    cmdline = image[64:576].split(b'\0', 1)[0].decode() + ' cpufreq.default_governor=schedutil module.sig_enforce=1'
    packed = gzip.compress(builder.archive(entries), compresslevel=1, mtime=0)
    output = builder.make_image(kernel, args.probe_dtb.read_bytes(), packed, cmdline)
    with args.output.open('xb') as stream:
        stream.write(output)
    result = {'image_path': str(args.output), 'image_sha256': sha(output), 'image_bytes': len(output),
              'kernel_sha256': sha(kernel), 'kernel_encoding_unchanged': True,
              'probe_DTB_sha256': sha(args.probe_dtb.read_bytes()), 'cmdline': cmdline,
              'CPIO_entries': 23, 'all_ten_qualified_base_payloads_and_modes_unchanged': True,
              'timer_seconds': 180, 'initially_moduleless': True,
              'module_count': 5, 'firmware_files': 0, 'loader_services': 0,
              'CPU_frequency_requests': [], 'remoteproc_state_writes': [],
              'worker_sha256': sha(additions['bin/modem-probe']),
              'DT_guard_properties': len(properties),
              'entries_sha256': {name: sha(data) for name, _, data in entries},
              'physical_entry': False, 'modem_firmware_started': False}
    args.output.with_suffix('.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'entries_sha256'}, indent=2))


if __name__ == '__main__':
    main()
