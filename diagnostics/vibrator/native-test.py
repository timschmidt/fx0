#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the installed Fx0 Sxmo vibrator path against PM8226 and MPU-6515."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import time

DEFAULT = Path('/dev/input/by-path/platform-vibrator-event')
VIBRATOR = Path('/dev/input/by-path/platform-fc4cf000.spmi-platform-fc4cf000.spmi:pm8226@1:vibrator@c000-event')
SYSMAP = Path('/sys/kernel/debug/regmap/0-01')
SXMO = Path('/usr/bin/sxmo_vibrate')
NOTES = 'cb8ff4d80009dbd0b4542ce5d28d7ce10e4d84e0db4e332c749ff8ae18a08269'
STRENGTH = 153 << 8  # Measured code 21 on uncorrected r50, bounded below the stock 2.4 V target.


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    return Path(path).read_text().strip()


def cmd(*args):
    return subprocess.check_output(args, text=True, timeout=10).strip()


def registers(fd):
    values = []
    for address in (0xc041, 0xc046):
        raw = os.pread(fd, 9, address * 9)
        require(len(raw) == 9 and raw.startswith(f'{address:04x}: '.encode()), 'SPMI regmap layout')
        values.append(int(raw[6:8], 16))
    return tuple(values)


def inventory(boot_id):
    require(read('/proc/sys/kernel/random/boot_id') == boot_id, 'native boot changed')
    require(os.uname().release == '6.18.59-fx0-dmp' and read('/proc/sys/kernel/tainted') == '0', 'native r50 identity')
    require(hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() == NOTES, 'linked r50 identity')
    sensors = [path for path in Path('/sys/bus/iio/devices').glob('iio:device*') if read(path / 'name') == 'mpu6515']
    require(len(sensors) == 1 and read(sensors[0] / 'buffer/enable') == '0', 'idle MPU-6515 direct mode')
    event = VIBRATOR.resolve(strict=True)
    input_dev = Path('/sys/class/input') / event.name / 'device'
    require(read(input_dev / 'name') == 'pm8xxx_vib_ffmemless', 'vibrator input identity')
    require((input_dev / 'device').resolve().name == 'fc4cf000.spmi:pm8226@1:vibrator@c000', 'PM8226 vibrator parent')
    require(read(SYSMAP / 'range') == '0-ffff', 'SPMI regmap range')
    require(read('/sys/class/power_supply/smbb-usbin/online') == '1', 'USB power source changed')
    require(cmd('systemctl', 'is-system-running') == 'running', 'native startup')
    sway = Path('/proc') / cmd('pgrep', '-x', 'sway')
    creds = sway.stat()
    groups = re.search(r'^Groups:\s+([\d \t]+)$', read(sway / 'status'), re.M)
    require(creds.st_uid != 0 and groups, 'native graphical session credentials')
    return sensors[0], sway.name, {'user': creds.st_uid, 'group': creds.st_gid,
                                  'extra_groups': [int(gid) for gid in groups[1].split()]}


def samples(fd, sensor, seconds, rows):
    limit = time.monotonic() + seconds
    while time.monotonic() < limit:
        then = time.monotonic()
        drv, en = registers(fd)
        axes = [int(read(sensor / f'in_accel_{axis}_raw')) for axis in 'xyz']
        rows.append((then, drv, en, axes))
        time.sleep(max(0, then + 0.008 - time.monotonic()))


def rms(rows):
    require(len(rows) >= 5, 'too few motion samples')
    return (sum(statistics.pvariance(axis) for axis in zip(*(row[3] for row in rows)))) ** 0.5


