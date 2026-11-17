#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Prepare and run isolated attachment checks using a completed public rebuild."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--inputs',type=Path,required=True)
p.add_argument('--build-output',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();inputs=a.inputs.resolve();build=a.build_output.resolve();output=a.output.resolve()
source=Path(__file__).resolve().parent/'tests/check-attachment.py'
assert source.is_file()
output.mkdir(exist_ok=False);tests=output/'tests';tests.mkdir();fixtures=tests/'fixtures';fixtures.mkdir();results=output/'results';results.mkdir()
catalog=json.loads((inputs/'module-signatures.json').read_text());key=sorted(catalog['payloads'])[0]
name=catalog['payloads'][key]['module_paths'][0];payload=build/name;sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert sha(payload)==key
shutil.copyfile(payload,fixtures/'sample.ko');shutil.copyfile(build/'scripts/sign-file',fixtures/'sign-file');(fixtures/'sign-file').chmod(0o755)
(fixtures/'fixture.json').write_text(json.dumps(dict(payload_SHA256=key,raw_module_path=name,
    kernel_sign_file_SHA256=sha(build/'scripts/sign-file'),compiled_kernel_source_head=catalog['source_head']),indent=2)+'\n')
shutil.copyfile(source,tests/'check.py')
command=['bwrap','--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL',
    '--ro-bind','/usr','/usr','--ro-bind','/etc','/etc',
    '--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin',
    '--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
    '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
    '--ro-bind',str(inputs),'/inputs','--ro-bind',str(tests),'/tests',
    '--bind',str(results),'/results','--clearenv',
    '--setenv','PATH','/usr/bin:/usr/sbin:/bin:/sbin',
    '--setenv','PYTHONDONTWRITEBYTECODE','1','--chdir','/','--',
    '/usr/bin/python3','-B','/tests/check.py']
record=dict(started_UTC=datetime.now(timezone.utc).isoformat(),passed=False,state='prepared',
    source_head=catalog['source_head'],controller_script_SHA256=sha(Path(__file__)),phone_access=False,network_namespace_isolated=True,
    development_private_key_not_mounted=True,test_script_SHA256=sha(source))
controller=output/'controller.json';child=None
def save():controller.write_text(json.dumps(record,indent=2)+'\n')
def interrupted(sig,frame):raise InterruptedError(str(sig))
signal.signal(signal.SIGTERM,interrupted)
try:
    with (output/'test.log').open('xb') as stream:
        child=subprocess.Popen(command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        record.update(state='running',active_PID=child.pid);save();code=child.wait(timeout=120)
    assert code==0,code
    result=json.loads((results/'qualification.json').read_text())
    assert result['passed'] and result['cases']==10
    record.update(passed=True,state='terminal success',cases=10,qualification_SHA256=sha(results/'qualification.json'))
except BaseException as error:
    record.update(state='terminal failure',error_type=type(error).__name__,error=str(error))
    raise
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:os.killpg(child.pid,signal.SIGKILL);child.wait(timeout=5)
    record.pop('active_PID',None);record['owned_child_terminal_and_reaped']=child is None or child.returncode is not None
    record['finished_UTC']=datetime.now(timezone.utc).isoformat();save()
print(json.dumps(dict(passed=record['passed'],cases=record.get('cases'))))
