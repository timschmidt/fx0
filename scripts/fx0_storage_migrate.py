#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Plan, verify and (guarded) apply the Fx0 single-root GPT layout.

The target keeps original entries 1-34 byte for byte and replaces the five
contiguous Android entries (system, cache, userdata, sdcard, grow) with one
Linux filesystem entry. Only the primary (LBA 0-33) and backup (last 33 LBAs)
GPT regions are ever written. Filesystem creation is a separate step.
"""
import argparse
import binascii
import json
import os
import struct
import sys
import uuid
from pathlib import Path

SECTOR = 512
TOTAL_SECTORS = 30777344
ENTRY_SIZE = 128
ENTRY_COUNT = 40
RETAINED = 34
RECLAIMED = ['system', 'cache', 'userdata', 'sdcard', 'grow']
ROOT_FIRST, ROOT_LAST = 786432, 30777310
ROOT_NAME = 'nura-root'
LINUX_FS = uuid.UUID('0fc63daf-8483-4772-8e79-3d69d8477de4')
PRIMARY_SECTORS = 34
BACKUP_SECTORS = 33


class LayoutError(Exception):
    pass


def crc(data):
    return binascii.crc32(data) & 0xffffffff


def parse_header(sector):
    if sector[:8] != b'EFI PART':
        raise LayoutError('missing GPT signature')
    hsize = struct.unpack_from('<I', sector, 12)[0]
    h = bytearray(sector[:hsize])
    stored = struct.unpack_from('<I', h, 16)[0]
    struct.pack_into('<I', h, 16, 0)
    if crc(h) != stored:
        raise LayoutError('GPT header CRC mismatch')
    f = struct.unpack_from('<QQQQ16sQIII', sector, 24)
    return {'size': hsize, 'current': f[0], 'backup': f[1], 'first_usable': f[2], 'last_usable': f[3],
            'disk_guid': f[4], 'entries_lba': f[5], 'count': f[6], 'entry_size': f[7], 'entries_crc': f[8]}


def entries_from(array, count, size):
    out = []
    for i in range(count):
        raw = array[i * size:(i + 1) * size]
        first, last = struct.unpack_from('<QQ', raw, 32)
        out.append({'raw': bytes(raw), 'empty': not any(raw[:16]), 'type': uuid.UUID(bytes_le=bytes(raw[:16])),
                    'first': first, 'last': last, 'name': raw[56:128].decode('utf-16le').rstrip('\0')})
    return out


def read_pair(primary, backup):
    """Parse and cross-check primary (34 sectors) and backup (33 sectors) GPT regions."""
    if len(primary) != PRIMARY_SECTORS * SECTOR or len(backup) != BACKUP_SECTORS * SECTOR:
        raise LayoutError('unexpected GPT region sizes')
    ph = parse_header(primary[SECTOR:2 * SECTOR])
    bh = parse_header(backup[-SECTOR:])
    if (ph['count'], ph['entry_size']) != (ENTRY_COUNT, ENTRY_SIZE):
        raise LayoutError('unexpected partition array geometry')
    if ph['current'] != 1 or ph['backup'] != TOTAL_SECTORS - 1 or bh['current'] != TOTAL_SECTORS - 1 or bh['backup'] != 1:
        raise LayoutError('GPT header locations do not match the Fx0 eMMC geometry')
    if ph['disk_guid'] != bh['disk_guid']:
        raise LayoutError('primary and backup disk GUIDs differ')
    alen = ENTRY_COUNT * ENTRY_SIZE
    parr = primary[2 * SECTOR:2 * SECTOR + alen]
    boff = (bh['entries_lba'] - (TOTAL_SECTORS - BACKUP_SECTORS)) * SECTOR
    if boff < 0:
        raise LayoutError('backup array outside the backup region')
    barr = backup[boff:boff + alen]
    if crc(parr) != ph['entries_crc'] or crc(barr) != bh['entries_crc']:
        raise LayoutError('partition array CRC mismatch')
    if parr != barr:
        raise LayoutError('primary and backup partition arrays differ')
    return ph, bh, entries_from(parr, ENTRY_COUNT, ENTRY_SIZE)


def check_original(entries):
    used = [e for e in entries if not e['empty']]
    if len(used) != RETAINED + len(RECLAIMED):
        raise LayoutError(f'expected {RETAINED + len(RECLAIMED)} original entries, found {len(used)}')
    tail = [e['name'] for e in entries[RETAINED:RETAINED + len(RECLAIMED)]]
    if tail != RECLAIMED:
        raise LayoutError(f'entries 35-39 are {tail}, expected {RECLAIMED}')
    span = entries[RETAINED:RETAINED + len(RECLAIMED)]
    if span[0]['first'] != ROOT_FIRST or span[-1]['last'] != ROOT_LAST:
        raise LayoutError('reclaimed span does not match the measured sectors')
    for a, b in zip(span, span[1:]):
        if b['first'] != a['last'] + 1:
            raise LayoutError('reclaimed entries are not contiguous')
    if any(e['last'] >= ROOT_FIRST for e in entries[:RETAINED]):
        raise LayoutError('a retained entry overlaps the root span')


def build_region(header, array, *, primary, protective_mbr):
    """Return primary (34 sectors) or backup (33 sectors) bytes for a header template and array."""
    h = bytearray(SECTOR)
    h[:92] = header[:92]
    struct.pack_into('<I', h, 88, crc(array))
    struct.pack_into('<I', h, 16, 0)
    struct.pack_into('<I', h, 16, crc(bytes(h[:92])))
    arr = array + bytes(32 * SECTOR - len(array))
    return (protective_mbr + bytes(h) + arr) if primary else (arr[:32 * SECTOR] + bytes(h))


def plan(primary, backup, root_guid=None):
    ph, bh, entries = read_pair(primary, backup)
    check_original(entries)
    if ph['entries_lba'] != 2 or bh['entries_lba'] != TOTAL_SECTORS - BACKUP_SECTORS:
        raise LayoutError('partition arrays are not at the standard locations')
    alen = ENTRY_COUNT * ENTRY_SIZE
    if any(primary[2 * SECTOR + alen:]) or any(backup[alen:-SECTOR]):
        raise LayoutError('non-zero bytes after the partition array would be lost')
    root = bytearray(ENTRY_SIZE)
    root[:16] = LINUX_FS.bytes_le
    root[16:32] = (root_guid or uuid.uuid4()).bytes_le
    struct.pack_into('<QQQ', root, 32, ROOT_FIRST, ROOT_LAST, 0)
    root[56:56 + 2 * len(ROOT_NAME)] = ROOT_NAME.encode('utf-16le')
    array = b''.join(e['raw'] for e in entries[:RETAINED]) + bytes(root) + bytes((ENTRY_COUNT - RETAINED - 1) * ENTRY_SIZE)
    new_primary = build_region(primary[SECTOR:2 * SECTOR], array, primary=True, protective_mbr=primary[:SECTOR])
    new_backup = build_region(backup[-SECTOR:], array, primary=False, protective_mbr=None)
    return new_primary, new_backup


def verify(original_primary, original_backup, primary, backup):
    """Check a target pair against the original; returns a summary dict or raises."""
    _, _, old = read_pair(original_primary, original_backup)
    ph, bh, new = read_pair(primary, backup)
    for i in range(RETAINED):
        if new[i]['raw'] != old[i]['raw']:
            raise LayoutError(f'retained entry {i + 1} changed')
    root = new[RETAINED]
    if (root['type'], root['first'], root['last'], root['name']) != (LINUX_FS, ROOT_FIRST, ROOT_LAST, ROOT_NAME):
        raise LayoutError('root entry does not match the target')
    if any(not e['empty'] for e in new[RETAINED + 1:]):
        raise LayoutError('unexpected entries after the root')
    used = sorted((e['first'], e['last'], e['name']) for e in new if not e['empty'])
    for (a0, a1, an), (b0, b1, bn) in zip(used, used[1:]):
        if b0 <= a1:
            raise LayoutError(f'{an} overlaps {bn}')
    if used[0][0] < ph['first_usable'] or used[-1][1] > ph['last_usable']:
        raise LayoutError('an entry lies outside the usable LBA range')
    if primary[:SECTOR] != original_primary[:SECTOR]:
        raise LayoutError('protective MBR changed')
    if (ROOT_FIRST * SECTOR) % (1 << 20):
        raise LayoutError('root start is not 1 MiB aligned')
    return {'retained_entries_identical': RETAINED, 'root_bytes': (ROOT_LAST - ROOT_FIRST + 1) * SECTOR,
            'root_first_lba': ROOT_FIRST, 'root_last_lba': ROOT_LAST, 'crc_and_overlap_checks': 'pass'}


def mounted_partitions(device, mounts_text):
    base = os.path.basename(device)
    return sorted({line.split()[0] for line in mounts_text.splitlines()
                   if line.split() and os.path.basename(line.split()[0]).startswith(base + 'p')})


def apply(device, original_primary, original_backup, primary, backup, *, sysfs='/sys/class/block',
          mounts='/proc/mounts', confirm_restoration=False):
    """Write the target GPT regions to the eMMC after exhaustive checks; returns a summary."""
    if not confirm_restoration:
        raise LayoutError('refusing: factory-stock restoration rehearsal must be confirmed first')
    if os.path.realpath(device) != '/dev/mmcblk0' and not device.startswith('/tmp/'):
        raise LayoutError('refusing: target must be the whole internal eMMC /dev/mmcblk0')
    name = os.path.basename(device)
    sizefile = Path(sysfs, name, 'size')
    if int(sizefile.read_text()) != TOTAL_SECTORS:
        raise LayoutError('refusing: device size differs from the measured Fx0 eMMC')
    removable = Path(sysfs, name, 'removable')
    if removable.exists() and removable.read_text().strip() != '0':
        raise LayoutError('refusing: removable device')
    busy = [p for p in mounted_partitions(device, Path(mounts).read_text())
            if int(p.rsplit('p', 1)[1]) > RETAINED]
    if busy:
        raise LayoutError(f'refusing: reclaimed partitions are mounted: {busy}')
    verify(original_primary, original_backup, primary, backup)
    end = TOTAL_SECTORS * SECTOR
    with open(device, 'r+b', buffering=0) as dev:
        dev.seek(0)
        if dev.read(len(original_primary)) != original_primary:
            raise LayoutError('refusing: device primary GPT is not the expected original')
        dev.seek(end - len(original_backup))
        if dev.read(len(original_backup)) != original_backup:
            raise LayoutError('refusing: device backup GPT is not the expected original')
        dev.seek(end - len(backup)); dev.write(backup); os.fsync(dev.fileno())
        dev.seek(0); dev.write(primary); os.fsync(dev.fileno())
        dev.seek(0); got_p = dev.read(len(primary))
        dev.seek(end - len(backup)); got_b = dev.read(len(backup))
    if got_p != primary or got_b != backup:
        raise LayoutError('readback mismatch after write; restore the original GPT regions')
    return {'written': ['backup', 'primary'], 'readback': 'match'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='cmd', required=True)
    for name in ('plan', 'verify', 'apply'):
        s = sub.add_parser(name)
        s.add_argument('--original-primary', type=Path, required=True)
        s.add_argument('--original-backup', type=Path, required=True)
        if name == 'plan':
            s.add_argument('--out-primary', type=Path, required=True)
            s.add_argument('--out-backup', type=Path, required=True)
            s.add_argument('--root-guid', type=uuid.UUID)
        else:
            s.add_argument('--primary', type=Path, required=True)
            s.add_argument('--backup', type=Path, required=True)
        if name == 'apply':
            s.add_argument('--device', required=True)
            s.add_argument('--restoration-rehearsed', action='store_true')
    a = p.parse_args(argv)
    op, ob = a.original_primary.read_bytes(), a.original_backup.read_bytes()
    try:
        if a.cmd == 'plan':
            np, nb = plan(op, ob, a.root_guid)
            for path, data in ((a.out_primary, np), (a.out_backup, nb)):
                with path.open('xb') as f:
                    f.write(data)
            print(json.dumps(verify(op, ob, np, nb), indent=2))
        elif a.cmd == 'verify':
            print(json.dumps(verify(op, ob, a.primary.read_bytes(), a.backup.read_bytes()), indent=2))
        else:
            print(json.dumps(apply(a.device, op, ob, a.primary.read_bytes(), a.backup.read_bytes(),
                                   confirm_restoration=a.restoration_rehearsed), indent=2))
    except LayoutError as e:
        print('error:', e, file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
