# SPDX-License-Identifier: GPL-2.0-only
"""Pinned two-package software-clock update with captured scoped recovery.

This separate controller retains the qualified snapshot and transaction protocol.
The earlier thirty-package and APK-pair controllers remain unchanged.
"""
import argparse,resource,base64,ctypes,datetime,fcntl,hashlib,importlib.util,json,os,re,signal,stat,subprocess,tarfile,time
from pathlib import Path
from snapshot_core import Snapshot,atomic,database,sha,DB,LOCK,WORLD,INVENTORY,EXECUTOR
from apk_actions import equivalent

BOOT='e134d38d-f8b1-4115-8bff-8e91f69d1d01'
RELEASE='6.18.63-fx0-vibrator-alpine'
SIDECARS=set()
STATE={WORLD,DB,'/usr/lib/apk/db/scripts.tar.gz','/usr/lib/apk/db/triggers',INVENTORY}
SIDEFILE=INVENTORY+'.new'
TRIGGER_OWNERS={'busybox','postmarketos-base-systemd','systemd'}
LIVE_WORK=Path('/var/lib/fx0-rollback/swclock-live-01')
FIXTURE=Path('/var/lib/fx0-rollback/edge-native-rehearsal-01/baseline23/root')
OLD={'swclock-offset': {'checksum': 'Q1Qa8gLImaxi4j7I1ZSmOrq8VLw6Q=', 'version': '0.3.0-r0'}, 'swclock-offset-systemd': {'checksum': 'Q1xXYN6XlCLWTdmi8uuIu127tOZZE=', 'version': '0.3.0-r0'}}
NEW={'swclock-offset': {'checksum': 'Q1ooP9zcGn5rN/t+y/r1Qeu+r4hPA=', 'version': '0.3.0-r1'}, 'swclock-offset-systemd': {'checksum': 'Q1Op62WkD5oncXXYP0Eh4od57wj8Y=', 'version': '0.3.0-r1'}}
INDEXES=['32c059ddb7b3dbd77c6e10a1a99c78aa507fd799e0e1e58f28bf02251427ddfe']
MUTABLE={'/usr/lib/apk/db/scripts.tar.gz', '/usr/lib/apk/db/triggers', '/var/lib/systemd-apk/installed.units.new', '/usr/lib/systemd/system/swclock-offset-shutdown.service', '/usr/lib/systemd/system/swclock-offset-boot.service', '/usr/lib/apk/db/installed', '/var/lib/systemd-apk/installed.units', '/usr/bin/swclock-offset-boot', '/etc/apk/world', '/usr/lib/systemd/system/swclock-offset.target', '/usr/bin/swclock-offset-shutdown'}
DIRECTORIES={'/usr/lib/apk/db', '/usr/lib/apk/exec', '/etc/apk', '/usr', '/usr/lib/systemd/system', '/var/lib/systemd-apk', '/usr/lib', '/usr/bin', '/usr/lib/systemd'}
CANDIDATE_SHA='1d0cbfd58a8fb651624c55686cd6bbb74541404311659c65b97fb8fad3ff36a7'
GUARD_NAMES_SHA='6c91bb405d20f0c5aff3daefc932066e724ef9405c6a315c54594bf50266d1a3'
KNOWN_EXECUTORS={'busybox-1.37.0-r31.trigger': {'sha256': 'c7840b111dd82669de2074ea3c7e345c063928db2bbff650a81289777b3ff98f', 'size': 576}, 'postmarketos-base-systemd-77-r0.trigger': {'sha256': 'f877c85a409566ff36cea4e1d2d04cb6640140840377f2582b30a5c199e5b851', 'size': 44}, 'systemd-261-r0.trigger': {'sha256': 'd35f00aae36895ccd02c24dc8b2272384af7ba7ac8d4f6f66adfa8af312807cd', 'size': 2766}}

