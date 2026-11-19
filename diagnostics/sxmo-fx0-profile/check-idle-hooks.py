"""Replay the observed idle controls with the exact packaged hooks and a mock PATH."""
from pathlib import Path
import hashlib
import itertools
import json
import subprocess
import sys
import tempfile

if len(sys.argv) != 2:
    sys.exit(f'Usage: {sys.argv[0]} /path/to/packaged/sxmo/default_hooks')
hooks = Path(sys.argv[1]).resolve()
hook_names = ('unlock', 'lock', 'screenoff', 'block_suspend')
hashes = {name: hashlib.sha256((hooks / f'sxmo_hook_{name}.sh').read_bytes()).hexdigest()
          for name in (*hook_names, 'start')}
mock = '''#!/bin/sh
name=${0##*/}
printf '%s %s\\n' "$name" "$*" >> "$EVENTS"
case "$name" in
    pgrep|netstat|awk) exit 1 ;;
    sleep) /usr/bin/rm -f "$XDG_CACHE_HOME/sxmo/sxmo.nosuspend" ;;
esac
'''
results = []
with tempfile.TemporaryDirectory(prefix='fx0-sxmo-idle-hooks-') as directory:
    work = Path(directory)
    bin_dir = work / 'bin'
    bin_dir.mkdir()
    common = bin_dir / 'sxmo_common.sh'
    common.write_text('sxmo_log() { printf "%s\\n" "$*" >> "$EVENTS"; }\n')
    for name in ('sxmo_led.sh', 'sxmo_wm.sh', 'sxmo_jobs.sh', 'swaymsg',
                 'sleep', 'pgrep', 'nmcli', 'netstat', 'awk'):
        script = bin_dir / name
        script.write_text(mock)
        script.chmod(0o700)

    for idle, suspend, effective in itertools.product((False, True), repeat=3):
        cache = work / f'cache-{idle}-{suspend}-{effective}'
        flags = cache / 'sxmo' if effective else cache
        flags.mkdir(parents=True)
        if idle:
            (flags / 'sxmo.noidle').touch()
        if suspend:
            (flags / 'sxmo.nosuspend').touch()
        events = work / 'events'
        environment = dict(PATH=str(bin_dir), XDG_CACHE_HOME=str(cache), SXMO_WM='sway', EVENTS=str(events))
        observed = {}
        for hook in hook_names:
            events.write_text('')
            result = subprocess.run(['/bin/sh', str(hooks / f'sxmo_hook_{hook}.sh')],
                                    env=environment, capture_output=True, timeout=5, text=True)
            assert result.returncode == 0, (hook, result.stderr)
            calls = events.read_text().splitlines()
            if hook in ('unlock', 'lock'):
                queued = any(row.startswith('sxmo_jobs.sh start idle_locker sxmo_idle.sh ') for row in calls)
                stopped = 'sxmo_jobs.sh stop idle_locker' in calls
                assert queued == (not (idle and effective)) and stopped == (not queued)
                observed[hook + '_queues_idle_locker'] = queued
            elif hook == 'screenoff':
                assert 'sxmo_wm.sh display off' in calls and 'sxmo_wm.sh inputevent touchscreen off' in calls
                blinks = any(row.startswith('sxmo_jobs.sh start periodic_blink ') for row in calls)
                assert blinks == (not (suspend and effective))
                observed['screenoff_queues_periodic_blink'] = blinks
            else:
                blocked = 'Blocking suspend for suspend_disabled' in calls
                assert blocked == (suspend and effective)
                observed['suspend_blocked_by_flag'] = blocked
        results.append(dict(noidle=idle, nosuspend=suspend, effective_location=effective, **observed))
print(json.dumps(dict(passed=True, packaged_hook_sha256=hashes, host_cases=len(results),
                      hook_invocations=len(results) * len(hook_names), results=results), indent=2))
