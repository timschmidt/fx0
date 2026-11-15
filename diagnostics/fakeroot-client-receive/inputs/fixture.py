# SPDX-License-Identifier: MIT
import hashlib
import json
import os
from pathlib import Path
import stat
import signal
import subprocess
import tarfile

assert os.getuid() == os.geteuid() == 0
base = Path('/tmp/work')
(base / 'ready.json').write_text(json.dumps(dict(inner_PID=os.getpid(), fake_uid=os.geteuid())) + '\n')
os.kill(os.getpid(), signal.SIGSTOP)
payload = base / 'payload'
payload.mkdir()
(payload / 'alpha').write_bytes(b'owned fakeroot diagnostic fixture alpha\n')
(payload / 'beta').write_bytes(b'owned fakeroot diagnostic fixture beta\n')
os.chown(payload, 0, 0)
os.chmod(payload, 0o755)
os.chown(payload / 'alpha', 321, 654)
os.chmod(payload / 'alpha', 0o640)
os.chown(payload / 'beta', 0, 0)
os.chmod(payload / 'beta', 0o644)
expected = {'.': (0, 0, 0o755), 'alpha': (321, 654, 0o640), 'beta': (0, 0, 0o644)}
observed = {}
for name, values in expected.items():
    status = (payload / name).stat()
    actual = (status.st_uid, status.st_gid, stat.S_IMODE(status.st_mode))
    assert actual == values, (name, actual, values)
    observed[name] = actual
command = ['tar', '--format=ustar', '--sort=name', '--mtime=@1794702522',
           '-cf', str(base / 'fixture.tar'), '-C', str(payload), '.']
subprocess.run(command, check=True)
rows = []
with tarfile.open(base / 'fixture.tar', 'r:') as archive:
    for member in archive:
        name = member.name.removeprefix('./')
        if member.isdir():
            name = '.'
        assert name in expected
        assert (member.uid, member.gid, member.mode) == expected[name]
        assert member.mtime == 1794702522
        assert member.isdir() or member.isfile()
        rows.append(dict(name=name, uid=member.uid, gid=member.gid, mode=member.mode,
                         mtime=member.mtime, bytes=member.size))
assert len(rows) == 3
result = dict(fake_uid=os.geteuid(), metadata=observed, tar_metadata=rows,
              tar_SHA256=hashlib.sha256((base / 'fixture.tar').read_bytes()).hexdigest(),
              passed=True, scope='Owned metadata fixture only; not the original package build')
(base / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result))
