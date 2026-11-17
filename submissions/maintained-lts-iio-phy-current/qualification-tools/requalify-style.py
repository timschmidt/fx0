# SPDX-License-Identifier: GPL-2.0-only
"""Rebuild only the three formatter objects after a blank-line cleanup."""
from pathlib import Path
import hashlib, json, os, signal, subprocess
N = Path(__file__).resolve().parent
C = N.parents[2] / 'worktrees/linux-fx0-lts-integration-current-01'
O = N / 'native-03'
O.mkdir()
read = lambda p: json.loads(p.read_text())
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
j = read(N / 'native-02/controller.json')
f = 'drivers/iio/test/iio-test-format.c'
old = (N / 'committed-patches-01').glob('*.patch')
j.update(passed=False, state='prepared', incremental_outputs='native-02',
         source_only_change='Two blank lines before a closing brace removed',
         recompiled_objects=3, unchanged_objects_reused=66)
j['stages'] = []
assert all(sha(C / p) == h for p, h in j['source_files'].items() if p != f)
j['source_files'][f] = sha(C / f)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
try:
    for row in j['profiles']:
        out = N / 'native-02' / (row['profile'] + '-out')
        assert sha(out / '.config') == row['config_SHA256']
        for obj, h in row['objects'].items():
            assert sha(out / obj) == h
        cmd = ['make', 'O=' + str(out), 'ARCH=' + row['ARCH'], 'LLVM=-21',
               'W=1', 'KCFLAGS=-Werror=incompatible-function-pointer-types',
               '-j2', f[:-2] + '.o']
        log = O / (row['profile'] + '.log')
        with log.open('xb') as stream:
            child = subprocess.Popen(cmd, cwd=C, env=os.environ | {'TMPDIR': str(out / 'tmp'),
                'GIT_NO_LAZY_FETCH': '1'}, stdout=stream, stderr=subprocess.STDOUT,
                start_new_session=True)
            j.update(state='running ' + row['profile'], active_PID=child.pid)
            save()
            code = child.wait(timeout=180)
        diagnostics = [l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()]
        assert code == 0 and not diagnostics
        assert 'CC ' in log.read_text() and 'iio-test-format.o' in log.read_text()
        for obj, h in row['objects'].items():
            if obj != f[:-2] + '.o':
                assert sha(out / obj) == h
        row['objects'][f[:-2] + '.o'] = sha(out / (f[:-2] + '.o'))
        j['stages'].append(dict(profile=row['profile'], returncode=code,
            diagnostics=diagnostics, log_SHA256=sha(log)))
    j.update(passed=True, state='terminal success')
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try: child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait(timeout=5)
    j.pop('active_PID', None)
    j['owned_child_terminal_and_reaped'] = child is None or child.returncode is not None
    save()
print(json.dumps(dict(passed=j['passed'], rebuilt=3, reused=66)))
