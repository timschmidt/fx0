"""Regress the empty BusyBox depmod output found in the first NFC APK."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_kernel_module_dependencies import validate_graph


class DependencyMetadataTests(unittest.TestCase):
    def test_empty_metadata_cannot_hide_declared_dependencies(self):
        declared = {'rfkill': [], 'nfc': ['rfkill'], 'nci': ['nfc'],
                    'nxp-nci': ['nci'], 'i2c': ['nxp-nci', 'nci']}
        with self.assertRaisesRegex(ValueError, 'differs from signed module dependencies'):
            validate_graph(declared, {name: [] for name in declared})
        correct = {'rfkill': [], 'nfc': ['rfkill'], 'nci': ['nfc', 'rfkill'],
                   'nxp-nci': ['nci', 'nfc', 'rfkill'],
                   'i2c': ['nxp-nci', 'nci', 'nfc', 'rfkill']}
        self.assertEqual(validate_graph(declared, correct)['i2c'], set(correct['i2c']))

    def test_missing_and_cyclic_dependencies_are_rejected(self):
        for declared, recorded in [({'a': ['b']}, {'a': ['b']}),
                                    ({'a': ['b'], 'b': ['a']}, {'a': ['b'], 'b': ['a']})]:
            with self.assertRaises(ValueError):
                validate_graph(declared, recorded)


if __name__ == '__main__':
    unittest.main()
