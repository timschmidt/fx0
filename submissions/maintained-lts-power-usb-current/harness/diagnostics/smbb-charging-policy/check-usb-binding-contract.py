#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check real processed USB schemas against valid and malformed property shapes."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

import dtschema


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--dtb', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    validator = dtschema.DTValidator([str(args.schema)])
    decoded = validator.decode_dtb(args.dtb.read_bytes())
    if len(decoded) != 1:
        raise ValueError('expected one tree')
    node = decoded[0]['soc']['usb@f9a55000']
    selected = ['ci-hdrc-usb2']
    results = []

    def check(label, value, expected_valid, property=None, filters=None):
        errors = list(validator.iter_errors(value, filter=filters or selected))
        if expected_valid:
            if errors:
                raise ValueError(label + ': valid property contract rejected')
        elif not any(property in list(error.path) or property in list(error.schema_path)
                     or property in error.message
                     or (error.schema is False and error.instance == value[property])
                     for error in errors):
            raise ValueError(label + ': expected property diagnostic missing')
        results.append({'label': label, 'expected_valid': expected_valid,
                        'validation_errors': len(errors), 'expected_result_verified': True})

    check('current-controller', copy.deepcopy(node), True)
    tuples = [('one-phandle-two-arguments', [[1, 0xb000, 0]], True),
              ('missing-argument', [[1, 0xb000]], False),
              ('extra-argument', [[1, 0xb000, 0, 1]], False),
              ('multiple-tuples', [[1, 0xb000, 0], [1, 0xb000, 1]], False),
              ('flat-cells', [1, 0xb000, 0], False),
              ('empty-tuple-list', [], False)]
    for label, value, valid in tuples:
        candidate = copy.deepcopy(node)
        candidate['phy-select'] = value
        check(label, candidate, valid, 'phy-select')
    for label, value, valid in [('role-switch-flag', True, True),
                                 ('role-switch-string', ['enabled'], False),
                                 ('role-switch-cells', [[1]], False)]:
        candidate = copy.deepcopy(node)
        candidate.pop('power-supplies')
        candidate['usb-role-switch'] = value
        check(label, candidate, valid, 'usb-role-switch')
    candidate = copy.deepcopy(node)
    candidate['dr_mode'] = ['host']
    check('managed-host-role', candidate, False, 'dr_mode')
    candidate = copy.deepcopy(node)
    candidate['usb-role-switch'] = True
    check('managed-role-switch', candidate, False, 'usb-role-switch')
    charger = decoded[0]['soc']['spmi@fc4cf000']['pm8226@0']['charger@1000']
    check('current-managed-charger', copy.deepcopy(charger), True,
          filters=['qcom,pm8941-charger'])
    candidate = copy.deepcopy(charger)
    candidate['usb-charge-current-limit'] = 500000
    check('managed-manual-limit', candidate, False, 'usb-charge-current-limit',
          filters=['qcom,pm8941-charger'])
    result = {'cases': len(results), 'results': results,
              'schema_SHA256': hashlib.sha256(args.schema.read_bytes()).hexdigest(),
              'DTB_SHA256': hashlib.sha256(args.dtb.read_bytes()).hexdigest(),
              'scope': 'Actual processed ChipIdea/USB-DRD schemas with decoded current controller node; no hardware or kernel execution.'}
    (args.output / 'verified.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(results), 'all_expected_results_verified': True,
                      'phone_access': False}))


if __name__ == '__main__':
    main()
