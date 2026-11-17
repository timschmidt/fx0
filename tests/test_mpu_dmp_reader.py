"""Reader restoration against IIO's exclusive scan-mask semantics."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('native_reader', Path(__file__).resolve().parents[1] /
    'diagnostics/imu-dmp-native/read_quaternion.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Attribute:
    def __init__(self, name, state):
        self.name, self.state = name, state
        self.fail = False

    def write_text(self, value):
        if self.fail:
            raise OSError('injected failure')
        value = value.strip()
        if value == '1' and self.name in ('raw', 'quat'):
            other = 'quat' if self.name == 'raw' else 'raw'
            if self.state[other] == '1':
                raise OSError('invalid exclusive scan mask')
        self.state[self.name] = value

    def __str__(self):
        return self.name


class ReaderRestore(unittest.TestCase):
    def test_saved_raw_scan_restored_after_quaternion_capture(self):
        state = {'raw': '0', 'quat': '1', 'stamp': '1', 'length': '64'}
        paths = {name: Attribute(name, state) for name in state}
        saved = {paths['raw']: '1', paths['quat']: '0', paths['stamp']: '0', paths['length']: '8'}
        reader.restore_configuration(saved, [paths[k] for k in ('raw', 'quat', 'stamp')])
        self.assertEqual(state, {'raw': '1', 'quat': '0', 'stamp': '0', 'length': '8'})

    def test_restore_failure_reported_and_remaining_attributes_attempted(self):
        state = {'raw': '0', 'quat': '1', 'stamp': '1', 'length': '64'}
        paths = {name: Attribute(name, state) for name in state}
        paths['raw'].fail = True
        saved = {paths['raw']: '1', paths['quat']: '0', paths['stamp']: '0', paths['length']: '8'}
        with self.assertRaisesRegex(RuntimeError, 'injected failure'):
            reader.restore_configuration(saved, [paths[k] for k in ('raw', 'quat', 'stamp')])
        self.assertEqual(state['quat'], '0')
        self.assertEqual(state['length'], '8')


class ReaderDecode(unittest.TestCase):
    VALUES = [
        (0, 0, 0, 0, 0),
        (1 << 30, 0, 0, 0, 123456789),
        (-(1 << 30), 1, -1, 17, 987654321),
        (2**31-1, -2**31, 123, -456, 2**63-1),
        (5, 6, 7, 8, -2**63),
        (1, 2, 3, 4, -1),
        (-1, -2, -3, -4, 16),
        (123, 456, 789, 1000, 24),
        (111, -222, 333, -444, 31415926535),
    ]

    def test_maintained_timestamp_precedes_nonzero_tail_padding(self):
        for values in self.VALUES:
            with self.subTest(values=values):
                data = bytearray(struct.pack('=iiiiq8x', *values))
                data[24:] = b'\xa5' * 8
                self.assertEqual(reader.SCAN.size, 32)
                self.assertEqual(reader.decode_scan(data), values)

    def test_explicit_legacy_timestamp_follows_nonzero_padding(self):
        for values in self.VALUES:
            with self.subTest(values=values):
                data = bytearray(struct.pack('=iiii8xq', *values))
                data[16:24] = b'\x5a' * 8
                self.assertEqual(reader.LEGACY_R1_SCAN.size, 32)
                self.assertEqual(reader.decode_scan(data, legacy_r1_timestamp=True), values)

    def test_layouts_select_different_timestamp_slots(self):
        data = struct.pack('=iiiiqq', 1, 2, 3, 4, 987654321, 123456789)
        self.assertEqual(reader.decode_scan(data), (1, 2, 3, 4, 987654321))
        self.assertEqual(reader.decode_scan(data, legacy_r1_timestamp=True),
                         (1, 2, 3, 4, 123456789))

    def test_incomplete_frame_rejected(self):
        for size in [0, 15, 16, 23, 24, 31]:
            with self.subTest(size=size):
                with self.assertRaises(struct.error):
                    reader.decode_scan(bytes(size))

    def test_first_scan_in_a_queued_batch(self):
        first = self.VALUES[1]
        second = self.VALUES[2]
        data = struct.pack('=iiiiq8x', *first) + struct.pack('=iiiiq8x', *second)
        self.assertEqual(reader.decode_scan(data), first)
        self.assertEqual(reader.decode_scan(memoryview(data)[32:]), second)


if __name__ == '__main__':
    unittest.main()
