#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Read-only verification after the qualified stable userspace transaction."""
import argparse
import datetime
import hashlib
import base64
import io
import zlib
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import tarfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--boot-id', required=True, help='Expected new persistent boot ID')
args = parser.parse_args()
parent = Path('/var/lib/fx0-rollback/kernel-6.18.63-01')
plan = json.loads((parent / 'install-plan-confirmed-02.json').read_text())
status = json.loads((parent / 'kernel-update-status.json').read_text())
release = plan['candidate_release']
boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot == args.boot_id
assert os.uname().release == release and boot != plan['boot_id']
assert Path('/proc/sys/kernel/tainted').read_text().strip() == '0'
def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()
def out(*args):
    return subprocess.check_output(args, text=True, timeout=20).strip()
kernel_notes_sha256 = sha('/sys/kernel/notes')
assert kernel_notes_sha256 == '05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
assert status['stage'] == 'updated-and-verified' and status['all_owned_process_groups_terminal']
assert sha(parent / 'install_native_v2.py') == plan['controller_sha256']
assert sha(parent / 'update_transaction.py') == plan['transaction_helper_sha256']
assert sha(parent / 'commit_state.py') == plan['commit_state_helper_sha256']
assert sha(parent / 'backup.private.json') == plan['backup_metadata_sha256']
backup = json.loads((parent / 'backup.private.json').read_text())
assert sha(parent / 'before-files.private.tar.gz') == backup['archive_sha256']
assert sha(parent / 'boot-partition.private.img') == backup['raw_boot_sha256']
sys.path.insert(0, str(parent))
import install_native_v2 as verifier
needed = {'lib/apk/db/installed', 'etc/apk/world', 'boot/boot.img'}
original = {}
with tarfile.open(parent / 'before-files.private.tar.gz', 'r|gz') as archive:
    for member in archive:
        if member.name in needed:
            assert member.isfile()
            original[member.name] = archive.extractfile(member).read()
assert set(original) == needed
baseline = verifier.database(original['lib/apk/db/installed'])
current = verifier.database(Path('/lib/apk/db/installed').read_bytes())
kernel_package = 'linux-postmarketos-qcom-msm8226'
assert current.keys() == baseline.keys()
stable = Path('/var/lib/fx0-rollback/stable-userspace-live-03')
assert sha(stable/'scope.json')=='543794c39a150a26044f806285893c82c76f7ac5ddd6a926188cdf0025eacc80'
stable_scope=json.loads((stable/'scope.json').read_text())
stable_plan=json.loads((stable/'install-plan.json').read_text())
stable_status=json.loads((stable/'install-status.json').read_text())
assert stable_status['stage']=='updated-and-verified' and stable_status['all_owned_process_groups_terminal']
assert stable_status['selected_candidate_identities_verified']==30 and stable_status['other_package_identities_unchanged']==745
assert stable_status['world_exact'] and not stable_status['boot_written']
upgrade_window=stable_status['upgrade_window_ns']
assert len(upgrade_window)==2 and all(type(n) is int for n in upgrade_window)
assert upgrade_window[0]<=upgrade_window[1]
assert sha(stable/'stable_transaction.py')==stable_plan['controller_sha256']==stable_plan['qualified_controller_sha256']
assert sha(stable/'update_transaction.py')==stable_plan['transaction_helper_sha256']
assert sha(stable/'controller-qualification.json')==stable_plan['qualification_result_sha256']
stable_qualified=json.loads((stable/'controller-qualification.json').read_text())
assert stable_qualified['status']=='passed' and stable_qualified['same_source_success_and_two_failure_recoveries']
assert stable_qualified['controller_sha256']==stable_plan['controller_sha256']
assert stable_qualified['scope_sha256']=='543794c39a150a26044f806285893c82c76f7ac5ddd6a926188cdf0025eacc80'
assert sha('/lib/apk/db/installed')==stable_status['database_sha256']
changed_packages = {kernel_package, 'treescan'} | set(stable_scope['new_identities'])
assert len(changed_packages)==32
for name,row in stable_scope['new_identities'].items():
    assert current[name]==dict(V=[row['version']],C=[row['checksum']])
for name,row in stable_scope['old_identities'].items():
    assert baseline[name]==dict(V=[row['version']],C=[row['checksum']])
assert {k: v for k, v in current.items() if k not in changed_packages} == {
    k: v for k, v in baseline.items() if k not in changed_packages}
