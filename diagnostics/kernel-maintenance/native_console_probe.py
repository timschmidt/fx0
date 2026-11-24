# SPDX-License-Identifier: MIT
"""Bounded read-only pstore capture; its transport output is private boot data."""
import argparse
import base64
import errno
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import sys

PATHS = tuple(f'{base}/console-ramoops-{number}'
              for base in ('/sys/fs/pstore', '/var/lib/systemd/pstore') for number in range(4))
PER_FILE = 1024 * 1024
TOTAL = 4 * 1024 * 1024


def digest(data):
    return hashlib.sha256(data).hexdigest()


def identity(root):
    return ((root/'proc/sys/kernel/random/boot_id').read_text().strip(),
            digest((root/'sys/kernel/notes').read_bytes()))


def open_regular(root, path, owner):
    """Never follow symlinks in either directory components or the final name."""
    flags = os.O_RDONLY | os.O_CLOEXEC | os.O_NOFOLLOW
    directory = os.open(root, flags | os.O_DIRECTORY)
    try:
        parts = Path(path).parts[1:]
        for part in parts[:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], flags | os.O_NONBLOCK, dir_fd=directory)
    finally:
        os.close(directory)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_uid != owner or info.st_mode & 0o022:
        os.close(fd)
        raise ValueError('Console must be an owned nonwritable regular file')
    return fd


def limited_read(fd, limit):
    result = bytearray()
    while len(result) <= limit:
        part = os.read(fd, min(65536, limit + 1 - len(result)))
        if not part:
            return bytes(result)
        result += part
    raise ValueError('Console exceeds explicit byte limit')


def metadata(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def capture(expected_boot, expected_notes, *, root=Path('/'), owner=0):
    if sys.flags.optimize:
        raise RuntimeError('Optimized Python is forbidden')
    if identity(root) != (expected_boot, expected_notes):
        raise ValueError('Expected native boot and notes do not match')
    records, total = {}, 0
    for path in PATHS:
        fd = None
        try:
            fd = open_regular(root, path, owner)
            before = os.fstat(fd)
            limit = min(PER_FILE, TOTAL - total)
            if before.st_size > limit:
                raise ValueError('Console exceeds explicit byte limit')
            body = limited_read(fd, limit)
            os.lseek(fd, 0, os.SEEK_SET)
            second = limited_read(fd, limit)
            after = os.fstat(fd)
            stable = metadata(before) == metadata(after) and body == second
            total += len(body)
            records[path] = {'state': 'captured' if stable else 'changed-during-read',
                             'SHA256': digest(body), 'bytes': len(body),
                             'content_base64': base64.b64encode(body).decode(),
                             'stable': stable, 'mtime_ns': after.st_mtime_ns}
        except FileNotFoundError:
            records[path] = {'state': 'missing'}
        except (OSError, ValueError) as error:
            records[path] = {'state': 'rejected', 'error_type': type(error).__name__}
            if isinstance(error, OSError):
                records[path]['errno'] = errno.errorcode.get(error.errno, 'UNKNOWN')
        finally:
            if fd is not None:
                os.close(fd)
    if identity(root) != (expected_boot, expected_notes):
        raise ValueError('Native identity changed while reading consoles')
    return {'format': 1, 'boot_id': expected_boot, 'kernel_notes_SHA256': expected_notes,
            'records': records, 'captured_bytes': total, 'read_only': True,
            'complete': all(row['state'] in ('captured', 'missing') for row in records.values()),
            'candidate_boot_attribution_proven': False, 'reset_cause_proven': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--expected-boot-id', required=True)
    parser.add_argument('--expected-notes-sha256', required=True)
    args = parser.parse_args()
    if re.fullmatch(r'[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}', args.expected_boot_id) is None:
        raise ValueError('Canonical expected boot ID required')
    if re.fullmatch('[a-f0-9]{64}', args.expected_notes_sha256) is None:
        raise ValueError('Expected kernel notes SHA256 required')
    print(json.dumps(capture(args.expected_boot_id, args.expected_notes_sha256)))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'capture_failed': True, 'error_type': type(error).__name__}), file=sys.stderr)
        raise SystemExit(1)
