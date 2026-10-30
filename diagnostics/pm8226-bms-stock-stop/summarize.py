#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export selected measurements; never export raw register maps or calibration."""
import argparse
import json
import re
from pathlib import Path


def summarize(text):
    samples = []
    previous_trim = None
    for block in text.split("SAMPLE ")[1:]:
        lines = block.splitlines()
        tag = lines[0]
        if not re.fullmatch(r"(?:charging-before|stopped|restarted)-[0-9]+", tag):
            raise ValueError("Unexpected sample tag")
        sample = {"tag": tag}
        supply = None
        for index, line in enumerate(lines):
            if line.startswith("UPTIME "):
                sample["uptime_s"] = float(line.split()[1])
            elif line.startswith("REGISTER_0x"):
                address = line.removeprefix("REGISTER_0x")
                # Use only known registers. The trim comparison never exports bytes.
                if address not in {"1049", "1210", "4098", "36f2"}:
                    continue
                raw = bytes(int(x, 16) for x in lines[index + 1].split())
                if address == "1049":
                    sample["charge_enabled"] = bool(raw[0] & 128)
                    sample["force_battery"] = bool(raw[0] & 1)
                elif address == "1210":
                    sample["BATFET_closed_snapshot"] = bool(raw[0] & 4)
                elif address == "4098":
                    sample["VSENSE_raw_signed"] = int.from_bytes(raw, "little", signed=True)
                else:
                    sample["trim_changed_since_previous"] = (
                        None if previous_trim is None else raw != previous_trim
                    )
                    previous_trim = raw
            elif line.startswith("SUPPLY "):
                supply = line.split()[1]
            elif line == "ADC_EXTERNAL_RSENSE":
                supply = None
                result = re.search(r"Result:\s*(-?[0-9]+)", lines[index + 1])
                if result:
                    sample["manual_IADC_uA"] = int(result[1])
            elif supply in {"battery", "bms"} and "=" in line:
                key, value = line.split("=", 1)
                if key in {"status", "health"}:
                    if value not in {"Charging", "Discharging", "Not charging", "Full", "Unknown", "Good", "Overheat", "Cold"}:
                        raise ValueError("Unexpected supply state")
                    sample[f"{supply}_{key}"] = value
                elif key in {"current_now", "voltage_now", "temp", "charge_counter", "charge_counter_shadow"}:
                    sample[f"{supply}_{key}"] = int(value)
        samples.append(sample)
    if not samples or "CAPTURE_COMPLETED" not in text:
        raise ValueError("Incomplete capture")
    return {
        "stock_current_sign": "negative charging; manual IADC positive charging",
        "raw_register_atomicity": "VSENSE/BATFET reads are not a latched joint snapshot",
        "samples": samples,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("capture", type=Path)
    args = parser.parse_args()
    print(json.dumps(summarize(args.capture.read_text(errors="replace")), indent=2))
