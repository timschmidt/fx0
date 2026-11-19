"""Exercise the Fx0 Sway display and verify the DRM and RMI4 recovery paths."""

import argparse
from contextlib import contextmanager
from ctypes import CDLL, POINTER, byref, c_int, c_uint32, c_uint64
import os
import shutil
import time

import hashlib
import json
from pathlib import Path
import re
import subprocess

BOOT_ID = Path('/proc/sys/kernel/random/boot_id')

def read(path):
    return Path(path).read_text().strip()

def run(*args):
    return subprocess.run(args, capture_output=True, text=True, check=True, timeout=4).stdout.strip()

def guard_boot():
    assert read(BOOT_ID) == EXPECTED_BOOT
    assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() == NOTES_SHA256
    assert read('/proc/sys/kernel/tainted') == '0'
    assert read('/sys/module/module/parameters/sig_enforce') == 'Y'

def display_session():
    sockets = [path for path in Path('/run/user').glob('*/sway-ipc.*.sock') if path.is_socket()]
    assert len(sockets) == 1
    socket = sockets[0]
    assert re.fullmatch(r'/run/user/(\d+)/sway-ipc\.\1\.\d+\.sock', str(socket))
    return str(socket)

def output(socket):
    outputs = json.loads(run('swaymsg', '-s', socket, '-r', '-t', 'get_outputs'))
    assert len(outputs) == 1 and outputs[0]['name'] == 'DSI-1'
    return {key: outputs[0].get(key) for key in ('active', 'power', 'dpms', 'current_mode')}

def drm_display():
    paths = [path for path in Path('/sys/class/drm').glob('card*-DSI-1')]
    assert len(paths) == 1
    connector = paths[0]
    card = connector.name.split('-')[0]
    state = Path('/sys/kernel/debug/dri') / card.removeprefix('card') / 'state'
    text = read(state)
    crtc = re.findall(r'^crtc\[(\d+)\]: ([^\n]+)\n\s+enable=(\d+)\n\s+active=(\d+)', text, re.M)
    drm = {field: read(connector / field) for field in ('enabled', 'dpms', 'status')}
    drm['crtcs'] = [dict(object=int(num), name=name, enabled=int(enabled), active=int(active))
                    for num, name, enabled, active in crtc]
    assert drm['crtcs']
    return drm

def filters():
    names = ('sway', 'lisgd')
    result = {}
    for name in names:
        result[name] = [int(pid) for pid in run('pgrep', '-x', name).splitlines()]
    assert len(result['sway']) == 1 and len(result['lisgd']) == 1
    return result

def preflight():
    guard_boot()
    socket = display_session()
    events = [event.name for event in Path('/sys/kernel/tracing/events/drm').glob('*') if event.is_dir()]
    rmi = [path.name for path in Path('/sys/bus/rmi/devices').glob('*')]
    counter = {field: read(Path('/sys/power/suspend_stats') / field) for field in ('success', 'fail')}
    return dict(boot_id=EXPECTED_BOOT, sway=output(socket), drm=drm_display(), processes=filters(),
                suspend=counter, drm_trace_events=events, rmi_devices=rmi,
                rtc_clear=not read('/sys/class/rtc/rtc0/wakealarm'))


TRACE = Path('/sys/kernel/tracing')
RESTORE = f'fx0-display-restore-{os.getpid()}'
NAME = f'fx0_display_cycle_{os.getpid()}'


