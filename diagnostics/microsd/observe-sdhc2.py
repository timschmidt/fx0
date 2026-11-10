#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe Fx0 SDHC2 and GPIO37 counters with an optional bounded direct read."""
import argparse
import json
import mmap
import os
from pathlib import Path
import re
import stat
import struct
import time

SDHC_NODE = '/soc/mmc@f98a4900'
HOST = 'mmc1'
READ_BYTES = 4 * 1024 * 1024
ROLES = {
    'controller': ('GIC-0', 157, 'Level', HOST),
    'power': ('GIC-0', 253, 'Level', 'f98a4900.mmc'),
    'card_detect': ('msmgpio', 37, 'Edge', 'f98a4900.mmc cd'),
}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def interrupt_rows(text):
    lines = text.splitlines()
    require(bool(lines), 'Empty interrupt table')
    cpus = lines[0].split()
    require(bool(cpus) and len(cpus) == len(set(cpus)) and all(re.fullmatch(r'CPU\d+', cpu) for cpu in cpus),
            'Missing or invalid CPU counter columns')
    matches = {}
    for line in lines[1:]:
        irq, separator, body = line.partition(':')
        if not separator or not irq.strip().isdigit():
            continue
        fields = body.split(maxsplit=len(cpus))
        if len(fields) != len(cpus) + 1:
            continue
        info = fields[-1].split(maxsplit=3)
        if len(info) != 4 or not info[1].isdigit():
            continue
        chip, hardware, trigger, action = info
        for role, identity in ROLES.items():
            if (chip, int(hardware), trigger, action) != identity:
                continue
            require(role not in matches and all(value.isdigit() for value in fields[:-1]),
                    f'Ambiguous or invalid {role} interrupt row')
            matches[role] = {'irq': int(irq), 'chip': chip, 'hwirq': int(hardware), 'trigger': trigger,
                             'action': action, 'per_cpu': dict(zip(cpus, map(int, fields[:-1])))}
    require(matches.keys() == ROLES.keys(), 'Missing expected SDHC2 or GPIO37 interrupt row')
    return matches


def counter_delta(before, after):
    deltas = {}
    for role in ROLES:
        a, b = before[role], after[role]
        require(all(a[name] == b[name] for name in ['irq', 'chip', 'hwirq', 'trigger', 'action']),
                f'{role} IRQ identity changed during the sample')
        require(a['per_cpu'].keys() == b['per_cpu'].keys(), 'CPU columns changed during the sample')
        require(all(b['per_cpu'][cpu] >= a['per_cpu'][cpu] for cpu in a['per_cpu']),
                f'{role} counters decreased during the sample')
        deltas[role] = sum(b['per_cpu'].values()) - sum(a['per_cpu'].values())
    return deltas


def read_text(path):
    return path.read_text().strip()


def identify(sysfs):
    tree = sysfs/'firmware/devicetree/base'
    alias = (tree/'aliases'/HOST).read_bytes()
    require(alias == SDHC_NODE.encode() + b'\0', 'mmc1 DT alias is not Fx0 SDHC2')
    of_node = tree/SDHC_NODE.lstrip('/')
    host = sysfs/'class/mmc_host'/HOST
    parent = host.resolve().parent.parent
    require(parent.name == 'f98a4900.mmc' and (parent/'of_node').resolve() == of_node and
            (parent/'driver').resolve().name == 'sdhci_msm', 'SDHC2 driver or OF topology differs')
    irqs = struct.unpack('>6I', (of_node/'interrupts').read_bytes())
    require(irqs == (0, 125, 4, 0, 221, 4), 'SDHC2 GIC interrupt specifiers differ')
    phandle, pin, flags = struct.unpack('>3I', (of_node/'cd-gpios').read_bytes())
    tlmm = (sysfs/'bus/platform/devices/fd510000.pinctrl/of_node').resolve()
    require(tlmm.is_relative_to(tree) and struct.unpack('>I', (tlmm/'phandle').read_bytes())[0] == phandle and
            (pin, flags) == (37, 1), 'Card-detect GPIO controller, number or polarity differs')
    cards = [path for path in host.glob('mmc1:*') if (path/'type').exists()]
    require(len(cards) == 1 and read_text(cards[0]/'type') == 'SD', 'Expected one SD card in SDHC2')
    blocks = list((cards[0]/'block').glob('mmcblk*'))
    require(len(blocks) == 1 and re.fullmatch(r'mmcblk\d+', blocks[0].name), 'Expected one SD block disk')
    block = blocks[0].resolve()
    require((sysfs/'class/block'/block.name).resolve() == block, 'SD block alias does not match its host')
    return block


