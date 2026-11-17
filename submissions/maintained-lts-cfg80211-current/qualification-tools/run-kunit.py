# SPDX-License-Identifier: GPL-2.0-only
"""Bounded cfg80211 tests on unregistered wiphys inside isolated UML."""
from pathlib import Path
import argparse, hashlib, json, os, signal, subprocess, sys
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--source', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--build-dir', type=Path)
ap.add_argument('--expect-failure', action='store_true')
a = ap.parse_args()
N = Path(__file__).resolve().parent
C = a.source.resolve()
O = a.output.resolve()
O.mkdir()
(O / 'tmp').mkdir()
B = (a.build_dir or O / 'out').resolve()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
paths = ['net/wireless/scan.c', 'net/wireless/tests/scan.c', 'net/wireless/tests/util.c', 'net/wireless/tests/util.h']
j = dict(passed=False, state='prepared', source_files={f:sha(C / f) for f in paths},
    UML=True, unregistered_dummy_wiphy_only=True, phone_access=False, real_wireless_execution=False,
    expect_test_failure=a.expect_failure)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
cmd = [sys.executable, '-B', 'tools/testing/kunit/kunit.py', 'run',
    '--kunitconfig=' + str(N / 'wireless.kunitconfig'), '--build_dir=' + str(B),
    '--make_options=LLVM=-21', '--make_options=W=1', '--jobs=2', '--timeout=90',
    '--json=' + str(O / 'results.json'), 'cfg80211-inform-bss.test_inform_bss_mbssid*']
env = os.environ | {'TMPDIR':str(O / 'tmp'), 'PYTHONDONTWRITEBYTECODE':'1',
    'GIT_NO_LAZY_FETCH':'1', 'KBUILD_BUILD_USER':'fx0-review', 'KBUILD_BUILD_HOST':'source-check',
    'KBUILD_BUILD_TIMESTAMP':'2026-11-17 00:00:00 UTC'}
env.pop('KBUILD_SIGN_PIN', None)
try:
    with (O / 'run.log').open('xb') as log:
        child = subprocess.Popen(cmd, cwd=C, env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        j.update(state='running bounded UML build and MBSSID tests', active_PID=child.pid)
        save()
        code = child.wait(timeout=900)
    j.update(returncode=code, log_SHA256=sha(O / 'run.log'))
    assert code in [0, 1] and (code == 1) == a.expect_failure
    assert (O / 'results.json').exists()
    cfg = (B / '.config').read_text()
    for sym in ['CFG80211_KUNIT_TEST', 'CFG80211', 'KUNIT']: assert 'CONFIG_' + sym + '=y\n' in cfg
    for sym in ['NETDEVICES', 'UML_NET', 'INET', 'UNIX', 'HOSTFS', 'MODULES', 'MODULE_SIG',
                ]:
        assert 'CONFIG_' + sym + '=y\n' not in cfg and 'CONFIG_' + sym + '=m\n' not in cfg
    assert not (B / 'certs/signing_key.pem').exists()
    assert all(sha(C / f) == h for f, h in j['source_files'].items())
    j.update(passed=True, state='terminal expected test result', config_SHA256=sha(B / '.config'),
        results_SHA256=sha(O / 'results.json'), build_dir=str(B), host_network_device_support=False,
        host_filesystem_support=False, private_key_used=False,
        public_regdb_verification=('CONFIG_CFG80211_REQUIRE_SIGNED_REGDB=y\n' in cfg),
        public_source_certificates_only=True)
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    j.pop('active_PID', None)
    j['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    if not j['passed']: j['state'] = 'terminal failure'
    save()
print(json.dumps(dict(passed=j['passed'], expected_failure=a.expect_failure)))
