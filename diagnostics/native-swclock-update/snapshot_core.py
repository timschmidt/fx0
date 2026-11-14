# SPDX-License-Identifier: GPL-2.0-only
"""Unchanged snapshot primitive extracted from the qualified stable controller.

Source diagnostics/stable-update/stable_transaction.py, pinned in provenance.
The original thirty-package transaction implementation remains untouched.
"""
import contextlib,fcntl,hashlib,importlib.util,json,os,stat,tempfile
from pathlib import Path
DB='/usr/lib/apk/db/installed'
LOCK='/usr/lib/apk/db/lock'
WORLD='/etc/apk/world'
INVENTORY='/var/lib/systemd-apk/installed.units'
EXECUTOR='/usr/lib/apk/exec'


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
