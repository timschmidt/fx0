#!/usr/bin/env python3
"""Verify the expected failing probes against the unchanged pinned guard."""
import argparse
import hashlib
import json
from pathlib import Path
import re


def summarize(directory, base='d8e650c3180db30b4c7df59caadefae9c2ff2866'):
    controller = json.loads((directory / 'controller.json').read_text())
    if controller['state'] != 'complete':
        raise ValueError('Probe process is not terminal')
    controls = {'test_validity_unavailable_coldplug_read',
                'test_battery_without_charge_information',
                'test_battery_with_design_information_only',
                'test_battery_with_measurements_but_no_charge_information',
                'test_battery_with_zero_remaining_charge'}
    results = []
    aborts = []
    for case in controller['cases']:
        path = directory / (case['name'] + '.log')
        log = re.sub(r'\x1b\[[0-9;]*m', '', path.read_text())
        expected = 0 if case['name'] in controls else 1
        if case['returncode'] != expected:
            raise ValueError('Unexpected case result: ' + case['name'])
        known_nan_abort = (base == '1ddb4275a13932db1a64d8549182947066c57fb0'
                           and case['name'] == 'test_validity_nan_capacity'
                           and 'GLib-GObject-CRITICAL' in log
                           and 'value "nan"' in log
                           and "property 'percentage'" in log
                           and 'AssertionError: -6 != 0' in log
                           and 'FAILED (failures=2)' in log)
        if known_nan_abort:
            aborts.append(case['name'])
        if expected and not known_nan_abort and ('FAILED (failures=1)' not in log or '\nERROR:' in log):
            raise ValueError('Probe failed outside its contract assertion: ' + case['name'])
        if not expected and '\nOK\n' not in log:
            raise ValueError('Control did not pass: ' + case['name'])
        observations = [json.loads(line.split('FX0_VALIDITY_OBSERVATION ', 1)[1])
                        for line in log.splitlines() if 'FX0_VALIDITY_OBSERVATION ' in line]
        results.append({'case': case['name'], 'expected_exitcode': expected,
                        'observations': observations,
                        'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    if len(results) != 16 or sum(r['expected_exitcode'] == 1 for r in results) != 11:
        raise ValueError('Unexpected case count')
    if {r['case'] for r in results if r['expected_exitcode'] == 0} != controls:
        raise ValueError('Missing control')
    false_critical = [o for r in results for o in r['observations']
                      if r['expected_exitcode'] == 1 and o['percentage'] == 0 and o['warning'] == 5]
    false_full = [o for r in results for o in r['observations']
                  if o['label'] == 'infinite_capacity' and o['percentage'] == 100]
    expected_critical = 8 if base == '1ddb4275a13932db1a64d8549182947066c57fb0' else 9
    if len(false_critical) != expected_critical or len(false_full) != 1:
        raise ValueError('Observed behavior differs from the recorded baseline')
    expected_aborts = ['test_validity_nan_capacity'] if expected_critical == 8 else []
    if aborts != expected_aborts:
        raise ValueError('Unexpected fatal-diagnostic behavior')
    return {'source_guard_base': base,
            'probes_and_controls': 16, 'expected_failing_contract_probes': 11,
            'passing_controls': 5, 'false_critical_states': len(false_critical),
            'fatal_diagnostic_abort_cases': aborts,
            'infinite_capacity_reported_as_full': True,
            'ignored_supply_does_not_recover_on_change': True,
            'GUdev_read_failure_at_coldplug_already_rejected': True,
            'genuine_zero_charge_retains_critical_handling': True,
            'kernel_ENODATA_injection': False,
            'read_failure_scope': 'libudev NULL-return model with errno ENODATA and injection-log assertion; no kernel fault',
            'production_fix': False, 'cases': results}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--base', default='d8e650c3180db30b4c7df59caadefae9c2ff2866',
                        choices=['d8e650c3180db30b4c7df59caadefae9c2ff2866',
                                 '1ddb4275a13932db1a64d8549182947066c57fb0'])
    args = parser.parse_args()
    if args.report.exists():
        raise ValueError('Report already exists')
    args.report.write_text(json.dumps(summarize(args.results, args.base), indent=2) + '\n')
    print('Verified: 11 expected failing probes and 5 passing controls')
