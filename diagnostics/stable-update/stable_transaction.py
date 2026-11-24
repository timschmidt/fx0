#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Apply a fixed authenticated stable update with narrowly scoped recovery."""
import argparse
import base64
import contextlib
import datetime
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
import tarfile
import tempfile
import time

BOOT='6114df77-29f2-43ac-8ede-1ca72c743895'
RELEASE='6.18.63-fx0-vibrator-alpine'
BACKUP=Path('/var/lib/fx0-rollback/post-treescan-userspace-baseline-02')
MANIFEST_SHA='815afabfc4705e77ac322a39627503271425b1d21ea4ac9611696d47703ca4da'
ARCHIVE_SHA='813662124af17fafbccba10c575c56a2503716e3d1a9803e034af008c7a882b2'
SCOPE_SHA='543794c39a150a26044f806285893c82c76f7ac5ddd6a926188cdf0025eacc80'
DB='/usr/lib/apk/db/installed'
LOCK='/usr/lib/apk/db/lock'
WORLD='/etc/apk/world'
INVENTORY='/var/lib/systemd-apk/installed.units'
EXECUTOR='/usr/lib/apk/exec'
LIVE_WORK=Path('/var/lib/fx0-rollback/stable-userspace-live-03')
FIXTURE_ROOT=Path('/var/lib/fx0-rollback/stable-post-treescan-fixture-02/root')


def digest(data):return hashlib.sha256(data).hexdigest()

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def database(data):
    result={}
    for paragraph in data.decode().split('\n\n'):
        row={line[:1]:line[2:] for line in paragraph.splitlines() if len(line)>1 and line[1]==':'}
        if row.get('P'):
            assert row['P'] not in result,'Duplicate package'
            result[row['P']]=dict(version=row['V'],checksum=row['C'])
    return result


def atomic(path,data,mode=0o600):
    fd,temporary=tempfile.mkstemp(prefix='.fx0-stable-',dir=path.parent)
    try:
        os.fchmod(fd,mode)
        with os.fdopen(fd,'wb') as stream:
            stream.write(data);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
        directory=os.open(path.parent,os.O_RDONLY|os.O_DIRECTORY)
        try:os.fsync(directory)
        finally:os.close(directory)
    finally:
        if os.path.lexists(temporary):os.unlink(temporary)


