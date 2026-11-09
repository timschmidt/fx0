"""Synthetic ELF/segment fixtures only; no proprietary firmware needed."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('firmware_layout', ROOT / 'diagnostics/modem-control/inspect-firmware.py')
LAYOUT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(LAYOUT)


def elf(rows, entry=0x08000000, packed_hash=b''):
    ident = b'\x7fELF\x01\x01\x01' + b'\0' * 9
    header = struct.pack('<16sHHIIIIIHHHHHH', ident, 2, 164, 1, entry, 52, 0, 0, 52, 32, len(rows), 0, 0, 0)
    return header + b''.join(struct.pack('<8I', *row) for row in rows) + packed_hash


class ModemFirmwareLayoutTests(unittest.TestCase):
    def fixture(self, directory, relocate=False):
        root = Path(directory)
        address = 0x100000 if relocate else 0x08000000
        flags = 5 | (LAYOUT.RELOCATABLE if relocate else 0)
        rows = [[0, 0, 0, 0, 180, 0, 0, 4],
                [0, 0x1000, 0, 0, 16, 0, LAYOUT.TYPE_HASH, 4],
                [1, 0x2000, address, address, 32, 0x1000, flags, 4096],
                [1, 0x3000, address+0x1000, address+0x1000, 0, 0x1000, flags, 4096]]
        (root/'modem.mdt').write_bytes(elf(rows, entry=address, packed_hash=b'H'*16))
        (root/'modem.b02').write_bytes(b'F'*32)
        (root/'mba.mdt').write_bytes(elf([[1, 0, 0x0d100000, 0x0d100000, 64, 64, 5, 4]], entry=0x0d100000))
        (root/'mba.b00').write_bytes(b'M'*64)
        return root, rows

    def inspect(self, root):
        return LAYOUT.inspect(root, 0x08000000, 0x05100000, 0x0d100000, 0x100000)

    def test_fixed_and_relocatable_split_layout_and_zero_fill(self):
        for relocate in [False, True]:
            with self.subTest(relocate=relocate), tempfile.TemporaryDirectory() as directory:
                root, _ = self.fixture(directory, relocate)
                before = {p.name:p.read_bytes() for p in root.iterdir()}
                result = self.inspect(root)
                self.assertTrue(result['layout_checks_passed'])
                self.assertEqual(result['MPSS']['relocatable'], relocate)
                self.assertEqual(result['MPSS']['loadable_segments'][0]['physical_start'], 0x08000000)
                self.assertEqual(result['MPSS']['loadable_segments'][1]['zero_fill_bytes'], 4096)
                self.assertFalse(result['firmware_authentication_tested'])
                self.assertFalse(result['firmware_started'])
                self.assertEqual({p.name:p.read_bytes() for p in root.iterdir()}, before)

    def test_invalid_headers_and_segments_rejected(self):
        for mode in ['magic', 'class', 'machine', 'phoff', 'truncated-table', 'first-loadable',
                     'no-hash', 'two-hashes', 'filesz', 'below-memory', 'above-memory', 'overlap',
                     'missing-split', 'wrong-split-size', 'embedded-truncated', 'oversized-mba', 'wrong-mba-entry']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root, rows = self.fixture(directory)
                if mode == 'first-loadable': rows[0][0] = 1
                if mode == 'no-hash': rows[1][6] = 0
                if mode == 'two-hashes': rows[3][6] = LAYOUT.TYPE_HASH
                if mode == 'filesz': rows[2][4] = 0x1001
                if mode == 'below-memory': rows[2][3] = 0x07fff000
                if mode == 'above-memory': rows[3][3] = 0x0d100000
                if mode == 'overlap': rows[3][3] = rows[2][3]
                if mode == 'embedded-truncated': rows[2][1] = 195
                data = bytearray(elf(rows, packed_hash=b'H'*16))
                if mode == 'magic': data[0] = 0
                if mode == 'class': data[4] = 2
                if mode == 'machine': struct.pack_into('<H', data, 18, 40)
                if mode == 'phoff': struct.pack_into('<I', data, 28, 64)
                if mode == 'truncated-table': data = data[:100]
                (root/'modem.mdt').write_bytes(data)
                if mode == 'missing-split': (root/'modem.b02').unlink()
                if mode == 'wrong-split-size': (root/'modem.b02').write_bytes(b'bad')
                if mode == 'oversized-mba': (root/'mba.b00').write_bytes(b'M'*(0x100000+1))
                if mode == 'wrong-mba-entry':
                    data=bytearray((root/'mba.mdt').read_bytes());struct.pack_into('<I',data,24,0x0d200000);(root/'mba.mdt').write_bytes(data)
                with self.assertRaises((ValueError, FileNotFoundError)):
                    self.inspect(root)

    def test_embedded_and_separate_metadata_hash_sources(self):
        for mode in ['embedded', 'split']:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root, rows = self.fixture(directory)
                if mode == 'embedded':
                    rows[1][1] = 196
                    rows[2][1] = 212
                    (root/'modem.mdt').write_bytes(elf(rows) + b'P'*16 + b'H'*16 + b'F'*32)
                else:
                    (root/'modem.mdt').write_bytes(elf(rows))
                    (root/'modem.b01').write_bytes(b'H'*16)
                result = self.inspect(root)
                self.assertEqual(result['MPSS']['metadata']['source'],
                                 'embedded segment' if mode == 'embedded' else 'modem.b01')
                if mode == 'embedded':
                    self.assertEqual(result['MPSS']['loadable_segments'][0]['source'], 'embedded in modem.mdt')

    def test_split_file_outside_original_directory_rejected(self):
        with tempfile.TemporaryDirectory() as directory, tempfile.TemporaryDirectory() as elsewhere:
            root, _ = self.fixture(directory)
            other = Path(elsewhere)/'unexpected-segment'
            other.write_bytes(b'F'*32)
            (root/'modem.b02').unlink()
            (root/'modem.b02').symlink_to(other)
            with self.assertRaisesRegex(ValueError, 'one original directory'):
                self.inspect(root)


if __name__ == '__main__':
    unittest.main()
