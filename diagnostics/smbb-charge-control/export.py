#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export only qualified control samples, excluding device identity and logs."""
import argparse
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("capture", type=Path)
parser.add_argument("return_proof", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
rows = [json.loads(line) for line in args.capture.read_text().splitlines()]
proof = json.loads(args.return_proof.read_text())
assert proof["normal_installed_r4_boot"] and proof["kernel_taint"] == 0
assert proof["diagnostic_modules_absent"] and proof["upower_and_tinydm_active"]
samples = [row for row in rows if "manual_IADC_uA" in row]
assert len(samples) == 19 and samples[0]["stage"] == "auto-before"
assert len({row["stage"] for row in samples}) == len(samples)
assert all(samples[i]["boottime_ns"] < samples[i + 1]["boottime_ns"]
           for i in range(len(samples) - 1))
baseline = samples[0]["registers"]
exported = []
for row in samples:
    inhibited = row["stage"].startswith("inhibited-")
    assert row["mode"] == ("inhibit-charge" if inhibited else "auto")
    assert row["USB_online"] == 1 and row["health"] == "Good"
    assert row["input_limit_uA"] == 500000
    assert row["registers"]["1049"] & 0x7f == baseline["1049"] & 0x7f
    assert baseline["1049"] & 1 == 0
    assert bool(row["registers"]["1049"] & 0x80) != inhibited
    assert all(row["registers"][key] == baseline[key] for key in ("1249", "124a"))
    assert row["status"] == ("Not charging" if inhibited else "Charging")
    if inhibited:
        assert abs(row["manual_IADC_uA"]) < 30000
    else:
        assert row["manual_IADC_uA"] > 50000
    exported.append({key: row[key] for key in
                     ("stage", "boottime_ns", "mode", "status", "health",
                      "manual_IADC_uA", "USB_online", "input_limit_uA")})
    exported[-1]["registers"] = {key: row["registers"][key]
                                for key in ("1049", "1249", "124a")}
for cycle in range(3):
    for mode in ("inhibited", "resumed"):
        assert all(any(row["stage"] == f"{mode}-{cycle}-{index}"
                       for row in samples) for index in range(3))
rejected = [row["mode"] for row in rows if row["stage"] == "invalid-mode-rejected"]
assert rejected == ["force-discharge", "inhibit-charge-awake", "invalid"]
assert all(row["control_unchanged"] for row in rows
           if row["stage"] == "invalid-mode-rejected")
cleanup = rows[-1]
assert cleanup["stage"] == "cleanup" and cleanup["control_and_thresholds_restored"]
assert cleanup["original_mode_restored"] == "auto"
assert cleanup["input_limit_restored_uA"] in (100000, 500000)
result = {
    "date": "2026-10-30",
    "kernel_commit": "05bec5027f57dd80ae7edc38dcab225fb8327b81",
    "kernel_base": "5c3efd4c7fa8a8d2bec768d826b5daac57a45e76",
    "kernel_release": "6.18.59",
    "kernel_GNU_build_id": "192ef1e5e8d3af8bbc0f026d3ad5610d20374f48",
    "RAM_image_sha256": "f97d570227c78219fd6fd2771b1f68aab9ba98106f6fedcab063a294ea29d82d",
    "boot": "Full candidate kernel from RAM; original r4 DTB/initramfs and installed root retained",
    "shared_module_symbol_CRCs": {"compared": 14228, "changed": 0},
    "module_signature_caveat": "Old r4 modules and a new build trust key; unsigned-module taint allowed in RAM, out-of-tree observer adds diagnostic taint; no enforcement bypass",
    "host_actual_helper_cases_ASan_UBSan": 1051,
    "full_ARM_LLVM22_W1_build": "PASS; no SMBB diagnostics",
    "checkpatch": "0 errors, 0 warnings, 0 checks",
    "patch_applies_to_upstream_commit": "d89e1d186ec9271bf78e62771779e9fc03bf0fc3",
    "full_current_upstream_build": False,
    "controls": "Only charge-enable changes; forced-battery off, USB online, BTC/reference and current/voltage limits preserved",
    "current": "Unmodified r4 IADC code; positive charging; independent electrical accuracy unverified",
    "thermistor_or_BMS_consumer_loaded": False,
    "samples": exported,
    "unsupported_modes_rejected": rejected,
    "cleanup": {key: cleanup[key] for key in
                ("original_mode_restored", "input_limit_restored_uA", "control_and_thresholds_restored")},
    "normal_return": {key: proof[key] for key in
                      ("normal_installed_r4_boot", "new_boot_id_verified_privately",
                       "kernel_taint", "diagnostic_modules_absent", "four_display_controls_auto",
                       "upower_and_tinydm_active", "physical_UI_retest_claimed")},
    "not_qualified": ["absolute current accuracy or electrically measured zero current",
                      "thermal policy or wider BTC window", "suspend/wake",
                      "unplug/replug", "persistent package integration"],
}
args.output.write_text(json.dumps(result, indent=2) + "\n")
print(f"Exported {len(exported)} allowlisted samples; three cycles and normal return verified")
