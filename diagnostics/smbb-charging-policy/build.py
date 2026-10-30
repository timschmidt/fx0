#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the isolated policy/provider diagnostic; no device access or flashing."""
import argparse
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import stat
import struct

parser = argparse.ArgumentParser(description=__doc__)
for name in ['kernel', 'dtb', 'busybox', 'observer', 'vadc', 'common', 'output']:
    parser.add_argument('--'+name, type=Path, required=True)
args = parser.parse_args()
root = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('diagnostic', root/'scripts/make_diagnostic_image.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
assert not args.output.exists()
items = {name: getattr(args, name).read_bytes() for name in ['kernel', 'dtb', 'busybox', 'observer', 'vadc', 'common']}
for name in ['busybox', 'observer', 'vadc', 'common']:
    assert items[name][:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H', items[name], 18)[0] == 40
offset = struct.unpack_from('<I', items['busybox'], 28)[0]
entry_size, entries_count = struct.unpack_from('<HH', items['busybox'], 42)
assert not any(struct.unpack_from('<I', items['busybox'], offset+i*entry_size)[0] == 3 for i in range(entries_count))
entries = [(name, stat.S_IFDIR | 0o755, b'') for name in ['bin', 'dev', 'sys', 'proc', 'www', 'modules']]
entries += [('bin/busybox', stat.S_IFREG | 0o755, items['busybox']),
            ('bin/sh', stat.S_IFLNK | 0o777, b'busybox'),
            ('bin/serve-http', stat.S_IFREG | 0o755, helper.HTTP.encode()),
            ('init', stat.S_IFREG | 0o755, Path(__file__).with_name('init').read_bytes()),
            ('modules/fx0-btc-reference.ko', stat.S_IFREG | 0o600, items['observer']),
            ('modules/qcom-spmi-vadc.ko', stat.S_IFREG | 0o600, items['vadc']),
            ('modules/qcom-vadc-common.ko', stat.S_IFREG | 0o600, items['common'])]
initrd = gzip.compress(helper.archive(entries), mtime=0)
command = ('console=ttyMSM0,115200 earlycon rdinit=/init loglevel=8 ignore_loglevel '
           'panic=30 reboot=w lk2nd.pass-ramoops=zap console=tty0 lk2nd.pass-simplefb=autorefresh')
image = helper.make_image(items['kernel'], items['dtb'], initrd, command)
with args.output.open('xb') as stream:
    stream.write(image)
print(json.dumps({'image_sha256': hashlib.sha256(image).hexdigest(), 'image_bytes': len(image),
                  'inputs_sha256': {name: hashlib.sha256(data).hexdigest() for name, data in items.items()},
                  'eMMC_filesystems_mounted': False, 'independent_return_timer_after_init_seconds': 180}, indent=2))
