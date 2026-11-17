#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Replay MBSSID tests from tracked public source only, inside isolated UML."""
from pathlib import Path
import argparse, hashlib, json, os, signal, subprocess, sys, tarfile
P = Path(__file__).resolve().parent
ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--kernel-repository', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
a = ap.parse_args()
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
m = json.loads((P / 'manifest.json').read_text())
assert all(sha(P / f) == h for f, h in m['files'].items())
O = a.output.resolve()
O.mkdir(mode=0o700)
source = O / 'kernel-source'
source.mkdir()
j = dict(passed=False, state='prepared', source_head=m['source_head'],
    tracked_git_archive_only=True, ignored_files_excluded=True,
    phone_access=False, WiFi_scans=False, network_changes=False)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
env = os.environ | {'GIT_NO_LAZY_FETCH':'1', 'PYTHONDONTWRITEBYTECODE':'1'}
try:
    assert not subprocess.check_output(['git', 'ls-tree', '--name-only', m['source_head'], 'certs/signing_key.pem'], cwd=a.kernel_repository, env=env)
    archive = O / 'public-source.tar'
    with archive.open('xb') as output:
        child = subprocess.Popen(['git', 'archive', '--format=tar', m['source_head']],
            cwd=a.kernel_repository, env=env, stdout=output, start_new_session=True)
        j.update(state='archiving tracked public source', active_PID=child.pid)
        save()
        assert child.wait(timeout=120) == 0
    with tarfile.open(archive) as tar:
        tar.extractall(source, filter='data')
    assert not (source / 'certs/signing_key.pem').exists()
    for f, h in json.loads((P / 'evidence/source-current.json').read_text())['source_files'].items():
        assert sha(source / f) == h, f
    with (O / 'UML-launcher.log').open('xb') as log:
        child = subprocess.Popen([sys.executable, '-B', str(P / 'qualification-tools/run-kunit.py'),
            '--source', str(source), '--output', str(O / 'UML')], env=env,
            stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        j.update(state='running isolated UML from public-source archive', active_PID=child.pid)
        save()
        assert child.wait(timeout=1000) == 0
    receipt = json.loads((O / 'UML/controller.json').read_text())
    assert receipt['passed'] and receipt['owned_child_terminal_and_reaped']
    def tests(node):
        return node.get('test_cases', []) + [t for g in node.get('sub_groups', []) for t in tests(g)]
    cases = tests(json.loads((O / 'UML/results.json').read_text()))
    assert len(cases) == 19 and all(t['status'] == 'PASS' for t in cases)
    assert all(sha(P / f) == h for f, h in m['files'].items())
    j.update(passed=True, state='terminal success', public_archive_SHA256=sha(archive),
        real_kernel_tests=19, private_key_used=False, host_network_devices=False,
        default_public_regdb_verification=receipt['public_regdb_verification'])
    print(json.dumps(dict(passed=True, real_kernel_tests=19, tracked_source_only=True)))
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
