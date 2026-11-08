#!/usr/bin/env python3
"""Measure a known tone in PCM16 WAV captures; never infer a hardware pass.

Use explicit S16_LE capture to avoid repeating the historical mis-packed
24-bit microphone measurement. Keep captures in ignored local/ directories.
A tone measurement alone cannot prove the microphone, speaker route or volume.
"""
import argparse
import array
import cmath
import json
import math
import sys
import wave


def dbfs(power):
    return 10 * math.log10(power / (32768 ** 2)) if power > 0 else None


def measure(samples, rate, frequency):
    if not samples:
        raise ValueError("empty analysis window")
    mean = sum(samples) / len(samples)
    centered = [sample - mean for sample in samples]
    power = sum(sample * sample for sample in centered) / len(centered)
    rotation = cmath.exp(-2j * math.pi * frequency / rate)
    phase = 1 + 0j
    coefficient = 0j
    for sample in centered:
        coefficient += sample * phase
        phase *= rotation
    tone_power = min(power, 2 * abs(coefficient) ** 2 / len(centered) ** 2)
    return {
        "rms_dbfs": dbfs(power),
        "tone_dbfs": dbfs(tone_power),
        "tone_power_fraction": tone_power / power if power else 0,
        "dc_offset": mean,
        "clipped_samples": sum(s in (-32768, 32767) for s in samples),
    }


def analyze(path, frequency=1000, channel=0, window_ms=100):
    with wave.open(str(path), "rb") as wav:
        if wav.getsampwidth() != 2 or wav.getcomptype() != "NONE":
            raise ValueError("require uncompressed signed 16-bit PCM WAV")
        rate, channels = wav.getframerate(), wav.getnchannels()
        if not 0 < frequency < rate / 2:
            raise ValueError("tone frequency must be below Nyquist and positive")
        if not 0 <= channel < channels:
            raise ValueError("capture channel is out of range")
        size = round(rate * window_ms / 1000)
        if size < 2 or frequency * size / rate < 2:
            raise ValueError("window must contain at least two tone cycles")
        # Integral cycles make the single-frequency power estimate comparable
        # with the broadband RMS without window leakage corrections.
        cycles = frequency * size / rate
        if not math.isclose(cycles, round(cycles), abs_tol=1e-8):
            raise ValueError("choose a window containing an integral number of tone cycles")
        windows = []
        index = 0
        while raw := wav.readframes(size):
            if len(raw) != size * channels * 2:
                break  # Do not compare an incomplete trailing window.
            samples = array.array("h")
            samples.frombytes(raw)
            if sys.byteorder != "little":
                samples.byteswap()
            result = measure(samples[channel::channels], rate, frequency)
            result["start_seconds"] = index * size / rate
            windows.append(result)
            index += 1
        if not windows:
            raise ValueError("capture has no complete analysis windows")
    return {
        "sample_rate": rate,
        "channel": channel,
        "frequency": frequency,
        "window_samples": size,
        "windows": windows,
        "qualification": "Measurement only; no automatic hardware pass or route assertion.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture")
    parser.add_argument("--frequency", type=float, default=1000)
    parser.add_argument("--channel", type=int, default=0, help="zero-based capture channel")
    parser.add_argument("--window-ms", type=float, default=100)
    args = parser.parse_args()
    try:
        result = analyze(args.capture, args.frequency, args.channel, args.window_ms)
    except (ValueError, OSError, wave.Error) as exc:
        parser.exit(2, f"{exc}\n")
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
