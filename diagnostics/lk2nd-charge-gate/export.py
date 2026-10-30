#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export allowlisted gate results without raw logs, unit IDs or storage hashes."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('first', type=Path)
parser.add_argument('qualified', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
first = args.first
run = args.qualified
before = json.loads((first/'preflight.private.json').read_text())
meta = json.loads((run/'preflight.private.json').read_text())
gate = json.loads((run/'gate-qualified.private.json').read_text())
normal = json.loads((run/'normal-return/verified.json').read_text())
unchanged = json.loads((run/'bootloader-GPT-unchanged.private.json').read_text())
assert gate['early_firmware_gate'] and gate['native_charger_driver_disabled']
assert gate['charge_control_hex'] == '00' and gate['BTC_hex'] == '81'
assert unchanged['bootloader_prefix_and_both_GPTs_identical']
assert normal['normal_installed_r4_boot'] and normal['kernel_taint'] == 0
assert 'Completed RAM gate qualification and verified normal r4 return' in (run/'supervised.log').read_text()
early = json.loads((first/'early-gate-messages.private.json').read_text())
assert 'control=00 BTC=82 reference=c0' in early and 'FAIL unexpected-BTC-window' in early
count = re.search(r'PASS: (\d+) actual gate/', (run/'host-gate.log').read_text())
assert count and int(count[1]) == 307
spmi = (first/'host-spmi.log').read_text()
assert spmi.count('PASS: 1024 complete SPMI') == 2
profile = (first/'profile-regression.log').read_text()
assert '128 actual selector/FDT/data/atomic-failure cases' in profile
assert '155 vendor OCV values' in profile
build = (first/'full-firmware-build-conservative.log').read_text()
assert 'error:' not in build and build.count('warning:') == 1
assert 'LOAD segment with RWX permissions' in build
old_source = (run/'source/lk2nd/device/2nd/gpl/lg-madai-charge-gate.c').read_text()
assert 'MADAI_BTC_CONSERVATIVE 0x81' in old_source
result = {
    'date': '2026-10-30',
    'repository': 'https://github.com/timschmidt/fx0-lk2nd',
    'branch': 'integration/fx0-charge-gate',
    'physically_qualified_source_commit': meta['source_commit'],
    'firmware_version': meta['firmware_version'],
    'firmware_image_sha256': meta['firmware_image_sha256'],
    'firmware_image_bytes': meta['firmware_bytes'],
    'diagnostic_image_sha256': meta['diagnostic_image_sha256'],
    'first_run': {'source_commit': before['source_commit'], 'charge_control': '0x00',
                  'inherited_BTC': '0x82', 'reference': '0xc0',
                  'result': 'Inhibition verified; expected narrow-window assertion failed.',
                  'exact_boot_stage_or_reset_writer_traced': False,
                  'normal_r4_return_verified': json.loads((first/'normal-return/verified.json').read_text())['kernel_taint'] == 0},
    'host': {'complete_SPMI_transfer_cases': 2048, 'gate_libfdt_bus_fault_cases': 307,
             'ASan_UBSan': 'PASS', 'existing_battery_profile_cases': 128,
             'all155_vendor_OCV_points_regression': 'PASS',
             'full_GCC15_2_firmware_build': 'PASS; no new-source diagnostics, one linker RWX LOAD warning',
             'physical_SPMI_timeout_timing_measured': False},
    'qualified_RAM_run': {'native_charger_driver': 'disabled for isolation',
                          'firmware_marker': 'present', 'charge_control': '0x00',
                          'BTC': '0x81 conservative/enabled', 'reference': '0xc0 unchanged',
                          'real_fw_devlink_supplier_deferral_tested': False,
                          'eMMC_filesystem_mounted': False, 'automatic_return': True,
                          'RAM_observer_kernel_taint': 12288},
    'normal_return': {'installed_r4_build': 5, 'original_firmware': 'fx0-fd380ac6',
                      'kernel_taint': 0, 'four_display_controls_auto': normal['four_display_controls_auto'],
                      'UPower_and_tinydm_active': normal['upower_and_tinydm_active'],
                      'bootloader_prefix_and_both_GPTs_identical': True,
                      'whole_eMMC_identity_claimed': False, 'physical_UI_retest_claimed': False},
    'scope': ['Firmware opt-in/marker properties are proposed, not accepted upstream bindings.',
              'Linux profile/sensor/thermal worker and handoff validation remain unconnected.',
              'An older driver can re-enable charging after normal setup; this marker is not a complete policy.',
              'Permanent bus failure may prevent inhibition; DT update error currently asserts in aboot.',
              'No persistent firmware/kernel install, gauge reset, factory restoration or repartition.',
              'No charging-current accuracy, SOC, runtime removal, suspend or whole-hardware qualification.']
}
args.output.write_text(json.dumps(result, indent=2)+'\n')
print('Exported allowlisted early-gate evidence and its failed-run boundary')
