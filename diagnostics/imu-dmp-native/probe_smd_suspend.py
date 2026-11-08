#!/usr/bin/env python3
"""RTC-controlled real suspend with DMP SMD armed; no physical-motion wake claim."""
import argparse
import array
import csv
import fcntl
import json
import os
from pathlib import Path
import re
import select
import signal
import struct
import subprocess
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--seconds', type=int, default=12)
    parser.add_argument('--motion', action='store_true')
    parser.add_argument('--masked-motion', action='store_true')
    args = parser.parse_args()
    if args.motion and args.masked_motion:
        parser.error('--motion and --masked-motion are exclusive')
    if not 8 <= args.seconds <= 60:
        parser.error('--seconds must be between 8 and 60')
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    os.umask(0o077)
    out = args.output.resolve()
    out.mkdir(mode=0o700, exist_ok=False)
    devices = [p for p in Path('/sys/bus/iio/devices').glob('iio:device*')
               if (p / 'name').read_text().strip() == 'mpu6515']
    if len(devices) != 1:
        raise RuntimeError('expected one MPU6515')
    d = devices[0]
    event = d / 'events/in_activity_still_change_falling_en'
    wake = Path('/sys/bus/i2c/devices/0-0068/power/wakeup')
    alarm = Path('/sys/class/rtc/rtc0/wakealarm')
    rtc_epoch = Path('/sys/class/rtc/rtc0/since_epoch')
    memsleep = Path('/sys/power/mem_sleep')
    port = Path('/sys/kernel/debug/iio') / d.name / 'direct_reg_access'
    debug = Path('/sys/kernel/debug/dynamic_debug/control')
    wake_sources = Path('/sys/kernel/debug/wakeup_sources')
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    if event.read_text().strip() != '0' or (d / 'buffer/enable').read_text().strip() != '0':
        raise RuntimeError('IMU is already in use')
    pmtest = Path('/sys/power/pm_test')
    if pmtest.exists() and '[none]' not in pmtest.read_text():
        raise RuntimeError('disable simulated PM test levels first')
    saved_wake, saved_alarm = wake.read_text().strip(), alarm.read_text().strip()
    saved_mem = re.search(r'\[([^]]+)\]', memsleep.read_text()).group(1)
    usb = list(Path('/sys/class/udc').glob('*/device/power/wakeup'))
    saved_usb = {p: p.read_text().strip() for p in usb}
    debug_restore = []
    trace = None
    fd = event_fd = None
    result = {'boot_id': boot_id, 'seconds_requested': args.seconds,
              'scope': ('Masked physical-motion control' if args.masked_motion else 'Owner-assisted DMP wake test' if args.motion else 'RTC control with armed DMP; not a physical DMP wake pass')}
    error = None
    start_wall = int(time.time()) - 1

    def reg_read(address):
        port.write_text(f'0x{address:02x}\n')
        return int(port.read_text().strip(), 0)

    def counter():
        # Read-only RAM observation; explicitly address each byte in bank 1.
        data = bytearray()
        for offset in range(4):
            port.write_text('0x6d 0x01\n')
            port.write_text(f'0x6e 0x{128 + offset:02x}\n')
            data.append(reg_read(0x6f))
        return int.from_bytes(data, 'big')

    try:
        instances = Path('/sys/kernel/tracing/instances')
        if instances.exists():
            trace = instances / ('fx0-dmp-' + out.parent.name + '-' + out.name)
            trace.mkdir()
            (trace / 'buffer_size_kb').write_text('128\n')
            if 'boot' in (trace / 'trace_clock').read_text().replace('[', '').replace(']', '').split():
                (trace / 'trace_clock').write_text('boot\n')
            (trace / 'events/power/suspend_resume/enable').write_text('1\n')
            wake_event = trace / 'events/power/wakeup_source_activate/enable'
            if wake_event.exists():
                wake_event.write_text('1\n')
            for line in Path('/proc/interrupts').read_text().splitlines():
                if 'inv_mpu' in line:
                    irq = int(line.split(':', 1)[0])
                    (trace / 'events/irq/irq_handler_entry/filter').write_text(f'irq == {irq}\n')
                    (trace / 'events/irq/irq_handler_entry/enable').write_text('1\n')
                    break
            (trace / 'tracing_on').write_text('1\n')
        if debug.exists():
            for line in debug.read_text().splitlines():
                if 'inv_mpu_dmp.c:' in line:
                    location = line.split()[0]
                    flags = line.split('=', 1)[1].split()[0]
                    if 'p' not in flags:
                        debug_restore.append(location.rsplit(':', 1))
            debug.write_text('file inv_mpu_dmp.c +p\n')
        wake.write_text('enabled\n')
        for p in usb:
            p.write_text('disabled\n')
        memsleep.write_text('s2idle\n')
        fd = os.open('/dev/' + d.name, os.O_RDONLY | os.O_NONBLOCK)
        value = array.array('i', [0])
        fcntl.ioctl(fd, 0x80046990, value, True)
        event_fd = value[0]
        os.set_blocking(event_fd, False)
        if not args.masked_motion:
            event.write_text('1\n')
            result['registers_before'] = {hex(a): reg_read(a) for a in (0x23, 0x38, 0x6a, 0x72, 0x73)}
        else:
            result['masked_enable_readback'] = event.read_text().strip()
        if wake_sources.exists():
            (out / 'wakeup-sources-before.txt').write_text(wake_sources.read_text())
        (out / 'interrupts-before.txt').write_text(Path('/proc/interrupts').read_text())
        alarm.write_text('0\n')
        alarm.write_text(f'+{args.seconds}\n')
        result['rtc_alarm'] = alarm.read_text().strip()
        if not args.masked_motion:
            result['counter_before'] = counter()
        print('ARMED: entering real s2idle; keep still 5 seconds, then move for 15 seconds' if args.motion else 'MASKED CONTROL READY: keep still 5 seconds, then move for 15 seconds' if args.masked_motion else 'RTC CONTROL: armed; entering real s2idle', flush=True)
        before = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
        Path('/sys/power/state').write_text('mem\n')
        result['elapsed_boottime_ns'] = time.clock_gettime_ns(time.CLOCK_BOOTTIME) - before
        result['armed_after_resume'] = event.read_text().strip()
        if not args.masked_motion and result['armed_after_resume'] == '1':
            result['counter_after'] = counter()
            result['counter_delta'] = (result['counter_after'] - result['counter_before']) & 0xffffffff
        result['rtc_alarm_after'] = alarm.read_text().strip()
        result['rtc_epoch_after'] = int(rtc_epoch.read_text())
        if not args.masked_motion and result['armed_after_resume'] == '1':
            result['registers_after'] = {hex(a): reg_read(a) for a in (0x23, 0x38, 0x6a, 0x72, 0x73)}
        result['events'] = []
        if select.select([event_fd], [], [], 0)[0]:
            data = os.read(event_fd, 16 * 16)
            for offset in range(0, len(data), 16):
                code, stamp = struct.unpack_from('=Qq', data, offset)
                result['events'].append({'code': hex(code), 'timestamp_ns': stamp})
        if wake_sources.exists():
            (out / 'wakeup-sources-after.txt').write_text(wake_sources.read_text())
        (out / 'interrupts-after.txt').write_text(Path('/proc/interrupts').read_text())
        if args.motion:
            assert result['armed_after_resume'] == '0' and len(result['events']) == 1, 'no one-shot motion event'
            assert result['events'][0]['code'] == '0x5021e1300000000', 'wrong event identity'
            assert result['rtc_alarm_after'] and int(result['rtc_alarm_after']) > result['rtc_epoch_after'], 'RTC fallback fired'
            assert result['elapsed_boottime_ns'] < (args.seconds - 3) * 10**9, 'wake too close to RTC fallback'
        elif args.masked_motion:
            assert result['elapsed_boottime_ns'] > (args.seconds - 3) * 10**9, 'motion/other source caused early wake'
            assert result['armed_after_resume'] == '0' and not result['events'], 'masked control produced event'
            assert not result['rtc_alarm_after'], 'RTC control did not fire'
        else:
            assert result['elapsed_boottime_ns'] > (args.seconds - 3) * 10**9, 'early or aborted suspend'
            assert args.seconds * 100 < result['counter_delta'] < (args.seconds + 10) * 500, 'DMP did not retain execution'
            assert result['armed_after_resume'] == '1' and not result['events'], 'unexpected motion event'
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == boot_id
    except BaseException as exc:
        error = exc
        result['error'] = repr(exc)
    finally:
        try:
            event.write_text('0\n')
        finally:
            if event_fd is not None:
                os.close(event_fd)
            if fd is not None:
                os.close(fd)
            alarm.write_text('0\n')
            if saved_alarm and int(saved_alarm) > int(rtc_epoch.read_text()):
                alarm.write_text(saved_alarm + '\n')
            wake.write_text(saved_wake + '\n')
            for p, value in saved_usb.items():
                p.write_text(value + '\n')
            memsleep.write_text(saved_mem + '\n')
            for filename, line in debug_restore:
                debug.write_text(f'file {filename} line {line} -p\n')
        if trace is not None:
            (trace / 'tracing_on').write_text('0\n')
            (out / 'power-irq.trace').write_text((trace / 'trace').read_text())
            trace.rmdir()
        result['disabled_after'] = event.read_text().strip()
        result['raw_after'] = [int((d / f'in_accel_{axis}_raw').read_text()) for axis in 'xyz']
        journal = subprocess.run(['journalctl', '-k', '-b', '--since', '@' + str(start_wall), '--no-pager'], capture_output=True, text=True)
        (out / 'kernel.log').write_text(journal.stdout + journal.stderr)
        with (out / 'manifest.json').open('x') as stream:
            json.dump(result, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
        print(json.dumps(result, indent=2), flush=True)
    if error:
        raise error
    if args.motion and 'DMP resume status 0x4, event 1' not in journal.stdout:
        raise RuntimeError('retained SMD status not recorded at resume')
    reader = Path(__file__).with_name('read_quaternion.py')
    with (out / 'quaternion-after-resume.csv').open('x') as output, (out / 'quaternion-after-resume.log').open('x') as log:
        subprocess.run(['python3', str(reader), '--seconds', '3'], stdout=output, stderr=log, timeout=30, check=True)
        output.flush(); os.fsync(output.fileno())
        log.flush(); os.fsync(log.fileno())


if __name__ == '__main__':
    main()
