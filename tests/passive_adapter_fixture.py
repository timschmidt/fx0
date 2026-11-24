# SPDX-License-Identifier: MIT
"""Synthetic public inputs and forbidden-by-default transport providers."""
"""Actual adapter methods with a forbidden-by-default offline I/O boundary."""
import ast,contextlib,copy,datetime,hashlib,importlib.util,io,json,os,shlex,subprocess,sys,tempfile,time,types,unittest
from unittest import mock
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HERE=Path(__file__).resolve().parent
SOURCE=(ROOT/'diagnostics/modem-control/passive_adapter.py').read_text()
TREE=ast.parse(SOURCE)

CANDIDATE=next(n.value for n in ast.walk(TREE) if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='candidate' for t in n.targets))

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

PUBLIC=module('public_adapter_under_test',ROOT/'diagnostics/modem-control/passive_adapter.py')
FLOW=module('public_flow',ROOT/'diagnostics/modem-control/passive_trial.py')
RUNTIME=module('public_runtime',ROOT/'diagnostics/modem-control/passive_runtime.py')
WAIT=types.SimpleNamespace(wait_ssh=PUBLIC.wait_ssh)


class Fixture:
    def __init__(self,test,name,mode='success'):
        self.test=test;self.mode=mode;self.events=[];self.vendor='18d1';self.product='d001';self.generation=200;self.serial='offline-fixture-device'
        self.temporary=tempfile.TemporaryDirectory();test.addCleanup(self.temporary.cleanup)
        self.case=Path(self.temporary.name);self.children=[];self.ops=None;self.logical=0
        image=self.case/'fixture.img';image.write_bytes(b'public offline image profile')
        image_hash=hashlib.sha256(image.read_bytes()).hexdigest()
        for key,value in [('IMAGE_SHA256',image_hash),('IMAGE_BYTES',image.stat().st_size)]:
            patch=mock.patch.object(PUBLIC,key,value);patch.start();test.addCleanup(patch.stop)
        files={p:'c'*64 for p in ['/lib/apk/db/installed','/etc/apk/world','/etc/apk/repositories','/boot/boot.img','/boot/initramfs']}
        before={'boot_id':'00000000-0000-4000-8000-000000000001','kernel':'6.18.63-fx0-vibrator-alpine',
                'kernel_notes_SHA256':'05292e44d9f13de78b5ebf602b0b3f9ff22b7820d765f6e796cf3473beee4377',
                'trial':False,'taint':0,'boot_partition_sha256':'b'*64,'files_sha256':files,
                'installed_DB_sha256':files['/lib/apk/db/installed'],'world_sha256':files['/etc/apk/world'],
                'module_tree_digest':'d'*64,'modules_FSType':'ext4','systemd':'running','Sway':'fixture','gesture':'fixture','native_USB_generation':200}
        prep={'image_path':str(image),'image_SHA256':image_hash,'image_bytes':image.stat().st_size}
        (self.case/'before.json').write_text(json.dumps(before));(self.case/'preparation.json').write_text(json.dumps(prep))
        (self.case/'index').write_bytes(b'fixture index')
        (self.case/'fixture-device.json').write_text(json.dumps({'serial':self.serial}))
        (self.case/'control-node').write_bytes(b'fixture-only')
        before=json.loads((self.case/'before.json').read_text())
        prep=json.loads((self.case/'preparation.json').read_text())
        self.owner={'answer':'Available; display and touch work','boot_id':before['boot_id'],'image_SHA256':prep['image_SHA256'],'recorded_UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
        (self.case/'owner-availability.json').write_text(json.dumps(self.owner))
        fixture=self
        def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
        def sha(path):
            with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
        def read(path):
            values={'idVendor':self.vendor,'idProduct':self.product,'serial':self.serial,'speed':'480','devnum':str(self.generation)}
            if path.parent!=Path('/sys/bus/usb/devices/1-7') or path.name not in values:raise RuntimeError('Unexpected sysfs access in offline fixture')
            return values[path.name]
        def monotonic():self.logical+=25;return self.logical
        def run_native(command,**kwargs):
            if command=='systemctl reboot --reboot-argument=bootloader':
                self.events.append('enter');self.product='d00d';self.generation+=1;return b''
            self.events.append('native-audit')
            if not command.startswith(('python3 -B -c ','python3 -c ')):raise RuntimeError('Unexpected native command')
            result=copy.deepcopy(before)
            if self.product=='d001' and self.generation>200:result['boot_id']='00000000-0000-4000-8000-000000000002'
            if mode=='baseline-mismatch':result['kernel']='offline-wrong-kernel'
            return json.dumps(result).encode()
        def query(serial,boot=False):
            if serial!=self.serial:raise RuntimeError('Unexpected fixture identity')
            if not boot:return {'product':['OKAYlk2nd-msm8226'],'lk2nd_version':['OKAYfx0-pon-reboot']}
            self.events.append('BOOT')
            state=json.loads((self.case/'controller.json').read_text())
            test.assertTrue(state['BOOT_attempted']);test.assertTrue((self.case/'attempt.claim').is_file())
            self.product='d001';self.generation+=1
            if mode=='uncertain-BOOT':raise OSError('offline acknowledgement missing')
            return {'boot':['OKAY']}
        def ioctl(descriptor,request,value):
            test.assertEqual(Path(os.readlink('/proc/self/fd/'+str(descriptor))),self.case/'control-node')
            test.assertEqual((request,value),(0x5514,0));self.events.append('reset')
        def spawn(command,**kwargs):
            if command[:3]!=[sys.executable,'-B',str(HERE/'fixtures/passive_adapter_child.py')]:raise RuntimeError('Forbidden real process command in offline adapter test')
            child=subprocess.Popen(command,**kwargs);self.children.append(child);return child
        def check_output(command,**kwargs):
            if command!=['ip','-j','route','show','default']:raise RuntimeError('Forbidden host query')
            return b'[]'
        def run(command,**kwargs):
            if command!=['fixture-ssh','true']:raise RuntimeError('Forbidden subprocess run')
            return subprocess.CompletedProcess(command,0,b'',b'')
        def wait(child,timeout):
            actual=.03 if mode=='parent-deadline' and self.ops and child is self.ops.children.get('transfer') else timeout
            return RUNTIME.wait_owned(child,actual,terminate_grace=.1,kill_grace=.5)
        namespace={'root':ROOT,'base':self.case,'owner_path':self.case/'owner-availability.json',
                   'Path':Path,'json':json,'datetime':datetime,'sys':sys,'os':os,'shlex':shlex,
                   'now':now,'sha':sha,'read':read,'AttemptJournal':RUNTIME.AttemptJournal,'wait_owned':wait,
                   'wait_ssh':WAIT.wait_ssh,'time':types.SimpleNamespace(monotonic=monotonic,sleep=lambda value:time.sleep(min(value,.01))),
                   'n':types.SimpleNamespace(OPTS=['fixture-ssh'],run=run_native),
                   'boot':types.SimpleNamespace(query=query,device=lambda serial:(self.case/'control-node',None,None,None)),
                   'fcntl':types.SimpleNamespace(ioctl=ioctl),
                   'subprocess':types.SimpleNamespace(Popen=spawn,check_output=check_output,run=run,STDOUT=subprocess.STDOUT)}
        self.client=self.case/'dummy-client.py';self.client.write_text('raise RuntimeError("offline client must not be imported")\n')
        proof=self.case/'image-audit.json'
        proof.write_text(json.dumps({'image_SHA256':prep['image_SHA256'],'initial_shell_alias_and_all_script_interpreters_present':True,'GNU_cpio_independent_extraction_matches_every_entry':True}))
        plan={'format':1,'repository_root':str(ROOT),'workspace':str(self.case),
              'image_path':str(ROOT/prep['image_path']),'image_SHA256':prep['image_SHA256'],'image_bytes':prep['image_bytes'],
              'image_audit_path':str(proof),'image_audit_SHA256':sha(proof),'baseline_boot_id':before['boot_id'],
              'workspace_inputs_SHA256':{n:sha(self.case/n) for n in ['preparation.json','before.json']},
              'source_files_SHA256':{n:sha(ROOT/n) for n in PUBLIC.SOURCES},
              'credential_client':str(self.client),'device_record':str(self.case/'fixture-device.json'),'usb_port':'1-7',
              'host_index_path':str(self.case/'index'),'host_index_SHA256':sha(self.case/'index'),
              'port_lock_path':str(self.case/'fx0-ram-port-1-7.lock')}
        self.plan_path=self.case/'plan.json';self.plan_path.write_text(json.dumps(plan));self.plan_path.chmod(0o600)
        self.context=PUBLIC.Context(self.plan_path,sha(self.plan_path))
        self.wait_hook={'function':wait}
        namespace['runtime']=RUNTIME;namespace['wait_owned']=lambda child,timeout:self.wait_hook['function'](child,timeout)
        Real=PUBLIC.adapter_type(self.context,namespace)
        class Offline(Real):
            def spawn(adapter,name,command):
                expected={'transfer':'transfer_fx0_ram.py','observer':'passive_observer.py','normal-reboot':None}
                if name not in expected:raise RuntimeError('Unknown process role')
                if name=='normal-reboot':
                    test.assertEqual(command,['fastboot','-s',fixture.serial,'reboot']);fixture.events.append('return');fixture.product='d001';fixture.generation+=1
                else:test.assertEqual(Path(command[1]).name,expected[name])
                actual=[sys.executable,'-B',str(HERE/'fixtures/passive_adapter_child.py'),name,str(fixture.case),mode,str(adapter.payload)]
                child=super().spawn(name,actual)
                if mode=='dead-observer' and name=='observer':child.wait(timeout=3)
                if mode=='parent-deadline' and name=='transfer':
                    until=time.monotonic()+3
                    while not (fixture.case/'transfer-ready').exists() and time.monotonic()<until:
                        test.assertIsNone(child.poll());time.sleep(.01)
                    test.assertTrue((fixture.case/'transfer-ready').exists())
                return child
        self.Real=Offline
        self.ops=Offline(device_record=self.case/'fixture-device.json')
        test.addCleanup(self.close)

    def close(self):
        for child in self.children:
            if child.poll() is None:child.kill()
            child.wait(timeout=3)
        if self.ops:self.ops.journal.close()
        for path in self.case.rglob('*'):
            if path.is_file():path.chmod(0o600)

    def execute(self):
        with contextlib.redirect_stdout(io.StringIO()):return FLOW.Trial(self.ops).execute()
    def candidate(self):
        serial=json.loads((self.case/'serial-observation.json').read_text()) if (self.case/'serial-observation.json').exists() else {}
        return eval(compile(ast.Expression(CANDIDATE),str(ROOT/'diagnostics/modem-control/passive_adapter.py'),'eval'),{'serial':serial})
