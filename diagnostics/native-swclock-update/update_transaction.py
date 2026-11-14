# SPDX-License-Identifier: MIT
"""Small transaction and boot-tail guards used by the native kernel updater."""
import hashlib
import os
from pathlib import Path


class HooksActive(RuntimeError):
    """Owned hook processes still run; keep observing without rollback writes."""


class RolledBack(RuntimeError):
    """The update failed and the original state was verified after rollback."""


class RollbackFailed(RuntimeError):
    """Both the update and rollback failed; no reboot should be requested."""


def execute(ops):
    """Only restore after the installer has reaped all owned hook processes."""
    ops.preflight()
    try:
        ops.install()
        if not ops.hooks_terminal():
            raise HooksActive('Package hooks are not terminal')
        ops.verify_candidate()
    except HooksActive:
        ops.record('stopped-hooks-active')
        raise
    except Exception as update_error:
        ops.record('update-failed', error=str(update_error))
        if not ops.hooks_terminal():
            ops.record('stopped-hooks-active')
            raise HooksActive('Refusing rollback while hooks are active') from update_error
        try:
            ops.rollback()
            ops.verify_rollback()
        except Exception as rollback_error:
            ops.record('rollback-failed', error=str(rollback_error))
            raise RollbackFailed(str(rollback_error)) from update_error
        ops.record('rolled-back')
        raise RolledBack(str(update_error)) from update_error
    ops.record('updated-and-verified')


def restore_boot_tail(backup, target, offset, expected_sha256):
    """Restore verified bytes after an unchanged bootloader prefix.

    The caller identifies the physical target. This guard requires its size and
    preserved prefix to match the backup, never truncates it, and checks complete
    readback. A matching partition is left untouched.
    """
    if not isinstance(offset, int) or offset <= 0 or offset % 512:
        raise ValueError('Boot offset must be positive and sector aligned')
    original = Path(backup).read_bytes()
    if hashlib.sha256(original).hexdigest() != expected_sha256:
        raise ValueError('Boot backup checksum mismatch')
    if offset >= len(original):
        raise ValueError('Boot offset exceeds backup')
    descriptor = os.open(target, os.O_RDWR | os.O_CLOEXEC | os.O_NOFOLLOW)
    try:
        if os.lseek(descriptor, 0, os.SEEK_END) != len(original):
            raise ValueError('Boot partition size mismatch')
        current = os.pread(descriptor, len(original), 0)
        if len(current) != len(original):
            raise OSError('Incomplete boot partition read')
        if current[:offset] != original[:offset]:
            raise ValueError('Preserved bootloader prefix mismatch')
        if current == original:
            return dict(written=False, bootloader_prefix_preserved=True)
        cursor = offset
        while cursor < len(original):
            count = os.pwrite(descriptor, original[cursor:cursor + 1024 * 1024], cursor)
            if count <= 0:
                raise OSError('Boot-tail write made no progress')
            cursor += count
        os.fsync(descriptor)
        readback = os.pread(descriptor, len(original), 0)
        if hashlib.sha256(readback).hexdigest() != expected_sha256:
            raise OSError('Boot-tail readback checksum mismatch')
        return dict(written=True, bootloader_prefix_preserved=True,
                    first_write_offset=offset, bytes_written=len(original) - offset)
    finally:
        os.close(descriptor)
