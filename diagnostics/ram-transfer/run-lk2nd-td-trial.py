#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run one matched Fastboot transport trial from a physical stock Fastboot entry."""
import argparse
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from dataclasses import dataclass

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import boot_fx0_ram as boot

PORTS = Path('/sys/bus/usb/devices')
PAIR_VERSION = 'OKAYfx0-usb-td-pair'
PAIR_PRODUCT = 'OKAYlk2nd-msm8226'
USBDEVFS_RESET = 0x5514
FASTBOOT_PAIR = {
    'control': ('d85a1dbb3720e468504c1a14a417d79191e3e6852013d41ed230139005da09ef', 32768),
    'single_td': ('60a88b8bedfe6c3f18815493701e0f981e0af45eb2ddfb2ca2e05073bf2d938b', 16384),
}
PAYLOAD_SHA256 = '0fff381eeb94f8ce8673404a3fb5d896e4767c0d9fb2eb3a942b00cb70980dce'
PAYLOAD_BYTES = 6809600
HOST_CHUNK = 16384
PACE_MS = 5


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def digest(path):
    with path.open('rb') as file:
        return hashlib.file_digest(file, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text())


def checked_image(row, file_key, size, expected):
    path = ROOT / row[file_key]
    boot.require(row['image_bytes' if file_key == 'image_path' else 'bytes'] == size and
                 path.stat().st_size == size, 'Wrong pinned image size')
    boot.require(digest(path) == expected, 'Pinned image checksum mismatch')
    return path


def inputs():
    pair = load(ROOT / 'manifests/lk2nd-fastboot-single-td.json')
    result = {}
    for arm, (sha256, limit) in FASTBOOT_PAIR.items():
        row = pair['images'][arm]
        boot.require(row['sha256'] == sha256 and pair['data_request_limit_bytes'][arm] == limit,
                     'Bootloader manifest differs from the verified pair')
        result[arm] = checked_image(row, 'path', 258064, sha256)
    payload = load(ROOT / 'manifests/nfc-open-teardown-startup-ram.json')['image']
    boot.require(payload['image_sha256'] == PAYLOAD_SHA256, 'Use the pinned XZ3 payload')
    return result, checked_image(payload, 'image_path', PAYLOAD_BYTES, PAYLOAD_SHA256)


@dataclass(frozen=True)
class UsbDevice:
    bus: int
    number: int
    vendor: str
    product: str
    speed: str
    serial: str

    def public(self):
        return {key: getattr(self, key) for key in ['bus', 'number', 'vendor', 'product', 'speed']}


def usb_at(path):
    try:
        bus = int((path / 'busnum').read_text())
        number = int((path / 'devnum').read_text())
        properties = [(path / name).read_text().strip()
                      for name in ['idVendor', 'idProduct', 'speed', 'serial']]
        if (bus, number) != (int((path / 'busnum').read_text()), int((path / 'devnum').read_text())):
            return None
    except (OSError, ValueError):
        return None
    return UsbDevice(bus, number, *properties)


def unique_device(path, device):
    boot.require(usb_at(path) == device, 'Device changed on the selected USB port')
    boot.require(re.fullmatch(r'[a-zA-Z0-9_.:-]+', device.serial) is not None, 'Invalid USB serial')
    matches = [entry for entry in PORTS.iterdir() if boot.read(entry / 'serial') == device.serial]
    boot.require(matches == [path], 'USB serial does not uniquely select this port')


def stock_query(path, device, name):
    unique_device(path, device)
    result = subprocess.run(['fastboot', '-s', device.serial, 'getvar', name],
                            capture_output=True, text=True, timeout=15)
    found = re.findall(r'^(?:\(bootloader\)\s*)?' + name + r':\s*(\S+)\s*$',
                       result.stdout + result.stderr, re.MULTILINE)
    boot.require(result.returncode == 0 and len(found) == 1, 'Stock Fastboot identity query failed')
    return found[0]


def stock_identity(path, device):
    boot.require(stock_query(path, device, 'product') == 'MADAI' and
                 stock_query(path, device, 'version') == '0.5',
                 'Expected stock MADAI Fastboot 0.5. Use the physical Volume Up entry.')
    unique_device(path, device)


