# SPDX-License-Identifier: MIT
import unittest

from summarize import summarize


class SummaryTest(unittest.TestCase):
    def capture(self, trim="01 02 03 04", suffix=""):
        return f"""SAMPLE stopped-1
UPTIME 34.01 100.00
REGISTER_0x1049
00
REGISTER_0x1210
00
REGISTER_0x4098
fb ff
REGISTER_0x36f2
{trim}
SUPPLY battery
health=Good
status=Full
current_now=-2593
serial_number=PRIVATE_UNIT
SUPPLY bms
charge_counter=0
ADC_EXTERNAL_RSENSE
Result:0
{suffix}
CAPTURE_COMPLETED
"""

    def test_selected_values_and_signs(self):
        row = summarize(self.capture())["samples"][0]
        self.assertEqual(row["VSENSE_raw_signed"], -5)
        self.assertFalse(row["charge_enabled"])
        self.assertFalse(row["force_battery"])
        self.assertFalse(row["BATFET_closed_snapshot"])
        self.assertEqual(row["battery_current_now"], -2593)
        self.assertEqual(row["manual_IADC_uA"], 0)

    def test_private_unknown_fields_are_excluded(self):
        result = str(summarize(self.capture()))
        self.assertNotIn("PRIVATE_UNIT", result)
        self.assertNotIn("01 02 03 04", result)
        self.assertNotIn("36f2", result)

    def test_only_trim_change_boolean_escapes(self):
        blocks = [self.capture().replace("CAPTURE_COMPLETED", ""),
                  self.capture("05 06 07 08")]
        rows = summarize("".join(blocks))["samples"]
        self.assertIsNone(rows[0]["trim_changed_since_previous"])
        self.assertTrue(rows[1]["trim_changed_since_previous"])

    def test_incomplete_capture_rejected(self):
        with self.assertRaises(ValueError):
            summarize(self.capture().replace("CAPTURE_COMPLETED", ""))

    def test_unknown_tag_rejected(self):
        with self.assertRaises(ValueError):
            summarize(self.capture().replace("stopped-1", "PRIVATE_UNIT"))

    def test_unknown_supply_state_rejected(self):
        with self.assertRaises(ValueError):
            summarize(self.capture().replace("status=Full", "status=PRIVATE_UNIT"))


if __name__ == "__main__":
    unittest.main()