assert current['treescan'] == dict(V=['0.1-r1'], C=['Q1ReYHEKb42riq9D9r5JZ4CWKD8I4='])
assert current[kernel_package] == dict(V=['6.18.63-r1'], C=[plan['candidate_control_checksum']])
old_world = original['etc/apk/world'].decode()
held = [line for line in old_world.splitlines(keepends=True) if line.startswith(kernel_package + '><Q1')]
assert len(held) == 1
expected_world = old_world.replace(held[0], kernel_package + '><' + plan['candidate_control_checksum'] + '\n').encode()
assert Path('/etc/apk/world').read_bytes() == expected_world
assert Path('/etc/kernel-cmdline.d/90-fx0-module-signatures.conf').read_bytes() == b'module.sig_enforce=1\n'
assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip() == 'Y'
cmdline = Path('/proc/cmdline').read_text().split()
assert [word for word in cmdline if word.startswith('module.sig_enforce=')] == ['module.sig_enforce=1']
assert not any(word.startswith('fx0.native_trial=') for word in cmdline)
assert not Path('/run/systemd/system/fx0-native-return.timer').exists()
modules = []
for name, expected in plan['candidate_payload_sha256'].items():
    assert sha('/' + name) == expected, name
    if name.endswith('.ko.zst'):
        modules.append(name)
assert Path('/usr/share/kernel/postmarketos-qcom-msm8226/kernel.release').read_text().strip() == release
assert out('findmnt', '-n', '-o', 'FSTYPE', '-T', '/usr/lib/modules') != 'tmpfs'
image = Path('/boot/boot.img').read_bytes()
assert hashlib.sha256(image).hexdigest() == status['candidate_boot_image_sha256']
kernel, dtb, ramdisk, image_cmdline = verifier.boot_parts(image, plan['kernel_bytes'])
assert hashlib.sha256(kernel).hexdigest() == plan['kernel_sha256']
assert hashlib.sha256(dtb).hexdigest() == plan['DTB_sha256']
assert ramdisk == Path('/boot/initramfs').read_bytes()
assert verifier.cpio_index(ramdisk) == plan['expected_initramfs_payloads']
assert image_cmdline.count('module.sig_enforce=1') == 1
raw = Path('/dev/mmcblk0p15').read_bytes()
assert hashlib.sha256(raw[:plan['boot_offset']]).hexdigest() == plan['bootloader_prefix_sha256']
assert raw[plan['boot_offset']:plan['boot_offset'] + len(image)] == image
assert out('systemctl', 'is-system-running') == 'running'
assert not out('systemctl', '--failed', '--no-legend')
assert not out('systemctl', 'list-jobs', '--no-legend')
assert out('systemctl', 'is-active', 'tinydm', 'upower', 'iio-sensor-proxy').splitlines() == ['active'] * 3
assert Path('/sys/devices/system/cpu/online').read_text().strip() == '0-3'
assert Path('/sys/class/graphics/fb0/name').read_text().strip() == 'msmdrmfb'
display = {}
for name in ['fd900000.display-subsystem', 'fd928000.iommu', 'fd922800.dsi', 'fd922a00.phy']:
    path = Path('/sys/bus/platform/devices') / name / 'power/control'
    assert path.read_text().strip() == 'auto'
    display[name] = 'auto'
sway = int(out('pgrep', '-x', 'sway'))
gestures = [int(value) for value in out('pgrep', '-x', 'lisgd').splitlines()]
assert len(gestures) == 1
touch = Path('/dev/input/by-path/first-touchscreen').resolve()
assert any(os.readlink(path) == str(touch) for path in Path('/proc', str(gestures[0]), 'fd').iterdir())
temperatures = {path.parent.name: int(path.read_text()) for path in Path('/sys/class/thermal').glob('thermal_zone*/temp')}
assert len(temperatures) == 2 and all(-40000 <= value < 60000 for value in temperatures.values())
with open('/sys/kernel/debug/regmap/0-01/registers', 'rb') as stream:
    pmic = {hex(address): os.pread(stream.fileno(), 9, address * 9).decode()
            for address in [0xc041, 0xc046, 0x1740, 0x1741]}
assert pmic == {'0xc041': 'c041: 00\n', '0xc046': 'c046: 00\n', '0x1740': '1740: 01\n', '0x1741': '1741: 73\n'}
serious = [line for line in out('dmesg').splitlines()
           if re.search(r'CFI failure|Kernel panic|Internal error: Oops|BUG:|WARNING: CPU:', line)]
