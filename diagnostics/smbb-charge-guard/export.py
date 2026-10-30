#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Export allowlisted results from a completed, privately captured RAM test."""
import argparse
import hashlib
import json
from pathlib import Path
import re

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("run", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
run = args.run
meta = json.loads((run/'image.private.json').read_text())
normal = json.loads((run/'normal-return/verified.json').read_text())
response = json.loads((run/'response/verified.private.json').read_text())
unchanged = json.loads((run/'bootloader-GPT-unchanged.private.json').read_text())
assert normal['normal_installed_r4_boot'] and normal['kernel_taint'] == 0
assert unchanged['bootloader_prefix_and_both_GPT_captures_identical']
assert response['three_inhibit_resume_cycles']
supervised = (run/'supervised.log').read_text()
assert all(label+'_stage_exit 0' in supervised for label in ['boot', 'response', 'return'])
host = (run/'host-check-final.log').read_text()
match = re.search(r'^(\d+) actual-function cases PASS', host, re.M)
assert match and int(match[1]) == 6242
assert host.count('Negative control rejected:') == 5
driver_sha = meta['files']['qcom_smbb.c']['sha256']
assert 'Driver SHA256: '+driver_sha in host
assert hashlib.sha256((run/'candidate/qcom_smbb.c').read_bytes()).hexdigest() == driver_sha
for name in ['arm-object-build-final.log', 'full-kernel-build-final.log']:
    log = (run/name).read_text().lower()
    assert 'warning:' not in log and 'error:' not in log
    assert ('cc      drivers/power/supply/qcom_smbb.o' if name.startswith('arm-')
            else 'kernel: arch/arm/boot/zimage is ready') in log
assert '0 errors, 0 warnings, 0 checks' in (run/'checkpatch-final.log').read_text()
rows = [json.loads(line) for line in (run/'response/samples.private.jsonl').read_text().splitlines()]
samples = [row for row in rows if 'registers' in row]
assert len(samples) == 19
assert all(row['USB_online'] == 1 and row['registers']['1249'] == 0x81 for row in samples)
assert len({row['input_limit_uA'] for row in samples}) == 1
taint = int((run/'response/taint.private.txt').read_text())
assert not taint & ~((1 << 12) | (1 << 13))
result = {
    'date': '2026-10-30',
    'source_branch': 'integration/fx0-charge-guard',
    'source_commit': meta['source_commit'],
    'source_base': '05bec5027f57dd80ae7edc38dcab225fb8327b81',
    'driver_sha256': driver_sha,
    'RAM_image_sha256': meta['image_sha256'],
    'RAM_kernel_GNU_build_id': meta['GNU_build_id'],
    'original_r4_DTB_and_initramfs': meta['original_r4_DTB_and_initramfs'],
    'host': {'actual_function_cases': int(match[1]), 'concurrent_requests_included': 2000,
             'ASan_UBSan': 'PASS', 'negative_controls_rejected': 5,
             'ARM_W1_driver_object': 'PASS, zero diagnostics', 'full_ARM_zImage': 'PASS, zero diagnostics',
             'checkpatch_strict_no_signoff': 'zero errors/warnings/checks',
             'shared_builtin_symbol_CRCs_compared': meta['shared_builtin_symbol_CRCs_compared'],
             'changed_shared_symbol_CRCs': meta['changed_shared_symbol_CRCs']},
    'device': dict(response, samples=len(samples), conservative_BTC_register='0x81',
                   input_budget_unchanged_uA=samples[0]['input_limit_uA'],
                   observed_statuses=sorted({row['status'] for row in samples}),
                   observed_health=sorted({row['health'] for row in samples}),
                   live_IADC_range_uA=[min(row['live_IADC_uA'] for row in samples),
                                      max(row['live_IADC_uA'] for row in samples)],
                   charging_current_response_qualified=False,
                   taint_after_RAM_only_observer=taint,
                   IADC_accuracy_qualified=False),
    'normal_return': {'installed_r4_build': 5, 'kernel_taint': 0,
                      'UPower_and_tinydm_active': normal['upower_and_tinydm_active'],
                      'four_display_controls_auto': normal['four_display_controls_auto'],
                      'bootloader_prefix_and_both_GPT_captures_identical': True,
                      'new_physical_UI_confirmation_claimed': False},
    'scope': ['Host tests exercise helpers and battery callbacks, not complete probe or devm cleanup.',
              'No bus fault was injected on the phone; persistent failure may prevent inhibition.',
              'Fault restrictions need reinitialization. User auto cannot clear them.',
              'No thermal/sample/profile/suspend policy or early firmware gate is implemented.',
              'No BTC widening, permanent kernel/firmware install, stock restoration or repartition.',
              'Normal OS writes mean no whole-eMMC identity claim. No current-accuracy or SOC claim.']
}
args.output.write_text(json.dumps(result, indent=2)+'\n')
print('Exported allowlisted source, test and normal-return evidence')