def effect(fd, sensor, creds, milliseconds, strength):
    rows = []
    samples(fd, sensor, 0.3, rows)
    require(all(row[1:3] == (0, 0) for row in rows), 'vibrator must start idle')
    env = {'PATH': '/usr/bin:/bin', 'LANG': 'C', 'SXMO_VIBRATE_DEV': str(VIBRATOR)}
    args = [SXMO, str(milliseconds)] + ([] if strength is None else [str(strength)])
    with subprocess.Popen(args, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **creds) as child:
        try:
            samples(fd, sensor, milliseconds / 1000 + 0.25, rows)
            _, error = child.communicate(timeout=1)
            require(child.returncode == 0, f'Sxmo vibrator exited {child.returncode}: {error.decode(errors="replace")}')
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=2)
    require(registers(fd) == (0, 0), 'vibrator registers did not return to off')
    enabled = [index for index, row in enumerate(rows) if row[2] & 0x80]
    if strength is None:
        require(not enabled, 'implicit strength unexpectedly enabled the vibrator')
        return {'requested_ms': milliseconds, 'explicit_strength': None, 'enabled_samples': 0,
                'command_exit': 0, 'PMIC_off_after': True}

    require(enabled, 'no PMIC enable observed for explicit strength')
    first, last = enabled[0], enabled[-1]
    require(first > 0 and last < len(rows) - 1 and enabled == list(range(first, last + 1)), 'unexpected enable transitions')
    observed = [rows[index][1:3] for index in enabled]
    # The driver clears drive before enable on stop. Only the final enabled
    # sample can straddle these two register writes.
    stable_last = last - (observed[-1] == (0, 128))
    stable = rows[first:stable_last + 1]
    require(stable and all(row[1:3] == (21, 128) for row in stable),
            f'unexpected enabled PMIC register values: {sorted(set(observed))}')
    lower = (rows[last][0] - rows[first][0]) * 1000
    upper = (rows[last + 1][0] - rows[first - 1][0]) * 1000
    require(lower <= milliseconds + 70 and upper >= milliseconds - 70 and upper - lower < 80, 'unexpected pulse timing')
    on_motion = rms(stable)
    off_motion = rms(rows[:first])
    settled = rms(rows[-10:])
    ratio = on_motion / max(off_motion, settled, 1)
    return {'requested_ms': milliseconds, 'explicit_strength': strength, 'enabled_samples': len(enabled),
            'PMIC_drive_code': 21, 'programmed_target_mV': 2100, 'PMIC_off_after': True,
            'terminal_enable_clear_sample': stable_last != last,
            'enable_duration_bounds_ms': [round(lower, 2), round(upper, 2)],
            'motion_RMS_ratio': round(ratio, 3), 'motion_fourfold_increase': ratio > 4,
            'sample_count': len(rows),
            'accel_vector_RMS_counts': {'pre': round(off_motion, 2), 'enabled': round(on_motion, 2),
                                        'settled': round(settled, 2)}}


def run(boot_id):
    sensor, sway, creds = inventory(boot_id)
    require(not os.path.lexists(DEFAULT), 'default vibrator path is already present')
    report = {'boot_id': boot_id, 'Sway_PID': int(sway), 'uses_native_graphical_user_credentials': True, 'pulses': []}
    with (SYSMAP / 'registers').open('rb') as regmap:
        fd = regmap.fileno()
        require(registers(fd) == (0, 0), 'vibrator is not idle')
        failed = subprocess.run([SXMO, '100'], env={'PATH': '/usr/bin:/bin', 'LANG': 'C'},
                                capture_output=True, text=True, timeout=2, **creds)
        require(failed.returncode != 0 and "Can't open vibrator event device" in failed.stderr,
                'default path did not reproduce the open failure')
        report['missing_path'] = {'default_link_exists': False, 'returncode': failed.returncode}
        report['implicit_strength'] = effect(fd, sensor, creds, 300, None)
        for milliseconds in (150, 300, 600):
            report['pulses'].append(effect(fd, sensor, creds, milliseconds, STRENGTH))
    require(inventory(boot_id)[1] == sway, 'Sway changed during trial')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    print(json.dumps(run(parser.parse_args().boot_id)))
