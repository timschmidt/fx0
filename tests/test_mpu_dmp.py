import importlib.util
import pathlib
import random
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


extract = load('extract_dmp', 'scripts/extract_mpu6515_dmp.py')
memory = load('dmp_memory', 'diagnostics/imu-dmp-memory/check_memory.py')


class FirmwareExtraction(unittest.TestCase):
    def test_crc_matches_independent_bitwise_implementation(self):
        for data in (b'', b'123456789', bytes(range(256)), bytes(2943)):
            crc = 0
            for value in data:
                crc ^= value
                for _ in range(8):
                    crc = (crc >> 1) ^ (0xedb88320 if crc & 1 else 0)
            self.assertEqual(extract.linux_crc32(data), crc)

    def test_array_syntax_and_byte_bounds(self):
        start = 'static const unsigned char dmpMemory[DMP_CODE_SIZE] = {'
        self.assertEqual(extract.parse_array(start + '/* bank 10 */ 0x0, 0xff, };'), b'\0\xff')
        for body in ('0x100};', '0x01 + 0x02};', '-1};', '0x01,,0x02};', '0x01'):
            with self.assertRaises(ValueError):
                extract.parse_array(start + body)
        with self.assertRaises(ValueError):
            extract.parse_array(start + '0x01};' + start + '0x02};')

    def test_unpinned_source_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'source'):
            extract.extract(b'not the manufacturer source', b'not a license')


class Port:
    def __init__(self):
        self.ram = bytearray((i * 31 + 7) % 256 for i in range(memory.RAM_SIZE))
        self.bank = 0
        self.offset = 0
        self.writes = []

    def read(self, register):
        assert register == memory.DATA
        value = self.ram[self.bank * 256 + self.offset]
        self.offset = (self.offset + 1) % 256
        return value

    def write(self, register, value):
        self.writes.append((register, value))
        if register == memory.BANK:
            assert 0 <= value < 12
            self.bank = value
        elif register == memory.ADDRESS:
            self.offset = value
        elif register == memory.DATA:
            self.ram[self.bank * 256 + self.offset] = value
            self.offset = (self.offset + 1) % 256
        else:
            raise AssertionError('unexpected register write')


class NonIncrementingPort(Port):
    """Models debugfs byte reads losing the hardware auto-increment state."""
    def read(self, register):
        assert register == memory.DATA
        return self.ram[self.bank * 256 + self.offset]

    def write(self, register, value):
        if register == memory.DATA:
            self.writes.append((register, value))
            self.ram[self.bank * 256 + self.offset] = value
        else:
            super().write(register, value)


class BankedMemory(unittest.TestCase):
    def test_nonincrementing_debugfs_transactions(self):
        port = NonIncrementingPort()
        ram = memory.Memory(port)
        saved = ram.read(memory.START, memory.SIZE)
        image = bytes((i * 13 + 5) % 256 for i in range(memory.SIZE))
        ram.write(memory.START, image)
        self.assertEqual(ram.read(memory.START, memory.SIZE), image)
        ram.write(memory.START, saved)
        self.assertEqual(ram.read(memory.START, memory.SIZE), saved)

    def test_reference_layout_and_last_byte(self):
        plan = list(memory.segments(memory.START, memory.SIZE))
        self.assertEqual(plan[0], (32, 224))
        self.assertEqual(plan[-1], (2816, 159))
        self.assertEqual(sum(size for _, size in plan), 2943)
        self.assertEqual(list(memory.segments(3071, 1)), [(3071, 1)])

    def test_invalid_transfers_do_not_touch_hardware(self):
        port = Port()
        ram = memory.Memory(port)
        for addr, length in ((0, 1), (31, 1), (32, 0), (3072, 1), (3071, 2), (-1, 4)):
            with self.assertRaises(ValueError):
                ram.read(addr, length)
            with self.assertRaises(ValueError):
                ram.write(addr, bytes(max(length, 0)))
        self.assertEqual(port.writes, [])

    def test_roundtrip_across_every_bank_preserves_surroundings(self):
        rng = random.Random(6515)
        for start, length in ((32, 2943), (254, 4), (511, 257), (3071, 1)):
            port = Port()
            original = bytes(port.ram)
            ram = memory.Memory(port)
            saved = ram.read(start, length)
            data = rng.randbytes(length)
            ram.write(start, data)
            self.assertEqual(ram.read(start, length), data)
            self.assertEqual(port.ram[:start], original[:start])
            self.assertEqual(port.ram[start + length:], original[start + length:])
            ram.write(start, saved)
            self.assertEqual(bytes(port.ram), original)


if __name__ == '__main__':
    unittest.main()
