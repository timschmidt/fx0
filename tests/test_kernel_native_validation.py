# SPDX-License-Identifier: GPL-2.0-only
import gzip
import hashlib
import importlib.util
from pathlib import Path
import stat
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'diagnostics/kernel-maintenance'))
import install_native as native
spec = importlib.util.spec_from_file_location('image_builder', ROOT/'scripts/make_diagnostic_image.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


class ImageValidationTests(unittest.TestCase):
    def setUp(self):
        kernel = bytearray(64)
        struct.pack_into('<I', kernel, 36, 0x016f2818)
        self.kernel = bytes(kernel)
        self.dtb = b'\xd0\x0d\xfe\xed' + struct.pack('>I', 40) + bytes(32)
        self.ramdisk = gzip.compress(builder.archive([('init', stat.S_IFREG | 0o755, b'ordinary init\n')]), mtime=0)
        self.image = builder.make_image(self.kernel, self.dtb, self.ramdisk, 'quiet module.sig_enforce=1')
    def test_independent_builder_payloads_and_commandline_match(self):
        kernel, dtb, ramdisk, words = native.boot_parts(self.image, len(self.kernel))
        self.assertEqual((kernel, dtb, ramdisk), (self.kernel, self.dtb, self.ramdisk))
        self.assertEqual(words, ['quiet', 'module.sig_enforce=1'])
    def test_header_payload_padding_and_hidden_arguments_reject(self):
        for fault in ['address', 'version', 'digest', 'kernel', 'padding', 'hidden-cmdline', 'truncated']:
            with self.subTest(fault=fault):
                data = bytearray(self.image)
                if fault == 'address': struct.pack_into('<I', data, 20, 0x03200000)
                if fault == 'version': struct.pack_into('<I', data, 40, 1)
                if fault == 'digest': data[576] ^= 1
                if fault == 'kernel': data[2048] ^= 1
                if fault == 'padding': data[2048 + len(self.kernel) + len(self.dtb)] = 1
                if fault == 'hidden-cmdline': data[608] = ord('x')
                if fault == 'truncated': del data[-1]
                with self.assertRaises(AssertionError): native.boot_parts(bytes(data), len(self.kernel))
    def test_ordinary_cpio_file_identity_preserved(self):
        index = native.cpio_index(self.ramdisk)
        self.assertEqual(index, {'init': dict(mode=stat.S_IFREG | 0o755, uid=0, gid=0, sha256=hashlib.sha256(b'ordinary init\n').hexdigest())})
    def test_appended_RAM_wrapper_archive_rejects(self):
        raw = gzip.decompress(self.ramdisk)
        extra = builder.archive([('fx0-native-return', stat.S_IFREG | 0o755, b'helper')])
        with self.assertRaises(AssertionError): native.cpio_index(gzip.compress(raw + extra, mtime=0))
    def test_duplicate_canonical_filename_rejects(self):
        raw = builder.archive([('init', stat.S_IFREG | 0o755, b'one'), ('./init', stat.S_IFREG | 0o755, b'two')])
        with self.assertRaises(AssertionError): native.cpio_index(gzip.compress(raw, mtime=0))
    def test_parent_traversal_or_absolute_member_rejects(self):
        for name in ['../init', '/init', 'dir/../../init']:
            with self.subTest(name=name):
                raw = builder.archive([(name, stat.S_IFREG | 0o755, b'one')])
                with self.assertRaises(AssertionError): native.cpio_index(gzip.compress(raw, mtime=0))


if __name__ == '__main__': unittest.main()