def validate_scope(scope):
    assert scope['format']=='fx0-swclock-two-scope-v1'
    assert set(scope['mutable_files'])==MUTABLE and set(scope['mutable_directories'])==DIRECTORIES
    assert len(MUTABLE)==11 and len(DIRECTORIES)==9
    assert hashlib.sha256(json.dumps(scope['candidate_payloads'],sort_keys=True).encode()).hexdigest()==CANDIDATE_SHA
    assert set(scope['mutable_state_files'])==STATE and not scope['config_paths'] and not scope['config_sidecars'] and not scope['retained_owner_payloads']
    assert scope['known_executor_scripts']==KNOWN_EXECUTORS and scope['old_identities']==OLD and scope['new_identities']==NEW
    assert len(scope['packages'])==2 and {r['package']:{k:r[k] for k in ['version','checksum']} for r in scope['packages']}==NEW
    assert all(r['repository']==0 for r in scope['packages']) and scope['index_sha256']==INDEXES and len(scope['public_keys'])==22
    assert scope['guard_paths_SHA256']==GUARD_NAMES_SHA and set(scope['new_file_xattrs'])=={SIDEFILE}
    return scope

def load_baseline(work,plan):
    assert sha(work/'scope.json')==plan['scope_sha256']
    scope=validate_scope(json.loads((work/'scope.json').read_text()))
    assert sha(work/'baseline-manifest.private.json')==plan['baseline_manifest_sha256']==scope['baseline_manifest_sha256']
    assert sha(work/'baseline-files.private.tar.gz')==plan['baseline_archive_sha256']==scope['baseline_archive_sha256']
    manifest=json.loads((work/'baseline-manifest.private.json').read_text())
    assert manifest['boot_id']==BOOT and manifest['kernel']==RELEASE and manifest['private_key_files_excluded']
    assert len(manifest['paths'])==1929 and len(manifest['directory_membership'])==64
    assert hashlib.sha256(json.dumps(sorted(manifest['paths'])).encode()).hexdigest()==GUARD_NAMES_SHA
    wanted={n for n in MUTABLE if manifest['paths'][n]['kind']=='file'};assert len(wanted)==10
    assert manifest['paths'][SIDEFILE]['kind']=='absent'
    payloads={}
    with tarfile.open(work/'baseline-files.private.tar.gz','r|gz') as archive:
        for member in archive:
            name='/'+member.name;assert name in wanted and member.isfile() and name not in payloads
            row=manifest['paths'][name];assert row['nlink']==1 and member.size==row['size']
            body=archive.extractfile(member).read();assert hashlib.sha256(body).hexdigest()==row['sha256'];payloads[name]=body
    assert set(payloads)==wanted
    assert hashlib.sha256(payloads[DB]).hexdigest()=='b106cfa76000084e240f6b1e40496a06b52f5d1820593364f8b13bfb54c9665f'
    assert hashlib.sha256(payloads[WORLD]).hexdigest()=='8dcb9d843a2805ae9ab8fe925fc34f9b95c7beef798c5019617d8720cb52c64a'
    return scope,manifest,payloads

class ClockSnapshot(Snapshot):
    def transaction_row(self,name,actual):
        if name==SIDEFILE:
            if actual['kind']=='absent':return
            assert actual['kind']=='file' and actual['nlink']==1 and actual['uid']==actual['gid']==0 and actual['mode']==0o644
            assert actual['size']<=1048576 and not (actual['xattrs'].keys()-{'security.selinux'}),'Unknown inventory sidecar metadata'
            return
        return super().transaction_row(name,actual)