assert not serious, serious
treescan_sha = sha('/usr/bin/treescan')
assert treescan_sha == '933ebbc4bfe8017a5a6e39bc97d76a499cfaecf5598bacde68744a69206ad4a0'
activation = Path('/var/lib/fx0-rollback/treescan-live-r1-01')
activation_plan = json.loads((activation / 'install-plan.json').read_text())
activation_status = json.loads((activation / 'install-status.json').read_text())
assert activation_status['stage'] == 'updated-and-verified'
assert activation_status['all_owned_process_groups_terminal']
assert activation_status['other_package_identities_unchanged'] == 774
assert activation_status['world_exact'] and not activation_status['boot_written']
assert stable_scope['baseline_manifest_sha256']=='815afabfc4705e77ac322a39627503271425b1d21ea4ac9611696d47703ca4da'
assert sha(activation / 'treescan_transaction.py') == activation_plan['controller_sha256']
assert activation_plan['qualified_controller_sha256'] == activation_plan['controller_sha256']
assert sha(activation / 'update_transaction.py') == activation_plan['transaction_helper_sha256']
assert sha(activation / 'repo/armv7/treescan-0.1-r1.apk') == '24f63c20f7197468a005b08c023242e70c491edb40c965372c540d70736ddf11'
assert sha(activation / 'controller-qualification.json') == activation_plan['qualification_result_sha256']
qualified = json.loads((activation / 'controller-qualification.json').read_text())
assert qualified['status'] == 'passed' and qualified['same_source_success_and_failure']
assert qualified['controller_sha256'] == activation_plan['controller_sha256']
assert qualified['normal_native_signed_APK_hooks_verified'] and qualified['private_fixture_removed']
metadata = Path('/usr/bin/treescan').lstat()
assert stat.S_ISREG(metadata.st_mode) and stat.S_IMODE(metadata.st_mode) == 0o755
assert (metadata.st_uid, metadata.st_gid, metadata.st_nlink) == (0, 0, 1)
assert metadata.st_mtime_ns == activation_plan['candidate_mtime_ns']
fresh_path = Path('/var/lib/fx0-rollback/post-r1-userspace-baseline-01/manifest.private.json')
assert sha(fresh_path) == '17eebbe77e2a19896035b3791d4253cebdc2f659c7c9509e2e9dd660b3d96a06'
fresh = json.loads(fresh_path.read_text())
assert {key: os.getxattr('/usr/bin/treescan', key).hex() for key in os.listxattr('/usr/bin/treescan')} == fresh['paths']['/usr/bin/treescan']['xattrs']
wanted_units = {}
for stem in ['system', 'user']:
    start = Path('/usr/lib/systemd') / stem
    for directory, directories, files in os.walk(start, followlinks=False):
        for leaf in directories + files:
            path = Path(directory) / leaf
            kind = 'symlink' if path.is_symlink() else 'dir' if path.is_dir() else 'file'
            wanted_units[str(path)] = (kind, path.stat().st_mtime_ns // 10**9)
def unit_rows(data):
    rows = {}
    for line in data.decode().splitlines():
        name, kind, timestamp = line.rsplit(' ', 2)
        assert name not in rows and kind.startswith('type=') and timestamp.startswith('mtime=')
        rows[name] = (kind[5:], int(timestamp[6:]))
    return rows
assert len(wanted_units) == 545
assert unit_rows(Path('/var/lib/systemd-apk/installed.units').read_bytes()) == wanted_units
scanned = {}
for stem in ['system', 'user']:
    output = subprocess.run(['/usr/bin/treescan', '/usr/lib/systemd/' + stem], capture_output=True, check=True, timeout=20)
    assert not output.stderr
    rows = unit_rows(output.stdout)
    assert not (scanned.keys() & rows.keys())
    scanned.update(rows)
assert scanned == wanted_units


# Parse the authenticated archives independently of the controller's candidate
# metadata table, and check the actual installed paths before executing APK.
fresh_path=Path('/var/lib/fx0-rollback/post-treescan-userspace-baseline-02/manifest.private.json')
assert sha(fresh_path)=='815afabfc4705e77ac322a39627503271425b1d21ea4ac9611696d47703ca4da'
fresh=json.loads(fresh_path.read_text())
assert fresh['private_key_files_excluded']
def canonical(name):
    path=Path(name)
    assert not path.is_absolute() and '..' not in path.parts
    if path.parts[0] in ['bin','sbin','lib']:path=Path('usr')/path
    result='/'+str(path)
    assert '/etc/ssh/ssh_host_' not in result and not result.startswith('/etc/ssl/private/')
    return result

def actual_path(name):
    path=Path('/')
    for part in Path(name).parts[1:-1]:
        path/=part
        assert path.is_dir() and not path.is_symlink(),('Unexpected parent type',name)
    return path/Path(name).name

payloads={};archives=[];incoming_owners={};incoming_controls={}
for package in stable_scope['packages']:
    path=stable/'repos'/str(package['repository'])/'armv7'/(package['package']+'-'+package['version']+'.apk')
    assert not path.is_symlink() and sha(path)==package['sha256']
    archives.append(str(path));data=path.read_bytes();streams=[]
    while data:
        decoder=zlib.decompressobj(31);plain=decoder.decompress(data,128*1024**2)
        assert decoder.eof and not decoder.unconsumed_tail
        streams.append((data[:len(data)-len(decoder.unused_data)],plain));data=decoder.unused_data
    assert len(streams) in [2,3]
    assert 'Q1'+base64.b64encode(hashlib.sha1(streams[1][0]).digest()).decode()==package['index_control_checksum']
    with tarfile.open(fileobj=io.BytesIO(streams[1][1]),mode='r:') as control:
        controls={}
        for line in control.extractfile('.PKGINFO').read().decode().splitlines():
            if ' = ' in line:
                key,value=line.split(' = ',1);controls.setdefault(key,[]).append(value)
        fields={key:values[-1] for key,values in controls.items()}
    assert fields['pkgname']==package['package'] and fields['pkgver']==package['version']
    incoming_controls[package['package']]=controls
    if len(streams)==2:
        assert 'datahash' not in fields;continue
    assert hashlib.sha256(streams[2][0]).hexdigest()==fields['datahash']
    with tarfile.open(fileobj=io.BytesIO(streams[2][1]),mode='r:') as data_archive:
        for member in data_archive:
            if member.isdir():continue
            name=canonical(member.name);assert name not in payloads
            incoming_owners[name]=package['package']
            row=dict(mode=member.mode,uid=member.uid,gid=member.gid,mtime_ns=int(member.mtime)*10**9)
            if member.issym():row.update(kind='symlink',target=member.linkname,apk_checksum='Q1'+base64.b64encode(hashlib.sha1(member.linkname.encode()).digest()).decode())
            elif member.islnk():row.update(kind='hardlink',target=canonical(member.linkname))
            else:
                assert member.isfile();body=data_archive.extractfile(member).read()
                row.update(kind='file',size=len(body),sha256=hashlib.sha256(body).hexdigest(),apk_checksum='Q1'+base64.b64encode(hashlib.sha1(body).digest()).decode())
            payloads[name]=row
# Independently derive files skipped during extraction by the installed
# package's replacement rule. These files never reach APK's config merge.
original_owners={};original_packages={}
with tarfile.open(Path('/var/lib/fx0-rollback/post-treescan-userspace-baseline-02/files.private.tar.gz'),'r|gz') as archive:
    for member in archive:
        if member.name=='usr/lib/apk/db/installed':
            assert member.isfile()
            post_treescan_database=archive.extractfile(member).read();break
    else:raise AssertionError('Captured package database missing')
assert hashlib.sha256(post_treescan_database).hexdigest()==fresh['paths']['/usr/lib/apk/db/installed']['sha256']
for paragraph in post_treescan_database.decode().split('\n\n'):
    header={};directory=None
    for line in paragraph.splitlines():
        if line.startswith('F:'):break
        if len(line)>1 and line[1]==':':
            assert line[0] not in header
            header[line[0]]=line[2:]
    if 'P' not in header:continue
    owner=header['P'];assert owner not in original_packages
    original_packages[owner]=header
    for line in paragraph.splitlines():
        if line.startswith('F:'):directory=line[2:]
        elif line.startswith('R:'):
            assert directory is not None
            name=canonical(str(Path(directory)/line[2:]))
            original_owners.setdefault(name,set()).add(owner)
retained={}
for name,provider in incoming_owners.items():
    owners=original_owners.get(name,set())
    if not owners or owners=={provider}:continue
    assert len(owners)==1
    owner=next(iter(owners));assert owner not in incoming_controls
    before=original_packages[owner];after=incoming_controls[provider]
    old_replaces=before.get('r','').split()
    new_replaces=[dep for value in after.get('replaces',[]) for dep in value.split()]
    assert all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9+_.-]*',dep) for dep in old_replaces+new_replaces)
    old_priority=int(before.get('q','0')) if provider in old_replaces else -1
    new_priority=int(after.get('replaces_priority',['0'])[0]) if owner in new_replaces else -1
    if old_priority>new_priority:
        retained[name]=owner
    else:assert new_priority>=0 or (before.get('o') and [before['o']]==after.get('origin'))
