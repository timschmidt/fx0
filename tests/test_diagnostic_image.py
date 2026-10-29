"""Check Fx0 RAM image placement without accessing a device."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('image', Path(__file__).parents[1] / 'scripts/make_diagnostic_image.py')
image = importlib.util.module_from_spec(spec)
spec.loader.exec_module(image)


class RamdiskPlacement(unittest.TestCase):
    def setUp(self):
        self.kernel = bytearray(48)
        struct.pack_into('<I', self.kernel, 36, 0x016f2818)
        self.dtb = bytes.fromhex('d00dfeed')

    def test_inherited_framebuffer_boundary(self):
        # lk2nd loads the ramdisk at 32 MiB; framebuffer starts at 50 MiB.
        ramdisk = bytes(0x01200000)
        data = image.make_image(self.kernel, self.dtb, ramdisk, 'lk2nd.pass-simplefb=autorefresh')
        self.assertEqual(struct.unpack_from('<I', data, 20)[0], 0x02000000)
        self.assertEqual(struct.unpack_from('<I', data, 16)[0], len(ramdisk))
        with self.assertRaisesRegex(ValueError, 'overlaps inherited'):
            image.make_image(self.kernel, self.dtb, ramdisk + b'x', 'lk2nd.pass-simplefb')

    def test_no_inherited_buffer_does_not_use_its_reservation(self):
        image.make_image(self.kernel, self.dtb, bytes(0x01200001), 'console=tty0')

    def test_kernel_cannot_overlap_forced_ramdisk_slot(self):
        large = self.kernel + bytes(0x02000000)
        with self.assertRaisesRegex(ValueError, 'do not fit'):
            image.make_image(large, self.dtb, b'initrd', '')


if __name__ == '__main__':
    unittest.main()