def pair_identity(path, device):
    unique_device(path, device)
    boot.require((device.vendor, device.product) == ('18d1', 'd00d'), 'Expected lk2nd Fastboot USB')
    identity = boot.query(device.serial)
    boot.require(identity['product'][-1] == PAIR_PRODUCT and identity['lk2nd_version'][-1] == PAIR_VERSION,
                 'Expected the temporary lk2nd pair, version fx0-usb-td-pair')
    unique_device(path, device)


def wait_port(path, predicate, seconds=90):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        device = usb_at(path)
        if device is not None and predicate(device):
            return device
        time.sleep(0.25)
    raise RuntimeError('Expected USB mode did not appear on the selected port')


def usb_reset(path, device):
    unique_device(path, device)
    node, _, _, _ = boot.device(device.serial)
    with node.open('r+b', buffering=0) as file:
        fcntl.ioctl(file, USBDEVFS_RESET, 0)


def terminal(record):
    return 'returncode' in record and not (Path('/proc') / str(record['PID'])).exists()


def transfer_counts(result):
    confirmed = result['bytes']
    boot.require(0 <= confirmed <= PAYLOAD_BYTES, 'Invalid confirmed transfer progress')
    if result.get('phase') == 'readback':
        return {'download_confirmed_bytes': PAYLOAD_BYTES, 'readback_confirmed_bytes': confirmed}
    return {'download_confirmed_bytes': confirmed, 'readback_confirmed_bytes': 0}


class Trial:
    def __init__(self, arm, port, output, image, payload):
        self.arm = arm
        self.port = port
        self.output = output
        self.image = image
        self.payload = payload
        self.report = {
            'arm': arm, 'USB_port': port.name,
            'loader_sha256': FASTBOOT_PAIR[arm][0], 'loader_request_bytes': FASTBOOT_PAIR[arm][1],
            'payload_sha256': PAYLOAD_SHA256, 'payload_bytes': PAYLOAD_BYTES,
            'host_request_bytes': HOST_CHUNK, 'pace_ms': PACE_MS,
            'started_UTC': utc(), 'processes': {}, 'linux_BOOT_sent': False,
        }

    def save(self):
        path = self.output / 'trial.json'
        scratch = path.with_suffix('.tmp')
        scratch.write_text(json.dumps(self.report, indent=2) + '\n')
        scratch.replace(path)

    def run(self, name, command):
        record = {'started_UTC': utc()}
        self.report['processes'][name] = record
        with (self.output / (name + '.log')).open('xb') as log:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
            record['PID'] = process.pid
            self.save()
            # The transport tool owns its I/O timeout. Wait for the actual child.
            record['returncode'] = process.wait()
        record['finished_UTC'] = utc()
        self.save()
        boot.require(terminal(record), 'Child still exists after wait')
        return record['returncode']

    def stage(self, device):
        pair_identity(self.port, device)
        result_dir = self.output / 'transfer'
        rc = self.run('transfer', [sys.executable, str(ROOT / 'scripts/transfer_fx0_ram.py'),
                                   '--serial', device.serial, '--payload', str(self.payload),
                                   '--sha256', PAYLOAD_SHA256, '--output', str(result_dir),
                                   '--pace-ms', str(PACE_MS)])
        path = result_dir / 'result.json'
        if not path.is_file():
            return 'transfer failed before journal'
        result = load(path)
        boot.require(result['sha256'] == PAYLOAD_SHA256 and result['chunk_bytes'] == HOST_CHUNK and
                     result['pace_ms'] == PACE_MS, 'Unexpected transfer inputs')
        if not rc:
            boot.require(result['state'] == 'verified' and result['readback_sha256'] == PAYLOAD_SHA256 and
                         (result_dir / 'readback.bin').read_bytes() == self.payload.read_bytes(),
                         'Expected exact transfer readback')
            return 'verified'
        if result['state'] == 'failed' and result.get('last_IO', {}).get('errno') == 110:
            self.report['first_unconfirmed_request'] = result['last_IO']
            self.report.update(transfer_counts(result))
            self.save()
            return 'timeout'
        return 'transfer failed'

    def return_native(self, device, outcome):
        transfer = self.report['processes'].get('transfer')
        if transfer is not None:
            boot.require(terminal(transfer),
                         'Transfer is not confirmed terminal. Leave the USB session alone.')
        unique_device(self.port, device)
        if outcome == 'timeout':
            usb_reset(self.port, device)
            self.report['USB_reset_after_terminal_timeout'] = True
            self.save()
            device = wait_port(self.port, lambda current: current.serial == device.serial and
                               (current.vendor, current.product) == ('18d1', 'd00d'))
        pair_identity(self.port, device)
        self.report['USB_before_normal_reboot'] = device.public()
        self.save()
        boot.require(self.run('reboot', ['fastboot', '-s', device.serial, 'reboot']) == 0,
                     'Normal reboot did not acknowledge')
        native = wait_port(self.port, lambda current: (current.vendor, current.product) == ('18d1', 'd001'))
        self.report['native_USB'] = native.public()
        self.save()

    def execute(self):
        self.report['state'] = 'verifying stock Fastboot'
        self.save()
        stock = usb_at(self.port)
        boot.require(stock is not None, 'No USB device on selected port')
        stock_identity(self.port, stock)
        self.report['stock'] = stock.public() | {'product_name': 'MADAI', 'protocol': '0.5'}
        self.report['state'] = 'launching temporary lk2nd'
        self.save()
        launch = self.run('stock-boot', ['fastboot', '-s', stock.serial, 'boot', str(self.image)])
        try:
            device = wait_port(self.port, lambda current: (current.bus, current.number) != (stock.bus, stock.number)
                               and (current.vendor, current.product) == ('18d1', 'd00d'))
        except RuntimeError:
            if usb_at(self.port) != stock:
                raise
            stock_identity(self.port, stock)
            boot.require(self.run('reboot', ['fastboot', '-s', stock.serial, 'reboot']) == 0,
                         'Stock Fastboot reboot did not acknowledge')
            self.report['native_USB'] = wait_port(
                self.port, lambda current: (current.vendor, current.product) == ('18d1', 'd001')).public()
            raise RuntimeError('Temporary loader did not appear and stock Fastboot returned to native')
        pair_identity(self.port, device)
        self.report['temporary_lk2nd'] = device.public() | {'version': PAIR_VERSION.removeprefix('OKAY')}
        self.report['state'] = 'temporary lk2nd verified'
        self.save()
        outcome = 'uncertain launch acknowledgement' if launch else 'transfer failed to qualify'
        try:
            if not launch:
                outcome = self.stage(device)
        finally:
            self.report['transfer_outcome'] = outcome
            self.report['state'] = 'returning to native USB'
            self.save()
            self.return_native(device, outcome)
        boot.require(outcome in {'verified', 'timeout'}, outcome)


