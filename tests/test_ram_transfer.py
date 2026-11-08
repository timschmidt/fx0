"""Exercise RAM transfer framing, short-I/O failure stops and readback."""
import json
import sys
from pathlib import Path
import tempfile
import unittest
from unittest import mock

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
        self.max_read = RAM.CHUNK
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
        count = min(size, self.max_read, len(self.data) - self.position)
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

    def test_partial_readback_advances_without_duplicating_bytes(self):
        self.wire.max_read = 997
        self.assertEqual(self.transfer(), self.data)
        self.assertEqual(self.wire.sent, self.data)

    def test_short_data_write_stops_without_resuming_or_upload(self):
        # Include both a USB-packet-aligned prefix and a short packet. The
        # host must not guess which state a positive short result left behind.
        for count in [0, 1, 997, 8192, RAM.CHUNK - 1]:
            with self.subTest(count=count):
                self.wire = Wire(self.data)
                self.wire.max_part = count
                with self.assertRaisesRegex(ValueError, 'do not resume or boot'):
                    self.transfer()
                self.assertEqual(self.wire.writes, 1)
                self.assertEqual(len(self.wire.sent), count)
                self.assertEqual(self.wire.commands, [b'download:0000c800'])

    def test_short_write_after_progress_preserves_confirmed_offset(self):
        wire = self.wire
        progress = []
        def short_second(*args, **kwargs):
            if kwargs.get('data') is not None and wire.phase == 'download bytes' and wire.writes == 1:
                wire.max_part = 997
            return wire(*args, **kwargs)
        with self.assertRaisesRegex(ValueError, 'offset 16384: 997 of 16384'):
            RAM.stage_readback(1, 1, 129, self.data, io=short_second,
                               progress=lambda **values: progress.append(values))
        self.assertEqual(wire.writes, 2)
        self.assertEqual(progress, [{'phase': 'download', 'bytes': RAM.CHUNK}])
        self.assertEqual(wire.commands, [b'download:0000c800'])

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

    def test_identity_failure_report_has_zero_confirmed_bytes(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            payload = base / 'payload.bin'
            payload.write_bytes(self.data)
            output = base / 'report'
            argv = ['transfer_fx0_ram.py', '--serial', 'fixture-device',
                    '--payload', str(payload), '--sha256', hashlib.sha256(self.data).hexdigest(),
                    '--output', str(output)]
            with mock.patch.object(sys, 'argv', argv), mock.patch.object(RAM.boot, 'query', side_effect=OSError('identity unavailable')), mock.patch.object(RAM.os, 'open') as opened:
                with self.assertRaisesRegex(OSError, 'identity unavailable'):
                    RAM.main()
                opened.assert_not_called()
            report = json.loads((output / 'result.json').read_text())
            self.assertEqual(report['state'], 'failed')
            self.assertEqual(report['bytes'], 0)
            self.assertEqual(report['payload_bytes'], len(self.data))
            self.assertIn('finished_UTC', report)

    def test_data_failure_report_never_marks_unconfirmed_bytes(self):
        import hashlib
        original = RAM.stage_readback
        for mode, expected in [('first_timeout', 0), ('second_short', RAM.CHUNK)]:
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                base = Path(directory)
                payload = base / 'payload.bin'
                payload.write_bytes(self.data)
                output = base / 'report'
                argv = ['transfer_fx0_ram.py', '--serial', 'fixture-device',
                        '--payload', str(payload), '--sha256', hashlib.sha256(self.data).hexdigest(),
                        '--output', str(output), '--pace-ms', '0']
                wire = Wire(self.data)
                wire.fail_write = 1 if mode == 'first_timeout' else 0
                def io(*args, **kwargs):
                    if mode == 'second_short' and kwargs.get('data') is not None and wire.phase == 'download bytes' and wire.writes == 1:
                        wire.max_part = 997
                    return wire(*args, **kwargs)
                def transfer(*args, **kwargs):
                    return original(*args, io=io, **kwargs)
                with mock.patch.object(sys, 'argv', argv), mock.patch.object(RAM.boot, 'query', return_value={'product': 'fixture'}), mock.patch.object(RAM.boot, 'device', return_value=('/dev/fixture', 0, 1, 129)), mock.patch.object(RAM.os, 'open', return_value=123), mock.patch.object(RAM.os, 'close') as closed, mock.patch.object(RAM.boot, 'ioctl', return_value=0) as ioctl, mock.patch.object(RAM, 'stage_readback', side_effect=transfer):
                    with self.assertRaises((OSError, ValueError)):
                        RAM.main()
                    closed.assert_called_once_with(123)
                    self.assertEqual([call.args[1] for call in ioctl.call_args_list], [RAM.boot.CLAIM, RAM.boot.RELEASE])
                report = json.loads((output / 'result.json').read_text())
                self.assertEqual(report['state'], 'failed')
                self.assertEqual(report['bytes'], expected)
                self.assertEqual(report['payload_bytes'], len(self.data))
                self.assertNotIn('readback_sha256', report)
                self.assertFalse((output / 'readback.bin').exists())
                self.assertEqual(wire.writes, 1 if mode == 'first_timeout' else 2)
                self.assertEqual(wire.commands, [b'download:0000c800'])


if __name__ == '__main__':
    unittest.main()
