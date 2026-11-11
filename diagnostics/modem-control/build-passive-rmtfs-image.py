#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pack the verified, passive RMTFS diagnostic without accessing a device."""
import argparse
import gzip
import importlib.util
import json
from pathlib import Path
import stat
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KERNEL_BYTES = 5_558_784
BASE_IMAGE_SHA = '349ab28ce8d8c48a9699d67e9b84ed53e9038baeac896f3a8fd923c96b1d853b'
BASE_KERNEL_SHA = '32610058b1d03c1e16df671be169ded43aae7b2f46224d3bea82f3c5751c5416'
KERNEL_SHA = '7e896bb7c3fc80d7d8c8306a659fa57c1bcb3924ec2aaf37b77924e23c274417'
NOTES_SHA = 'cb8ff4d80009dbd0b4542ce5d28d7ce10e4d84e0db4e332c749ff8ae18a08269'
BASE_DTB_SHA = '1658cb8cee4e8800c6163f76b5153f2a50eeae8bfbfcfbe2dd818ff3d3a87eda'
RMTFS_DTB_SHA = '674788b21487182bfca96a9d3d280b538e5717fd92d002843fe382216e573385'
RMTFS_SHA = '281b6d358ff6ddc44523821d79876e362024eaf5168dce796760ce976336cfae'
QRTR_SHA = 'ee922e99e1be948af029926dc7ec3acf4b21db6b46f7fc4e8d25cff8043b3329'
RMTFS_NODE = '/reserved-memory/rmtfs@fd80000'
MSS_NODE = '/soc/remoteproc@fc880000'
CHANGED = {('/reserved-memory/reserved@fb00000', 'reg')} | {
    (RMTFS_NODE, key) for key in ('compatible', 'reg', 'no-map', 'qcom,client-id')
}


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def arm_static(path):
    info = subprocess.check_output(['readelf', '-W', '-h', '-l', '-d', path], text=True)
    assert 'ELF32' in info and 'Machine:                           ARM' in info
    assert 'INTERP' not in info and '(NEEDED)' not in info
    return path.read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('qualified-image', 'native-kernel', 'baseline-dtb', 'rmtfs-dtb', 'rmtfs', 'qrtr', 'observer',
                   'observer-build', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    images = load('image_parser', ROOT / 'diagnostics/smbb-usb-budget-ram/verify-images.py')
    builder = load('image_builder', ROOT / 'scripts/make_diagnostic_image.py')
    desc = load('rmtfs_dtb', HERE / 'verify-rmtfs-description.py')
    sha = images.sha
    base = args.qualified_image.read_bytes()
    assert sha(base) == BASE_IMAGE_SHA
    base_kernel, base_dtb, ramdisk, cmdline = images.unpack_image(base, KERNEL_BYTES)
    assert sha(base_kernel) == BASE_KERNEL_SHA
    kernel = args.native_kernel.read_bytes()
    assert len(kernel) == KERNEL_BYTES and sha(kernel) == KERNEL_SHA
    assert base_dtb == args.baseline_dtb.read_bytes() and sha(base_dtb) == BASE_DTB_SHA
    dtb = args.rmtfs_dtb.read_bytes()
    assert sha(dtb) == RMTFS_DTB_SHA
    desc.check(args.rmtfs_dtb)
    old_dt, new_dt = desc.properties(args.baseline_dtb), desc.properties(args.rmtfs_dtb)
    assert {key for key in old_dt.keys() | new_dt.keys() if old_dt.get(key) != new_dt.get(key)} == CHANGED
    assert new_dt[MSS_NODE, 'status'] == b'disabled\0'

    original = images.unpack_cpio(gzip.decompress(ramdisk))
    assert len(original) == 10
    assert original['init'][1].count(b'(sleep 180;') == 1
    assert b'reboot -f) &' in original['init'][1]
    assert sha(original['bin/busybox'][1]) == '2b6c948da829c4eb46084f947316d7439607fff47eb8687c45330adb273c4540'
    rmtfs = arm_static(args.rmtfs)
    assert sha(rmtfs) == RMTFS_SHA
    qrtr = args.qrtr.read_bytes()
    assert sha(qrtr) == QRTR_SHA
    observer = arm_static(args.observer)
    observer_build = json.loads(args.observer_build.read_text())
    assert observer_build['binary_sha256'] == sha(observer)
    assert observer_build['source_sha256'] == sha((HERE / 'qrtr-local-rmtfs.c').read_bytes())

    worker = (HERE / 'rmtfs-passive.sh').read_bytes()
    guard = {f'sys/firmware/devicetree/base{node}/{key}': new_dt[node, key]
             for node, key in sorted(CHANGED | {(MSS_NODE, 'status')})}
    executables = {'bin/rmtfs': rmtfs, 'bin/qrtr-local-rmtfs': observer, 'bin/rmtfs-passive': worker}
    guard.update(executables)
    guard['modules/qrtr.ko'] = qrtr
    metadata = {'etc/fx0-rmtfs-trial': b'native-r50-passive-rmtfs\n',
                'etc/fx0-rmtfs-notes.sha256': (NOTES_SHA + '\n').encode(),
                'etc/fx0-rmtfs-inputs.sha256': ''.join(f'{sha(data)}  {name}\n'
                                                     for name, data in guard.items()).encode()}
    entries = dict(original)
    entries.update({name: (stat.S_IFDIR | 0o755, b'') for name in ('etc', 'modules')})
    entries.update({name: (stat.S_IFREG | 0o755, data) for name, data in executables.items()})
    entries.update({name: (stat.S_IFREG | 0o644, data) for name, data in metadata.items()})
    entries['modules/qrtr.ko'] = (stat.S_IFREG | 0o600, qrtr)
    assert len(entries) == 19
    cmdline += ' module.sig_enforce=1'
    archive = builder.archive([(name, mode, data) for name, (mode, data) in entries.items()])
    packed = gzip.compress(archive, compresslevel=1, mtime=0)
    image = builder.make_image(kernel, dtb, packed, cmdline)

    # Decode the final image and compare the exact bytes and metadata before writing it.
    assert images.unpack_image(image, KERNEL_BYTES) == (kernel, dtb, packed, cmdline)
    assert images.unpack_cpio(gzip.decompress(packed)) == entries
    with args.output.open('xb') as file:
        file.write(image)
    report = {'image_sha256': sha(image), 'image_bytes': len(image), 'kernel_sha256': KERNEL_SHA,
              'kernel_bytes': KERNEL_BYTES, 'base_image_sha256': BASE_IMAGE_SHA,
              'base_reconstructed_kernel_sha256': BASE_KERNEL_SHA,
              'base_DTB_sha256': BASE_DTB_SHA, 'DTB_sha256': RMTFS_DTB_SHA,
              'DT_property_differences': sorted(CHANGED), 'MSS_disabled': True,
              'cmdline': cmdline, 'ramdisk_sha256': sha(packed), 'CPIO_entries': len(entries),
              'qualified_base_entries_preserved': len(original), 'timer_seconds': 180,
              'init_launches_worker': False, 'initially_moduleless': True,
              'module_names': ['qrtr'], 'firmware_files': 0,
              'entries_sha256': {name: sha(data) for name, (_, data) in entries.items()}}
    with args.output.with_suffix('.json').open('x') as file:
        json.dump(report, file, indent=2)
        file.write('\n')
    print(json.dumps({key: value for key, value in report.items() if key != 'entries_sha256'}))


if __name__ == '__main__':
    main()