def compare_trials(directories):
    reports = [load(directory / 'trial.json') for directory in directories]
    outcomes = {}
    for directory, report, arm in zip(directories, reports, FASTBOOT_PAIR, strict=True):
        expected_hash, expected_limit = FASTBOOT_PAIR[arm]
        boot.require(report['arm'] == arm and report['state'] == 'terminal' and not report['linux_BOOT_sent'],
                     'Expected a terminal data-only receipt for each selected arm')
        boot.require((report['loader_sha256'], report['loader_request_bytes']) == (expected_hash, expected_limit),
                     'Receipt does not match the pinned loader')
        boot.require((report['payload_sha256'], report['payload_bytes'], report['host_request_bytes'],
                      report['pace_ms']) == (PAYLOAD_SHA256, PAYLOAD_BYTES, HOST_CHUNK, PACE_MS),
                     'Receipt does not match the shared payload and host settings')
        boot.require(report['stock']['protocol'] == '0.5' and report['stock']['product_name'] == 'MADAI' and
                     report['temporary_lk2nd']['version'] == PAIR_VERSION.removeprefix('OKAY'),
                     'Missing stock-to-temporary loader handoff evidence')
        generations = {(report[name]['bus'], report[name]['number'])
                       for name in ['stock', 'temporary_lk2nd', 'native_USB']}
        boot.require(len(generations) == 3, 'Expected fresh USB generations across the trial')
        boot.require(all(report['processes'][name]['returncode'] == 0 for name in ['stock-boot', 'reboot']),
                     'Missing acknowledged loader launch or normal reboot')
        boot.require((report['native_USB']['vendor'], report['native_USB']['product']) == ('18d1', 'd001'),
                     'Missing native USB return')
        transfer = load(directory / 'transfer/result.json')
        boot.require((transfer['sha256'], transfer['chunk_bytes'], transfer['pace_ms']) ==
                     (PAYLOAD_SHA256, HOST_CHUNK, PACE_MS), 'Transfer inputs differ from the receipt')
        transfer_code = report['processes']['transfer']['returncode']
        if report['transfer_outcome'] == 'verified':
            boot.require(transfer_code == 0 and transfer['state'] == 'verified' and
                         transfer_counts(transfer)['readback_confirmed_bytes'] == PAYLOAD_BYTES and
                         digest(directory / 'transfer/readback.bin') == PAYLOAD_SHA256,
                         'Readback does not match the pinned payload')
            outcomes[arm] = {'outcome': 'exact readback', 'bytes': PAYLOAD_BYTES}
        else:
            failed = transfer['last_IO']
            boot.require(transfer_code != 0 and report['transfer_outcome'] == 'timeout' and
                         transfer['state'] == 'failed' and
                         failed['errno'] == 110 and failed['actual_bytes'] is None and
                         report['first_unconfirmed_request'] == failed,
                         'Missing terminal timeout evidence')
            outcomes[arm] = {'outcome': 'timeout', **transfer_counts(transfer), 'first_unconfirmed_request': failed}
    ordered = sorted(reports, key=lambda report: report['started_UTC'])
    boot.require(ordered[0]['finished_UTC'] < ordered[1]['started_UTC'], 'The two sessions overlapped')
    boot.require(reports[0]['USB_port'] == reports[1]['USB_port'] and
                 reports[0]['temporary_lk2nd']['speed'] == reports[1]['temporary_lk2nd']['speed'],
                 'USB port or transfer speed differs between sessions')
    return {'USB_port': reports[0]['USB_port'], 'speed_Mbps': reports[0]['temporary_lk2nd']['speed'],
            'shared_payload_sha256': PAYLOAD_SHA256, 'outcomes': outcomes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-inputs', action='store_true')
    parser.add_argument('--compare', type=Path, nargs=2, metavar=('CONTROL_DIR', 'SINGLE_TD_DIR'))
    parser.add_argument('--arm', choices=FASTBOOT_PAIR)
    parser.add_argument('--usb-port', help='Physical port name, such as 1-14')
    parser.add_argument('--output', type=Path, help='Fresh private result directory')
    args = parser.parse_args()
    if args.check_inputs:
        inputs()
        print('Two pinned temporary lk2nd images and one shared r59 payload verified.')
        return
    if args.compare:
        print(json.dumps(compare_trials(args.compare), indent=2))
        return
    if not args.arm or not args.output or not args.usb_port or not re.fullmatch(r'\d+-\d+(?:\.\d+)*', args.usb_port):
        parser.error('Provide --arm, --usb-port and a fresh --output')
    images, payload = inputs()
    os.umask(0o077)
    lock = ROOT / 'local' / f'lk2nd-td-{args.usb_port}.lock'
    with lock.open('a') as file:
        fcntl.flock(file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        args.output.mkdir(mode=0o700, parents=True)
        trial = Trial(args.arm, PORTS / args.usb_port, args.output.resolve(), images[args.arm], payload)
        try:
            trial.execute()
        except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
            trial.report['failed_at'] = trial.report['state']
            uncertain_child = any('PID' in row and not terminal(row) for row in trial.report['processes'].values())
            trial.report['state'] = 'child completion unverified' if uncertain_child else 'terminal failure'
            trial.report['error_type'] = type(error).__name__
            (trial.output / 'trial-error.log').write_text(str(error) + '\n')
            print(f'Trial stopped in {args.output}. Inspect its private receipt and logs.', file=sys.stderr)
            raise SystemExit(1)
        else:
            trial.report['state'] = 'terminal'
            print(json.dumps({'arm': args.arm, 'transfer': trial.report['transfer_outcome'],
                              'native_USB_observed': True}))
        finally:
            trial.report['finished_UTC'] = utc()
            trial.save()


if __name__ == '__main__':
    main()