class Snapshot:
    """Guard the complete capture; mutate only the separately pinned scope."""

    def __init__(self,root,manifest,scope,payloads,*,allow_live=False):
        self.root=Path(root).resolve(strict=True)
        assert self.root!=Path('/') or allow_live,'Live root requires the fixed qualified controller'
        self.manifest=manifest;self.scope=scope;self.rows=manifest['paths'];self.payloads=payloads
        self.files=frozenset(scope['mutable_files']);self.directories=frozenset(scope['mutable_directories'])
        assert len(self.files)==len(scope['mutable_files']) and len(self.directories)==len(scope['mutable_directories'])
        assert not self.files&self.directories
        assert self.files|self.directories<=self.rows.keys()
        assert LOCK not in self.files|self.directories
        for name in self.files|self.directories:
            assert name.startswith('/') and name!='/' and '..' not in Path(name).parts
            assert not name.startswith(('/boot/','/usr/lib/modules/','/usr/share/kernel/','/root/','/etc/ssl/private/'))
            assert name!='/usr/bin/treescan' and '/etc/ssh/ssh_host_' not in name
            assert not name.endswith(('.pem','.key','.rsa'))
        for name in self.files:
            row=self.rows[name]
            assert row['kind'] in {'file','symlink','absent'}
            if row['kind']=='file' and 'hardlink_to' in row:assert row['hardlink_to'] in self.files
        assert set(payloads)=={n for n in self.files if self.rows[n]['kind']=='file' and 'hardlink_to' not in self.rows[n]}
        for name,data in payloads.items():assert digest(data)==self.rows[name]['sha256']
        groups={}
        for name,row in self.rows.items():
            if row['kind']=='file':groups.setdefault(row.get('hardlink_to',name),set()).add(name)
        assert all(not (names&self.files) or names<=self.files for names in groups.values()),'Captured hardlink crosses recovery scope'
        for names in groups.values():
            assert all(self.rows[name]['nlink']==len(names) for name in names),'Incomplete captured hardlink group'
        assert all(self.rows[n]['kind']=='directory' for n in self.directories)
        assert manifest['directory_membership'][EXECUTOR]==[]
        self.lock_fd=None;self.lock_inode=None;self.install_window=None
        self.retained=scope.get('retained_owner_payloads',{})
        assert self.retained.keys()<=scope['candidate_payloads'].keys() & self.rows.keys()
        assert not self.retained.keys() & (self.files | self.directories), 'Retained owner files must be immutable'
        self.candidates={n:r['expected'] for n,r in scope['candidate_payloads'].items() if n not in self.retained}
        self.configs=set(scope['config_paths']);self.sidecars=set(scope['config_sidecars'])
        assert not self.configs & self.retained.keys()
        assert not {n+suffix for n in self.retained for suffix in ['.apk-new','.apk-old']} & self.files
        self.state_files=set(scope['mutable_state_files'])
        assert self.state_files|self.sidecars<=self.files
        self.allowed_members={}
        for name in self.files|self.directories:
            self.allowed_members.setdefault(str(Path(name).parent),set()).add(Path(name).name)
        self.ownership=None
        self.retained_owner_metadata={}
        if self.retained:
            helper=Path(__file__).with_name('apk_payload_ownership.py')
            assert sha(helper)==scope['ownership_helper_sha256']
            spec=importlib.util.spec_from_file_location('apk_payload_ownership',helper)
            self.ownership=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.ownership)
            assert self.ownership.retained_payloads(self.original_data(DB).decode(),scope['candidate_payloads'],
                scope['incoming_ownership'])==self.retained, 'Retained ownership does not follow captured replacement rules'
            packages,_=self.ownership.installed_ownership(self.original_data(DB).decode())
            self.retained_owner_metadata={r['owner']:packages[r['owner']] for r in self.retained.values()}

    def verify_retained_ownership(self):
        if not self.retained:return
        packages,owners=self.ownership.installed_ownership(self.target(DB).read_text())
        for name,rule in self.retained.items():
            assert owners.get(name)==[rule['owner']],('Retained file owner changed',name)
            assert {k:packages[rule['owner']][k] for k in ['version','checksum']}==rule['owner_identity']
            assert packages[rule['owner']]==self.retained_owner_metadata[rule['owner']],('Retained owner replacement metadata changed',name)

    def target(self,name):
        assert name.startswith('/') and name!='/' and '..' not in Path(name).parts
        path=self.root
        for part in Path(name).parts[1:-1]:
            path/=part
            assert not path.is_symlink(),('Symlink ancestor',name)
            if path.exists():assert path.is_dir(),('Non-directory ancestor',name)
        return path/Path(name).name

    @staticmethod
    def attributes(path):
        return {key:os.getxattr(path,key,follow_symlinks=False).hex() for key in os.listxattr(path,follow_symlinks=False)}

    def locks(self):
        assert self.lock_fd is not None
        held=os.fstat(self.lock_fd);found=set()
        linked=self.target(LOCK).lstat()
        assert (held.st_dev,held.st_ino)==(linked.st_dev,linked.st_ino)==self.lock_inode,'APK lock inode replaced'
        for line in Path('/proc/locks').read_text().splitlines():
            fields=line.split()
            if len(fields)<8 or fields[1] not in {'FLOCK','POSIX'} or fields[4]!=str(os.getpid()):continue
            major,minor,inode=fields[5].split(':')
            if (int(major,16),int(minor,16),int(inode))==(os.major(held.st_dev),os.minor(held.st_dev),held.st_ino):
                assert fields[3]=='WRITE';found.add(fields[1])
        assert found=={'FLOCK','POSIX'},'Both real APK lock types must remain held'

    @contextlib.contextmanager
    def locked(self):
        assert self.lock_fd is None
        fd=os.open(self.target(LOCK),os.O_RDWR|os.O_CLOEXEC|os.O_NOFOLLOW)
        try:
            fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB);fcntl.lockf(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
            st=os.fstat(fd);identity=st.st_dev,st.st_ino
            assert self.lock_inode is None or self.lock_inode==identity,'APK lock inode replaced'
            self.lock_inode=identity;self.lock_fd=fd;self.locks()
            try:yield
            finally:self.locks()
        finally:self.lock_fd=None;os.close(fd)

    def row(self,name):
        path=self.target(name)
        try:st=path.lstat()
        except FileNotFoundError:return dict(kind='absent')
        result=dict(mode=stat.S_IMODE(st.st_mode),uid=st.st_uid,gid=st.st_gid,mtime_ns=st.st_mtime_ns,xattrs=self.attributes(path))
        if stat.S_ISDIR(st.st_mode):result['kind']='directory'
        elif stat.S_ISLNK(st.st_mode):result.update(kind='symlink',target=os.readlink(path))
        else:
            assert stat.S_ISREG(st.st_mode),('Special file in guarded namespace',name)
            if name==LOCK:
                assert self.lock_fd is not None
                checksum=digest(os.pread(self.lock_fd,st.st_size,0))
            else:checksum=sha(path)
            result.update(kind='file',size=st.st_size,nlink=st.st_nlink,sha256=checksum)
        return result

    @staticmethod
    def clean(row):return {k:v for k,v in row.items() if k not in {'data_source','hardlink_to'}}

    def original_data(self,name):
        row=self.rows[name]
        return self.payloads[row.get('hardlink_to',name)]

    def desired_xattrs(self,name):
        if name in self.sidecars:name=name.removesuffix('.apk-new').removesuffix('.apk-old')
        if self.rows[name]['kind']=='absent':return self.scope['new_file_xattrs'][name]
        return self.rows[name]['xattrs']

    def possibilities(self,name):
        before=self.clean(self.rows[name]);choices=[before]
        source=name
        if name in self.sidecars:source=name.removesuffix('.apk-new').removesuffix('.apk-old')
        if source in self.candidates:
            expected=dict(self.candidates[source]);expected.pop('apk_checksum',None);expected.pop('hardlink_to',None)
            expected['xattrs']=self.desired_xattrs(name)
            if expected['kind']=='symlink':expected.pop('nlink',None)
            choices.append(expected)
        choices.append(dict(kind='absent'))
        return choices

    def transaction_row(self,name,actual):
        before=self.clean(self.rows[name])
        if name in self.directories:
            assert actual['kind']=='directory',('Directory replaced',name)
            acl=self.scope.get('directory_candidate_acl',{}).get(name,{k:before[k] for k in ['mode','uid','gid']})
            assert tuple(actual[k] for k in ['mode','uid','gid']) in [tuple(before[k] for k in ['mode','uid','gid']),tuple(acl[k] for k in ['mode','uid','gid'])],('Unknown directory ACL',name)
            assert actual['xattrs']==before['xattrs'],('Directory policy changed',name)
            return
        assert name in self.files
        if name in self.state_files:
            assert actual['kind']=='file' and actual['nlink']==1,('Transaction state type changed',name)
            assert all(actual[k]==before[k] for k in ['mode','uid','gid']),('Transaction state ownership changed',name)
            assert {k:v for k,v in actual['xattrs'].items() if k!='security.selinux'}=={k:v for k,v in before['xattrs'].items() if k!='security.selinux'},('Transaction state attributes changed',name)
            if name==WORLD:assert actual['sha256']==before['sha256'],'World selection changed'
            return
        # Accept only captured or signed payload bodies before any recovery write.
        for expected in self.possibilities(name):
            keys={'kind'} if expected['kind']=='absent' else {'kind','mode','uid','gid','target'} if expected['kind']=='symlink' else {'kind','mode','uid','gid','size','sha256'}
            if all(actual.get(k)==expected.get(k) for k in keys):
                if actual['kind']!='absent':
                    assert {k:v for k,v in actual['xattrs'].items() if k!='security.selinux'}=={k:v for k,v in expected['xattrs'].items() if k!='security.selinux'},('Unowned extended attribute',name)
                return
        raise AssertionError(('Unrecognised owned payload state; preserve for inspection',name))

    def verify(self,*,transaction=False,executor_may_contain_owned_scripts=False):
        assert self.lock_fd is not None
        changes=[];groups={};mutable_inodes={}
        for name,recorded in self.rows.items():
            wanted=self.clean(recorded);actual=self.row(name)
            if transaction and name in self.files|self.directories:self.transaction_row(name,actual)
            else:
                assert actual==wanted,('Unowned state changed',name)
                if actual['kind']=='file':
                    st=self.target(name).lstat();leader=recorded.get('hardlink_to',name);identity=st.st_dev,st.st_ino
                    assert leader not in groups or groups[leader]==identity,('Protected hardlink group changed',name)
                    groups[leader]=identity
            if actual!=wanted:changes.append(name)
            if transaction and name in self.files and actual['kind']=='file':
                st=self.target(name).lstat();mutable_inodes.setdefault((st.st_dev,st.st_ino),[]).append((name,st.st_nlink))
        for members in mutable_inodes.values():
            assert all(count==len(members) for name,count in members),'Owned inode has an out-of-scope hardlink'
        for name,children in self.manifest['directory_membership'].items():
            if name==EXECUTOR and executor_may_contain_owned_scripts:continue
            actual={p.name for p in self.target(name).iterdir()};expected=set(children)
            allowed=self.allowed_members.get(name,set()) if transaction else set()
            assert actual-allowed==expected-allowed,('Unowned directory membership changed',name)
        self.verify_retained_ownership()
        self.locks();return changes

    def metadata(self,name,*,xattrs_only=False):
        assert name in self.files|self.directories and name!=LOCK
        path=self.target(name);row=self.rows[name]
        if xattrs_only:
            desired=self.desired_xattrs(name)
        else:
            assert row['kind']!='absent'
            desired=row['xattrs'];os.chown(path,row['uid'],row['gid'],follow_symlinks=False)
            if row['kind']!='symlink':path.chmod(row['mode'])
        actual=self.attributes(path)
        for key in actual.keys()-desired.keys():os.removexattr(path,key,follow_symlinks=False)
        for key,value in desired.items():
            if actual.get(key)!=value:os.setxattr(path,key,bytes.fromhex(value),follow_symlinks=False)
        if not xattrs_only:os.utime(path,ns=(row['mtime_ns'],row['mtime_ns']),follow_symlinks=False)

    def normalise_labels(self):
        # Caller has verified all protected state before the first label write.
        assert self.lock_fd is not None
        for name in sorted(self.files):
            if self.row(name)['kind']!='absent':self.metadata(name,xattrs_only=True)
        self.locks()

    def restore(self,*,hooks_terminal):
        assert hooks_terminal and self.lock_fd is not None
        self.verify(transaction=True)
        ordered=sorted(self.files,key=lambda n:(len(Path(n).parts),n))
        for name in reversed(ordered):
            if self.rows[name]['kind']=='absent':
                path=self.target(name)
                if os.path.lexists(path):path.unlink()
        for name in ordered:
            row=self.rows[name];path=self.target(name)
            if row['kind']=='absent' or 'hardlink_to' in row:continue
            if row['kind']=='symlink':
                if os.path.lexists(path):path.unlink()
                path.symlink_to(row['target'])
            else:atomic(path,self.payloads[name],row['mode'])
        for name in ordered:
            row=self.rows[name]
            if 'hardlink_to' in row:
                path=self.target(name)
                if os.path.lexists(path):path.unlink()
                os.link(self.target(row['hardlink_to']),path,follow_symlinks=False)
        for name in ordered:
            row=self.rows[name]
            if row['kind']=='absent':continue
            self.metadata(name)
            if row['kind']=='file' and 'hardlink_to' not in row:
                descriptor=os.open(self.target(name),os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
                try:os.fsync(descriptor)
                finally:os.close(descriptor)
        for name in sorted(self.directories,key=lambda n:len(Path(n).parts),reverse=True):
            self.metadata(name)
            descriptor=os.open(self.target(name),os.O_RDONLY|os.O_DIRECTORY|os.O_CLOEXEC|os.O_NOFOLLOW)
            try:os.fsync(descriptor)
            finally:os.close(descriptor)
        self.locks()

    def matches(self,name,expected):
        actual=self.row(name)
        wanted={k:v for k,v in expected.items() if k not in {'apk_checksum','hardlink_to'}}
        if wanted['kind']=='absent':return actual==wanted
        wanted['xattrs']=self.desired_xattrs(name)
        if wanted['kind']=='symlink':
            # APK's fsys_file_extract deliberately preserves archive timestamps
            # only for non-symlinks. Require creation during our owned upgrade.
            if self.install_window is None:return False
            start,end=self.install_window
            if not start<=actual.get('mtime_ns',-1)<=end:return False
            actual.pop('mtime_ns',None);wanted.pop('mtime_ns',None)
        return actual==wanted

    def verify_candidate(self):
        changes=self.verify(transaction=True)
        if any(row['kind']=='symlink' for row in self.candidates.values()):
            assert self.install_window is not None,'Missing owned APK timestamp window'
            assert len(self.install_window)==2 and all(type(n) is int for n in self.install_window)
            assert self.install_window[0]<=self.install_window[1],'Invalid owned APK timestamp window'
        for name in self.state_files:
            assert self.row(name)['xattrs']==self.desired_xattrs(name),('Transaction state policy label differs',name)
        unchanged=set(self.scope['config_upstream_unchanged'])
        for name,expected in self.candidates.items():
            if expected['kind']=='directory':continue
            if name in self.configs:
                original=self.row(name)==self.clean(self.rows[name])
                installed=self.matches(name,expected)
                assert original or installed,('Unexpected protected configuration',name)
                new=name+'.apk-new';old=name+'.apk-old'
                assert self.row(old)=={'kind':'absent'},('Unexpected apk-old configuration',name)
                if self.row(new)['kind']!='absent':
                    assert original and self.matches(new,expected),('Unverified apk-new configuration',name)
                else:
                    body_keys=['kind','target'] if expected['kind']=='symlink' else ['kind','size','sha256']
                    same_body=all(self.row(name).get(k)==expected.get(k) for k in body_keys)
                    assert installed or name in unchanged or same_body,('Missing changed upstream configuration',name)
            else:assert self.matches(name,expected),('Candidate payload differs from signed archive',name)
            if expected['kind']=='file' and 'hardlink_to' in expected:
                one=self.target(name).lstat();other=self.target(expected['hardlink_to']).lstat()
                assert (one.st_dev,one.st_ino)==(other.st_dev,other.st_ino),('Candidate hardlink group differs',name)
        expected_names=set(self.candidates)|self.state_files|self.sidecars
        for name in self.files-expected_names:assert self.row(name)=={'kind':'absent'},('Obsolete payload remains',name)
        return changes


def load_snapshot(root,scope_path,*,allow_live=False):
    assert sha(scope_path)==SCOPE_SHA and sha(BACKUP/'manifest.private.json')==MANIFEST_SHA
    assert sha(BACKUP/'files.private.tar.gz')==ARCHIVE_SHA
    scope=json.loads(Path(scope_path).read_text());manifest=json.loads((BACKUP/'manifest.private.json').read_text())
    assert scope['format']=='fx0-stable-userspace-scope-v3'
    assert scope['symlink_mtime_policy']=='creation-within-owned-upgrade-command'
    assert scope['baseline_manifest_sha256']==MANIFEST_SHA and scope['baseline_archive_sha256']==ARCHIVE_SHA
    assert manifest['boot_id']==BOOT and manifest['kernel']==RELEASE and manifest['private_key_files_excluded']
    assert len(manifest['paths'])==7002 and len(manifest['directory_membership'])==701
    assert len(scope['mutable_files'])==2708 and len(scope['mutable_directories'])==133
    wanted={n for n in scope['mutable_files'] if manifest['paths'][n]['kind']=='file' and 'hardlink_to' not in manifest['paths'][n]}
    payloads={}
    with tarfile.open(BACKUP/'files.private.tar.gz','r|gz') as archive:
        for member in archive:
            name='/'+member.name
            if name not in wanted:continue
            assert name not in payloads and member.isfile() and member.size==manifest['paths'][name]['size']
            payloads[name]=archive.extractfile(member).read()
    return Snapshot(root,manifest,scope,payloads,allow_live=allow_live)


class StableUpdate:
    def __init__(self,plan,work,*,fixture_failure=None):
        self.plan=plan;self.work=Path(work).resolve(strict=True);self.root=Path(plan['root']).resolve(strict=True)
        self.live=self.root==Path('/')
        assert plan['format']=='fx0-stable-userspace-transaction-v1'
        assert plan['unit'].startswith('fx0-stable-userspace-') and plan['unit'].endswith('.service')
        assert plan['status_name']==Path(plan['status_name']).name and plan['status_name'].endswith('.json')
        assert sha(Path(__file__))==plan['controller_sha256']
        assert fixture_failure in {None,'hook-exec-EIO','after-commit'}
        assert not self.live or fixture_failure is None,'Failure injection is private-fixture only'
        if self.live:
            assert self.work==LIVE_WORK and plan['inside']==str(self.work)
            assert plan['live_update_approved'] and plan['qualified_controller_sha256']==plan['controller_sha256']
        else:
            assert self.root==FIXTURE_ROOT and plan['inside']=='/.fixture-stable-controller'
        self.status=self.work/plan['status_name'];self.inside=plan['inside'];self.fixture_failure=fixture_failure
        self.snapshot=load_snapshot(self.root,self.work/'scope.json',allow_live=self.live)
        self.scope=self.snapshot.scope
        self.original_db=database(self.snapshot.payloads[DB]);assert len(self.original_db)==775
        self.old=self.scope['old_identities']
        self.new={n:{k:r[k] for k in ['version','checksum']} for n,r in self.scope['new_identities'].items()}
        assert len(self.old)==len(self.new)==30 and set(self.old)==set(self.new)
        assert all(self.original_db[n]==r for n,r in self.old.items())
        assert not {'treescan','linux-postmarketos-qcom-msm8226'}&self.old.keys()
        self.children=[];self.stopping=False;self.recovering=False;self.number=0
        self.state=dict(stage='created',live_OS_transaction=self.live,automatic_reboot=False,
                        started_UTC=datetime.datetime.now(datetime.timezone.utc).isoformat(),history=[])
        self.prefix=[] if self.live else ['/usr/sbin/chroot',str(self.root)]
        self.apk=self.prefix+['/usr/sbin/apk','--no-interactive','--arch','armv7','--no-network',
            '--keys-dir','/etc/apk/keys','--repositories-file',self.inside+'/repositories','--cache-dir',self.inside+'/cache']

    def record(self,stage,**fields):
        self.state.update(stage=stage,**fields)
        self.state['history'].append(dict(stage=stage,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        atomic(self.status,(json.dumps(self.state,indent=2)+'\n').encode())

    def hooks_terminal(self):
        if any(child.poll() is None for child in self.children):return False
        line=Path('/proc/self/cgroup').read_text().strip();assert line.startswith('0::') and '\n' not in line
        group=line.removeprefix('0::');assert group.endswith('/'+self.plan['unit']) or group=='/'
        parent=Path('/sys/fs/cgroup')/group.lstrip('/')
        pids={int(pid) for path in parent.rglob('cgroup.procs') for pid in path.read_text().split()}
        return pids=={os.getpid()}

    def command(self,phase,args):
        assert '--no-scripts' not in args and '--allow-untrusted' not in args
        assert self.snapshot.lock_fd is None or phase=='refresh-inventory'
        if self.stopping and not self.recovering:raise RuntimeError('Stop requested before next forward command')
        self.number+=1
        log=self.work/(self.status.stem+'-%02d-%s.log'%(self.number,phase))
        with log.open('xb') as stream:
            started_ns=time.time_ns()
            child=subprocess.Popen(args,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True,cwd=self.root)
            self.children.append(child);code=child.wait()
            while not self.hooks_terminal():
                self.record(phase+'-waiting-for-owned-descendants',package_parent_returncode=code);time.sleep(2)
            finished_ns=time.time_ns()
        if phase=='upgrade':
            assert finished_ns>=started_ns,'Wall clock moved backwards during the owned APK upgrade'
            self.snapshot.install_window=(started_ns,finished_ns)
            self.state['upgrade_window_ns']=[started_ns,finished_ns]
        self.record(phase+'-terminal',package_parent_returncode=code,all_owned_process_groups_terminal=True)
        assert code==0,('Command failed',phase,code)
        if self.stopping and not self.recovering:raise RuntimeError('Stop requested after owned command reaped')
        return log.read_text()

    def identity(self):
        assert os.geteuid()==0
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
        assert os.uname().release==RELEASE and Path('/proc/sys/kernel/tainted').read_text().strip()=='0'
        assert Path('/sys/module/module/parameters/sig_enforce').read_text().strip()=='Y'
        if self.live:assert sha('/dev/mmcblk0p15')==self.snapshot.manifest['raw_boot_sha256']

    def package_state(self,*,candidate=None):
        current=database(self.snapshot.target(DB).read_bytes())
        assert {n:r for n,r in current.items() if n not in self.old}=={n:r for n,r in self.original_db.items() if n not in self.old},'Unselected package identity changed'
        if candidate is not None:
            assert set(current)==set(self.original_db)
            assert {n:current[n] for n in self.old}==(self.new if candidate else self.old)
        else:
            assert set(current)<=set(self.original_db)
            assert all(current.get(n) in [None,self.old[n],self.new[n]] for n in self.old)
        return current

    def world_guard(self):
        assert self.snapshot.target(WORLD).read_bytes()==self.snapshot.payloads[WORLD],'World selection changed'

    def cache_guard(self):
        directory=self.snapshot.target(self.inside+'/cache');assert directory.is_dir() and not directory.is_symlink()
        allowed={}
        for row in self.scope['packages']:
            suffix=base64.b64decode(row['index_control_checksum'][2:],validate=True).hex()[:8]
            allowed[row['package']+'-'+row['version']+'.'+suffix+'.apk']=row['sha256']
        for path in directory.iterdir():
            st=path.lstat();assert stat.S_ISREG(st.st_mode) and st.st_nlink==1 and (st.st_uid,st.st_gid)==(0,0)
            expected=allowed.get(path.name)
            if expected is None:
                assert re.fullmatch(r'APKINDEX\.[0-9a-f]{8}\.tar\.gz',path.name),'Unknown cache member'
                assert sha(path) in self.scope['index_sha256'],'Unknown cached index'
            else:assert sha(path)==expected,'Cached package differs from authenticated input'

    def policy_guard(self):
        directory=self.snapshot.target('/etc/apk/protected_paths.d')
        assert directory.is_dir() and not directory.is_symlink()
        actual={}
        for path in directory.iterdir():
            assert path.name.endswith('.list') and path.is_file() and not path.is_symlink()
            actual[path.name]=sha(path)
        assert actual==self.scope['expected_protected_policy'],'APK protected-path policy changed'

    def input_guard(self):
        inside=self.snapshot.target(self.inside);assert inside.is_dir() and not inside.is_symlink()
        expected_repositories=''.join(self.inside+'/repos/'+str(i)+'\n' for i in range(4))
        assert (inside/'repositories').read_text()==expected_repositories
        for index,expected in enumerate(self.scope['index_sha256']):
            path=self.snapshot.target(self.inside+'/repos/'+str(index)+'/armv7/APKINDEX.tar.gz')
            assert not path.is_symlink() and sha(path)==expected
        paths=[]
        for row in self.scope['packages']:
            relative='/repos/'+str(row['repository'])+'/armv7/'+row['package']+'-'+row['version']+'.apk'
            path=self.snapshot.target(self.inside+relative)
            assert not path.is_symlink() and sha(path)==row['sha256']
            paths.append(self.inside+relative)
        self.cache_guard();return paths

    def preflight(self):
        assert not self.status.exists()
        assert self.work.stat().st_uid==0 and stat.S_IMODE(self.work.stat().st_mode)==0o700
        self.identity();assert self.hooks_terminal();self.policy_guard()
        if self.live:
            assert subprocess.check_output(['systemctl','is-system-running'],text=True).strip()=='running'
            assert subprocess.check_output(['systemctl','is-active','tinydm','upower','iio-sensor-proxy'],text=True).splitlines()==['active']*3
            assert 'NoNewPrivs:\t1' in Path('/proc/self/status').read_text()
            for path in ['/boot','/usr/lib/modules','/usr/share/kernel','/usr/bin/treescan']:
                assert os.statvfs(path).f_flag&os.ST_RDONLY,('Protected path must be read-only',path)
            caps=next(line.split()[1] for line in Path('/proc/self/status').read_text().splitlines() if line.startswith('CapEff:'))
            assert not int(caps,16)&(1<<16),'Module-loading capability must be absent'
        paths=self.input_guard()
        with self.snapshot.locked():
            self.snapshot.verify();self.package_state(candidate=False);self.world_guard()
        assert self.command('version',self.prefix+['/usr/sbin/apk','--version']).strip()=='apk-tools 3.0.8-r0, compiled for armv7.'
        self.command('verify-all-candidates',self.prefix+['/usr/sbin/apk','--no-network','--keys-dir','/etc/apk/keys','verify',*paths])
        self.command('load-local-indexes',self.apk+['update'])
        text=self.command('simulate',self.apk+['upgrade','--simulate'])
        actions=[]
        for line in text.splitlines():
            if not line.startswith('('):continue
            match=re.fullmatch(r'\(\s*\d+/\d+\) Upgrading (\S+) \((\S+) -> (\S+)\)',line)
            assert match,('Unexpected simulated action',line)
            name,old,new=match.groups();assert name in self.old and old==self.old[name]['version'] and new==self.new[name]['version']
            actions.append(name)
        assert len(actions)==30 and set(actions)==set(self.old)
        with self.snapshot.locked():self.snapshot.verify();self.package_state(candidate=False);self.world_guard()
        self.record('preflight-verified',baseline_paths=7002,memberships=701,simulated_actions=actions,
                    candidate_signatures_verified=30,mutable_files=2708,mutable_directory_metadata=133)

    def inventory(self):
        expected={}
        for stem in ['system','user']:
            for parent,dirs,files in os.walk(self.snapshot.target('/usr/lib/systemd/'+stem),followlinks=False):
                for leaf in dirs+files:
                    path=Path(parent)/leaf;name='/'+str(path.relative_to(self.root))
                    kind='symlink' if path.is_symlink() else 'dir' if path.is_dir() else 'file'
                    expected[name]=kind,path.stat().st_mtime_ns//10**9
        observed={}
        for line in self.snapshot.target(INVENTORY).read_text().splitlines():
            name,kind,timestamp=line.rsplit(' ',2)
            assert name not in observed and kind.startswith('type=') and timestamp.startswith('mtime=')
            observed[name]=kind[5:],int(timestamp[6:])
        assert len(expected)==545 and observed==expected,'Unit inventory differs from independent metadata'
        return len(expected)

    def cleanup_executor(self):
        assert self.hooks_terminal() and self.snapshot.lock_fd is not None
        directory=self.snapshot.target(EXECUTOR);entries=sorted(directory.iterdir());checked=[]
        owned=self.scope['known_executor_scripts'];owner=self.snapshot.rows[EXECUTOR]
        for path in entries:
            assert path.name in owned,'Unknown executor; preserve every file'
            st=path.lstat();wanted=owned[path.name]
            assert stat.S_ISREG(st.st_mode) and st.st_nlink==1
            assert (st.st_uid,st.st_gid,st.st_size)==(owner['uid'],owner['gid'],wanted['size'])
            descriptor=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
            try:
                held=os.fstat(descriptor)
                assert (held.st_dev,held.st_ino)==(st.st_dev,st.st_ino)
                with os.fdopen(os.dup(descriptor),'rb') as stream:
                    assert hashlib.file_digest(stream,'sha256').hexdigest()==wanted['sha256']
            finally:os.close(descriptor)
            checked.append((path,st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns))
        for path,device,inode,size,mtime in checked:
            st=path.lstat();assert (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==(device,inode,size,mtime)
            path.unlink()
        assert not list(directory.iterdir())
        return [path.name for path,*_ in checked]

    def install(self):
        self.record('installing',native_installation_started=True)
        args=self.apk+['--verbose','upgrade']
        if not self.live:
            trace=self.work/(self.status.stem+'.exec.trace')
            prefix=['/usr/bin/strace','-f','-e','trace=execve,execveat','-s','4096']
            if self.fixture_failure=='hook-exec-EIO':prefix+=['-P','lib/apk/exec/openssh-server-10.3_p1-r2.post-upgrade','--inject=execve:error=EIO']
            args=prefix+['-o',str(trace),*args]
        text=self.command('upgrade',args)
        for script in self.scope['known_executor_scripts']:
            assert 'Executing '+script in text,('Expected normal hook absent',script)
        assert self.command('version-upgraded',self.prefix+['/usr/sbin/apk','--version']).strip()=='apk-tools 3.0.9-r0, compiled for armv7.'
        with self.snapshot.locked():
            self.package_state(candidate=True);self.world_guard()
            self.snapshot.verify(transaction=True,executor_may_contain_owned_scripts=True)
            removed=self.cleanup_executor();self.snapshot.normalise_labels()
            self.command('refresh-inventory',self.prefix+['/etc/apk/commit_hooks.d/postmarketos-base-systemd','pre-commit'])
            self.snapshot.metadata(INVENTORY,xattrs_only=True);self.inventory()
        self.record('installed-hooks-terminal',owned_executor_files_removed=removed)
        if self.fixture_failure=='after-commit':raise RuntimeError('Private controlled failure after actual commit and refresh')

    def verify_candidate(self):
        assert self.hooks_terminal();self.identity();self.input_guard();self.policy_guard()
        with self.snapshot.locked():
            self.package_state(candidate=True);self.world_guard()
            changes=self.snapshot.verify_candidate();count=self.inventory()
        self.record('candidate-verified',baseline_paths_guarded=7002,memberships_guarded=701,
            other_package_identities_unchanged=745,selected_candidate_identities_verified=30,world_exact=True,
            unit_entries_and_timestamps_verified=count,changed_captured_paths=changes,
            database_sha256=sha(self.snapshot.target(DB)),boot_written=False)

    def rollback(self):
        assert self.hooks_terminal(),'Never restore while owned package hooks remain'
        self.recovering=True;self.identity();self.input_guard();self.policy_guard()
        with self.snapshot.locked():
            self.package_state();self.world_guard()
            self.snapshot.verify(transaction=True,executor_may_contain_owned_scripts=True)
            removed=self.cleanup_executor()
            self.record('rollback-started',rollback_attempted=True,owned_executor_files_removed=removed)
            self.snapshot.restore(hooks_terminal=self.hooks_terminal())
        self.record('rollback-files-restored',restored_scope_files=2708,restored_directory_metadata=133,
            APK_lock_inode_never_replaced=True,no_partial_old_APK_downgrade=True)

    def verify_rollback(self):
        assert self.hooks_terminal();self.identity();self.input_guard();self.policy_guard()
        with self.snapshot.locked():
            self.snapshot.verify();self.package_state(candidate=False);self.world_guard();self.inventory()
        assert self.command('version-restored',self.prefix+['/usr/sbin/apk','--version']).strip()=='apk-tools 3.0.8-r0, compiled for armv7.'
        self.record('rollback-verified',recovered_paths=7002,recovered_memberships=701,
            original_775_package_identities_recovered=True,original_world_exact=True,hardlink_aliases=254,
            SELinux_label_paths=1480,unit_entries_and_timestamps_verified=545,boot_written=False)


def transaction_module(plan):
    here=Path(__file__).resolve().parent;path=here/'update_transaction.py'
    if not path.exists():path=here.parent/'kernel-maintenance/update_transaction.py'
    assert sha(path)==plan['transaction_helper_sha256']
    spec=importlib.util.spec_from_file_location('stable_update_protocol',path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result


def execute(plan,work,*,fixture_failure=None,check=False):
    protocol=transaction_module(plan);work=Path(work).resolve(strict=True)
    assert work.stat().st_uid==0 and stat.S_IMODE(work.stat().st_mode)==0o700
    descriptor=os.open(work/'transaction.lock',os.O_RDWR|os.O_CREAT|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ops=StableUpdate(plan,work,fixture_failure=fixture_failure);previous={}
        for signum in [signal.SIGTERM,signal.SIGINT]:previous[signum]=signal.signal(signum,lambda number,frame:setattr(ops,'stopping',True))
        try:
            if check:ops.preflight()
            else:protocol.execute(ops)
        finally:
            for signum,handler in previous.items():signal.signal(signum,handler)
        return ops
    finally:os.close(descriptor)


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('plan',type=Path)
    modes=parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--check',action='store_true');modes.add_argument('--install-live',action='store_true');modes.add_argument('--fixture',action='store_true')
    parser.add_argument('--fixture-failure',choices=['hook-exec-EIO','after-commit'])
    args=parser.parse_args()
    assert args.plan.stat().st_uid==0 and stat.S_IMODE(args.plan.stat().st_mode)==0o600
    plan=json.loads(args.plan.read_text());live=Path(plan['root']).resolve(strict=True)==Path('/')
    assert not live or (args.install_live or args.check)
    assert not args.install_live or live
    assert not args.fixture_failure or args.fixture
    execute(plan,args.plan.resolve().parent,fixture_failure=args.fixture_failure,check=args.check)


if __name__=='__main__':main()
