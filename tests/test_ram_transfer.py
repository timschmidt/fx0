"""Exercise synchronous RAM transfer framing, partial I/O and failure stops."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import transfer_fx0_ram as RAM


class Wire:
    def __init__(self, data):
        self.data = data
        self.sent = bytearray()
        self.commands = []
        self.queue = []
        self.phase = 'download command'
        self.position = 0
        self.max_part = RAM.CHUNK
        self.writes = 0
        self.fail_write = 0
        self.short_command = self.zero_read = self.corrupt = False
        self.first_response = None

    def __call__(self, fd, endpoint, *, data=None, size=64):
        if data is not None:
            if self.phase == 'download command':
                self.commands.append(data)
                if self.short_command:
                    return len(data) - 1
                self.assert_command(data, f'download:{len(self.data):08x}'.encode())
                self.queue.append(self.first_response or f'DATA{len(self.data):08x}'.encode())
                self.phase = 'download bytes'
                return len(data)
            if self.phase == 'download bytes':
                self.writes += 1
                if self.writes == self.fail_write:
                    raise OSError('completion uncertain')
                count = min(len(data), self.max_part)
                self.sent.extend(data[:count])
                if len(self.sent) == len(self.data):
                    self.queue.append(b'OKAY')
                    self.phase = 'upload command'
                return count
            self.assert_command(data, b'upload')
            if self.queue:
                raise AssertionError('Command before previous status was consumed')
            self.commands.append(data)
            self.queue.append(f'DATA{len(self.data):08x}'.encode())
            self.phase = 'readback bytes'
            return len(data)
        if self.queue:
            return self.queue.pop(0)
        if self.zero_read:
            return b''
        count = min(size, self.max_part, len(self.data) - self.position)
        part = self.data[self.position:self.position + count]
        if self.corrupt and self.position == 0:
            part = bytes([part[0] ^ 1]) + part[1:]
        self.position += count
        if self.position == len(self.data):
            self.queue.append(b'OKAY')
        return part

    @staticmethod
    def assert_command(actual, expected):
        if actual != expected:
            raise AssertionError((actual, expected))


class RamTransferTests(unittest.TestCase):
    def setUp(self):
        self.data = bytes(range(256)) * 200
        self.wire = Wire(self.data)

    def transfer(self):
        return RAM.stage_readback(1, 1, 129, self.data, io=self.wire)

    def test_chunked_exact_readback_and_no_boot(self):
        self.assertEqual(self.transfer(), self.data)
        self.assertEqual(self.wire.sent, self.data)
        self.assertEqual(self.wire.commands, [b'download:0000c800', b'upload'])

    def test_partial_transfers_advance_without_duplicating_bytes(self):
        self.wire.max_part = 997
        self.assertEqual(self.transfer(), self.data)
        self.assertEqual(self.wire.sent, self.data)

    def test_uncertain_completion_is_not_retried(self):
        self.wire.fail_write = 2
        with self.assertRaisesRegex(OSError, 'uncertain'):
            self.transfer()
        self.assertEqual(self.wire.writes, 2)
        self.assertEqual(self.wire.commands, [b'download:0000c800'])

    def test_short_command_is_not_resent(self):
        self.wire.short_command = True
        with self.assertRaisesRegex(ValueError, 'Short command'):
            self.transfer()
        self.assertEqual(len(self.wire.commands), 1)
        self.assertFalse(self.wire.sent)

    def test_empty_read_fails_without_looping(self):
        self.wire.zero_read = True
        with self.assertRaisesRegex(ValueError, 'read progress'):
            self.transfer()

    def test_corrupt_readback_is_rejected(self):
        self.wire.corrupt = True
        with self.assertRaisesRegex(ValueError, 'readback differs'):
            self.transfer()

    def test_malformed_or_wrong_size_rejected_before_data(self):
        for response in [b'DATAgggggggg', b'DATA0000c801', b'OKAY', b'FAILdenied']:
            self.wire = Wire(self.data)
            self.wire.first_response = response
            with self.assertRaises(ValueError):
                self.transfer()
            self.assertFalse(self.wire.sent)

    def test_info_limit_bounds_status_loop(self):
        self.wire.queue = [b'INFOmessage'] * 32
        with self.assertRaisesRegex(ValueError, 'Too many INFO'):
            self.transfer()
        self.assertFalse(self.wire.sent)

    def test_empty_payload_rejected_without_io(self):
        self.data = b''
        with self.assertRaisesRegex(ValueError, 'size'):
            self.transfer()
        self.assertFalse(self.wire.commands)

    def test_pacing_runs_between_data_chunks_only(self):
        pauses = []
        result = RAM.stage_readback(1, 1, 129, self.data, io=self.wire,
                                    pause=lambda: pauses.append(True))
        self.assertEqual(result, self.data)
        self.assertEqual(len(pauses), 8)


if __name__ == '__main__':
    unittest.main()
