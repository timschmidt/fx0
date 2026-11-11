"""Exercise permissions, native shell/APK execution and tracing in the unit."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

run = Path(__file__).resolve().parent
assert str(run) == '/var/lib/fx0-rollback/stable-native-hooks-01/prehook-probe-01'
inputs = run.parent / 'inputs-01'
root = run / 'root'
probe = run / 'attribute-probe'
assert all(os.statvfs(p).f_flag & os.ST_RDONLY for p in ['/', '/etc', '/usr', '/sys/fs/cgroup'])
assert not os.path.lexists('/dev/mmcblk0p15')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip() == '747e87fe-198f-49f8-997a-8e198315968d'
line = Path('/proc/self/cgroup').read_text().strip()
assert line.startswith('0::') and '\n' not in line
group = line.removeprefix('0::')
cgroup = Path('/sys/fs/cgroup') / group.lstrip('/') / 'cgroup.procs'
assert set(map(int,cgroup.read_text().split())) == {os.getpid()}
result = dict(status='starting', actual_ARM_kernel=os.uname().release,
              live_OS_files_written=False, package_transaction_executed=False)
try:
    with tarfile.open('/var/lib/fx0-rollback/stable-userspace-01/delta-files.private.tar.gz','r:gz') as archive:
        manifest = json.load(archive.extractfile('.capture-manifest.private.json'))
    label = next(row['xattrs']['security.selinux'] for row in manifest['paths'].values()
                 if 'security.selinux' in row.get('xattrs',{}))
    probe.write_bytes(b'owned private permission probe\n')
    os.chown(probe, 1000, 1000)
    os.chown(probe, 0, 0)
    probe.chmod(0o4755)
    os.setxattr(probe,'security.selinux',bytes.fromhex(label))
    assert os.getxattr(probe,'security.selinux').hex() == label
    os.setxattr(probe,'user.fx0-probe',b'roundtrip')
    assert os.getxattr(probe,'user.fx0-probe') == b'roundtrip'
    probe.unlink()
    (root/'usr/lib').mkdir(parents=True)
    (root/'usr/sbin').mkdir()
    (root/'usr/bin').mkdir()
    (root/'bin').symlink_to('usr/bin')
    (root/'sbin').symlink_to('usr/sbin')
    (root/'lib').symlink_to('usr/lib')
    runtime=json.loads((inputs/'runtime-manifest.json').read_text())
    with tarfile.open(inputs/'runtime-libraries.tar.gz','r:gz') as archive:
        for name,row in runtime['paths'].items():
            path=root/name.lstrip('/')
            if row['kind']=='file':
                data=archive.extractfile(name.lstrip('/')).read()
                assert hashlib.sha256(data).hexdigest()==row['sha256']
                path.write_bytes(data)
                path.chmod(row['mode'])
            else:
                path.symlink_to(row['target'])
    busybox=json.loads((inputs/'busybox-verification.json').read_text())['binaries'][0]
    assert busybox['native_path']=='/usr/bin/busybox'
    data=Path('/usr/bin/busybox').read_bytes()
    assert hashlib.sha256(data).hexdigest()==busybox['native_ELF_sha256']
    (root/'usr/bin/busybox').write_bytes(data)
    (root/'usr/bin/busybox').chmod(0o755)
    (root/'usr/bin/sh').symlink_to('/bin/busybox')
    (root/'etc/apk').mkdir(parents=True)
    (root/'etc/apk/arch').write_text('armv7\n')
    command=['/usr/bin/strace','-f','-e','trace=execve,execveat','-o',str(run/'exec.trace'),
             '/usr/sbin/chroot',str(root),'/bin/sh','-c','exec /usr/sbin/apk --version']
    child=subprocess.run(command,capture_output=True,text=True,timeout=30)
    (run/'execution.log').write_text(child.stdout+child.stderr)
    assert child.returncode==0 and child.stdout.strip()=='apk-tools 3.0.8-r0, compiled for armv7.', child.stderr
    comparisons=[]
    for old,threshold in [('10.3_p1-r1','10.0_p1-r2'),('1.23.4-r0','1.21.2-r1')]:
        child=subprocess.run(['/usr/sbin/chroot',str(root),'/usr/sbin/apk','version','-t',old,threshold],
                             capture_output=True,text=True,timeout=15)
        assert child.returncode==0 and child.stdout.strip()=='>',(child.stdout,child.stderr)
        comparisons.append(dict(installed=old,threshold=threshold,comparison='>'))
    assert set(map(int,cgroup.read_text().split()))=={os.getpid()}
    result.update(status='passed', ownership_and_setuid_mode_roundtrip=True,
                  SELinux_and_user_xattrs_roundtrip=True, actual_native_chroot_shell_APK_and_strace=True,
                  native_APK_version='3.0.8-r0', native_hook_version_comparisons=comparisons,
                  all_owned_children_reaped=True, actual_cgroup_ownership_verified=True)
except BaseException as error:
    result.update(status='failed',error=type(error).__name__+': '+str(error))
    raise
finally:
    if probe.exists():probe.unlink()
    if root.exists():
        assert set(map(int,cgroup.read_text().split()))=={os.getpid()}
        shutil.rmtree(root)
    result['private_fixture_removed']=not os.path.lexists(root) and not os.path.lexists(probe)
    (run/'result.json').write_text(json.dumps(result,indent=2)+'\n')
