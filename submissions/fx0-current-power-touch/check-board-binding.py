#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Check the actual root schema on complete DTBs and malformed identities."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, required=True)
    parser.add_argument('--before-schema', type=Path, required=True)
    parser.add_argument('--dtb-directory', type=Path, required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    manifest = json.loads(args.manifest.read_text())['DTBs']
    assert len(manifest) == 19
    validator = Path(sys.executable).parent / 'dt-validate'
    def validate(name, schema, dtb, selected=True):
        scope = ['-l', 'arm/qcom.yaml'] if selected else ['-m']
        p = subprocess.run([str(validator), '-s', str(schema), *scope, str(dtb)],
                           capture_output=True, timeout=60)
        (args.output / (name + '.stdout')).write_bytes(p.stdout)
        (args.output / (name + '.stderr')).write_bytes(p.stderr)
        assert p.returncode == 0 and not p.stdout
        return p.stderr
    positive = []
    complete = args.dtb_directory / 'qcom/qcom-msm8926-lg-madai.dtb'
    for n, (name, expected) in enumerate(manifest.items()):
        dtb = args.dtb_directory / name
        assert hashlib.sha256(dtb.read_bytes()).hexdigest() == expected
        error = validate('positive-' + str(n), args.schema, dtb)
        assert not error, name
        positive.append(name)
    # This failure comes from the actual parent binding; no baseline is
    # synthesized by editing processed validation data.
    error = validate('before-complete-Fx0', args.before_schema, complete)
    assert b'compatible' in error and b'/schemas/arm/qcom.yaml' in error
    for n, name in enumerate(['qcom/msm8226-motorola-falcon.dtb',
                             'qcom/msm8926-sony-xperia-yukon-eagle.dtb']):
        assert not validate('before-inherited-control-' + str(n), args.before_schema,
                            args.dtb_directory / name)
    negative = []
    mutations = [
        ('missing-family', ['lg,madai', 'qcom,msm8926']),
        ('missing-SoC', ['lg,madai', 'qcom,msm8226']),
        ('identity-only', ['lg,madai']),
        ('reversed-fallbacks', ['lg,madai', 'qcom,msm8226', 'qcom,msm8926']),
        ('wrong-SoC', ['lg,madai', 'qcom,msm8916', 'qcom,msm8226']),
        ('wrong-family', ['lg,madai', 'qcom,msm8926', 'qcom,msm8974']),
        ('extra-fallback', ['lg,madai', 'qcom,msm8926', 'qcom,msm8226', 'qcom,msm8916']),
        ('unknown-board', ['lg,not-madai', 'qcom,msm8926', 'qcom,msm8226']),
    ]
    for name, compatibles in mutations:
        path = args.output / (name + '.dtb')
        path.write_bytes(complete.read_bytes())
        subprocess.run(['fdtput', '-t', 's', str(path), '/', 'compatible', *compatibles], check=True)
        error = validate(name, args.schema, path)
        assert b'compatible' in error and b'/schemas/arm/qcom.yaml' in error, name
        negative.append({'case': name, 'compatible_diagnostic_verified': True})
    # A non-string compatible does not reliably select the QCOM board schema.
    # Check its type with the unfiltered validator and keep that distinct from
    # the eight enum/fallback contract controls above.
    path = args.output / 'cell-identity.dtb'
    path.write_bytes(complete.read_bytes())
    subprocess.run(['fdtput', '-t', 'x', str(path), '/', 'compatible', '1'], check=True)
    malformed = validate('cell-identity', args.schema, path)
    global_error = validate('cell-identity-unfiltered', args.schema, path, selected=False)
    assert any(b': / (0): compatible:' in line and b"is not of type 'array'" in line
               for line in global_error.splitlines())
    result = {'passed': True, 'complete_DTB_positive_cases': positive,
              'actual_parent_binding_rejects_Fx0_identity': True,
              'actual_parent_binding_inherited_positive_controls': 2,
              'rejected_compatible_controls': negative,
              'nonstring_identity_selected_schema_rejected': bool(malformed),
              'nonstring_identity_unfiltered_root_type_error_verified': True,
              'unfiltered_control_other_diagnostics_not_counted_as_identity_rejections': True,
              'all_original_DTBs_preserved': all(hashlib.sha256((args.dtb_directory / name).read_bytes()).hexdigest() == expected
                                                  for name, expected in manifest.items()),
              'checker_SHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'schema_SHA256': hashlib.sha256(args.schema.read_bytes()).hexdigest(),
              'parent_schema_SHA256': hashlib.sha256(args.before_schema.read_bytes()).hexdigest(),
              'runtime_driver_or_new_DTB_build_or_physical_qualification': False,
              'phone_access': False}
    (args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
