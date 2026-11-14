#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Build the exact paired Fx0 firmware offline using read-only host tools/source."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('source', type=Path)
parser.add_argument('output', type=Path)
args = parser.parse_args()
source = args.source.resolve(strict=True)
commit = '2ce757408f364ec6f1197b1d5d0be4128a309b1e'
version = 'next-2ce7574-20261030'
output = args.output.resolve()
assert source not in output.parents and output not in source.parents, 'source and output must be separate'
assert not output.exists(), 'each output must be new'
assert subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip() == commit
assert not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain', '--untracked-files=all', '--ignored=matching'])
output.mkdir(parents=True)
(output / 'build').mkdir()
(output / 'home').mkdir()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
tools = {}
for name in ['arm-none-eabi-gcc', 'arm-none-eabi-ld', 'gcc', 'ld.bfd', 'make', 'dtc', 'python3', 'bwrap']:
    path = Path('/usr/bin') / name
    tools[name] = {'SHA256': sha(path), 'resolved_path': str(path.resolve()),
                   'version': subprocess.check_output([str(path), '--version'], stderr=subprocess.STDOUT, text=True).splitlines()[0]}
command = [
    '/usr/bin/bwrap', '--die-with-parent', '--unshare-all', '--clearenv',
    '--ro-bind', '/usr', '/usr', '--symlink', 'usr/lib64', '/lib64',
    '--symlink', 'usr/lib', '/lib', '--symlink', 'usr/bin', '/bin',
    '--proc', '/proc', '--dev', '/dev', '--tmpfs', '/tmp',
    '--dir', '/etc', '--dir', '/etc/alternatives', '--symlink', '/usr/bin/ld.bfd', '/etc/alternatives/ld',
    '--dir', '/home', '--bind', str(output / 'home'), '/home/build',
    '--ro-bind', str(source), '/src', '--tmpfs', '/src/lk2nd/certs',
    '--bind', str(output / 'build'), '/out', '--chdir', '/src',
    '--setenv', 'PATH', '/usr/bin:/bin', '--setenv', 'HOME', '/home/build',
    '--setenv', 'LC_ALL', 'C', '--setenv', 'TZ', 'UTC',
    '--setenv', 'SOURCE_DATE_EPOCH', '1793385591',
    '--setenv', 'PYTHONHASHSEED', '0', '--setenv', 'PYTHONDONTWRITEBYTECODE', '1',
    '/usr/bin/make', '-j8', 'TOOLCHAIN_PREFIX=arm-none-eabi-',
    'BOOTLOADER_OUT=/out', 'APPSBOOTHEADER_DIR=/out', 'LK2ND_VERSION=' + version,
    'LK2ND_FORCE_FASTBOOT=1', 'SIGN_BOOTIMG=0', 'lk2nd-msm8226',
]
record = {'started_UTC': datetime.now(timezone.utc).isoformat(), 'source_commit': commit,
          'firmware_version': version, 'SOURCE_DATE_EPOCH': 1793385591,
          'script_SHA256': sha(Path(__file__)), 'tools': tools, 'command': command,
          'network_enabled': False, 'source_and_tools_readonly': True,
          'source_test_signing_credentials_hidden': True, 'signing_enabled': False,
          'fresh_output_and_HOME': True, 'phone_access': False}
def save():
    (output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
save()
with (output / 'build.log').open('xb') as log:
    process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env={'PATH': '/usr/bin:/bin'})
    record['PID'] = process.pid
    save()
    record['returncode'] = process.wait()
record['finished_UTC'] = datetime.now(timezone.utc).isoformat()
save()
print(json.dumps({'output': str(output), 'returncode': record['returncode']}))
raise SystemExit(record['returncode'])
