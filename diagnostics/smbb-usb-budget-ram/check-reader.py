#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Test the ARM register reader and read-only diagnostic endpoints with synthetic inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
QEMU = shutil.which('qemu-arm-static')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reader', type=Path, required=True)
    parser.add_argument('--busybox', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(mode=0o700)
    reader = args.reader.resolve()
    busybox = args.busybox.resolve()
    assert QEMU
    checks = []

    def check(name, condition):
        assert condition, name
        checks.append(name)

    register_map = {0x1049: 0, 0x1208: 0x80, 0x1304: 2, 0x1305: 0x34,
                    0x1310: 2, 0x1344: 5, 0x1347: 0, 0x1348: 0}
    values = b''.join(f'{address:04x}: {register_map.get(address, 0):02x}\n'.encode()
                      for address in range(0x1349))
    raw = output / 'raw-regmap'
    raw.write_bytes(values)
    expected = 'charge_control=00 battery_presence=80 usb_rt=02 imax_selector=05 usb_suspend=00 usb_otg=00\n'
    result = subprocess.run([QEMU, '-strace', reader, raw], capture_output=True, text=True)
    (output / 'arm-strace.log').write_text(result.stderr)
    check('ARM register tuple', result.returncode == 0 and result.stdout == expected)
    check('exactly eight bounded ARM pread calls',
          len(re.findall(r'\bpread64\(', result.stderr)) == 8 and
          all(str(9 * offset) in result.stderr for offset in register_map))
    check('read-only ARM register access', str(raw) + '",O_RDONLY' in result.stderr and raw.read_bytes() == values)

    for name, offset, field in [
        ('wrong subtype', 0x1305, b'1305: 02\n'),
        ('wrong USB type', 0x1304, b'1304: 00\n'),
        ('misaligned row', 0x1344, b'1345: 05\n'),
        ('non-hex value', 0x1347, b'1347: XX\n'),
        ('missing newline', 0x1348, b'1348: 00\r'),
    ]:
        start = offset * 9
        raw.write_bytes(values[:start] + field + values[start + 9:])
        result = subprocess.run([QEMU, reader, raw], capture_output=True, text=True)
        check(name, result.returncode == 1 and not result.stdout)
    raw.write_bytes(values[:-3])
    result = subprocess.run([QEMU, reader, raw], capture_output=True, text=True)
    check('short read rejected', result.returncode == 1 and not result.stdout)
    raw.write_bytes(values)

    sys = output / 'sys'
    map_path = sys / 'kernel/debug/regmap/0-00'
    map_path.mkdir(parents=True)
    (map_path / 'registers').symlink_to(raw)
    (map_path / 'range').write_text('0-ffff\n')
    usb = sys / 'class/power_supply/smbb-usbin'
    battery = sys / 'class/power_supply/smbb-bif'
    udc = sys / 'class/udc/ci_hdrc.0'
    gadget = sys / 'kernel/config/usb_gadget/fx0-budget'
    charger = sys / 'firmware/devicetree/base/soc/spmi@fc4cf000/pm8226@0/charger@1000'
    parent = sys / 'devices/0-00/0-00:charger@1000'
    for path in [usb, battery, udc, gadget, charger, parent]:
        path.mkdir(parents=True)
    (usb / 'device').symlink_to(parent)
    for file, content in [
        (usb / 'online', '1'), (usb / 'input_current_limit', '500000'),
        (usb / 'charge_control_limit', '500000'), (battery / 'present', '1'),
        (battery / 'charge_behaviour', 'auto [inhibit-charge]'), (udc / 'state', 'configured'),
        (udc / 'current_speed', 'high-speed'), (gadget / 'UDC', 'ci_hdrc.0'),
    ]:
        file.write_text(content + '\n')
    wrapper = output / 'run-arm-reader'
    wrapper.write_text(f'#!/bin/sh\nexec {shlex.quote(QEMU)} {shlex.quote(str(reader))} "$@"\n')
    wrapper.chmod(0o700)

    def sample():
        return subprocess.run(['/bin/sh', HERE / 'sample', sys, wrapper], capture_output=True, text=True)

    line = ('state=configured speed=high-speed bound=1 online=1 battery=1 charging=inhibited '
            'input_uA=500000 legacy_uA=500000 ' + expected)
    result = sample()
    check('control sample', result.returncode == 0 and result.stdout == 'mode=control ' + line)
    (charger / 'qcom,usb-gadget-current-limit').touch()
    result = sample()
    check('managed sample', result.returncode == 0 and result.stdout == 'mode=managed ' + line)
    (usb / 'input_current_limit').write_text('0\n')
    (udc / 'state').write_text('suspended\n')
    raw.write_bytes(values.replace(b'1347: 00\n', b'1347: 01\n'))
    result = sample()
    check('suspended sample', result.returncode == 0 and 'state=suspended' in result.stdout
          and 'input_uA=0' in result.stdout and 'usb_suspend=01' in result.stdout)
    (map_path / 'range').write_text('0-1350\n')
    check('partial map rejected', sample().returncode != 0)
    (map_path / 'range').write_text('0-ffff\n')
    (usb / 'device').unlink()
    wrong_parent = sys / 'devices/0-01/0-01:charger@1000'
    wrong_parent.mkdir(parents=True)
    (usb / 'device').symlink_to(wrong_parent)
    check('wrong SPMI parent rejected', sample().returncode != 0)
    (usb / 'device').unlink()
    (usb / 'device').symlink_to(parent)
    (udc / 'state').write_text('not attached\n')
    (udc / 'current_speed').write_text('UNKNOWN\n')
    (gadget / 'UDC').write_text('\n')
    result = sample()
    check('detached sample', result.returncode == 0 and 'state=not_attached speed=UNKNOWN bound=0' in result.stdout)
    (usb / 'input_current_limit').write_text('bad\n')
    check('invalid limit rejected', sample().returncode != 0)

    www = output / 'www'
    www.mkdir()
    (www / 'status.txt').write_text(line)
    for method, path, status in [('GET', '/status.txt', b'200'), ('GET', '/trace.txt', b'404'),
                                  ('GET', '/init', b'404'), ('POST', '/status.txt', b'404')]:
        response = subprocess.check_output(['/bin/sh', HERE / 'serve-http', www],
                                           input=f'{method} {path} HTTP/1.0\r\n\r\n'.encode())
        head, body = response.split(b'\r\n\r\n', 1)
        check(f'{method} {path}', head.startswith(b'HTTP/1.0 ' + status) and
              (body == line.encode() if status == b'200' else not body) and
              f'Content-Length: {len(body)}'.encode() in head)
    (www / 'trace.txt').write_text('synthetic trace\n')
    result = subprocess.check_output(['/bin/sh', HERE / 'serve-http', www],
                                     input=b'GET /trace.txt HTTP/1.0\r\n\r\n')
    check('trace file readable', result.endswith(b'\r\n\r\nsynthetic trace\n'))

    for script in ['init', 'sample', 'serve-http']:
        check(f'ARM BusyBox syntax {script}', subprocess.run(
            [QEMU, busybox, 'sh', '-n', HERE / script], capture_output=True).returncode == 0)
    record = {'cases': len(checks), 'passed': checks, 'reader_sha256': hashlib.sha256(reader.read_bytes()).hexdigest(),
              'scope': 'QEMU ARM reader, synthetic sysfs and HTTP fixtures, and ARM BusyBox syntax'}
    (output / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
