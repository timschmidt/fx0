import array
import importlib.util
import math
import pathlib
import random
import sys
import tempfile
import unittest
import wave

SPEC = importlib.util.spec_from_file_location(
    "check_audio_tone", pathlib.Path(__file__).resolve().parents[1] / "scripts/check_audio_tone.py")
tone = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(tone)


class ToneMeasurement(unittest.TestCase):
    def test_tone_level_and_dc_rejection(self):
        samples = [round(1000 + 12000 * math.sin(2 * math.pi * 1000 * n / 48000))
                   for n in range(4800)]
        result = tone.measure(samples, 48000, 1000)
        expected = 20 * math.log10(12000 / (32768 * math.sqrt(2)))
        self.assertAlmostEqual(result["tone_dbfs"], expected, places=3)
        self.assertGreater(result["tone_power_fraction"], 0.999)
        self.assertAlmostEqual(result["dc_offset"], 1000)
        self.assertEqual(result["clipped_samples"], 0)

    def test_silence_noise_and_other_frequency(self):
        result = tone.measure([0] * 4800, 48000, 1000)
        self.assertIsNone(result["tone_dbfs"])
        self.assertEqual(result["tone_power_fraction"], 0)
        rng = random.Random(72)
        noise = [rng.randrange(-1000, 1001) for _ in range(4800)]
        self.assertLess(tone.measure(noise, 48000, 1000)["tone_power_fraction"], 0.01)
        other = [round(10000 * math.sin(2 * math.pi * 2000 * n / 48000))
                 for n in range(4800)]
        self.assertLess(tone.measure(other, 48000, 1000)["tone_power_fraction"], 1e-8)
        self.assertEqual(tone.measure([-32768, 32767], 48000, 1000)["clipped_samples"], 2)

    def test_channel_selection_windows_and_format_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "capture.wav"
            data = array.array("h")
            for n in range(4800 * 2 + 10):
                # First window silent, second window has tone only in channel 1.
                value = round(12000 * math.sin(2 * math.pi * 1000 * n / 48000))
                data.extend((0, value if n >= 4800 else 0))
            if sys.byteorder != "little":
                data.byteswap()
            with wave.open(str(path), "wb") as wav:
                wav.setparams((2, 2, 48000, 0, "NONE", "not compressed"))
                wav.writeframes(data.tobytes())
            left = tone.analyze(path)
            right = tone.analyze(path, channel=1)
            self.assertEqual(len(right["windows"]), 2)
            self.assertIsNone(right["windows"][0]["tone_dbfs"])
            self.assertGreater(right["windows"][1]["tone_power_fraction"], 0.999)
            self.assertEqual(right["windows"][1]["start_seconds"], 0.1)
            self.assertTrue(all(w["tone_dbfs"] is None for w in left["windows"]))
            for kwargs in ({"channel": 2}, {"frequency": 24000}, {"window_ms": 0},
                           {"window_ms": 99.5}):
                with self.assertRaises(ValueError):
                    tone.analyze(path, **kwargs)
            with wave.open(str(path), "wb") as wav:
                wav.setparams((1, 3, 48000, 0, "NONE", "not compressed"))
                wav.writeframes(bytes(4800 * 3))
            with self.assertRaisesRegex(ValueError, "16-bit"):
                tone.analyze(path)


if __name__ == "__main__":
    unittest.main()