def drop_package_privileges():
    """Permanently remove setup/label authority in the package child only."""
    libc=ctypes.CDLL(None,use_errno=True)
    class Header(ctypes.Structure):_fields_=[('version',ctypes.c_uint32),('pid',ctypes.c_int32)]
    class Data(ctypes.Structure):_fields_=[('effective',ctypes.c_uint32),('permitted',ctypes.c_uint32),('inheritable',ctypes.c_uint32)]
    header=Header(0x20080522,0);caps=(Data*2)()
    assert libc.capget(ctypes.byref(header),caps)==0,ctypes.get_errno()
    for capability in [21,8,33]:
        assert libc.prctl(24,capability,0,0,0)==0,ctypes.get_errno()
        word,bit=divmod(capability,32)
        for field in ['effective','permitted','inheritable']:setattr(caps[word],field,getattr(caps[word],field)&~(1<<bit))
    assert libc.capset(ctypes.byref(header),caps)==0,ctypes.get_errno()
    status=dict(line.split(':',1) for line in Path('/proc/self/status').read_text().splitlines() if ':' in line)
    blocked=sum(1<<n for n in [8,16,17,19,21,22,33])
    for field in ['CapBnd','CapEff','CapPrm','CapInh']:assert not int(status[field].strip(),16)&blocked
    assert int(status.get('CapAmb','0').strip(),16)==0

def package_records(data):
    result={}
    for paragraph in data.decode().split('\n\n'):
        lines=tuple(paragraph.splitlines())
        if not lines:continue
        names=[l[2:] for l in lines if l.startswith('P:')]
        assert len(names)==1 and names[0] not in result
        result[names[0]]=lines
    return result

def record_flags(lines):
    flags=[l[2:] for l in lines if l.startswith('f:')]
    assert len(flags)<=1
    return set(flags[0]) if flags else set()

def known_trigger_record(before,actual):
    # Recovery permits only the source-defined broken-script flag on the
    # unchanged BusyBox package whose exact trigger is authorized for cleanup.
    strip=lambda rows:tuple(l for l in rows if not l.startswith('f:'))
    return strip(before)==strip(actual) and record_flags(actual)<=record_flags(before)|{'s'}

