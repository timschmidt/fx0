# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import hashlib, json, os, signal, subprocess
N = Path(__file__).resolve().parent
C = N.parents[2] / 'worktrees/linux-fx0-lts-integration-current-01'
O = N / 'native-01'
O.mkdir()
objects = ['net/wireless/' + s + '.o' for s in ['scan', 'core', 'nl80211', 'util']]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
files = [s[:-2] + '.c' for s in objects] + ['net/wireless/core.h', 'include/net/cfg80211.h', 'include/linux/ieee80211.h']
j = dict(passed=False, state='prepared', source_files={f:sha(C / f) for f in files},
    profiles=[], stages=[], phone_access=False, radio_or_network_execution=False,
    ARM32_RT_unsupported_not_counted=True)
child = None
save = lambda: (O / 'controller.json').write_text(json.dumps(j, indent=2) + '\n')
try:
    for arch, rt, mode, wext, seed in [
        ('arm', False, 'y', True, 'native-01/arm-normal-CPU-enabled-system-on-out'),
        ('arm64', False, 'm', False, 'native-01/arm64-normal-CPU-enabled-system-off-out'),
        ('arm64', True, 'm', False, 'native-02/arm64-rt-CPU-enabled-system-off-out')]:
        label = arch + ('-rt' if rt else '-normal') + '-cfg80211-' + mode
        out = O / (label + '-out')
        out.mkdir()
        (out / 'tmp').mkdir()
        (out / '.config').write_bytes((N.parent / 'system-coordinator-01' / seed / '.config').read_bytes())
        cmd = ['scripts/config', '--file', str(out / '.config'), '--disable', 'COMPILE_TEST',
            '--enable', 'MODULES', '--enable', 'NET', '--enable', 'WIRELESS', '--enable', 'RFKILL',
            '--enable' if mode == 'y' else '--module', 'CFG80211',
            '--enable' if wext else '--disable', 'CFG80211_WEXT']
        subprocess.run(cmd, cwd=C, check=True)
        make = ['make', 'O=' + str(out), 'ARCH=' + arch, 'LLVM=-21', 'W=1',
            'KCFLAGS=-Werror=incompatible-function-pointer-types', '-j2']
        for phase, targets in [('config', ['olddefconfig']), ('objects', objects)]:
            log = O / (label + '-' + phase + '.log')
            with log.open('xb') as stream:
                child = subprocess.Popen(make + targets, cwd=C,
                    env=os.environ | {'TMPDIR':str(out / 'tmp'), 'GIT_NO_LAZY_FETCH':'1'},
                    stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
                j.update(state='running ' + label + ' ' + phase, active_PID=child.pid)
                save()
                code = child.wait(timeout=600)
            diagnostics = [l for l in log.read_text().splitlines() if 'warning:' in l.lower() or 'error:' in l.lower()]
            j['stages'].append(dict(profile=label, phase=phase, returncode=code, diagnostics=diagnostics, log_SHA256=sha(log)))
            save()
            assert code == 0 and not diagnostics, diagnostics
        cfg = (out / '.config').read_text()
        assert 'CONFIG_CFG80211=' + mode + '\n' in cfg
        assert ('CONFIG_CFG80211_WEXT=y\n' in cfg) == wext
        assert ('CONFIG_PREEMPT_RT=y\n' in cfg) == rt
        assert 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg
        assert '# CONFIG_COMPILE_TEST is not set\n' in cfg
        assert not (out / 'certs/signing_key.pem').exists()
        assert all(sha(C / f) == h for f, h in j['source_files'].items())
        j['profiles'].append(dict(profile=label, ARCH=arch, PREEMPT_RT=rt, mode=mode,
            WEXT=wext, CFI=True, CFI_PERMISSIVE=False, config_SHA256=sha(out / '.config'),
            objects={f:sha(out / f) for f in objects}))
    j.update(passed=True, state='terminal success', native_objects=12)
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
print(json.dumps(dict(passed=j['passed'], native_objects=12)))
