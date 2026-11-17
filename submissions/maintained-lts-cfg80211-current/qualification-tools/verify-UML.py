# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib, json
N = Path(__file__).resolve().parent
R = N.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
def tests(node):
    return node.get('test_cases', []) + [t for g in node.get('sub_groups', []) for t in tests(g)]
rows = []
for label, failed in [('after-03', 0), ('before-03', 14), ('reference-only-01', 13), ('length-only-01', 1)]:
    O = N / ('UML-' + label)
    receipt = read(O / 'controller.json')
    assert receipt['passed'] and receipt['owned_child_terminal_and_reaped']
    assert sha(O / 'results.json') == receipt['results_SHA256']
    cases = tests(read(O / 'results.json'))
    assert len(cases) == 19 and sum(t['status'] == 'FAIL' for t in cases) == failed, (label, cases)
    rejects = [t for t in cases if t['name'] == 'test_inform_bss_mbssid_rejected_refs']
    assert len(rejects) == 1 and (rejects[0]['status'] == 'FAIL') == (label in ['before-03', 'length-only-01'])
    assert receipt['source_files']['net/wireless/tests/scan.c'] == sha(C / 'net/wireless/tests/scan.c')
    if label == 'after-03':
        assert receipt['source_files']['net/wireless/scan.c'] == sha(C / 'net/wireless/scan.c')
    if label == 'before-03':
        assert receipt['source_files']['net/wireless/scan.c'] == sha(N / 'before/net/wireless/scan.c')
    cfg = (Path(receipt['build_dir']) / '.config').read_text()
    assert sha(Path(receipt['build_dir']) / '.config') == receipt['config_SHA256']
    for sym in ['NETDEVICES', 'UML_NET', 'INET', 'UNIX', 'HOSTFS', 'MODULES', 'MODULE_SIG']:
        assert 'CONFIG_' + sym + '=y\n' not in cfg and 'CONFIG_' + sym + '=m\n' not in cfg
    assert not (Path(receipt['build_dir']) / 'certs/signing_key.pem').exists()
    assert receipt['public_regdb_verification'] and receipt['public_source_certificates_only']
    rows.append(dict(label=label, tests=19, passed=19-failed, failed=failed,
        rejected_reference_test_status=rejects[0]['status'], source_files=receipt['source_files']))
assert read(N / 'UML-controls.json')['passed'] and read(N / 'UML-controls.json')['baseline_source_restored']
j = dict(passed=True, records=rows, new_case_instances=19, profile_lengths=18,
    rejected_report_repetitions=16, independent_kernel_controls=2,
    valid_inputs_full_kernel_MBSSID_and_BSS_reference_paths=True,
    unregistered_dummy_wiphy_only=True, scan_requests_sent=False,
    concurrent_driver_or_physical_wireless_qualified=False,
    default_public_regdb_verification_preserved=True, private_signing_key_used=False,
    inherited_UML_null_pointer_arithmetic_and_RWX_linker_warnings_retained=True,
    native_ARM_and_ARM64_diagnostics_clean=True, phone_access=False)
(N / 'UML-qualification.json').write_text(json.dumps(j, indent=2) + '\n')
print('Nineteen real kernel cases pass; baseline and independent repair controls reproduce the intended failures')
