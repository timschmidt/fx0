import importlib.util
from pathlib import Path
import unittest
import json

spec = importlib.util.spec_from_file_location('speedbin', Path(__file__).resolve().parents[1] / 'scripts/decode_msm8226_speedbin.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class SpeedbinTests(unittest.TestCase):
    def test_stock_corner_votes_and_version_difference(self):
        plans = json.loads((Path(__file__).resolve().parents[1] / 'manifests/msm8926-cpu-corner-plans.json').read_text())
        self.assertEqual(module.preview_corner(8, 300000000, plans)['virtual_CPR_corner'], 2)
        self.assertEqual(module.preview_corner(8, 600000000, plans)['virtual_CPR_corner'], 4)
        self.assertEqual(module.preview_corner(8, 998400000, plans)['virtual_CPR_corner'], 7)
        self.assertEqual(module.preview_corner(0x18, 998400000, plans)['virtual_CPR_corner'], 5)
        self.assertEqual(module.preview_corner(0x1D, 1785600000, plans)['virtual_CPR_corner'], 14)

    def test_unknown_plan_uses_separate_conservative_fallback(self):
        plans = json.loads((Path(__file__).resolve().parents[1] / 'manifests/msm8926-cpu-corner-plans.json').read_text())
        result = module.preview_corner(0x3F, 998400000, plans)
        self.assertTrue(result['conservative_plan_fallback'])
        self.assertEqual(result['selected_plan'], 'qcom,speed0-bin-v0')
        self.assertEqual(result['virtual_CPR_corner'], 7)
        with self.assertRaises(ValueError):
            module.preview_corner(8, 1190400001, plans)

    def test_malformed_or_missing_conservative_plan_rejected(self):
        for plans in [{'plans': {}, 'fallback_plan': 'missing'},
                      {'plans': {'fallback': [[0, 0], [2, 2], [1, 3]]}, 'fallback_plan': 'fallback'}]:
            with self.assertRaises(ValueError):
                module.preview_corner(8, 1, plans)

    def test_primary_valid_with_version(self):
        result = module.decode(0x2D)
        self.assertEqual((result['speed_bin'], result['pvs_version'], result['valid']), (5, 2, True))
        self.assertEqual(result['voltage_plan_property'], 'qcom,speed5-bin-v2')

    def test_redundant_copy_only_for_selector_one(self):
        self.assertEqual(module.decode(0x31000019)['speed_bin'], 6)
        self.assertEqual(module.decode(0x32000019)['speed_bin'], 1)
        self.assertEqual(module.decode(0x31000019)['selected_copy'], 'redundant')

    def test_invalid_fuse_falls_back_speed_but_retains_version(self):
        result = module.decode(0x31000031)
        self.assertEqual((result['speed_bin'], result['pvs_version']), (0, 3))
        self.assertTrue(result['invalid_speed_fallback'])
        self.assertEqual(result['voltage_plan_property'], 'qcom,speed0-bin-v3')

    def test_extremes_and_unrelated_high_bit(self):
        self.assertEqual(module.decode(0)['voltage_plan_property'], 'qcom,speed0-bin-v0')
        self.assertEqual(module.decode(0xFFFFFFFF)['voltage_plan_property'], 'qcom,speed7-bin-v3')
        self.assertEqual(module.decode(0x8000002D), module.decode(0x2D))

    def test_reject_non_uint32(self):
        for word in [-1, 0x100000000, True, '0x2d']:
            with self.subTest(word=word), self.assertRaises(ValueError):
                module.decode(word)


if __name__ == '__main__':
    unittest.main()
