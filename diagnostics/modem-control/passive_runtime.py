# SPDX-License-Identifier: MIT
"""Durable attempt ownership and bounded waits for actual owned children."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets
import stat
import subprocess


class AttemptJournal:
    """Consume one private workspace permanently, even after failure or close.

    The claim is never removed automatically. Opening another object/process
    against the same workspace is an error, not a restart/recovery mechanism.
    """
    def __init__(self, directory):
        self.directory = Path(directory)
        self.owner = os.getpid()
        self.fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY |
                          os.O_CLOEXEC | os.O_NOFOLLOW)
        try:
            info = os.fstat(self.fd)
            if info.st_uid != os.getuid() or stat.S_IMODE(info.st_mode) != 0o700:
                raise RuntimeError('Attempt workspace must be owned and mode 0700')
            try:
                os.stat('controller.json', dir_fd=self.fd, follow_symlinks=False)
            except FileNotFoundError:
                pass
            else:
                raise FileExistsError('Existing controller state must be inspected')
            claim = os.open('attempt.claim', os.O_WRONLY | os.O_CREAT |
                            os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
                            0o600, dir_fd=self.fd)
            with os.fdopen(claim, 'wb') as stream:
                stream.write(json.dumps({
                    'owner_PID': self.owner,
                    'reserved_UTC': datetime.now(timezone.utc).isoformat(),
                    'automatic_reuse_permitted': False,
                }, allow_nan=False).encode() + b'\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.fsync(self.fd)
        except BaseException:
            os.close(self.fd)
            self.fd = None
            raise

    def update(self, state):
        if self.fd is None or os.getpid() != self.owner:
            raise RuntimeError('Only the live owning process may update the journal')
        data = (json.dumps(state, indent=2, allow_nan=False) + '\n').encode()
        name = '.controller-' + secrets.token_hex(16) + '.tmp'
        descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                             os.O_NOFOLLOW | os.O_CLOEXEC, 0o600, dir_fd=self.fd)
        try:
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, 'controller.json',
                       src_dir_fd=self.fd, dst_dir_fd=self.fd)
            os.fsync(self.fd)
        finally:
            try:
                os.unlink(name, dir_fd=self.fd)
            except FileNotFoundError:
                pass

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class UnreapedChild(RuntimeError):
    """The owned child still retains resources; no transfer acceptance/recovery."""


def wait_owned(child, timeout, *, terminate_grace=2, kill_grace=2):
    """Wait on the actual Popen; a PID or state file cannot substitute for it.

    Expiry requests termination then kill, each with its own deadline. An
    unreaped child raises; it is never represented by a successful exit code.
    This process deadline is distinct from any USB I/O timeout reported by the
    transfer helper and does not itself authorize a USB reset.
    """
    if timeout <= 0 or terminate_grace <= 0 or kill_grace <= 0:
        raise ValueError('Owned-child deadlines must be positive')
    expired = terminate = kill = False
    try:
        code = child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        expired = terminate = True
        try:
            child.terminate()
        except ProcessLookupError:
            pass
        try:
            code = child.wait(timeout=terminate_grace)
        except subprocess.TimeoutExpired:
            kill = True
            try:
                child.kill()
            except ProcessLookupError:
                pass
            try:
                code = child.wait(timeout=kill_grace)
            except subprocess.TimeoutExpired as error:
                raise UnreapedChild('Owned child remains unreaped; resource ownership uncertain') from error
    if type(code) is not int or child.poll() != code:
        raise UnreapedChild('Owned child has no matching actual terminal exit status')
    return {'returncode': code, 'owned_child_reaped': True,
            'process_deadline_expired': expired,
            'termination_requested': terminate, 'kill_requested': kill}
