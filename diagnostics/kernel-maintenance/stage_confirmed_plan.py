# SPDX-License-Identifier: MIT
"""Stage a large confirmed plan through a pinned SSH client and verified root copy."""
import datetime
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shlex
import subprocess


def stage_confirmed_plan(client, plan_path, state_dir, native_directory,
                         native_plan_name, installation_unit):
    """Return verified staging metadata; client exports OPTS and run(..., root=True)."""
    state_dir = Path(state_dir)
    state_dir.mkdir(parents=True, exist_ok=False)
    plan_path = Path(plan_path)
    payload = plan_path.read_bytes()
    plan = json.loads(payload)
    parent = PurePosixPath(native_directory)
    assert parent.is_absolute() and '..' not in parent.parts
    assert parent.is_relative_to('/var/lib/fx0-rollback') and len(parent.parts) >= 5
    assert re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*\.json', native_plan_name)
    assert re.fullmatch(r'fx0-[A-Za-z0-9_.-]+\.service', installation_unit)
    assert re.fullmatch(r'[0-9a-f-]{36}', plan['boot_id'])
    assert re.fullmatch(r'[0-9a-f]{64}', plan['controller_sha256'])
    digest = hashlib.sha256(payload).hexdigest()
    temporary = '/tmp/fx0-confirmed-plan-' + digest[:16] + '.json'
    user_source = """import hashlib,json,os,sys
from pathlib import Path
data=sys.stdin.buffer.read()
assert len(data)==EXPECTED_BYTES and hashlib.sha256(data).hexdigest()==EXPECTED_SHA
os.umask(0o077)
path=Path(TEMPORARY)
with path.open('xb') as stream:
 stream.write(data);stream.flush();os.fsync(stream.fileno())
path.chmod(0o600)
metadata=path.stat()
print(json.dumps(dict(path=str(path),sha256=hashlib.sha256(data).hexdigest(),bytes=len(data),uid=metadata.st_uid,mode=metadata.st_mode & 0o777)))
""".replace('EXPECTED_BYTES', str(len(payload))).replace(
        'EXPECTED_SHA', repr(digest)).replace('TEMPORARY', repr(temporary))
    command = 'python3 -B -c ' + shlex.quote(user_source)
    assert len(command.encode()) < 8192
    record = dict(
        state='one ordinary SSH transfer requested', bytes=len(payload),
        sha256=digest, temporary=temporary,
        requested_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        payload_separate_from_root_authentication=True)
    record_path = state_dir / 'transfer.json'
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    child = subprocess.Popen([*client.OPTS, command], stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        stdout, stderr = child.communicate(input=payload, timeout=60)
    except BaseException:
        child.terminate()
        try:
            child.wait(timeout=15)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        record.update(state='transfer interrupted; inspect this staged path',
                      returncode=child.returncode, SSH_child_reaped=True)
        record_path.write_text(json.dumps(record, indent=2) + '\n')
        raise
    record.update(state='transfer terminal', returncode=child.returncode,
                  SSH_child_reaped=True, stderr=stderr.decode(errors='replace'))
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    assert child.returncode == 0
    user = json.loads(stdout)
    assert user['sha256'] == digest and user['bytes'] == len(payload) and user['mode'] == 0o600
    record['user_file'] = user
    record_path.write_text(json.dumps(record, indent=2) + '\n')
    root_source = """import hashlib,json,os,stat,subprocess
from pathlib import Path
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==EXPECTED_BOOT
parent=Path(NATIVE_DIRECTORY)
metadata=parent.lstat()
assert stat.S_ISDIR(metadata.st_mode) and metadata.st_uid==0 and stat.S_IMODE(metadata.st_mode)==0o700
assert not (parent/'kernel-update-status.json').exists()
assert hashlib.sha256((parent/'install_native_v2.py').read_bytes()).hexdigest()==EXPECTED_CONTROLLER
unit=subprocess.run(['systemctl','show',INSTALLATION_UNIT,'-p','LoadState'],capture_output=True,text=True,timeout=10,check=True)
assert unit.stdout.strip()=='LoadState=not-found'
source=Path(TEMPORARY)
descriptor=os.open(source,os.O_RDONLY|os.O_NOFOLLOW)
with os.fdopen(descriptor,'rb') as stream:
 before=os.fstat(stream.fileno())
 assert stat.S_ISREG(before.st_mode) and before.st_nlink==1 and before.st_uid==EXPECTED_UID
 assert stat.S_IMODE(before.st_mode)==0o600 and before.st_size==EXPECTED_BYTES
 data=stream.read()
assert len(data)==EXPECTED_BYTES and hashlib.sha256(data).hexdigest()==EXPECTED_SHA
assert json.loads(data)['boot_id']==EXPECTED_BOOT
target=parent/NATIVE_PLAN_NAME
os.umask(0o077)
with target.open('xb') as stream:
 stream.write(data);stream.flush();os.fsync(stream.fileno())
target.chmod(0o600)
directory=os.open(parent,os.O_RDONLY|os.O_DIRECTORY)
try:os.fsync(directory)
finally:os.close(directory)
after=source.lstat()
assert (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
source.unlink()
print(json.dumps(dict(native_plan_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),native_plan_bytes=target.stat().st_size,temporary_user_file_removed=True,exact_boot_and_unused_installation_unit_verified=True,native_plan_mode=stat.S_IMODE(target.stat().st_mode),native_plan_uid=target.stat().st_uid)))
"""
    substitutions = dict(
        EXPECTED_BOOT=repr(plan['boot_id']), NATIVE_DIRECTORY=repr(str(parent)),
        EXPECTED_CONTROLLER=repr(plan['controller_sha256']),
        INSTALLATION_UNIT=repr(installation_unit), TEMPORARY=repr(temporary),
        EXPECTED_UID=str(user['uid']), EXPECTED_BYTES=str(len(payload)),
        EXPECTED_SHA=repr(digest), NATIVE_PLAN_NAME=repr(native_plan_name))
    for key, value in substitutions.items():
        root_source = root_source.replace(key, value)
    assert len(root_source.encode()) < 8192
    staged = json.loads(client.run('python3 -B -c ' + shlex.quote(root_source),
                                   root=True, timeout=30))
    assert staged['native_plan_sha256'] == digest
    assert staged['temporary_user_file_removed']
    assert staged['native_plan_mode'] == 0o600 and staged['native_plan_uid'] == 0
    (state_dir / 'native-staging.json').write_text(json.dumps(staged, indent=2) + '\n')
    return staged