assert set(retained)==set(stable_scope['retained_owner_payloads'])=={'/etc/issue','/etc/os-release','/usr/lib/os-release'}
current_owners={};current_headers={}
for paragraph in Path('/usr/lib/apk/db/installed').read_text().split('\n\n'):
    header={}
    for line in paragraph.splitlines():
        if line.startswith('F:'):break
        if len(line)>1 and line[1]==':':
            assert line[0] not in header
            header[line[0]]=line[2:]
    if 'P' in header:
        assert header['P'] not in current_headers
        current_headers[header['P']]=header
    owner=None;directory=None
    for line in paragraph.splitlines():
        if line.startswith('P:'):owner=line[2:]
        elif line.startswith('F:'):directory=line[2:]
        elif line.startswith('R:'):
            assert owner is not None and directory is not None
            name=canonical(str(Path(directory)/line[2:]))
            if name in retained:current_owners.setdefault(name,set()).add(owner)
for name,owner in retained.items():
    assert current_owners[name]=={owner}
    assert name not in stable_scope['mutable_files']
    assert current[owner]==dict(V=[original_packages[owner]['V']],C=[original_packages[owner]['C']])
    assert current_headers[owner].get('r','').split()==original_packages[owner].get('r','').split()
    assert int(current_headers[owner].get('q','0'))==int(original_packages[owner].get('q','0'))
    assert current_headers[owner].get('o','')==original_packages[owner].get('o','')
    before=fresh['paths'][name];path=actual_path(name);st=path.lstat()
    assert (stat.S_IMODE(st.st_mode),st.st_uid,st.st_gid,st.st_mtime_ns)==tuple(before[k] for k in ['mode','uid','gid','mtime_ns'])
    assert {k:os.getxattr(path,k,follow_symlinks=False).hex() for k in os.listxattr(path,follow_symlinks=False)}==before['xattrs']
    if before['kind']=='file':assert stat.S_ISREG(st.st_mode) and st.st_nlink==before['nlink'] and sha(path)==before['sha256']
    else:assert stat.S_ISLNK(st.st_mode) and os.readlink(path)==before['target']
    if name.startswith('/etc/'):
        assert not os.path.lexists(name+'.apk-new') and not os.path.lexists(name+'.apk-old')
