"""Exercise the actual CLI journal at each protocol failure boundary, without USB."""
import contextlib
import errno
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'scripts'),
               str(Path(__file__).resolve().parent)]
import transfer_fx0_ram as RAM
from test_ram_transfer import Wire


class RamTransferTraceTests(unittest.TestCase):
    def run_cli(self, base, *, fault=None, short=False, partial_read=False):
        data = bytes(range(256)) * 200
        payload = base / 'payload.bin'
        payload.write_bytes(data)
        output = base / 'report'
        wire = Wire(data)
        if partial_read:
            wire.max_read = 997
        current = {}
        original = RAM.stage_readback
        attempts = []

        def transfer(*args, **kwargs):
            journal_trace = kwargs.pop('trace')
            def trace(**values):
                current.clear()
                current.update(values)
                journal_trace(**values)
            def io(*args, **kwargs):
                # The real main journal must already contain the start before USB.
                rows = [json.loads(row) for row in (output / 'io.jsonl').read_text().splitlines()]
                self.assertTrue(rows, 'I/O begins without a visible journal start')
                self.assertEqual(rows[-1]['event'], 'started')
                self.assertEqual(rows[-1]['phase'], current['phase'])
                self.assertEqual(rows[-1].get('offset'), current.get('offset'))
                attempts.append((current['phase'], current.get('offset')))
                if attempts[-1] == fault:
                    # A timeout may follow partial delivery. The report must not
                    # count that prefix or invent an actual byte count.
                    if current['phase'] == 'download-data':
                        wire.sent.extend(kwargs['data'][:997])
                    raise OSError(errno.ETIMEDOUT, 'completion uncertain')
                if short and attempts[-1] == ('download-data', RAM.CHUNK):
                    wire.max_part = 997
                return wire(*args, **kwargs)
            return original(*args, io=io, trace=trace, **kwargs)

        argv = ['transfer_fx0_ram.py', '--serial', 'fixture-device',
                '--payload', str(payload), '--sha256', hashlib.sha256(data).hexdigest(),
                '--output', str(output), '--pace-ms', '0']
        error = None
        with mock.patch.object(sys, 'argv', argv), \
             mock.patch.object(RAM.boot, 'query', return_value={'product': 'fixture'}), \
             mock.patch.object(RAM.boot, 'device', return_value=('/dev/fixture', 0, 1, 129)), \
             mock.patch.object(RAM.os, 'open', return_value=123), \
             mock.patch.object(RAM.os, 'close') as closed, \
             mock.patch.object(RAM.boot, 'ioctl', return_value=0) as ioctl, \
             mock.patch.object(RAM, 'stage_readback', side_effect=transfer), \
             contextlib.redirect_stdout(__import__('io').StringIO()):
            try:
                RAM.main()
            except (OSError, ValueError) as caught:
                error = caught
            closed.assert_called_once_with(123)
            self.assertEqual([call.args[1] for call in ioctl.call_args_list],
                             [RAM.boot.CLAIM, RAM.boot.RELEASE])
        report = json.loads((output / 'result.json').read_text())
        journal = [json.loads(row) for row in (output / 'io.jsonl').read_text().splitlines()]
        for row in journal:
            self.assertLessEqual(set(row), {'sequence', 'UTC', 'event', 'phase', 'direction',
                                           'offset', 'requested_bytes', 'elapsed_seconds',
                                           'actual_bytes', 'error_type', 'errno'})
        self.assertEqual(report['last_IO'], journal[-1])
        self.assertNotIn('fixture-device', (output / 'io.jsonl').read_text())
        return error, report, journal, attempts, wire, output, data

    def test_success_records_every_framed_io_and_exact_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            error, report, journal, attempts, wire, output, data = self.run_cli(Path(directory))
            self.assertIsNone(error)
            self.assertEqual(report['state'], 'verified')
            self.assertEqual((output / 'readback.bin').read_bytes(), data)
            self.assertEqual(len(journal), 2 * len(attempts))
            self.assertEqual(sorted(set(row['sequence'] for row in journal)),
                             list(range(1, len(attempts) + 1)))
            for first, last in zip(journal[::2], journal[1::2]):
                self.assertEqual(first['event'], 'started')
                self.assertEqual(last['event'], 'returned')
                self.assertEqual(first['sequence'], last['sequence'])
                self.assertEqual(last['actual_bytes'], first['requested_bytes']
                                 if first['direction'] == 'OUT' or 'offset' in first else
                                 (12 if first['phase'].endswith('-size') else 4))
            self.assertEqual([offset for phase, offset in attempts if phase == 'download-data'],
                             [0, 16384, 32768, 49152])
            self.assertEqual(wire.commands, [b'download:0000c800', b'upload'])

    def test_each_protocol_timeout_is_identified_and_never_retried(self):
        cases = [('download-command', None, 0), ('download-size', None, 0),
                 ('download-data', 0, 0), ('download-data', 16384, 16384),
                 ('download-status', None, 51200), ('upload-command', None, 51200),
                 ('upload-size', None, 51200), ('readback-data', 0, 51200),
                 ('readback-data', 997, 997), ('upload-status', None, 51200)]
        for phase, offset, confirmed in cases:
            with self.subTest(phase=phase, offset=offset), tempfile.TemporaryDirectory() as directory:
                error, report, journal, attempts, wire, output, data = self.run_cli(
                    Path(directory), fault=(phase, offset), partial_read=offset == 997)
                self.assertIsInstance(error, OSError)
                self.assertEqual(report['state'], 'failed')
                self.assertEqual(report['bytes'], confirmed)
                last = journal[-1]
                self.assertEqual(last['event'], 'failed')
                self.assertEqual(last['phase'], phase)
                self.assertEqual(last.get('offset'), offset)
                self.assertEqual(last['errno'], errno.ETIMEDOUT)
                self.assertIsNone(last['actual_bytes'])
                self.assertGreaterEqual(last['elapsed_seconds'], 0)
                self.assertEqual(attempts.count((phase, offset)), 1)
                self.assertEqual(attempts[-1], (phase, offset))
                self.assertNotIn('readback_sha256', report)
                self.assertFalse((output / 'readback.bin').exists())
                if phase.startswith('download'):
                    self.assertNotIn(b'upload', wire.commands)

    def test_short_out_count_remains_distinct_from_uncertain_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            error, report, journal, attempts, wire, output, data = self.run_cli(
                Path(directory), short=True)
            self.assertIsInstance(error, ValueError)
            self.assertEqual(report['bytes'], RAM.CHUNK)
            self.assertEqual(journal[-1]['event'], 'returned')
            self.assertEqual(journal[-1]['actual_bytes'], 997)
            self.assertEqual(journal[-1]['offset'], RAM.CHUNK)
            self.assertEqual(attempts[-1], ('download-data', RAM.CHUNK))
            self.assertEqual(wire.commands, [b'download:0000c800'])
            self.assertFalse((output / 'readback.bin').exists())

    def test_observer_failure_stops_before_next_io(self):
        data = b'x' * (2 * RAM.CHUNK)
        wire = Wire(data)
        def trace(**values):
            if values['event'] == 'started' and values.get('offset') == RAM.CHUNK:
                raise OSError(errno.ENOSPC, 'diagnostic storage unavailable')
        with self.assertRaisesRegex(OSError, 'storage unavailable'):
            RAM.stage_readback(1, 1, 129, data, io=wire, trace=trace)
        self.assertEqual(wire.writes, 1)
        self.assertEqual(wire.commands, [b'download:00008000'])


if __name__ == '__main__':
    unittest.main()
