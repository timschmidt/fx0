# SPDX-License-Identifier: GPL-2.0-only
"""Tests for scripts/fx0_storage_migrate.py using synthetic GPTs only."""
import importlib.util
import os
import struct
import tempfile
import unittest
import uuid
from pathlib import Path

spec = importlib.util.spec_from_file_location('m', Path(__file__).resolve().parents[1] / 'scripts/fx0_storage_migrate.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
S, T = m.SECTOR, m.TOTAL_SECTORS
BASIC = uuid.UUID('ebd0a0a2-b9e5-4433-87c0-68b6b72699c7')


def entry(name, first, last, type_guid=BASIC):
    e = bytearray(m.ENTRY_SIZE)
    e[:16] = type_guid.bytes_le
    e[16:32] = uuid.uuid4().bytes_le
    struct.pack_into('<QQQ', e, 32, first, last, 0)
    e[56:56 + 2 * len(name)] = name.encode('utf-16le')
    return bytes(e)


def original_layout():
    entries, lba = [], 16384
    for i in range(m.RETAINED):
        entries.append(entry(f'p{i + 1}', lba, lba + 2047))
        lba += 2048
    spans = [(786432, 2883583), (2883584, 4317183), (4317184, 12705791), (12705792, 30507007), (30507008, 30777310)]
    for name, (a, b) in zip(m.RECLAIMED, spans):
        entries.append(entry(name, a, b))
    array = b''.join(entries) + bytes((m.ENTRY_COUNT - len(entries)) * m.ENTRY_SIZE)
    disk = uuid.uuid4().bytes_le

    def header(current, backup, entries_lba):
        h = bytearray(S)
        struct.pack_into('<8sIII', h, 0, b'EFI PART', 0x10000, 92, 0)
        struct.pack_into('<QQQQ16sQIII', h, 24, current, backup, 34, T - 34, disk, entries_lba,
                         m.ENTRY_COUNT, m.ENTRY_SIZE, m.crc(array))
        struct.pack_into('<I', h, 16, m.crc(bytes(h[:92])))
        return bytes(h)
    mbr = bytearray(S)
    mbr[510:512] = b'\x55\xaa'
    arr32 = array + bytes(32 * S - len(array))
    primary = bytes(mbr) + header(1, T - 1, 2) + arr32
    backup = arr32 + header(T - 1, 1, T - 33)
    return primary, backup


class StorageMigrateTest(unittest.TestCase):
    def setUp(self):
        self.op, self.ob = original_layout()

    def test_plan_verify_round_trip(self):
        guid = uuid.UUID('11111111-2222-3333-4444-555555555555')
        p, b = m.plan(self.op, self.ob, guid)
        summary = m.verify(self.op, self.ob, p, b)
        self.assertEqual(summary['root_bytes'], 15355330048)
        _, _, new = m.read_pair(p, b)
        self.assertEqual(new[m.RETAINED]['name'], 'nura-root')
        self.assertEqual(uuid.UUID(bytes_le=new[m.RETAINED]['raw'][16:32]), guid)
        self.assertEqual(p[:S], self.op[:S])

    def test_corrupt_header_crc_rejected(self):
        bad = bytearray(self.op); bad[S + 40] ^= 1
        with self.assertRaises(m.LayoutError):
            m.plan(bytes(bad), self.ob)

    def test_array_mismatch_rejected(self):
        bad = bytearray(self.ob); bad[100] ^= 1
        with self.assertRaises(m.LayoutError):
            m.read_pair(self.op, bytes(bad))

    def test_unexpected_tail_names_rejected(self):
        p, b = m.plan(self.op, self.ob)
        with self.assertRaises(m.LayoutError):
            m.plan(p, b)

    def test_trailing_data_rejected(self):
        p = bytearray(self.op); p[-1] = 1
        p = bytes(p)
        # Re-stamping is unnecessary: trailing bytes lie outside the CRC-covered array.
        with self.assertRaises(m.LayoutError):
            m.plan(p, self.ob)

    def test_verify_detects_changed_retained_entry(self):
        p, b = m.plan(self.op, self.ob)
        tampered_p, tampered_b = m.plan(self.op, self.ob)
        _, _, entries = m.read_pair(tampered_p, tampered_b)
        raw = bytearray(entries[3]['raw']); raw[100] ^= 1
        array = b''.join(e['raw'] for e in entries[:3]) + bytes(raw) + b''.join(e['raw'] for e in entries[4:])
        tp = m.build_region(tampered_p[S:2 * S], array, primary=True, protective_mbr=tampered_p[:S])
        tb = m.build_region(tampered_b[-S:], array, primary=False, protective_mbr=None)
        with self.assertRaises(m.LayoutError):
            m.verify(self.op, self.ob, tp, tb)

    def _device(self, tmp, mounted=''):
        dev = Path(tmp, 'mmcblk0')
        with dev.open('wb') as f:
            f.write(self.op)
            f.seek(T * S - len(self.ob)); f.write(self.ob)
        sysfs = Path(tmp, 'sys'); (sysfs / 'mmcblk0').mkdir(parents=True)
        (sysfs / 'mmcblk0' / 'size').write_text(f'{T}\n'); (sysfs / 'mmcblk0' / 'removable').write_text('0\n')
        mounts = Path(tmp, 'mounts'); mounts.write_text(mounted)
        return str(dev), str(sysfs), str(mounts)

    def test_apply_writes_and_reads_back(self):
        p, b = m.plan(self.op, self.ob)
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            dev, sysfs, mounts = self._device(tmp, '/dev/mmcblk0p34 /boot ext2 rw 0 0\n')
            self.assertEqual(m.apply(dev, self.op, self.ob, p, b, sysfs=sysfs, mounts=mounts, confirm_restoration=True)['readback'], 'match')
            data = Path(dev).read_bytes()
            self.assertEqual(data[:len(p)], p)
            self.assertEqual(data[-len(b):], b)

    def test_apply_refusals(self):
        p, b = m.plan(self.op, self.ob)
        with tempfile.TemporaryDirectory(dir='/tmp') as tmp:
            dev, sysfs, mounts = self._device(tmp, '/dev/mmcblk0p37 / ext4 rw 0 0\n')
            with self.assertRaisesRegex(m.LayoutError, 'rehearsal'):
                m.apply(dev, self.op, self.ob, p, b, sysfs=sysfs, mounts=mounts)
            with self.assertRaisesRegex(m.LayoutError, 'mounted'):
                m.apply(dev, self.op, self.ob, p, b, sysfs=sysfs, mounts=mounts, confirm_restoration=True)
            Path(mounts).write_text('')
            Path(sysfs, 'mmcblk0', 'size').write_text('123\n')
            with self.assertRaisesRegex(m.LayoutError, 'size'):
                m.apply(dev, self.op, self.ob, p, b, sysfs=sysfs, mounts=mounts, confirm_restoration=True)
            Path(sysfs, 'mmcblk0', 'size').write_text(f'{T}\n')
            with open(dev, 'r+b') as f:
                f.seek(S * 5); f.write(b'\xff')
            with self.assertRaisesRegex(m.LayoutError, 'not the expected original'):
                m.apply(dev, self.op, self.ob, p, b, sysfs=sysfs, mounts=mounts, confirm_restoration=True)
        with self.assertRaisesRegex(m.LayoutError, 'mmcblk0'):
            m.apply('/dev/sda', self.op, self.ob, p, b, confirm_restoration=True)


if __name__ == '__main__':
    unittest.main()