old_config_checksums={}
for paragraph in post_treescan_database.decode().split('\n\n'):
    directory=None;name=None
    for line in paragraph.splitlines():
        if line.startswith('F:'):directory=line[2:];name=None
        elif line.startswith('R:'):
            assert directory is not None;name='/'+directory+'/'+line[2:] if directory else '/'+line[2:]
        elif line.startswith('Z:') and name in stable_scope['config_paths']:old_config_checksums[name]=line[2:]
assert set(old_config_checksums)==set(stable_scope['config_paths'])
def matches_payload(name,row):
    path=actual_path(name);st=path.lstat()
    assert (stat.S_IMODE(st.st_mode),st.st_uid,st.st_gid)==(row['mode'],row['uid'],row['gid']),('Signed payload metadata differs',name)
    if row['kind']=='symlink':
        assert stat.S_ISLNK(st.st_mode) and os.readlink(path)==row['target']
        assert upgrade_window[0]<=st.st_mtime_ns<=upgrade_window[1],('Symlink timestamp outside owned APK command',name)
    else:
        assert st.st_mtime_ns==row['mtime_ns'],('Signed regular-file timestamp differs',name)
        assert stat.S_ISREG(st.st_mode) and st.st_size==row['size'] and sha(path)==row['sha256']
    source=name.removesuffix('.apk-new')
    desired=fresh['paths'][source]['xattrs'] if fresh['paths'][source]['kind']!='absent' else stable_scope['new_file_xattrs'][source]
    assert {k:os.getxattr(path,k,follow_symlinks=False).hex() for k in os.listxattr(path,follow_symlinks=False)}==desired
