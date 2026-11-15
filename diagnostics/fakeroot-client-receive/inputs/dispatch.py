# SPDX-License-Identifier: MIT
import json
import os
from pathlib import Path
import subprocess

assert os.getuid() == os.geteuid() == 12345
Path('/tmp/work/real-user.json').write_text(json.dumps(dict(uid=os.getuid(), gid=os.getgid())) + '\n')
raise SystemExit(subprocess.run(['fakeroot', '--', '/usr/bin/python3', '-B', '/tmp/input/fixture.py']).returncode)