def snapshot(sysfs, proc, block):
    interrupts = interrupt_rows(read_text(proc/'interrupts'))
    for line in interrupts.values():
        metadata = sysfs/'kernel/irq'/str(line['irq'])
        require(int(read_text(metadata/'hwirq')) == line['hwirq'] and
                read_text(metadata/'actions') == line['action'] and
                read_text(metadata/'type') == line['trigger'].lower(), 'IRQ sysfs identity differs from proc')
    disk = list(map(int, read_text(block/'stat').split()))
    gpio = [line.strip() for line in (sysfs/'kernel/debug/gpio').read_text().splitlines()
            if re.match(r'\s*gpio-?37\s*:', line)]
    require(len(gpio) == 1 and len(disk) >= 7, 'Missing GPIO37 or SD disk statistics')
    return {'monotonic_seconds': time.monotonic(), 'IRQs': interrupts, 'GPIO37': gpio[0],
            'diskseq': int(read_text(block/'diskseq')), 'device_number': read_text(block/'dev'),
            'sectors_read': disk[2], 'sectors_written': disk[6]}


def compare(before, after):
    require(before['diskseq'] == after['diskseq'] and before['device_number'] == after['device_number'],
            'SD block device changed during the sample')
    sectors_read = after['sectors_read'] - before['sectors_read']
    sectors_written = after['sectors_written'] - before['sectors_written']
    require(sectors_read >= 0 and sectors_written >= 0, 'SD block counters decreased during the sample')
    return {'seconds': after['monotonic_seconds'] - before['monotonic_seconds'],
            'IRQ_delta': counter_delta(before['IRQs'], after['IRQs']),
            'sectors_read': sectors_read, 'sectors_written': sectors_written}


def check_unmounted(block, proc):
    device_numbers = {read_text(block/'dev')}
    for part in block.glob(block.name+'p*'):
        if (part/'partition').exists():
            device_numbers.add(read_text(part/'dev'))
    mounted = {row.split()[2] for row in (proc/'self/mountinfo').read_text().splitlines()}
    require(not mounted.intersection(device_numbers), 'SD media is mounted in the current mount namespace')
    require(not any((block/'holders').iterdir()), 'SD block disk has active holders')
    for part in block.glob(block.name+'p*'):
        if (part/'partition').exists():
            require(not any((part/'holders').iterdir()), 'SD partition has active holders')


def direct_read(block, proc):
    check_unmounted(block, proc)
    major, minor = map(int, read_text(block/'dev').split(':'))
    require(int(read_text(block/'size')) * 512 >= READ_BYTES, 'SD disk too small for the read control')
    fd = os.open('/dev/'+block.name, os.O_RDONLY | os.O_DIRECT | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        require(stat.S_ISBLK(info.st_mode) and info.st_rdev == os.makedev(major, minor), 'SD device node changed')
        with mmap.mmap(-1, READ_BYTES) as buffer:
            size = os.preadv(fd, [buffer], 0)
            require(size == READ_BYTES, 'Short SD direct read')
            return size
    finally:
        os.close(fd)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True, help='Expected current boot ID')
    parser.add_argument('--direct-read', action='store_true', help='Read and discard 4 MiB from unmounted SD')
    args = parser.parse_args()
    sysfs, proc = Path('/sys'), Path('/proc')
    boot_id = proc/'sys/kernel/random/boot_id'
    require(read_text(boot_id) == args.boot_id, 'Unexpected boot ID')
    block = identify(sysfs)
    first = snapshot(sysfs, proc, block)
    time.sleep(3)
    idle = snapshot(sysfs, proc, block)
    report = {'boot_id': args.boot_id, 'kernel': os.uname().release, 'device': block.name,
              'samples': {'before': first, 'idle': idle}, 'idle_delta': compare(first, idle),
              'direct_read_bytes': 0}
    if args.direct_read:
        report['direct_read_bytes'] = direct_read(block, proc)
        after = snapshot(sysfs, proc, block)
        report['samples']['direct_read'] = after
        report['direct_read_delta'] = compare(idle, after)
        time.sleep(3)
        settled = snapshot(sysfs, proc, block)
        report['samples']['settled'] = settled
        report['after_read_idle_delta'] = compare(after, settled)
        result = report['direct_read_delta']
        report['controller_counter_validated_by_direct_read'] = (
            result['IRQ_delta']['controller'] > 0 and result['sectors_read'] >= READ_BYTES // 512)
    require(read_text(boot_id) == args.boot_id and identify(sysfs) == block, 'Boot or SD topology changed')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
