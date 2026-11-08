#!/usr/bin/env python3
"""Run verified consecutive physical DMP wake cycles; operator motion is required."""
import argparse
import csv
import json
import math
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time


def interrupts(path):
    result = {}
    for line in path.read_text().splitlines():
        if ':' not in line:
            continue
        key, tail = line.split(':', 1)
        tokens, counts = tail.split(), []
        for token in tokens:
            if not token.isdigit():
                break
            counts.append(int(token))
        if counts:
            result[key.strip()] = (sum(counts), ' '.join(tokens[len(counts):]))
    return result


def verify_cycle(directory, boot_id):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest.get('error') or manifest['boot_id'] != boot_id:
        raise RuntimeError('cycle failed or boot identity changed')
    if manifest['armed_after_resume'] != '0' or manifest['disabled_after'] != '0':
        raise RuntimeError('motion event did not disarm')
    if len(manifest['events']) != 1 or manifest['events'][0]['code'] != '0x5021e1300000000':
        raise RuntimeError('cycle lacks exactly one SMD IIO event')
    if not manifest['rtc_alarm_after'] or int(manifest['rtc_alarm_after']) <= manifest['rtc_epoch_after']:
        raise RuntimeError('RTC fallback fired')
    controls = manifest.get('registers_before', {})
    if controls != {'0x23': 0, '0x38': 2, '0x6a': 128, '0x72': 0, '0x73': 0}:
        raise RuntimeError('hardware was not event-only with empty FIFO')
    trace = (directory / 'power-irq.trace').read_text()
    points = re.findall(r'(\d+\.\d+): suspend_resume: machine_suspend\[1\] (begin|end)', trace)
    starts = [float(t) for t, phase in points if phase == 'begin']
    ends = [float(t) for t, phase in points if phase == 'end']
    if len(starts) != 1 or len(ends) != 1 or ends[0] - starts[0] < 1:
        raise RuntimeError('not one real suspend interval of at least one second')
    before = interrupts(directory / 'interrupts-before.txt')
    after = interrupts(directory / 'interrupts-after.txt')
    imu = [(key, count - before.get(key, (0, ''))[0]) for key, (count, name) in after.items() if 'inv_mpu' in name]
    rtc = sum(count - before.get(key, (0, ''))[0] for key, (count, name) in after.items() if 'rtc' in name.lower())
    if len(imu) != 1 or imu[0][0] not in before or imu[0][1] != 1 or rtc != 0:
        raise RuntimeError(f'unexpected IRQ attribution: IMU={imu}, RTC delta={rtc}')
    kernel = (directory / 'kernel.log').read_text()
    if 'DMP resume status 0x4, event 1' not in kernel:
        raise RuntimeError('no retained SMD status at resume')
    if re.search(r'Kernel panic|stack-protector|Unbalanced|WARNING:|BUG:|DMP[^\n]*(?:failed|reset:)', kernel):
        raise RuntimeError('kernel or DMP recovery error during cycle')
    with (directory / 'quaternion-after-resume.csv').open() as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError('no quaternion recovery samples')
    stamps = [int(row['timestamp_ns']) for row in rows]
    if any(b <= a for a, b in zip(stamps, stamps[1:])):
        raise RuntimeError('nonmonotonic post-wake stream')
    if stamps[0] <= manifest['events'][0]['timestamp_ns']:
        raise RuntimeError('stream did not follow the wake event')
    for row in rows:
        norm = math.sqrt(sum(float(row[k]) ** 2 for k in ('w', 'x', 'y', 'z')))
        if not math.isfinite(norm) or abs(norm - 1) > 1e-5:
            raise RuntimeError('malformed quaternion recovery scan')
    return {'sleep_seconds': ends[0] - starts[0], 'IMU_irq': int(imu[0][0]),
            'IMU_irq_delta': 1, 'RTC_irq_delta': 0, 'event': manifest['events'][0],
            'quaternion_samples': len(rows), 'mdp5_warning_count': kernel.count('errors: 04000000')}


def write_manifest(path, value):
    temporary = path.with_suffix('.new')
    with temporary.open('w') as stream:
        json.dump(value, stream, indent=2); stream.write('\n'); stream.flush(); os.fsync(stream.fileno())
    temporary.replace(path)
    fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    os.fsync(fd); os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    parser.add_argument('--cycles', type=int, default=20)
    args = parser.parse_args()
    if not 1 <= args.cycles <= 20:
        parser.error('--cycles must be between 1 and 20')
    def interrupted(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGHUP, interrupted)
    os.umask(0o077)
    root = args.output.resolve()
    root.mkdir(mode=0o700, exist_ok=False)
    boot_id = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    summary = {'boot_id': boot_id, 'required': args.cycles, 'passed': [], 'status': 'running'}
    summary['observer_pid'] = os.getpid()
    batch_start = time.clock_gettime(time.CLOCK_BOOTTIME)
    write_manifest(root / 'summary.json', summary)
    try:
        for cycle in range(1, args.cycles + 1):
            if time.clock_gettime(time.CLOCK_BOOTTIME) - batch_start > 540:
                raise RuntimeError('operator window limit reached before all cycles completed')
            directory = root / f'cycle-{cycle:02d}'
            command = [sys.executable, str(Path(__file__).with_name('probe_smd_suspend.py')),
                       str(directory), '--motion', '--seconds', '45']
            with (root / f'observer-{cycle:02d}.log').open('x') as log:
                process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
                summary['active_cycle'] = cycle
                summary['child_pid'] = process.pid
                write_manifest(root / 'summary.json', summary)
                try:
                    for line in process.stdout:
                        log.write(line); log.flush()
                        if line.startswith('ARMED:'):
                            print(f'ARMED CYCLE {cycle}/{args.cycles}', flush=True)
                    code = process.wait()
                finally:
                    if process.poll() is None:
                        process.terminate()
                        process.wait()
                    process.stdout.close()
                    log.flush(); os.fsync(log.fileno())
            if code:
                raise RuntimeError(f'cycle {cycle} exited {code}; see observer log')
            record = verify_cycle(directory, boot_id)
            if Path('/proc/sys/kernel/random/boot_id').read_text().strip() != boot_id:
                raise RuntimeError('boot identity changed')
            record['cycle'] = cycle
            summary['passed'].append(record)
            write_manifest(root / 'summary.json', summary)
            print(f'PASS {cycle}/{args.cycles}: sleep {record["sleep_seconds"]:.2f}s, '
                  f'IMU IRQ 1, RTC IRQ 0, quaternion {record["quaternion_samples"]}', flush=True)
        summary['status'] = 'passed'
    except BaseException as error:
        summary['status'] = 'failed'
        summary['error'] = repr(error)
        raise
    finally:
        write_manifest(root / 'summary.json', summary)


if __name__ == '__main__':
    main()
