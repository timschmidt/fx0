#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check the observable stages in an Fx0 USB budget trace or ramoops console."""
import argparse
from decimal import Decimal
import json
from pathlib import Path


def samples(path):
    rows = {}
    for line in path.read_text(errors='replace').splitlines():
        if 'fx0-usb-budget: SAMPLE ' in line:
            line = line.split('fx0-usb-budget: SAMPLE ', 1)[1]
        if not line.startswith('uptime_s='):
            continue
        row = dict(word.split('=', 1) for word in line.split())
        row['uptime_s'] = Decimal(row['uptime_s'])
        key = tuple(sorted(row.items()))
        rows[key] = row
    return sorted(rows.values(), key=lambda row: row['uptime_s'])


def check_budget(rows, mode):
    valid = [row for row in rows if row.get('mode') == mode]
    exact_mode = len(valid) == len(rows)
    off = all(row['charging'] == 'inhibited' and not int(row['charge_control'], 16) & 0x81
              for row in valid)
    battery = all(row['battery'] == '1' and int(row['battery_presence'], 16) & 0x80 for row in valid)
    otg_clear = all(not int(row['usb_otg'], 16) & 1 for row in valid)

    def programmed(row, mA):
        return (int(row['imax_selector'], 16) == mA // 100 if mA > 100 else row['imax_selector'] == '00')

    def configured(row, phase):
        return row['phase'] == phase and row['bound'] == '1' and row['state'] == 'configured'

    def active_limit(row, mA):
        return (int(row['input_uA']) == mA * 1000 and programmed(row, mA)
                and not int(row['usb_suspend'], 16) & 1)

    sequence = [('pre_bind', lambda row: row['phase'] == 'pre_bind' and row['bound'] == '0', 100),
                ('configured_500', lambda row: configured(row, 'bind_500'), 500),
                ('detached', lambda row: row['phase'] == 'detach' and row['bound'] == '0', 100),
                ('configured_300', lambda row: configured(row, 'bind_300'), 300)]
    first = {}
    previous = Decimal('-1')
    for name, predicate, mA in sequence:
        observation = next((row for row in valid
                            if row['uptime_s'] > previous and predicate(row)
                            and (mode == 'control' or active_limit(row, mA))), None)
        if observation is None:
            break
        first[name] = observation
        previous = observation['uptime_s']
    if mode == 'control':
        settings = {(row['input_uA'], row['imax_selector'], row['usb_suspend']) for row in valid}
        stable_control = len(settings) == 1
    else:
        stable_control = None

    suspend = next((row for row in valid if row['phase'] == 'bind_500' and row['bound'] == '1'
                    and row['state'] == 'suspended' and row['input_uA'] == '0'
                    and int(row['usb_suspend'], 16) & 1 and int(row['usb_rt'], 16) & 2
                    and 'configured_500' in first
                    and row['uptime_s'] > first['configured_500']['uptime_s']), None)
    resume = next((row for row in valid if suspend and row['uptime_s'] > suspend['uptime_s']
                   and configured(row, 'bind_500') and active_limit(row, 500)), None)
    automatic = (len(first) == len(sequence) and exact_mode and off and battery and otg_clear
                 and stable_control is not False)
    return {'mode': mode, 'trace_rows': len(rows), 'samples_valid': exact_mode,
            'battery_present_in_all_samples': bool(valid) and battery,
            'charge_inhibited_in_all_samples': bool(valid) and off,
            'OTG_clear_in_all_samples': bool(valid) and otg_clear,
            'automatic_stages_passed': automatic, 'stable_control_limit': stable_control,
            'stage_uptime_s': {name: str(row['uptime_s']) for name, row in first.items()},
            'managed_suspend_with_VBUS_valid': suspend is not None,
            'managed_suspend_resume_passed': resume is not None,
            'actual_current_measured': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('trace', type=Path)
    parser.add_argument('--mode', choices=['managed', 'control'], required=True)
    parser.add_argument('--require-suspend', action='store_true')
    args = parser.parse_args()
    if args.require_suspend and args.mode != 'managed':
        parser.error('--require-suspend applies to the managed image')
    result = check_budget(samples(args.trace), args.mode)
    print(json.dumps(result, indent=2))
    if not result['automatic_stages_passed'] or (
            args.require_suspend and not result['managed_suspend_resume_passed']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
