#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export allowlisted results; never export boot arguments or storage fingerprints."""
import argparse
import hashlib
import json
import math
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("capture", type=Path, help="Completed successful handoff capture")
parser.add_argument("output", type=Path)
args = parser.parse_args()


def read(relative):
    return json.loads((args.capture / relative).read_text())


metadata = read("manifest.private.json")
assert metadata["two_independent_backup_filesystems"]
assert hashlib.sha256((args.capture / "lk2nd-battery-handoff.img").read_bytes()).hexdigest() == metadata["image_sha256"]
core = read("RAM-test/core-result.private.json")
before = read("before.private.json")
qualification = read("RAM-test/core-qualified.json")
result = read("RAM-test/profile-result.private.json")
returned = read("normal-return/verified.json")
storage = read("normal-return/storage-unchanged.json")
assert qualification["all155_OCV_points_match_as_built_source"]
assert qualification["rated_capacity_and_charge_voltage_match"]
assert core["rated_charge_full_design_uAh"] == 2370000
assert core["constant_charge_voltage_max_uV"] == 4350000
assert core["ocv_temperatures_C"] == [-20, 0, 25, 40, 60]
assert core["capacity_property_absent"] and core["taint"] == 0
assert core["current_max_uA"] == int(before["supplies"]["current_max"])
assert core["voltage_max_uV"] == int(before["supplies"]["voltage_max"])
assert returned["kernel_taint"] == 0 and returned["upower_and_tinydm_active"]
assert all(storage[key] for key in
           ("installed_bootloader_prefix_unchanged", "primary_GPT_unchanged",
            "backup_GPT_unchanged", "profile_absent_after_original_firmware_return",
            "new_charge_full_design_attribute_absent"))
assert not (args.capture / "RAM-test/qualification-error.private.txt").exists()
upower = result["UPower"]
assert "DisplayDevice" in upower
assert upower["DisplayDevice"]["IsPresent"] == "b false"
assert upower["DisplayDevice"]["State"] == "u 0"
for row in upower.values():
    assert int(row["WarningLevel"].split()[1]) < 4
    assert math.isfinite(float(row["Percentage"].split()[1]))

evidence = {
    "date": "2026-10-30",
    "purpose": "Select removable-pack characteristics in firmware and verify existing kernel consumption",
    "firmware_source_commit": metadata["source_commit"],
    "firmware_version": metadata["firmware_version"],
    "RAM_firmware_image_sha256": metadata["image_sha256"],
    "RAM_firmware_image_bytes": metadata["image_bytes"],
    "GCC": metadata["GCC"],
    "firmware_build": "Full build passes; one linker RWX LOAD warning; no new-source compiler diagnostics",
    "firmware_debug_configuration": "Force fastboot at startup; installed filesystem r4 boot follows explicit continue",
    "first_stage_battery_type": "ISL6296_L, exactly one argument; boot-time selection, not live authentication",
    "Linux_kernel": "Installed signed 6.18.59-r4 build5; no package or module changes",
    "kernel_taint": 0,
    "profile": {key: core[key] for key in
                ("rated_charge_full_design_uAh", "constant_charge_voltage_max_uV",
                 "ocv_temperatures_C", "matched_consumers", "capacity_property_absent")},
    "all155_vendor_source_OCV_points_verified_in_running_kernel": True,
    "OCV_table_sha256": core["OCV_table_sha256"],
    "source_provenance": "Vendor03aba4427a7666d57b5ae06d375e259ea337f351, TOCAD_MADAI_Final.c; rated2370mAh from KDDI, distinct from nominal2440 and measured FCC",
    "host_actual_selector_FDT_fault_cases_ASan_UBSan": 128,
    "old_unaligned_workspace_failure_reproduced": True,
    "original_failure_address_or_return_code_captured_on_device": False,
    "schema": "Modified docs and generated R4/BMS DTBs pass with complete regulator dependency; baseline schemas reject monitored-battery",
    "prototype_BMS_consumer": "Host/FDT-schema qualification only; not loaded in physical run",
    "charger_observation": {key: core[key] for key in
                            ("status", "health", "current_max_uA", "voltage_max_uV",
                             "original_input_budget_uA", "development_input_budget_uA")},
    "configured_charger_current_and_voltage_limits_match_before": True,
    "extended_BTC_requested_by_change": False,
    "UPower_probe": {
        "ordinary_unit_temporarily_masked": True,
        "transient_Type": "dbus",
        "runtime_limit_s": 10,
        "stop_timeout_s": 1,
        "installed_critical_action_delay_s": 20,
        "actual_NameHasOwner_checked": True,
        "DisplayDevice": upower["DisplayDevice"],
        "usable_battery_interface_qualified": False,
        "note": "DisplayDevice not present and state unknown; percentage0 is not battery SOC. No usable BIF battery object was observed.",
    },
    "normal_return": {key: returned[key] for key in
                      ("normal_installed_r4_boot", "new_boot_id_verified_privately",
                       "kernel_taint", "four_display_controls_auto", "upower_and_tinydm_active",
                       "physical_UI_retest_claimed")},
    "storage_and_cleanup": storage,
    "two_independent_host_backup_filesystems": True,
    "installed_firmware_updated": False,
    "whole_eMMC_unchanged_claimed": False,
    "factory_stock_rehearsal_claimed": False,
    "prior_runs": [
        {"run": "01", "source": "47a77fa", "result": "Pack recognized; returned to original fastboot before Linux SSH. Four-byte allocation defect independently reproduced; exact physical failing address not captured. Original firmware/r4/storage restored."},
        {"run": "02", "source": "b4a9930", "result": "Aligned firmware boots r4 with profile. Probe mistook activatable bus name for owned name; masked activation triggers upower CLI SIGSEGV. Original firmware/r4/storage restored; complete native table-hash check not claimed for this run."},
    ],
    "not_qualified": ["battery capacity or absolute sensor accuracy", "charging thermal policy or broader BTC window",
                      "learned FCC and current/counter discrepancy", "live authentication and replacement",
                      "automatic boot of a non-debug firmware build", "persistent firmware deployment",
                      "UPower CLI error handling after failed activation", "suspend and full hardware acceptance"],
}
args.output.write_text(json.dumps(evidence, indent=2) + "\n")
print("Exported qualified core/profile and normal-return results without unit identity or raw fingerprints")
