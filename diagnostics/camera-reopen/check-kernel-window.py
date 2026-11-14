#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Classify the independent full camera-test kernel window, including unknown diagnostics."""
import argparse
import json
from pathlib import Path
import re

CAMERA = re.compile(r'camss|imx132|imx179|csid|csiphy|\bvfe\b|ispif|\bcci\b', re.I)
FAULT = re.compile(r'underrun|context fault|iommu.*fault|kernel bug|oops:|kernel panic|watchdog|'
                   r'missing ready buf|active buffer mismatch|last buff in wrong state|'
                   r'received wm done for unmapped|inactive buffer is busy|output idle with buffer set', re.I)
CAMERA_FAILURE = re.compile(r'error|fail|timeout|overflow', re.I)


def classify(rows):
    issues = []
    for row in rows:
        message = row['message']
        priority = row.get('priority')
        if priority is not None:
            priority = int(priority)
            if not 0 <= priority <= 7:
                raise ValueError('invalid journal priority')
        reason = None
        if FAULT.search(message):
            reason = 'explicit kernel diagnostic'
        elif CAMERA.search(message):
            if CAMERA_FAILURE.search(message):
                reason = 'camera failure diagnostic'
            elif priority is None:
                reason = 'camera message without severity; requires classification'
            elif priority <= 5:
                reason = 'camera notice/warning/error requires classification'
        elif priority is not None and priority <= 3:
            reason = 'kernel error during camera test'
        if reason:
            issues.append({'message': message, 'reason': reason})
    return {'kernel_messages_checked': len(rows), 'unresolved_diagnostics': issues,
            'clean_kernel_window': not issues}


def self_test():
    cases = [
        ({'message': 'qcom-camss: Missing ready buf 1 4!'}, False),
        ({'message': 'qcom-camss: future diagnostic'}, False),
        ({'message': 'qcom-camss: camera registered', 'priority': '6'}, True),
        ({'message': 'qcom-camss: future diagnostic', 'priority': '4'}, False),
        ({'message': 'qcom-camss: camera timeout', 'priority': '6'}, False),
        ({'message': 'arm-smmu: context fault', 'priority': '3'}, False),
        ({'message': 'msm_mdp: underrun', 'priority': '4'}, False),
        ({'message': 'other-driver: unexpected error', 'priority': '3'}, False),
        ({'message': 'other-driver: normal information', 'priority': '6'}, True),
    ]
    for row, clean in cases:
        assert classify([row])['clean_kernel_window'] is clean, row
    assert classify([])['clean_kernel_window']
    return len(cases) + 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('postflight', type=Path, nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        print(json.dumps({'classifier_cases_passed': self_test()}))
        return
    if args.postflight is None:
        parser.error('postflight JSON is required')
    report = json.loads(args.postflight.read_text())
    assert isinstance(report['kernel_journal_window_start_monotonic_usec'], int)
    rows = report['kernel_messages_in_full_launch_window']
    assert isinstance(rows, list)
    assert all(int(row['monotonic_usec']) >= report['kernel_journal_window_start_monotonic_usec'] for row in rows)
    result = classify(rows)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['clean_kernel_window'] else 1)


if __name__ == '__main__':
    main()
