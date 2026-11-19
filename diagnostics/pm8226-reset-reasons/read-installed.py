"""Read the PM8226 PON reasons and watchdog config on the signed Fx0 6.18.64 build."""

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import re
import sys


BOOT_ID = Path('/proc/sys/kernel/random/boot_id')
NOTES_SHA256 = '68596b5e7190f9dcd66eaa0cfeff249f02d920ce4c296611fc441212d42c7a0a'
REASONS = (0x808, 0x80a, 0x80b, 0x80c, 0x80d)
WATCHDOG_CONFIG = (0x854, 0x855, 0x856, 0x857)
REGISTERS = REASONS + WATCHDOG_CONFIG
LINE_BYTES = 9


def read_byte(fd, address):
    if address not in REGISTERS:
        raise ValueError('address outside the PON allowlist')
    line = os.pread(fd, LINE_BYTES, address * LINE_BYTES)
    match = re.fullmatch(rb'([0-9a-f]{4}): ([0-9a-f]{2})\n', line)
    if not match or int(match[1], 16) != address:
        raise RuntimeError('register read failed or returned a different address')
    return int(match[2], 16)


def verify_trace(trace, snapshots):
    count = re.search(r'entries-in-buffer/entries-written:\s*(\d+)/(\d+)', trace)
    if not count or count[1] != count[2]:
        raise RuntimeError('missing trace counters or overwritten events')
    begins = re.findall(r'spmi_read_begin: .* sid=(\d+) addr=(0x[0-9a-f]+)\b', trace)
    ends = re.findall(r'spmi_read_end: .* sid=(\d+) addr=(0x[0-9a-f]+)'
                      r' ret=(-?\d+) len=(\d+) buf=0x\[([0-9a-f]{2})\]', trace)
    actual_reads = Counter((int(sid), int(address, 16)) for sid, address in begins)
    actual_results = Counter((int(sid), int(address, 16), int(status), int(size), int(value, 16))
                             for sid, address, status, size, value in ends)
    expected_reads = Counter((0, address) for snapshot in snapshots for address in snapshot)
    expected_results = Counter((0, address, 0, 1, value)
                               for snapshot in snapshots for address, value in snapshot.items())
    if (actual_reads != expected_reads or actual_results != expected_results or
            int(count[1]) != len(begins) + len(ends)):
        raise RuntimeError('unexpected SPMI traffic or missing read evidence')
    return len(begins)


def read_with_trace(registers):
    trace = Path('/sys/kernel/tracing/instances') / f'fx0-pon-reasons-{os.getpid()}'
    trace.mkdir()
    try:
        (trace / 'tracing_on').write_text('0\n')
        (trace / 'set_event_pid').write_text(f'{os.getpid()}\n')
        # Enable all SPMI events for this process so an unexpected write or
        # command also fails trace validation.
        (trace / 'events/spmi/enable').write_text('1\n')
        (trace / 'tracing_on').write_text('1\n')
        fd = os.open(registers, os.O_RDONLY | os.O_CLOEXEC)
        try:
            snapshots = [{address: read_byte(fd, address) for address in REGISTERS}
                         for _ in range(2)]
        finally:
            os.close(fd)
        (trace / 'tracing_on').write_text('0\n')
        reads = verify_trace((trace / 'trace').read_text(), snapshots)
        return snapshots, reads
    finally:
        trace.rmdir()


def capture(expected_boot):
    boot = BOOT_ID.read_text().strip()
    if (boot != expected_boot or os.uname().release != '6.18.64-fx0-lts-alpine' or
            hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest() != NOTES_SHA256 or
            Path('/proc/sys/kernel/tainted').read_text().strip() != '0' or
            Path('/sys/module/module/parameters/sig_enforce').read_text().strip() != 'Y'):
        raise RuntimeError('the expected installed Fx0 boot is required')

    device = Path('/sys/bus/spmi/devices/0-00')
    compatible = (device / 'of_node/compatible').read_bytes().split(b'\0')
    if b'qcom,pm8226' not in compatible or (device / 'driver').resolve().name != 'pmic-spmi':
        raise RuntimeError('SID zero is not the bound PM8226')
    regmap = Path('/sys/kernel/debug/regmap') / device.name
    # The range file builds and checks the offset map without issuing SPMI
    # transfers. The installed uncached 16-bit register / 8-bit value map
    # gives one complete nine-byte record per register in this single range.
    with (regmap / 'range').open('rb', buffering=0) as ranges:
        if ranges.read(64) != b'0-ffff\n' or (regmap / 'cache_only').exists():
            raise RuntimeError('unexpected register layout or cache')

    snapshots, reads = read_with_trace(regmap / 'registers')
    if boot != BOOT_ID.read_text().strip():
        raise RuntimeError('the boot changed during capture')
    return dict(passed=True, boot_id=boot, reset_reasons=[
        ' '.join(f'{row[address]:02x}' for address in REASONS) for row in snapshots],
        watchdog_config=[
        ' '.join(f'{row[address]:02x}' for address in WATCHDOG_CONFIG) for row in snapshots],
        read_addresses=[f'{address:#x}' for address in REGISTERS],
        SPMI_reads=reads, SPMI_writes=0, lost_trace_entries=0)


if __name__ == '__main__':
    if len(sys.argv) != 2:
        raise SystemExit('Usage: read-installed.py EXPECTED_BOOT_ID')
    print(json.dumps(capture(sys.argv[1])))
