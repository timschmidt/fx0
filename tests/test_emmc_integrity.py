"""Exercise real direct-file I/O and reject corruption, aliasing and stale data."""
import hashlib
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('emmc_worker', ROOT / 'diagnostics/emmc-integrity/worker.py')
worker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(worker)
RUN = 'f87dc12b-a56b-43e8-92aa-98e499b9b415'


class EmmcIntegrityTests(unittest.TestCase):
    def test_sector_tags_bind_run_round_and_absolute_position(self):
        first = worker.pattern(RUN, 2, 0)
        later = worker.pattern(RUN, 2, 7)
        for data, block in [(first, 0), (later, 7)]:
            for at in [0, 512, worker.BLOCK - 512]:
                magic, token, round_, complement, sector = struct.unpack_from('<8s16sIIQ', data, at)
                self.assertEqual(magic, b'FX0EMMC1')
                self.assertEqual(token.hex(), RUN.replace('-', ''))
                self.assertEqual((round_, complement), (2, 0xfffffffd))
                self.assertEqual(sector, (block * worker.BLOCK + at) // 512)
        self.assertNotEqual(first, later)
        self.assertNotEqual(first, worker.pattern(RUN, 3, 0))
        self.assertNotEqual(first, worker.pattern('96cc3160-c0e8-489d-b9cf-9b66232b642e', 2, 0))

    def test_direct_write_close_reopen_and_full_readback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'payload.bin'
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_DIRECT, 0o600)
            try:
                written = worker.write_round(fd, RUN, 1, 2, lambda *args: None)
            finally:
                os.close(fd)
            expected = hashlib.sha256(worker.pattern(RUN, 1, 0) + worker.pattern(RUN, 1, 1)).hexdigest()
            self.assertEqual(written, expected)
            fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
            try:
                read = worker.read_round(fd, RUN, 1, 2, lambda *args: None)
            finally:
                os.close(fd)
            self.assertEqual(read, expected)

    def test_direct_read_rejects_corruption_misdirection_and_stale_round(self):
        for fault, offset in [('bitflip', 777), ('sector_alias', 512), ('stale_round', 24)]:
            with self.subTest(fault=fault), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'payload.bin'
                data = worker.pattern(RUN, 1 if fault == 'stale_round' else 2, 0)
                if fault == 'bitflip':
                    data[offset] ^= 1
                if fault == 'sector_alias':
                    data[512:1024] = data[:512]
                    # The sector index differs at header byte 32.
                    offset += 32
                with path.open('wb') as stream:
                    stream.write(data)
                    stream.flush()
                    os.fsync(stream.fileno())
                fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
                try:
                    with self.assertRaisesRegex(RuntimeError, 'payload mismatch at byte ' + str(offset)):
                        worker.read_round(fd, RUN, 2, 1, lambda *args: None)
                finally:
                    os.close(fd)

    def test_short_direct_read_does_not_pass_or_loop(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'payload.bin'
            with path.open('wb') as stream:
                stream.write(worker.pattern(RUN, 0, 0)[:4096])
                stream.flush()
                os.fsync(stream.fileno())
            fd = os.open(path, os.O_RDONLY | os.O_DIRECT)
            try:
                with self.assertRaisesRegex(RuntimeError, 'short direct read'):
                    worker.read_round(fd, RUN, 0, 1, lambda *args: None)
            finally:
                os.close(fd)


if __name__ == '__main__':
    unittest.main()
