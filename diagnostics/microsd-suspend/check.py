#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded Fx0 SD filesystem/RTC suspend trial; never format or repair media."""
from pathlib import Path
import argparse, hashlib, json, os, re, signal, subprocess, time, uuid

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('output', type=Path)
a = p.parse_args()
os.umask(0o077)
a.output.mkdir(parents=True, exist_ok=False)
out = a.output
mount = out / 'mount'
mount.mkdir()
media = Path('/dev/mmcblk1p1')
assert Path('/sys/class/block/mmcblk1/device/type').read_text().strip() == 'SD'
assert subprocess.run(['findmnt', '-rn', '-S', str(media)], capture_output=True).returncode == 1
assert subprocess.check_output(['blkid', '-s', 'TYPE', '-o', 'value', str(media)], text=True).strip() == 'vfat'
assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()

def run(args):
    r = subprocess.run(args, capture_output=True, text=True, timeout=90)
    if r.returncode:
        raise RuntimeError(f'{args[0]} failed ({r.returncode}): {r.stderr}')
    return r.stdout

def fsck(label):
    r = subprocess.run(['fsck.fat', '-n', str(media)], capture_output=True, text=True, timeout=90)
    (out / (label + '.log')).write_text(r.stdout + r.stderr)
    assert r.returncode == 0, 'Read-only filesystem check failed; no repair attempted'

def digest(path):
    with path.open('rb') as f:
        os.posix_fadvise(f.fileno(), 0, 0, os.POSIX_FADV_DONTNEED)
        return hashlib.file_digest(f, 'sha256').hexdigest()

def interrupt(signum, frame):
    raise InterruptedError(signum)

for sig in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(sig, interrupt)
alarm = Path('/sys/class/rtc/rtc0/wakealarm')
epoch = Path('/sys/class/rtc/rtc0/since_epoch')
mem = Path('/sys/power/mem_sleep')
udc = Path('/sys/class/udc/ci_hdrc.0/device/power/wakeup')
original = {'alarm': alarm.read_text().strip(), 'mem': re.search(r'\[([^]]+)\]', mem.read_text()).group(1), 'udc': udc.read_text().strip()}
result = {'status': 'running', 'boot_id': boot, 'kernel': run(['uname', '-r']).strip(), 'cycles': [], 'bytes': 67108864, 'original_power_state': original}
owned = mount / ('.fx0-suspend-' + uuid.uuid4().hex)
file = owned / 'payload.bin'
mounted = False
trace = None
error = None
try:
    fsck('fsck-before')
    run(['mount', '-t', 'vfat', '-o', 'rw,nosuid,nodev,noexec', str(media), str(mount)])
    mounted = True
    assert os.statvfs(mount).f_bavail * os.statvfs(mount).f_frsize > 2 * result['bytes']
    owned.mkdir()
    sha = hashlib.sha256()
    with file.open('xb') as f:
        for _ in range(64):
            chunk = os.urandom(1048576)
            f.write(chunk)
            sha.update(chunk)
        f.flush()
        os.fsync(f.fileno())
    os.sync()
    expected = sha.hexdigest()
    result['sha256'] = expected
    assert digest(file) == expected
    for cycle in range(1, 4):
        trace = Path('/sys/kernel/tracing/instances') / ('fx0-sd-' + uuid.uuid4().hex[:12])
        trace.mkdir()
        (trace / 'buffer_size_kb').write_text('128\n')
        (trace / 'trace_clock').write_text('boot\n')
        (trace / 'events/power/suspend_resume/enable').write_text('1\n')
        wake_event = trace / 'events/power/wakeup_source_activate/enable'
        if wake_event.exists():
            wake_event.write_text('1\n')
        wake_sources = Path('/sys/kernel/debug/wakeup_sources')
        if wake_sources.exists():
            (out / f'cycle-{cycle:02d}-wake-before.txt').write_text(wake_sources.read_text())
        (trace / 'tracing_on').write_text('1\n')
        udc.write_text('disabled\n')
        mem.write_text('s2idle\n')
        alarm.write_text('0\n')
        print(f'RTC SD CYCLE {cycle} ARMED', flush=True)
        log = run(['runuser', '-u', 'user', '--', '/usr/bin/fx0-hotspot-suspend', '--sync-wakeup-count', 'doas', '-n', 'rtcwake', '-m', 'mem', '-s', '12'])
        (out / f'cycle-{cycle:02d}-rtcwake.log').write_text(log)
        (trace / 'tracing_on').write_text('0\n')
        text = (trace / 'trace').read_text()
        (out / f'cycle-{cycle:02d}.trace').write_text(text)
        (trace / 'events/power/suspend_resume/enable').write_text('0\n')
        if wake_event.exists():
            wake_event.write_text('0\n')
        if wake_sources.exists():
            (out / f'cycle-{cycle:02d}-wake-after.txt').write_text(wake_sources.read_text())
        trace.rmdir()
        trace = None
        points = re.findall(r'(\d+\.\d+): suspend_resume: machine_suspend\[1\] (begin|end)', text)
        assert len(points) == 2 and [kind for _, kind in points] == ['begin', 'end']
        duration = float(points[1][0]) - float(points[0][0])
        assert duration > 9 and not alarm.read_text().strip()
        assert digest(file) == expected
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot
        assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
        result['cycles'].append({'cycle': cycle, 'real_sleep_seconds': duration, 'sha256_match': True})
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(f'PASS SD CYCLE {cycle}', flush=True)
    run(['umount', str(mount)])
    mounted = False
    fsck('fsck-after-suspend')
    run(['mount', '-t', 'vfat', '-o', 'rw,nosuid,nodev,noexec', str(media), str(mount)])
    mounted = True
    assert digest(file) == expected
    result['remount_sha256_match'] = True
    result['status'] = 'data checks passed; final fsck pending'
except BaseException as exc:
    result['status'] = 'failed or interrupted'
    result['error'] = repr(exc)
    error = exc
finally:
    if trace is not None:
        (trace / 'tracing_on').write_text('0\n')
        (out / 'interrupted.trace').write_text((trace / 'trace').read_text())
        if wake_sources.exists():
            (out / 'wake-after-abort.txt').write_text(wake_sources.read_text())
        if wake_event.exists():
            wake_event.write_text('0\n')
        (trace / 'events/power/suspend_resume/enable').write_text('0\n')
        if wake_event.exists():
            wake_event.write_text('0\n')
        if wake_sources.exists():
            (out / f'cycle-{cycle:02d}-wake-after.txt').write_text(wake_sources.read_text())
        trace.rmdir()
    alarm.write_text('0\n')
    if original['alarm'] and int(original['alarm']) > int(epoch.read_text()):
        alarm.write_text(original['alarm'] + '\n')
    mem.write_text(original['mem'] + '\n')
    udc.write_text(original['udc'] + '\n')
    if mounted:
        file.unlink(missing_ok=True)
        if owned.exists():
            owned.rmdir()
        os.sync()
        run(['umount', str(mount)])
        mounted = False
    (out / 'kernel-after.log').write_text(run(['dmesg']))
    result['unmounted_after'] = subprocess.run(['findmnt', '-rn', '-S', str(media)], capture_output=True).returncode == 1
    (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
if error:
    raise error
fsck('fsck-final')
assert result['unmounted_after']
result['status'] = 'passed'
result['final_fsck_exit'] = 0
(out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2), flush=True)
