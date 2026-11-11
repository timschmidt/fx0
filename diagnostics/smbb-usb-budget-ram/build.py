#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Pack a moduleless, timed Fx0 USB budget comparison using one linked kernel."""
import argparse
import difflib
import gzip
import hashlib
import importlib.util
import json
import lzma
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHARGER = '/soc/spmi@fc4cf000/pm8226@0/charger@1000'
USB = '/soc/usb@f9a55000'
CMDLINE = ('console=ttyMSM0,115200 earlycon rdinit=/init loglevel=8 ignore_loglevel '
           'panic=60 reboot=w lk2nd.pass-ramoops=zap')
BOARD_DTB = 'arch/arm/boot/dts/qcom/qcom-msm8926-lg-madai.dtb'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def static_arm(data):
    assert data[:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H', data, 18)[0] == 40
    phoff = struct.unpack_from('<I', data, 28)[0]
    phentsize, phnum = struct.unpack_from('<HH', data, 42)
    for i in range(phnum):
        kind, offset, _vaddr, _paddr, size = struct.unpack_from('<5I', data, phoff + i * phentsize)
        assert kind != 3
        if kind == 2:
            assert offset + size <= len(data) and size % 8 == 0
            tags = [entry[0] for entry in struct.iter_unpack('<iI', data[offset:offset + size])]
            assert 0 in tags and 1 not in tags[:tags.index(0)]


def checked_text(*command):
    return subprocess.check_output(command, text=True).strip()


def dt_properties(dtb, node):
    return checked_text('fdtget', '-p', dtb, node).splitlines()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['kernel-build', 'control-dtb', 'busybox', 'reader', 'output']:
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    build = args.kernel_build.resolve()
    config = (build / '.config').read_text().splitlines()
    assert '# CONFIG_MODULES is not set' in config
    for name in ['CHARGER_QCOM_SMBB', 'CHARGER_QCOM_SMBB_POLICY', 'USB_CONFIGFS_NCM', 'DEBUG_FS',
                 'USB_CHIPIDEA_UDC', 'USB_CHIPIDEA_MSM', 'PHY_QCOM_USB_HS', 'PSTORE_RAM', 'PSTORE_CONSOLE']:
        assert 'CONFIG_' + name + '=y' in config, name

    kernel = (build / 'arch/arm/boot/zImage').read_bytes()
    runtime = (build / 'arch/arm/boot/Image').read_bytes()
    piggy = (build / 'arch/arm/boot/compressed/piggy_data').read_bytes()
    assert kernel.count(piggy) == 1 and int.from_bytes(piggy[-4:], 'little') == len(runtime)
    assert lzma.decompress(piggy[:-4]) == runtime
    symbols = {}
    for line in (build / 'System.map').read_text().splitlines():
        address, _symbol_type, name = line.split(maxsplit=2)
        if name in {'_text', '_end'}:
            symbols[name] = int(address, 16)
    footprint = symbols['_end'] - symbols['_text']
    assert len(runtime) <= footprint and footprint + 0x8000 < 0x02000000
    elf_notes = checked_text('readelf', '-n', build / 'vmlinux')
    build_id = re.search(r'Build ID: ([0-9a-f]+)', elf_notes).group(1)
    elf_sections = checked_text('readelf', '-SW', build / 'vmlinux')
    note_section = re.search(r'\]\s+\.notes\s+\S+\s+\S+\s+([0-9a-f]+)\s+([0-9a-f]+)', elf_sections)
    note_offset, note_size = [int(field, 16) for field in note_section.groups()]
    with (build / 'vmlinux').open('rb') as file:
        file.seek(note_offset)
        notes = file.read(note_size)
    assert len(notes) == note_size and bytes.fromhex(build_id) in notes

    reader = args.reader.read_bytes()
    busybox = args.busybox.read_bytes()
    static_arm(reader)
    static_arm(busybox)
    spec = importlib.util.spec_from_file_location('diagnostic', ROOT / 'scripts/make_diagnostic_image.py')
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    entries = [(name, stat.S_IFDIR | 0o755, b'') for name in ('bin', 'dev', 'proc', 'sys', 'tmp', 'www')]
    entries += [('bin/sh', stat.S_IFLNK | 0o777, b'busybox')]
    entries += [(name, stat.S_IFREG | 0o755, data) for name, data in [
        ('bin/busybox', busybox),
        ('bin/usb-budget-registers', reader),
        ('bin/usb-budget-sample', (HERE / 'sample').read_bytes()),
        ('bin/serve-http', (HERE / 'serve-http').read_bytes()),
        ('init', (HERE / 'init').read_bytes()),
    ]]
    raw_archive = helper.archive(entries)
    ramdisk = gzip.compress(raw_archive, compresslevel=1, mtime=0)
    images = {}
    dts = {}
    for label, source in [('control', args.control_dtb), ('managed', build / BOARD_DTB)]:
        dtb = output / (label + '.dtb')
        shutil.copyfile(source, dtb)
        assert 'charge-policy' in checked_text('fdtget', '-l', dtb, CHARGER).splitlines()
        subprocess.run(['fdtput', '-r', dtb, CHARGER + '/charge-policy'], check=True)
        assert 'charge-policy' not in checked_text('fdtget', '-l', dtb, CHARGER).splitlines()
        charger_properties = dt_properties(dtb, CHARGER)
        assert 'qcom,software-charge-control' in charger_properties
        assert 'qcom,boot-charge-inhibited' not in charger_properties
        assert ('qcom,usb-gadget-current-limit' in charger_properties) == (label == 'managed')
        assert ('power-supplies' in dt_properties(dtb, USB)) == (label == 'managed')
        if label == 'managed':
            assert checked_text('fdtget', '-t', 'x', dtb, USB, 'power-supplies') == checked_text(
                'fdtget', '-t', 'x', dtb, CHARGER, 'phandle')
        assert checked_text('fdtget', '-t', 's', dtb, USB, 'dr_mode') == 'peripheral'
        result = subprocess.run(['dtc', '-I', 'dtb', '-O', 'dts', dtb], capture_output=True, text=True, check=True)
        dts[label] = result.stdout
        (output / (label + '-dtc.log')).write_text(result.stderr)
        image = helper.make_image(kernel, dtb.read_bytes(), ramdisk, CMDLINE)
        assert len(image) < 8 * 1024 * 1024
        name = f'fx0-usb-budget-{label}-ram.img'
        (output / name).write_bytes(image)
        images[label] = {'file': name, 'bytes': len(image), 'sha256': sha(image), 'DTB_sha256': sha(dtb.read_bytes())}

    difference = list(difflib.unified_diff(dts['control'].splitlines(), dts['managed'].splitlines(),
                                           fromfile='control', tofile='managed', n=2))
    (output / 'dtb.diff').write_text('\n'.join(difference) + '\n')
    added = [line[1:].strip() for line in difference[2:] if line.startswith('+')]
    removed = [line[1:].strip() for line in difference[2:] if line.startswith('-')]
    assert len(added) == 2 and any(line.startswith('power-supplies = ') for line in added)
    assert 'qcom,usb-gadget-current-limit;' in added and not removed
    record = {'images': images, 'kernel_bytes': len(kernel), 'kernel_sha256': sha(kernel),
              'runtime_Image_sha256': sha(runtime), 'runtime_Image_bytes': len(runtime),
              'kernel_GNU_build_id': build_id, 'kernel_notes_sha256': sha(notes),
              'kernel_text_to_end_bytes_including_BSS': footprint,
              'kernel_release': (build / 'include/config/kernel.release').read_text().strip(),
              'piggy_sha256': sha(piggy), 'ramdisk_sha256': sha(ramdisk),
              'ramdisk_bytes': len(ramdisk), 'raw_ramdisk_sha256': sha(raw_archive),
              'entries_sha256': {name: sha(data) for name, _mode, data in entries},
              'semantic_DTB_additions': added, 'semantic_DTB_removals': removed,
              'common_DTB_removed_policy_child': True, 'software_charge_inhibit_retained': True,
              'module_support_disabled': True, 'independent_return_timer_seconds': 180,
              'command_line': CMDLINE, 'staged_or_booted': False, 'phone_commands': 0}
    (output / 'images.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps({'images': images, 'kernel_release': record['kernel_release'], 'kernel_build_id': build_id}))


if __name__ == '__main__':
    main()
