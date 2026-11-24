# SPDX-License-Identifier: MIT
"""Verify release changes preserve unrelated newc records and hardlink metadata."""
import importlib.util
from pathlib import Path
import stat
import struct
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


transform = load('module_relabel', ROOT / 'diagnostics/kernel-maintenance/relabel_initramfs_modules.py')
builder = load('relabel_cpio_builder', ROOT / 'scripts/make_diagnostic_image.py')


class RelabelTests(unittest.TestCase):
    def fixture(self, extra=()):
        # Nondefault metadata on the unrelated init record must remain byte exact.
        raw = bytearray(builder.archive([
            ('init', stat.S_IFREG | 0o755, b'#!/bin/sh\n'),
            ('usr/lib/modules/old', stat.S_IFDIR | 0o755, b''),
            ('usr/lib/modules/old/kernel', stat.S_IFDIR | 0o755, b''),
            ('usr/lib/modules/old/kernel/one.ko.zst', stat.S_IFREG | 0o644, b'old-module'),
            ('usr/lib/modules/old/modules.dep', stat.S_IFREG | 0o644, b'old-index'),
            *extra,
        ]))
        for start, value in [(6, 987), (22, 41), (30, 42), (38, 3), (46, 123456)]:
            raw[start:start + 8] = f'{value:08x}'.encode()
        return bytes(raw)

    def records(self, raw):
        # Independent field offsets, preserving entire records for comparison.
        rows, offset = {}, 0
        while raw[offset:offset + 6] == b'070701':
            header = raw[offset:offset + 110]
            length = int(header[94:102], 16)
            size = int(header[54:62], 16)
            name = raw[offset + 110:offset + 110 + length - 1].decode()
            start = (offset + 110 + length + 3) // 4 * 4
            end = (start + size + 3) // 4 * 4
            if name == 'TRAILER!!!':
                break
            rows[name] = (header, raw[start:start + size], raw[offset:end])
            offset = end
        return rows

    def test_changed_release_body_lengths_and_unrelated_metadata(self):
        raw = self.fixture()
        replacements = {'kernel/one.ko.zst': b'new-longer-module-body', 'modules.dep': b'new'}
        updated, report = transform.relabel(raw, 'old', 'new-long-release', replacements)
        before, after = self.records(raw), self.records(updated)
        self.assertEqual(before['init'][2], after['init'][2])
        self.assertEqual(len(after), len(before))
        self.assertEqual(len(report['renamed_paths']), 4)
        for name, (header, body, _) in before.items():
            if name == 'init':
                continue
            new_name = name.replace('/old', '/new-long-release', 1)
            new_header, new_body, _ = after[new_name]
            self.assertEqual(header[:54], new_header[:54])
            self.assertEqual(header[62:94], new_header[62:94])
            self.assertEqual(header[102:], new_header[102:])
            relative = name.removeprefix('usr/lib/modules/old/')
            self.assertEqual(new_body, replacements.get(relative, body))
        self.assertEqual(len(updated) % 512, 0)

    def test_incomplete_or_extra_replacement_rosters_reject(self):
        for values in ({'kernel/one.ko.zst': b'new'},
                       {'kernel/one.ko.zst': b'new', 'modules.dep': b'index', 'unexpected': b'extra'}):
            with self.subTest(roster=sorted(values)), self.assertRaises(ValueError):
                transform.relabel(self.fixture(), 'old', 'new', values)

    def test_destination_collision_and_symlink_module_reject(self):
        for extra in ([('usr/lib/modules/new', stat.S_IFDIR | 0o755, b'')],
                      [('usr/lib/modules/old/link', stat.S_IFLNK | 0o777, b'kernel/one.ko.zst')]):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                transform.relabel(self.fixture(extra), 'old', 'new',
                                  {'kernel/one.ko.zst': b'new', 'modules.dep': b'index'})

    def test_concatenated_archive_and_truncation_reject(self):
        raw = self.fixture()
        for value in (raw + raw, raw[:-20], b''):
            with self.subTest(size=len(value)), self.assertRaises(ValueError):
                transform.relabel(value, 'old', 'new', {'kernel/one.ko.zst': b'new', 'modules.dep': b'index'})


if __name__ == '__main__':
    unittest.main()
