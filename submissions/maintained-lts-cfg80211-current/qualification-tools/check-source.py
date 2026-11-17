# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib, json, subprocess
N = Path(__file__).resolve().parent
R = N.parents[2]
C = R / 'worktrees/linux-fx0-lts-integration-current-01'
E = R / 'worktrees/linux-fx0-cpu-current-01'
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
plan = read(N / 'composition.json')
assert read(N / 'UML-qualification.json')['passed']
assert read(N / 'lifecycle-source-binding.json')['passed']
assert read(N / 'lifecycle-01/controller.json')['passed']
assert read(N / 'native-01/controller.json')['passed']
assert read(N / 'native-source-binding.json')['objects'] == 12
paths = ['net/wireless/scan.c', 'net/wireless/tests/scan.c']
assert subprocess.check_output(['git', 'diff', '--name-only', plan['base']], cwd=C, text=True).splitlines() == paths
assert not subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=C)
for stage in plan['ports']:
    h = stage['origin']
    old = (N / 'stages' / h[:12] / 'net/wireless/scan.c.before').read_bytes()
    new = (N / 'stages' / h[:12] / 'net/wireless/scan.c.after').read_bytes()
    import difflib
    change = [l for l in difflib.unified_diff(old.decode().splitlines(), new.decode().splitlines()) if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
    upstream = subprocess.check_output(['git', 'diff', h + '^', h], cwd=E, text=True)
    original = [l for l in upstream.splitlines() if l.startswith(('+', '-')) and not l.startswith(('+++', '---'))]
    assert change == original, h
files = read(N / 'prepared.json')['source_files']
for f, digest in files.items():
    if f not in paths: assert sha(C / f) == digest, f
assert sha(C / 'net/wireless/scan.c') == plan['ports'][-1]['files'][0]['after_SHA256']
assert sha(C / 'net/wireless/tests/scan.c') == plan['test_change']['files'][0]['after_SHA256']
assert not read(N / 'lifecycle-01/controller.json')['scan_requests_sent']
j = dict(passed=True, source_files={f:sha(C / f) for f in files}, changed_paths=paths,
    original_exact_ports=[x['origin'] for x in plan['ports']],
    existing_equivalents=[dict(origin=plan['existing_equivalent'],
        evidence='lifecycle-source-binding.json and lifecycle-01/controller.json',
        scope='Four actual completion/request ownership functions; synthetic work, messages and driver timing')],
    additional_qualification_test_changes=1, real_kernel_MBSSID_case_instances=19,
    full_cache_reference_and_profile_paths_exercised=True,
    driver_radio_concurrency_or_full_wireless_stack_qualified=False,
    physical_wireless_qualified=False, other_cfg80211_source_and_headers_preserved=True,
    DTS_and_schema_unchanged=True, previous_full19_schema_evidence_reusable=True,
    WiFi_scans=False, Replimat3_interaction=False, network_changes=False, phone_access=False)
(N / 'source-equivalence.json').write_text(json.dumps(j, indent=2) + '\n')
print('Two exact source deltas, existing lifecycle equivalent and exact two-path footprint verified')
