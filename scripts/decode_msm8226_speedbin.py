#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Decode a supplied MSM8226-format CPU fuse word; performs no hardware access.

Selection follows get_speed_bin in the MSM8226-matching Qualcomm clock-a7
reference at 866b728388bc6a1d774e8433482a08f11e8245d4 and the Madai vendor
reference at 03aba4427a7666d57b5ae06d375e259ea337f351. This is diagnostic only:
a decoded property name is not proof that a voltage plan exists or is safe.
"""
import argparse
import json
from pathlib import Path


def decode(word: int) -> dict:
    if type(word) is not int or not 0 <= word <= 0xFFFFFFFF:
        raise ValueError('Expected an unsigned 32-bit integer')
    selector = (word >> 24) & 7
    valid = bool(word & 8)
    version = (word >> 4) & 3
    speed = ((word >> 27) & 7) if selector == 1 else word & 7
    if not valid:
        speed = 0
    return {
        'valid': valid,
        'redundant_selector': selector,
        'selected_copy': 'redundant' if selector == 1 else 'primary',
        'speed_bin': speed,
        'pvs_version': version,
        'voltage_plan_property': f'qcom,speed{speed}-bin-v{version}',
        'invalid_speed_fallback': not valid,
    }


def preview_corner(word: int, frequency_hz: int, manifest: dict) -> dict:
    """Preview the vendor clock's first covering fmax entry, never set it."""
    if type(frequency_hz) is not int or frequency_hz <= 0:
        raise ValueError('Expected a positive integer frequency in Hz')
    decoded = decode(word)
    requested = decoded['voltage_plan_property']
    plans = manifest['plans']
    selected = requested if requested in plans else manifest['fallback_plan']
    if selected not in plans:
        raise ValueError('No conservative fallback plan available')
    plan = plans[selected]
    if not plan or plan[0] != [0, 0] or any(
        len(pair) != 2 or any(type(v) is not int or v < 0 for v in pair)
        for pair in plan
    ) or any(a[0] >= b[0] or a[1] >= b[1] for a, b in zip(plan, plan[1:])):
        raise ValueError('Malformed frequency/corner plan')
    for maximum, corner in plan[1:]:
        if frequency_hz <= maximum:
            return {
                'requested_plan': requested,
                'selected_plan': selected,
                'conservative_plan_fallback': selected != requested,
                'requested_frequency_Hz': frequency_hz,
                'covering_max_frequency_Hz': maximum,
                'virtual_CPR_corner': corner,
                'diagnostic_only': True,
            }
    raise ValueError('Frequency exceeds the selected vendor plan')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('word', type=lambda value: int(value, 0), help='Supplied uint32, e.g. 0x2d; never read from hardware')
    parser.add_argument('--frequency', type=int, help='Preview a vendor virtual corner for Hz; never set a clock or voltage')
    parser.add_argument('--plans', type=Path, default=Path(__file__).resolve().parents[1] / 'manifests/msm8926-cpu-corner-plans.json')
    args = parser.parse_args()
    try:
        result = decode(args.word)
        if args.frequency is not None:
            result['corner_preview'] = preview_corner(args.word, args.frequency, json.loads(args.plans.read_text()))
    except ValueError as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
