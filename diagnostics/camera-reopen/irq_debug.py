#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Lease exactly one pinned VFE41 IRQ-status dynamic-debug call site."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import stat

from queue_trace import NativeIO, private_json, require

CONTROL = Path('/sys/kernel/debug/dynamic_debug/control')
LOCK = Path('/run/fx0-camera-irq-debug.lock')
SELECTOR = 'module qcom_camss file drivers/media/platform/qcom/camss/camss-vfe-4-1.c line 903'
PREFIX = 'drivers/media/platform/qcom/camss/camss-vfe-4-1.c:903 [qcom_camss]'
FORMAT = '"VFE: status0 = 0x%08x, status1 = 0x%08x\\n"'


def snapshot(control, io):
    lines = [line for line in io.read(control).splitlines() if line and not line.startswith('#')]
    selected = [line for line in lines if line.startswith(PREFIX)]
    require(len(selected) == 1, 'expected exactly one pinned debug selector match')
    match = re.fullmatch(re.escape(PREFIX) + r'vfe_isr =([pmfslt_]+) (.*)', selected[0])
    require(match is not None and match[2] == FORMAT, 'pinned IRQ debug metadata differs')
    others = sorted(line for line in lines if not line.startswith(PREFIX))
    return {'target_flags': match[1], 'other_sites_SHA256': hashlib.sha256('\n'.join(others).encode()).hexdigest(),
            'other_site_count': len(others)}


class DebugLease:
    def __init__(self, claim, control=CONTROL, lock=LOCK, io=None):
        self.claim, self.control, self.lock = Path(claim), Path(control), Path(lock)
        self.io = io or NativeIO()
        self.fd = None
        self.armed = False
        self.cleanup = None

    def _lock(self):
        self.fd = os.open(self.lock, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            info = os.fstat(self.fd)
            require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1 and info.st_uid == os.geteuid()
                    and not info.st_mode & 0o077, 'debug lock ownership or permissions differ')
            fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BaseException:
            self._unlock()
            raise

    def _unlock(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def _owned_control(self):
        require(self.fd is not None and not self.control.is_symlink(), 'debug control is not owned')
        info = self.control.stat()
        require((info.st_dev, info.st_ino) == (self.device, self.inode), 'debug control identity changed')

    def _save(self, state):
        private_json(self.claim, {'state': state, 'selector': SELECTOR, 'device': self.device,
                                 'inode': self.inode, 'before': self.before, 'cleanup': self.cleanup})

    def __enter__(self):
        require(not self.claim.exists(), 'debug claim already exists; never reuse it')
        require(self.claim.parent.is_dir() and not self.claim.parent.stat().st_mode & 0o077,
                'debug workspace must be private')
        self._lock()
        try:
            require(not self.control.is_symlink(), 'unexpected debug control symlink')
            info = self.control.stat()
            self.device, self.inode = info.st_dev, info.st_ino
            self.before = snapshot(self.control, self.io)
            require(self.before['target_flags'] == '_', 'IRQ debug call site already configured')
            self._save('claimed; debug not enabled yet')
            # Arm recovery before the write; it also handles a write failure/no-op.
            self.armed = True
            self._owned_control()
            self.io.write(self.control, SELECTOR + ' +p\n')
            self.enabled = snapshot(self.control, self.io)
            require(self.enabled == self.before | {'target_flags': 'p'}, 'unexpected debug enable result')
            self._save('enabled')
            return self
        except BaseException:
            if self.armed:
                self.close()
            else:
                self._unlock()
            raise

    def close(self):
        if not self.armed:
            self._unlock()
            return
        try:
            self._owned_control()
            current = snapshot(self.control, self.io)
            require(current['target_flags'] in ('_', 'p'), 'debug flags changed outside lease')
            if current['target_flags'] == 'p':
                self.io.write(self.control, SELECTOR + ' -p\n')
            after = snapshot(self.control, self.io)
            self.cleanup = {'target_disabled': after['target_flags'] == '_',
                            'all_debug_settings_unchanged': after == self.before}
            self._save('restoration checked')
            require(self.cleanup['target_disabled'] and self.cleanup['all_debug_settings_unchanged'],
                    'debug restoration or other-site preservation failed')
            self.armed = False
        finally:
            self._unlock()

    def __exit__(self, *_exception):
        self.close()


def recover_debug(claim, control=CONTROL, lock=LOCK, io=None):
    claim = Path(claim)
    require(not claim.is_symlink() and not claim.parent.stat().st_mode & 0o077, 'debug recovery claim must be private')
    record = json.loads(claim.read_text())
    require(record['selector'] == SELECTOR and record['before']['target_flags'] == '_', 'unexpected debug recovery selector')
    lease = DebugLease(claim, control, lock, io)
    lease._lock()
    lease.device, lease.inode = record['device'], record['inode']
    lease.before, lease.armed = record['before'], True
    lease.close()
    return lease.cleanup
