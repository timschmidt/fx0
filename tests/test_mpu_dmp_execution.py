import importlib.util
import pathlib
import struct
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIAG = ROOT / 'diagnostics/imu-dmp-memory'
sys.path.insert(0, str(DIAG))
try:
    spec = importlib.util.spec_from_file_location('dmp_execution', DIAG / 'check_execution.py')
    execution = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(execution)
finally:
    sys.path.pop(0)


class FifoParsing(unittest.TestCase):
    def test_mixed_packets_at_every_fragment_boundary(self):
        accel = struct.pack('>Hhhh', 0x4000, -123, 456, -16000)
        quaternion = struct.pack('>HHiii', 0x0400, 0, -12345678, 12345678, -0x40000000)
        raw = accel + quaternion + accel
        for split in range(len(raw) + 1):
            decoder = execution.FifoDecoder()
            decoder.feed(raw[:split])
            decoder.feed(raw[split:])
            self.assertEqual(decoder.accel, [(-123, 456, -16000)] * 2)
            self.assertEqual(decoder.quaternion_xyz, [(-12345678, 12345678, -0x40000000)])
            self.assertEqual(decoder.pending, b'')

    def test_bytewise_input_step_flags_and_partial_packet(self):
        packet = struct.pack('>Hhhh', 0x4003, -32768, 0, 32767)
        decoder = execution.FifoDecoder()
        for value in packet:
            decoder.feed(bytes([value]))
        self.assertEqual(decoder.accel, [(-32768, 0, 32767)])
        decoder.feed(b'\x04\x00\x00')
        self.assertEqual(len(decoder.pending), 3)

    def test_unconfigured_packet_is_not_silently_accepted(self):
        for header in (0, 0x2000, 0x0800, 0xffff):
            with self.assertRaises(ValueError):
                execution.FifoDecoder().feed(struct.pack('>H', header))


class CountReading(unittest.TestCase):
    def test_high_byte_rollover_retries(self):
        class Port:
            def __init__(self):
                self.values = iter([0, 255, 1, 1, 0, 1])
            def read(self, reg):
                return next(self.values)
        self.assertEqual(execution.count_fifo(Port()), 256)

    def test_unstable_counter_is_bounded(self):
        class Port:
            def read(self, reg):
                self.counter = getattr(self, 'counter', 0) + 1
                return self.counter
        with self.assertRaises(RuntimeError):
            execution.count_fifo(Port())


class Configuration(unittest.TestCase):
    def test_configuration_stays_inside_uploaded_image_and_verifies(self):
        class Memory:
            def __init__(self):
                self.values = {}
            def write(self, address, data):
                assert execution.START <= address
                assert address + len(data) <= execution.START + execution.SIZE
                self.values[address] = data
            def read(self, address, length):
                return self.values[address]
        memory = Memory()
        execution.configure(memory)
        self.assertEqual(memory.values[744], b'\x00\x07')
        self.assertEqual(memory.values[730], b'\x00\x07')

    def test_readback_failure_stops_configuration(self):
        class Memory:
            writes = 0
            def write(self, address, data):
                self.writes += 1
            def read(self, address, length):
                return bytes(length)
        memory = Memory()
        with self.assertRaises(RuntimeError):
            execution.configure(memory)
        self.assertEqual(memory.writes, 1)

    def test_functional_controls_checked_but_cursor_not_read(self):
        class Port:
            def __init__(self):
                self.values = {r: 0 for r in execution.REGS}
                self.cursor_reads = 0
            def write(self, reg, value):
                self.values[reg] = value
            def read(self, reg):
                if reg == 0x6e:
                    self.cursor_reads += 1
                    self.values[reg] = (self.values[reg] + 1) & 255
                return self.values[reg]
        port = Port()
        saved = {r: (r * 7) & 255 for r in execution.REGS}
        execution.restore_registers(port, saved)
        self.assertEqual(port.cursor_reads, 0)
        self.assertEqual(port.values[0x6e], 0)
        self.assertTrue(all(port.values[r] == v for r, v in saved.items()))

    def test_bad_functional_control_still_fails_restoration(self):
        class Port:
            def write(self, reg, value):
                pass
            def read(self, reg):
                return 255
        with self.assertRaisesRegex(RuntimeError, 'configuration restoration'):
            execution.restore_registers(Port(), {r: 0 for r in execution.REGS})

    def test_private_capture_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / 'capture'
            execution.private_write(path, b'first')
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                execution.private_write(path, b'second')
            self.assertEqual(path.read_bytes(), b'first')


if __name__ == '__main__':
    unittest.main()
