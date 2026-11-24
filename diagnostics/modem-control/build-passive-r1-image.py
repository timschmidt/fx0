#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reassemble the exact prepared passive-r1 image from locked public materials."""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import stat
import sys

ROOT = Path(__file__).resolve().parents[2]
LOCK = ROOT / 'manifests/passive-r1-image.json'
EXPECTED = '428779913614a376bd40844bf80b10d004de0571d721b1bb29b85b68f31d4f53'
COMMAND = ('console=ttyMSM0,115200 earlycon rdinit=/init loglevel=8 ignore_loglevel '
           'panic=60 reboot=w lk2nd.pass-ramoops=zap console=tty0 '
           'lk2nd.pass-simplefb=autorefresh module.sig_enforce=1 '
           'fx0.native_trial=r1-rmtfs-passive-01')
MATERIALS = {
    'kernel.zImage', 'baseline.dtb', 'passive.dtb', 'qrtr.ko', 'busybox',
    'native-return', 'qrtr-local-rmtfs', 'rmtfs', 'ld-musl-armhf.so.1',
    'libqrtr.so.1.2', 'libudev.so.1.6.3', 'qrtr.COPYING', 'rmtfs.COPYING',
}
SOURCES = {
    'diagnostics/modem-control/rmtfs-passive-r1.sh',
    'diagnostics/modem-control/rmtfs-passive-r1-init-v2.sh',
    'scripts/make_diagnostic_image.py',
    'diagnostics/modem-control/verify-rmtfs-description.py',
    'diagnostics/modem-control/verify-description.py',
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def locked_file(path, metadata):
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode) and info.st_uid == os.getuid(),
            'Expected an owned regular input')
    require(not info.st_mode & 0o022, 'Input is writable by another account')
    require(info.st_size == metadata['bytes'], 'Input size differs from lock')
    data = path.read_bytes()
    require(sha(data) == metadata['SHA256'], 'Input digest differs from lock')
    return data


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def assemble(materials):
    require(not sys.flags.optimize, 'Optimized Python is forbidden')
    profile = json.loads(LOCK.read_text())
    require(profile['format'] == 1 and profile['image_SHA256'] == EXPECTED,
            'Unexpected image profile')
    require(set(profile['materials']) == MATERIALS, 'Unexpected material roster')
    require(set(profile['source_files_SHA256']) == SOURCES, 'Unexpected source roster')
    require(stat.S_ISDIR(materials.lstat().st_mode), 'Materials must be a real directory')
    require({p.name for p in materials.iterdir()} == MATERIALS, 'Material directory roster differs')
    data = {name: locked_file(materials / name, metadata)
            for name, metadata in profile['materials'].items()}
    source = {}
    for name, digest in profile['source_files_SHA256'].items():
        path = ROOT / name
        source[name] = locked_file(path, {'SHA256': digest, 'bytes': path.lstat().st_size})
    builder = load('passive_r1_container', ROOT / 'scripts/make_diagnostic_image.py')
    dt = load('passive_r1_dt', ROOT / 'diagnostics/modem-control/verify-rmtfs-description.py')
    dt.check(materials / 'passive.dtb')
    old, new = dt.properties(materials / 'baseline.dtb'), dt.properties(materials / 'passive.dtb')
    changed = {('/reserved-memory/reserved@fb00000', 'reg')} | {
        ('/reserved-memory/rmtfs@fd80000', name)
        for name in ('compatible', 'reg', 'no-map', 'qcom,client-id')}
    require({key for key in old.keys() | new.keys() if old.get(key) != new.get(key)} == changed,
            'DT changes exceed the five reviewed RFSA properties')
    entries = {name: (stat.S_IFDIR | 0o755, b'') for name in (
        'bin', 'dev', 'proc', 'sys', 'tmp', 'etc', 'modules', 'usr', 'usr/bin',
        'usr/lib', 'usr/share', 'usr/share/licenses', 'usr/share/licenses/qrtr',
        'usr/share/licenses/rmtfs')}
    for name, target in {
        'lib': 'usr/lib', 'bin/sh': 'busybox',
        'usr/lib/libc.musl-armv7.so.1': 'ld-musl-armhf.so.1',
        'usr/lib/libqrtr.so.1': 'libqrtr.so.1.2',
        'usr/lib/libudev.so.1': 'libudev.so.1.6.3',
    }.items():
        entries[name] = (stat.S_IFLNK | 0o777, target.encode())
    for name, material in {
        'bin/busybox': 'busybox', 'bin/fx0-native-return': 'native-return',
        'bin/qrtr-local-rmtfs': 'qrtr-local-rmtfs', 'usr/bin/rmtfs': 'rmtfs',
        'usr/lib/ld-musl-armhf.so.1': 'ld-musl-armhf.so.1',
        'usr/lib/libqrtr.so.1.2': 'libqrtr.so.1.2',
        'usr/lib/libudev.so.1.6.3': 'libudev.so.1.6.3',
    }.items():
        entries[name] = (stat.S_IFREG | 0o755, data[material])
    entries['init'] = (stat.S_IFREG | 0o755,
                       source['diagnostics/modem-control/rmtfs-passive-r1-init-v2.sh'])
    entries['bin/rmtfs-passive'] = (stat.S_IFREG | 0o755,
                                   source['diagnostics/modem-control/rmtfs-passive-r1.sh'])
    entries['modules/qrtr.ko'] = (stat.S_IFREG | 0o600, data['qrtr.ko'])
    for project in ('qrtr', 'rmtfs'):
        entries[f'usr/share/licenses/{project}/COPYING'] = (
            stat.S_IFREG | 0o644, data[project + '.COPYING'])
    entries['etc/fx0-rmtfs-trial'] = (stat.S_IFREG | 0o644, b'native-r1-passive-rmtfs-01\n')
    entries['etc/fx0-rmtfs-notes.sha256'] = (
        stat.S_IFREG | 0o644, (profile['kernel_notes_SHA256'] + '\n').encode())
    guards = {'sys/firmware/devicetree/base' + node + '/' + prop: new[node, prop]
              for node, prop in changed | {('/soc/remoteproc@fc880000', 'status')}}
    guards.update({name: body for name, (mode, body) in entries.items() if stat.S_ISREG(mode)})
    entries['etc/fx0-rmtfs-inputs.sha256'] = (stat.S_IFREG | 0o644,
        ''.join(sha(body) + '  ' + name + '\n' for name, body in sorted(guards.items())).encode())
    require(len(entries) == 34, 'Unexpected initramfs roster')
    cpio = builder.archive([(name, mode, body) for name, (mode, body) in sorted(entries.items())])
    packed = gzip.compress(cpio, compresslevel=9, mtime=0)
    image = builder.make_image(data['kernel.zImage'], data['passive.dtb'], packed, COMMAND)
    require(sha(cpio) == profile['CPIO_SHA256'], 'Canonical CPIO differs')
    require(sha(packed) == profile['ramdisk_SHA256'], 'Compressed ramdisk differs')
    require(sha(image) == EXPECTED and len(image) == profile['image_bytes'], 'Final image differs')
    return image, cpio, {'image_SHA256': sha(image), 'image_bytes': len(image),
                        'CPIO_SHA256': sha(cpio), 'ramdisk_SHA256': sha(packed),
                        'entries': len(entries), 'materials': len(data),
                        'phone_access': False, 'physical_qualification': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--materials', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    image, cpio, report = assemble(args.materials)
    # Validate everything before creating a fresh private output workspace.
    args.output_dir.mkdir(mode=0o700, exist_ok=False)
    for name, body in [('fx0-r1-rmtfs-passive.img', image), ('initramfs.cpio', cpio),
                       ('build-result.json', (json.dumps(report, indent=2) + '\n').encode())]:
        fd = os.open(args.output_dir / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as stream:
            stream.write(body)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