class ClockUpdate:
    def __init__(self,plan,work,*,failure=None):
        self.work=Path(work).resolve(strict=True);self.root=Path(plan['root']).resolve(strict=True);self.live=self.root==Path('/')
        assert plan['format']=='fx0-swclock-transaction-v1' and sha(Path(__file__))==plan['controller_sha256']
        assert plan['unit'].startswith('fx0-swclock-') and plan['unit'].endswith('.service')
        assert failure in {None,'before-commit','after-commit','hook-exec-EIO'} and (not self.live or failure is None)
        assert os.getpid()==1,'Controller requires the verified private PID namespace'
        if self.live:assert self.work==LIVE_WORK and plan['inside']==str(self.work) and plan['qualified_controller_sha256']==plan['controller_sha256']
        else:assert self.root==FIXTURE and plan['inside']=='/.fx0-stable-vim'
        self.plan=plan;self.inside=plan['inside'];self.failure=failure;self.stopping=False;self.recovering=False;self.children=[];self.number=0
        self.scope,manifest,payloads=load_baseline(self.work,plan)
        assert sha(self.work/'snapshot_core.py')==plan['snapshot_core_sha256'] and sha(self.work/'apk_actions.py')==plan['action_parser_sha256']
        self.snapshot=ClockSnapshot(self.root,manifest,self.scope,payloads,allow_live=self.live)
        self.before_records=package_records(payloads[DB])
        assert all(record_flags(r)<=set('S') for r in self.before_records.values())
        self.before=database(payloads[DB]);assert len(self.before)==775 and {n:self.before[n] for n in OLD}==OLD
        self.prefix=[] if self.live else ['/usr/sbin/chroot',str(self.root)]
        self.apk=self.prefix+['/usr/sbin/apk','--arch','armv7','--no-network','--no-interactive','--keys-dir','/etc/apk/keys','--repositories-file',self.inside+'/repositories','--cache-dir',self.inside+'/cache']
        self.status=self.work/plan['status_name'];assert Path(plan['status_name']).name==plan['status_name'] and not self.status.exists()
        self.state=dict(stage='created',live_OS_transaction=self.live,boot_written=False,reboot=False,audio_testing=False,history=[])

    def record(self,stage,**fields):
        self.state.update(stage=stage,**fields);self.state['history'].append(dict(stage=stage,UTC=datetime.datetime.now(datetime.timezone.utc).isoformat()))
        atomic(self.status,(json.dumps(self.state,indent=2)+'\n').encode())

    def hooks_terminal(self):
        for child in self.children:child.poll()
        while True:
            try:pid,_=os.waitpid(-1,os.WNOHANG)
            except ChildProcessError:break
            if not pid:break
        return not ({int(p.name) for p in Path('/proc').iterdir() if p.name.isdigit()}-{1})

    def command(self,name,args):
        assert not {'--no-scripts','--allow-untrusted'}&set(args)
        assert self.snapshot.lock_fd is None,'Never run APK while holding its writer locks'
        if self.stopping and not self.recovering:raise RuntimeError('Stop requested before next command')
        if name=='upgrade' and self.failure=='hook-exec-EIO':
            trace=self.work/(self.status.stem+'.hook-exec.private.trace')
            paths=['lib/apk/exec/'+n for n in KNOWN_EXECUTORS]+['/proc/self/fd/'+str(n) for n in range(128)]
            filters=[part for path in paths for part in ['-P',path]]
            args=['/usr/bin/strace','-f','-e','trace=execve,execveat','-s','4096',*filters,'--inject=execve:error=EIO','-o',str(trace),*args]
        self.number+=1;log=self.work/(self.status.stem+'-%02d-%s.private.log'%(self.number,name));started=time.time_ns()
        def setup_child():
            drop_package_privileges()
            if name=='upgrade' and self.failure=='hook-exec-EIO':resource.setrlimit(resource.RLIMIT_NOFILE,(128,128))
        with log.open('xb') as output:
            child=subprocess.Popen(args,stdout=output,stderr=subprocess.STDOUT,start_new_session=True,env=dict(os.environ,LC_ALL='C',LD_BIND_NOW='1'),umask=0o022,preexec_fn=setup_child,cwd=self.root);self.children.append(child);rc=child.wait()
            until=time.monotonic()+300
            while not self.hooks_terminal():
                self.record(name+'-waiting-for-owned-descendants',APK_returncode=rc)
                if time.monotonic()>until:raise RuntimeError('Owned descendants remain active; preserve fixture for observation')
                time.sleep(1)
        if name=='upgrade':self.snapshot.install_window=[started,time.time_ns()]
        self.record(name+'-terminal',command_returncode=rc,all_owned_descendants_terminal=True,package_child_setup_and_label_capabilities_permanently_removed=True)
        assert rc==0,('Command failed',name,rc)
        if self.stopping and not self.recovering:raise RuntimeError('Stop requested after owned command reaped')
        return log.read_text()

    def identity(self):
        assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT and os.uname().release==RELEASE
        assert sha('/sys/kernel/notes')=='05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377'
        assert Path('/proc/sys/kernel/tainted').read_text().strip()=='0' and Path('/sys/module/module/parameters/sig_enforce').read_text().strip()=='Y'
        assert 'NoNewPrivs:\t1' in Path('/proc/self/status').read_text()
        caps=int(next(l.split()[1] for l in Path('/proc/self/status').read_text().splitlines() if l.startswith('CapEff:')),16)
        assert not caps&sum(1<<n for n in [16,17,19,22])
        if self.live:assert sha('/dev/mmcblk0p15')==self.snapshot.manifest['raw_boot_sha256']
        else:assert not Path('/dev/mmcblk0p15').exists()

    def package_state(self,candidate=None):
        data=self.snapshot.target(DB).read_bytes();actual=database(data);records=package_records(data)
        assert {n:r for n,r in actual.items() if n not in OLD}=={n:r for n,r in self.before.items() if n not in OLD}
        for name,before in self.before_records.items():
            if name in OLD:continue
            current=records[name]
            assert current==before or (candidate is None and name in TRIGGER_OWNERS and known_trigger_record(before,current)),('Unselected complete package record changed',name)
        if candidate is None:
            assert set(actual)<=set(self.before) and all(actual.get(n) in [None,OLD[n],NEW[n]] for n in OLD)
        else:
            assert set(actual)==set(self.before) and {n:actual[n] for n in OLD}==(NEW if candidate else OLD)
            if candidate:assert all(record_flags(r)<=set('S') for r in records.values()),'Broken installed package flags'
            else:assert records==self.before_records,'Complete baseline package records differ'

    def input_guard(self):
        assert self.work.stat().st_uid==0 and stat.S_IMODE(self.work.stat().st_mode)==0o700
        assert self.snapshot.target(self.inside+'/repositories').read_text()==self.inside+'/repos/0\n'
        for i,expected in enumerate(self.scope['index_sha256']):assert sha(self.snapshot.target(self.inside+'/repos/'+str(i)+'/armv7/APKINDEX.tar.gz'))==expected
        paths=[]
        for r in self.scope['packages']:
            name=self.inside+'/repos/'+str(r['repository'])+'/armv7/'+r['file'];assert sha(self.snapshot.target(name))==r['sha256'];paths.append(name)
        keys=self.snapshot.target('/etc/apk/keys');assert {p.name:sha(p) for p in keys.iterdir()}==self.scope['public_keys']
        allowed={r['package']+'-'+r['version']+'.'+base64.b64decode(r['checksum'][2:],validate=True).hex()[:8]+'.apk':r['sha256'] for r in self.scope['packages']}
        for p in self.snapshot.target(self.inside+'/cache').iterdir():
            s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_nlink==1 and (s.st_uid,s.st_gid)==(0,0)
            if p.name in allowed:assert sha(p)==allowed[p.name]
            else:assert re.fullmatch(r'APKINDEX\.[0-9a-f]{8}\.tar\.gz',p.name) and sha(p) in self.scope['index_sha256']
        return paths

    def world_guard(self):assert self.snapshot.target(WORLD).read_bytes()==self.snapshot.payloads[WORLD]

    def inventory(self):
        expected={}
        for stem in ['system','user']:
            for parent,dirs,files in os.walk(self.snapshot.target('/usr/lib/systemd/'+stem),followlinks=False):
                for leaf in dirs+files:
                    path=Path(parent)/leaf;expected['/'+str(path.relative_to(self.root))]=('symlink' if path.is_symlink() else 'dir' if path.is_dir() else 'file',path.stat().st_mtime_ns//10**9)
        found={}
        for line in self.snapshot.target(INVENTORY).read_text().splitlines():
            name,kind,mtime=line.rsplit(' ',2);assert name not in found and kind.startswith('type=') and mtime.startswith('mtime=');found[name]=(kind[5:],int(mtime[6:]))
        assert len(expected)==545 and expected==found

    def preflight(self):
        self.identity();assert self.hooks_terminal();paths=self.input_guard()
        with self.snapshot.locked():self.snapshot.verify();self.package_state(False);self.world_guard();self.inventory()
        assert self.command('version-original',self.prefix+['/usr/sbin/apk','--version']).strip()=='apk-tools 3.0.9-r1, compiled for armv7.'
        self.command('verify-candidates',self.prefix+['/usr/sbin/apk','--no-network','--keys-dir','/etc/apk/keys','verify',*paths])
        self.command('load-signed-index',self.apk+['update'])
        expected='(1/2) Upgrading swclock-offset (0.3.0-r0 -> 0.3.0-r1)\n(2/2) Upgrading swclock-offset-systemd (0.3.0-r0 -> 0.3.0-r1)'
        assert equivalent(expected,self.command('simulate-exact-two',self.apk+['upgrade','--simulate']))==2
        with self.snapshot.locked():self.snapshot.verify();self.package_state(False);self.world_guard();self.inventory()
        self.record('preflight-verified',guarded_paths=1929,mutable_scope_files=11,mutable_directory_metadata=9,exact_candidate_packages=2)

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
        if self.failure=='before-commit':raise RuntimeError('Private controlled failure before package commit')
        self.command('upgrade',self.apk+['upgrade'])
        with self.snapshot.locked():
            self.package_state(True);self.world_guard();self.snapshot.verify(transaction=True,executor_may_contain_owned_scripts=True);self.cleanup_executor();self.snapshot.normalise_labels();self.snapshot.verify_candidate();self.inventory()
        self.record('installed-and-labels-normalised',selected_package_identities=2,unselected_package_identities=773)
        if self.failure=='after-commit':raise RuntimeError('Private controlled failure after actual two-package commit')

    def runtime_probe(self,candidate):
        unit=self.snapshot.target('/usr/lib/systemd/system/swclock-offset-boot.service').read_text()
        if candidate:
            assert 'Wants=local-fs-pre.target' in unit and 'Before=systemd-fsck-root.service local-fs-pre.target' in unit and 'systemd-fsck@.service' not in unit
        else:assert 'Before=systemd-fsck-root.service systemd-fsck@.service' in unit
        assert not self.snapshot.target(SIDEFILE).exists()
        self.record('runtime-'+('candidate' if candidate else 'restored')+'-verified',clock_unit_dependency_instructions_verified=True,clock_scripts_not_executed=True)

    def verify_candidate(self):
        self.identity();assert self.hooks_terminal();self.input_guard()
        with self.snapshot.locked():self.package_state(True);self.world_guard();self.snapshot.verify_candidate();self.inventory()
        assert self.command('version-candidate',self.prefix+['/usr/sbin/apk','--version']).strip()=='apk-tools 3.0.9-r1, compiled for armv7.'
        self.runtime_probe(True)
        self.record('candidate-verified',original_world_and_22_keys=True,boot_written=False)

    def rollback(self):
        assert self.hooks_terminal();self.recovering=True;self.identity();self.input_guard()
        with self.snapshot.locked():
            self.package_state();self.world_guard();self.snapshot.verify(transaction=True,executor_may_contain_owned_scripts=True);self.cleanup_executor();self.snapshot.restore(hooks_terminal=True)
        self.record('scoped-rollback-complete',restored_scope_files=11,restored_directory_metadata=9,lock_inode_preserved=True)

    def verify_rollback(self):
        self.identity();assert self.hooks_terminal();self.input_guard()
        with self.snapshot.locked():self.snapshot.verify();self.package_state(False);self.world_guard();self.inventory()
        assert self.command('version-restored',self.prefix+['/usr/sbin/apk','--version']).strip()=='apk-tools 3.0.9-r1, compiled for armv7.'
        self.runtime_probe(False)
        self.record('rollback-verified',all_1929_guards_exact=True,all_775_original_package_identities=True,world_and_22_keys_exact=True,boot_written=False)

def execute(plan,work,*,failure=None,check=False):
    path=Path(__file__).with_name('update_transaction.py');assert sha(path)==plan['transaction_protocol_sha256']
    spec=importlib.util.spec_from_file_location('clock_update_protocol',path);protocol=importlib.util.module_from_spec(spec);spec.loader.exec_module(protocol)
    work=Path(work).resolve(strict=True);assert work.stat().st_uid==0 and stat.S_IMODE(work.stat().st_mode)==0o700
    descriptor=os.open(work/'transaction.lock',os.O_RDWR|os.O_CREAT|os.O_CLOEXEC|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(descriptor,fcntl.LOCK_EX|fcntl.LOCK_NB)
        ops=ClockUpdate(plan,work,failure=failure);previous={}
        for number in [signal.SIGTERM,signal.SIGINT]:previous[number]=signal.signal(number,lambda n,f:setattr(ops,'stopping',True))
        try:
            if check:ops.preflight()
            else:protocol.execute(ops)
            return ops
        finally:
            for number,handler in previous.items():signal.signal(number,handler)
    finally:os.close(descriptor)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--plan',required=True);parser.add_argument('--work',required=True);parser.add_argument('--check',action='store_true');parser.add_argument('--private-failure',choices=['before-commit','after-commit','hook-exec-EIO']);a=parser.parse_args()
    execute(json.loads(Path(a.plan).read_text()),Path(a.work),failure=a.private_failure,check=a.check)
if __name__=='__main__':main()
