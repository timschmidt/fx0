"""Verify RAM handoff guards and ordering without opening a USB device."""
import hashlib
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ram_boot', ROOT/'scripts/boot_fx0_ram.py')
RAM = importlib.util.module_from_spec(spec)
spec.loader.exec_module(RAM)


class RamBootTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.image = self.base/'image.img'
        self.data = b'ANDROID!'+bytes(2040)
        self.image.write_bytes(self.data)
        self.sha = hashlib.sha256(self.data).hexdigest()
        self.output = self.base/'output'
        self.output.mkdir()
        self.calls = []
        self.corrupt = self.fail = self.bad_identity = self.ack_timeout = False

    def tearDown(self):
        self.tmp.cleanup()

    def probe(self, serial, boot=False):
        self.assertEqual(serial,'test-device')
        self.calls.append('boot' if boot else 'probe')
        if self.bad_identity:
            raise ValueError('Unexpected bootloader product')
        if boot and self.ack_timeout:
            raise OSError('boot response unavailable')
        return {'boot_response':['OKAY']} if boot else {'product':['OKAYlk2nd-msm8226']}

    def runner(self, argv, **kwargs):
        self.assertNotIn('timeout',kwargs,'Transfers must not be killed by an observation deadline')
        self.assertEqual(argv[:4],['fastboot','-v','-s','test-device'])
        action = argv[4]
        self.assertIn(action,['stage','get_staged'])
        self.calls.append(action)
        if action=='get_staged':
            Path(argv[5]).write_bytes(b'bad' if self.corrupt else self.data)
        return subprocess.CompletedProcess(argv,1 if self.fail else 0)

    def run_boot(self):
        return RAM.checked_transfer(self.image,self.sha,'test-device',self.output,
                                    probe=self.probe,runner=self.runner)

    def test_readback_before_single_boot(self):
        result = self.run_boot()
        self.assertEqual(self.calls,['probe','stage','get_staged','boot'])
        self.assertEqual(result['phase'],'boot acknowledged')
        self.assertEqual(result['readback_sha256'],self.sha)

    def test_corrupt_image_stops_before_usb(self):
        self.image.write_bytes(self.data+b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'):
            self.run_boot()
        self.assertFalse(self.calls)

    def test_wrong_format_stops_before_usb(self):
        self.image.write_bytes(b'wrong')
        self.sha = hashlib.sha256(b'wrong').hexdigest()
        with self.assertRaisesRegex(ValueError,'Android'):
            self.run_boot()
        self.assertFalse(self.calls)

    def test_wrong_device_does_not_download(self):
        self.bad_identity = True
        with self.assertRaisesRegex(ValueError,'product'):
            self.run_boot()
        self.assertEqual(self.calls,['probe'])

    def test_failed_transfer_does_not_boot(self):
        self.fail = True
        with self.assertRaisesRegex(ValueError,'transfer failed'):
            self.run_boot()
        self.assertEqual(self.calls,['probe','stage'])

    def test_readback_mismatch_does_not_boot(self):
        self.corrupt = True
        with self.assertRaisesRegex(ValueError,'readback differs'):
            self.run_boot()
        self.assertNotIn('boot',self.calls)

    def test_missing_boot_reply_is_not_retried(self):
        self.ack_timeout = True
        with self.assertRaises(OSError):
            self.run_boot()
        self.assertEqual(self.calls.count('boot'),1)

    def test_no_storage_command_can_use_the_raw_client(self):
        with self.assertRaisesRegex(ValueError,'not permitted'):
            RAM.command(None,1,129,b'flash:boot')


if __name__ == '__main__':
    unittest.main()
