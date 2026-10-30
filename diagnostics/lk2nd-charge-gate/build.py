#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build a RAM-only early-gate observer; never opens a device or mounts storage."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import struct

parser = argparse.ArgumentParser(description=__doc__)
for name in ['kernel', 'dtb', 'busybox', 'observer', 'output']:
    parser.add_argument('--'+name, type=Path, required=True)
args = parser.parse_args()
assert not args.output.exists()
root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('diagnostic_image', root/'scripts/make_diagnostic_image.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
busybox = args.busybox.read_bytes()
assert busybox[:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H', busybox, 18)[0] == 40
phoff = struct.unpack_from('<I', busybox, 28)[0]
phsize, phnum = struct.unpack_from('<HH', busybox, 42)
assert not any(struct.unpack_from('<I', busybox, phoff+i*phsize)[0] == 3 for i in range(phnum))
kernel, dtb, observer = args.kernel.read_bytes(), args.dtb.read_bytes(), args.observer.read_bytes()
entries = [(name, stat.S_IFDIR | 0o755, b'') for name in ['bin', 'dev', 'proc', 'sys']]
entries += [('bin/busybox', stat.S_IFREG | 0o755, busybox),
            ('bin/sh', stat.S_IFLNK | 0o777, b'busybox'),
            ('init', stat.S_IFREG | 0o755, Path(__file__).with_name('init').read_bytes()),
            ('fx0-btc-reference.ko', stat.S_IFREG | 0o600, observer)]
initrd = gzip.compress(helper.archive(entries), mtime=0)
command = ('console=ttyMSM0,115200 earlycon rdinit=/init loglevel=8 ignore_loglevel '
           'panic=30 reboot=w lk2nd.pass-ramoops=zap console=tty0 lk2nd.pass-simplefb=autorefresh')
image = helper.make_image(kernel, dtb, initrd, command)
with args.output.open('xb') as stream:
    stream.write(image)
print(json.dumps({'image_bytes': len(image), 'image_sha256': hashlib.sha256(image).hexdigest(),
                  'inputs_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in
                                   [('kernel', kernel), ('dtb', dtb), ('observer', observer), ('busybox', busybox)]},
                  'mounted_eMMC_filesystems': False, 'automatic_return_after_init_seconds_max': 90}, indent=2))