for name,row in payloads.items():
    if name in retained:continue
    if row['kind']=='hardlink':
        leader=row['target'];seen={name}
        while payloads[leader]['kind']=='hardlink':
            assert leader not in seen;seen.add(leader);leader=payloads[leader]['target']
        matches_payload(name,payloads[leader]);a=actual_path(name).lstat();b=actual_path(leader).lstat()
        assert (a.st_dev,a.st_ino)==(b.st_dev,b.st_ino);continue
    if name not in stable_scope['config_paths']:
        matches_payload(name,row);continue
    path=actual_path(name);st=path.lstat();before=fresh['paths'][name]
    if before['kind']=='file':
        preserved=stat.S_ISREG(st.st_mode) and sha(path)==before['sha256']
        body_is_candidate=stat.S_ISREG(st.st_mode) and row['kind']=='file' and sha(path)==row['sha256']
    else:
        preserved=stat.S_ISLNK(st.st_mode) and os.readlink(path)==before['target']
        body_is_candidate=stat.S_ISLNK(st.st_mode) and row['kind']=='symlink' and os.readlink(path)==row['target']
    new=actual_path(name+'.apk-new');assert not os.path.lexists(name+'.apk-old')
    preserved=preserved and (stat.S_IMODE(st.st_mode),st.st_uid,st.st_gid,st.st_mtime_ns)==(before['mode'],before['uid'],before['gid'],before['mtime_ns'])
    preserved=preserved and {k:os.getxattr(path,k,follow_symlinks=False).hex() for k in os.listxattr(path,follow_symlinks=False)}==before['xattrs']
    if preserved:
        if os.path.lexists(new):matches_payload(name+'.apk-new',row)
        else:assert body_is_candidate or old_config_checksums[name]==row['apk_checksum'],('Changed protected default unavailable',name)
    else:
        matches_payload(name,row);assert not os.path.lexists(new)
assert len(payloads)==2688
candidate_inodes={}
for name in payloads:
    if name in retained:continue
    st=actual_path(name).lstat()
    if stat.S_ISREG(st.st_mode):candidate_inodes.setdefault((st.st_dev,st.st_ino),[]).append(st.st_nlink)
assert all(all(nlink==len(group) for nlink in group) for group in candidate_inodes.values()),'Candidate inode has an unexpected hardlink'
for name in stable_scope['mutable_files']:
    if name not in payloads and name not in stable_scope['mutable_state_files'] and name not in stable_scope['config_sidecars']:
        assert not os.path.lexists(actual_path(name)),('Obsolete package path remains',name)
result=subprocess.run(['/usr/sbin/apk','--no-network','--keys-dir','/etc/apk/keys','verify',*archives],capture_output=True,text=True,timeout=120)
assert result.returncode==0
stable_APK_version=out('/usr/sbin/apk','--version')
assert stable_APK_version=='apk-tools 3.0.9-r0, compiled for armv7.'
assert sha('/etc/apk/repositories')=='37534543d9a1defca831a5b104f2e871f363555df8b817ec8a54b59d1138562a'

print(json.dumps(dict(
    recorded_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    boot_id=boot, kernel=release, package_version='6.18.63-r1',
    taint=0, kernel_notes_sha256=kernel_notes_sha256,
    signature_enforcement='Y', persistent_signature_cmdline=True,
    native_trial_marker=False, return_timer=False, modules_on_persistent_storage=True,
    candidate_payload_files_verified=len(plan['candidate_payload_sha256']),
    candidate_module_files_verified=len(modules),
    initramfs_payload_entries_verified=len(plan['expected_initramfs_payloads']),
    other_original_package_identities_unchanged=len(current)-32,
    other_post_treescan_package_identities_unchanged=745,
    intended_kernel_treescan_and_30_stable_identity_changes_only=True,
    stable_candidate_payload_paths_verified=len(payloads)-len(retained),
    retained_distro_payload_paths_verified=len(retained),
    stable_archive_signatures_verified=30,stable_APK_version=stable_APK_version,
    database_sha256=sha('/lib/apk/db/installed'),world_sha256=sha('/etc/apk/world'),
    repositories_sha256=sha('/etc/apk/repositories'),
    treescan_package_version='0.1-r1', treescan_ELF_sha256=treescan_sha,
    unit_inventory_paths_verified=len(wanted_units), installed_treescan_scans_verified=True,
    installed_world_exact=True, boot_image_sha256=hashlib.sha256(image).hexdigest(),
    raw_boot_sha256=hashlib.sha256(raw).hexdigest(), bootloader_prefix_preserved=True,
    original_r50_backups_still_verified=True, systemd='running',
    Sway_PID=sway, gesture_PID=gestures[0], gesture_touchscreen_open=True,
    display_PM_auto=display, CPUs_online='0-3', temperatures_mC=temperatures,
    PMIC_registers=pmic, serious_kernel_warnings=serious,
    audio_testing=False, read_only=True)))