def vblank(crtc):
    paths = list(Path('/sys/class/drm').glob('card*-DSI-1'))
    assert len(paths) == 1
    device = Path('/dev/dri') / paths[0].name.split('-')[0]
    drm = CDLL('libdrm.so.2')
    get_sequence = drm.drmCrtcGetSequence
    get_sequence.argtypes = [c_int, c_uint32, POINTER(c_uint64), POINTER(c_uint64)]
    get_sequence.restype = c_int
    fd = os.open(device, os.O_RDWR | os.O_CLOEXEC)
    try:
        samples = []
        for index in range(2):
            seq, stamp = c_uint64(), c_uint64()
            assert get_sequence(fd, crtc, byref(seq), byref(stamp)) == 0
            samples.append((seq.value, stamp.value))
            if index == 0:
                time.sleep(0.11)
    finally:
        os.close(fd)
    delta = samples[1][0] - samples[0][0]
    nanoseconds = samples[1][1] - samples[0][1]
    assert 2 <= delta <= 45 and 0 < nanoseconds < 1000000000
    return delta


def matches(socket, power, expected_mode):
    status = output(socket)
    drm = drm_display()
    assert len(drm['crtcs']) == 1 and drm['status'] == 'connected'
    crtc = drm['crtcs'][0]
    if status['power'] is not power or crtc['active'] != int(power):
        return None
    if power:
        assert status['active'] and status['current_mode'] == expected_mode
    return crtc['object']


def wait_for(socket, power, expected_mode, timeout=3):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        crtc = matches(socket, power, expected_mode)
        if crtc is not None:
            return crtc
        time.sleep(0.12)
    raise TimeoutError('compositor and CRTC did not converge')


def switch(socket, power):
    reply = json.loads(run('swaymsg', '-s', socket, '-r', 'output', 'DSI-1',
                           'power', 'on' if power else 'off'))
    assert len(reply) == 1 and reply[0]['success'] is True


def arm_restore(socket, unit):
    timeout = shutil.which('timeout')
    swaymsg = shutil.which('swaymsg')
    assert timeout and swaymsg
    run('systemd-run', '--quiet', f'--unit={unit}', '--on-active=5s',
        '--timer-property=AccuracySec=100ms', '--property=Type=exec',
        timeout, '4', swaymsg, '-s', socket, '-r', 'output', 'DSI-1', 'power', 'on')
    assert run('systemctl', 'show', unit + '.timer', '-p', 'ActiveState', '--value') == 'active'
    assert run('systemctl', 'show', unit + '.timer', '-p', 'Unit', '--value') == unit + '.service'
    assert run('systemctl', 'show', unit + '.timer', '-p', 'NextElapseUSecMonotonic', '--value') not in ('0', 'n/a', '')
    assert run('systemctl', 'show', unit + '.service', '-p', 'Transient', '--value') == 'yes'


def unit_inactive(unit):
    state = subprocess.run(['systemctl', 'is-active', unit], capture_output=True, text=True, timeout=4)
    return state.returncode in (3, 4) and state.stdout.strip() in ('inactive', 'unknown')


def stop_restore(unit):
    for suffix in ('.timer', '.service'):
        name = unit + suffix
        if not unit_inactive(name):
            subprocess.run(['systemctl', 'stop', name], capture_output=True, timeout=4)
        assert unit_inactive(name)


def kprobe_control(line):
    fd = os.open(TRACE / 'kprobe_events', os.O_WRONLY | os.O_APPEND | os.O_CLOEXEC)
    try:
        data = (line + '\n').encode()
        assert os.write(fd, data) == len(data)
    finally:
        os.close(fd)


@contextmanager
def capture():
    instance = TRACE / 'instances' / NAME
    instance.mkdir()
    registered = []
    unavailable = []
    try:
        (instance / 'tracing_on').write_text('0\n')
        for name in ('rmi_driver_suspend', 'rmi_driver_resume', 'rmi_i2c_panel_prepared'):
            try:
                kprobe_control(f'r:{NAME}/{name} {name} result=$retval:s32')
            except OSError as error:
                unavailable.append([name, error.errno])
                continue
            registered.append(name)
            (instance / 'events' / NAME / name / 'enable').write_text('1\n')
        (instance / 'tracing_on').write_text('1\n')
        yield instance, unavailable
    finally:
        try:
            instance.rmdir()
        finally:
            for name in registered:
                kprobe_control(f'-:{NAME}/{name}')


