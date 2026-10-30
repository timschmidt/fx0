#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export allowlisted hardware/host results, including the resumed return."""
import argparse
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('prepared', type=Path)
parser.add_argument('qualified', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
prepared, run = args.prepared, args.qualified
meta = json.loads((run/'preflight.private.json').read_text())
qualified = json.loads((run/'policy-qualified.private.json').read_text())
normal = json.loads((run/'normal-return/verified.json').read_text())
resume = json.loads((run/'resumed-return.private.json').read_text())
cleanup = json.loads((run/'host-network-cleanup-verified.private.json').read_text())
gpt = json.loads((run/'bootloader-GPT-unchanged.private.json').read_text())
assert all(qualified.values()) and normal['kernel_taint'] == 0
assert resume['normal_return_resumed_successfully'] and not resume['hardware_test_repeated']
assert cleanup['no_owned_prefix_profiles_remain'] and cleanup['duplicate_deleted_name_cleanup_regression_passed']
assert gpt['bootloader_prefix_and_both_GPTs_identical']
assert not json.loads((prepared/'not-booted.private.json').read_text())['booted']
messages = json.loads((run/'policy-messages.private.json').read_text())
assert 'kernel_notes_sha256='+meta['kernel_notes_sha256'] in messages
assert 'firmware='+meta['firmware_version'] in messages
assert not any('FAIL ' in value or 'TIMEOUT ' in value for value in messages)
assert 'taint=12288' in messages
assert 'explicit policy drivers_probe needed after supplier rebind' in messages
snapshots, readings = {}, {}
for value in messages:
    match = re.fullmatch(r'([A-Za-z-]+) mode=(auto|inhibit-charge) control=([0-9a-f]{2}) BTC=([0-9a-f]{2}) reference=([0-9a-f]{2})', value)
    if match:
        stage, mode, control, btc, reference = match.groups()
        assert btc == '81' and reference == 'c0'
        snapshots[stage] = {'mode': mode, 'charge_control': '0x'+control}
    match = re.fullmatch(r'([A-Za-z-]+) running=1 votes=0x([0-9a-f]+) state=(\d+) temp_decic=(-?\d+) voltage_uV=(\d+) error=0 age_ms=(\d+)', value)
    if match:
        stage, votes, state, temperature, voltage, age = match.groups()
        readings[stage] = dict(votes=int(votes, 16), state=int(state), temperature_decic=int(temperature), voltage_uV=int(voltage), age_ms=int(age))
for stage in ['provider-missing', 'provider-missing-USB-online', 'user-inhibit', 'provider-unbound']:
    assert snapshots[stage] == {'mode': 'inhibit-charge', 'charge_control': '0x00'}
for stage in ['provider-bound', 'user-auto', 'provider-rebound']:
    assert snapshots[stage] == {'mode': 'auto', 'charge_control': '0x80'}
assert readings['user-inhibit']['votes'] == 2
assert readings['provider-bound']['votes'] == readings['provider-rebound']['votes'] == 0
packets = [row['body'].split()[0] for row in json.loads((run/'HTTP-stages.private.json').read_text())]
assert 'provider-missing' in packets and 'provider-unbound' in packets
assert '21496 actual conversion/LG transition cases' in (prepared/'model-check.log').read_text()
assert '2604 actual policy worker/' in (prepared/'control-check.log').read_text()
assert '6242 actual-function cases PASS' in (prepared/'control-check.log').read_text()
assert '41 actual runtime policy identity/' in (prepared/'firmware-identity-check.log').read_text()
assert '84 battery-unit/' in (prepared/'VADC-units-regression.log').read_text()
for name in ['schema-doc.log', 'schema-process.log', 'schema-DTB.log']:
    assert not (prepared/name).read_text()
for name in ['full-kernel-build-provider-ABI.log', 'strict-ADC-modules-corrected.log']:
    text = (prepared/name).read_text()
    assert 'warning:' not in text and 'error:' not in text
text = (run/'ARM-driver-final.log').read_text()
assert 'warning:' not in text and 'error:' not in text
result = {
    'date': '2026-10-30', 'kernel_branch': 'integration/fx0-charging-policy',
    'kernel_commit': meta['kernel_source_commit'], 'firmware_branch': 'integration/fx0-policy-profile',
    'firmware_commit': meta['firmware_source_commit'], 'firmware_version': meta['firmware_version'],
    'kernel_GNU_build_id': meta['GNU_build_id'], 'RAM_diagnostic_sha256': meta['diagnostic_image_sha256'],
    'RAM_firmware_sha256': meta['firmware_image_sha256'],
    'host': {'model_stock_comparison_cases': 21496, 'policy_cases': 2604, 'legacy_control_cases': 6242,
             'concurrent_requests_included': 4500, 'runtime_firmware_identity_cases': 41, 'VADC_ABI_cases': 84,
             'ASan_UBSan': 'PASS', 'ARM_driver_W1': 'PASS', 'ARM_ADC_modules_W1': 'PASS',
             'full_ARM_zImage': 'PASS', 'static_and_runtime_DTB_schema_diagnostics': 0,
             'shared_builtin_symbol_CRCs_compared': meta['shared_builtin_symbol_CRCs_compared'],
             'changed_shared_symbol_CRCs': 0},
    'device': {'snapshots': snapshots, 'reported_readings': readings, 'USB_HTTP_stages_observed': packets,
               'initial_missing_provider_auto_probe': True, 'forced_unbind_auto_reprobe': False,
               'forced_unbind_explicit_drivers_probe_used': True, 'BTC': '0x81 conservative/enabled',
               'reference': '0xc0 unchanged', 'RAM_taint': 12288, 'eMMC_filesystem_mounted': False,
               'charging_current_or_SOC_qualified': False, 'absolute_sensor_accuracy_qualified': False},
    'host_cleanup': {'duplicate_profile_names_caused_redundant_delete_failure': True,
                     'hardware_test_repeated': False, 'same_return_resumed': True,
                     'all_temporary_profiles_absent': True, 'idempotence_regression': 'PASS'},
    'normal_return': {'installed_r4_build': 5, 'taint': 0, 'normal_services_active': True,
                      'four_display_controls_auto': True, 'bootloader_prefix_and_both_GPTs_identical': True,
                      'whole_eMMC_identity_claimed': False, 'physical_UI_retest_claimed': False},
    'scope': ['RAM integration prototype; no permanent firmware/kernel installation or accepted binding ABI.',
              'Initial prepared candidate with old raw-code ADC modules was never booted.',
              'Real system suspend, hardware-watchdog deadline, physical thermal boundaries and termination remain unqualified.',
              'Direct pack authentication and unobserved replacement remain open; observed loss is latched until reboot.',
              'No factory restoration/repartition, current accuracy, capacity estimator or whole-hardware completion.']
}
args.output.write_text(json.dumps(result, indent=2)+'\n')
print('Exported allowlisted native policy/supplier evidence and resumed-return boundary')