def trace_results(instance):
    (instance / 'tracing_on').write_text('0\n')
    raw = read(instance / 'trace')
    entries = re.search(r'entries-in-buffer/entries-written:\s*(\d+)/(\d+)', raw)
    assert entries and entries[1] == entries[2]
    return {key: [int(value) for value in re.findall(rf'\b{key}: .*\bresult=(-?\d+)', raw)]
            for key in ('rmi_driver_suspend', 'rmi_driver_resume', 'rmi_i2c_panel_prepared')}


def cycle_display(report):
    before = preflight()
    socket = display_session()
    expected_mode = before['sway']['current_mode']
    assert expected_mode and before['rtc_clear']
    assert not run('systemctl', 'list-units', '--plain', '--no-legend', 'fx0-display-restore-*')
    assert not list((TRACE / 'instances').glob('fx0_display_cycle_*'))
    crtc = wait_for(socket, True, expected_mode)
    report['baseline_vblank_increment'] = vblank(crtc)
    assert read('/sys/class/power_supply/smbb-usbin/online') == '1'
    begin = time.monotonic()
    with capture() as (instance, omitted):
        for attempt in range(6):
            unit = f'{RESTORE}-{attempt}'
            try:
                report['stage'] = 'arm_restore'
                arm_restore(socket, unit)
                report['stage'] = 'power_off'
                switch(socket, False)
                wait_for(socket, False, expected_mode, timeout=2)
                report['stage'] = 'power_on'
                if attempt == 0:
                    wait_for(socket, True, expected_mode, timeout=6)
                    assert run('systemctl', 'show', unit + '.service', '-p', 'Result', '--value') == 'success'
                    report['timer_restored_first_cycle'] = True
                else:
                    time.sleep(0.45)
                    switch(socket, True)
                crtc = wait_for(socket, True, expected_mode)
                report['vblank_increments'].append(vblank(crtc))
            finally:
                report['cycle_index_at_cleanup'] = attempt
                # Keep the independent timer armed unless the exact output has
                # recovered. The timer also survives interruption of this probe.
                if not matches(socket, True, expected_mode):
                    switch(socket, True)
                if matches(socket, True, expected_mode):
                    stop_restore(unit)
            assert filters() == before['processes']
        report['trace_return_values'] = trace_results(instance)
        report['trace_unavailable'] = omitted
    report['stage'] = 'postflight'
    after = preflight()
    assert before == after
    assert not (TRACE / 'instances' / NAME).exists() and NAME not in read(TRACE / 'kprobe_events')
    for attempt in range(6):
        for suffix in ('.timer', '.service'):
            unit = f'{RESTORE}-{attempt}{suffix}'
            assert unit_inactive(unit)
    report.update(output=after['sway'], drm=after['drm'], same_processes=True,
                  rtc_clear=True, suspend_counts=after['suspend'],
                  cleanup_verified=True, elapsed_seconds=round(time.monotonic() - begin, 2), passed=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('boot_id', help='expected installed boot ID')
    parser.add_argument('notes_sha256', help='SHA-256 of the expected signed kernel notes')
    args = parser.parse_args()
    if os.geteuid() != 0 or not __debug__:
        parser.error('run as root with Python assertions enabled')
    EXPECTED_BOOT = args.boot_id
    NOTES_SHA256 = args.notes_sha256
    result = dict(boot_id=EXPECTED_BOOT, stage='baseline', vblank_increments=[])
    try:
        cycle_display(result)
        if result['trace_unavailable'] or any(
                returns != [0] * len(result['vblank_increments'])
                for returns in result['trace_return_values'].values()):
            result.update(passed=False, stage='RMI4 trace verification')
    except Exception as error:
        result.update(passed=False, error=type(error).__name__)
        if isinstance(error, subprocess.CalledProcessError):
            result.update(failed_command=Path(error.cmd[0]).name, returncode=error.returncode)
    print(json.dumps(result))
    raise SystemExit(0 if result['passed'] else 1)
