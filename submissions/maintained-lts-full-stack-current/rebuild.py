"""Reproduce the maintained integration artifacts using public inputs only."""
from pathlib import Path
from datetime import datetime,timezone
import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',type=Path,required=True)
p.add_argument('--inputs',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
p.add_argument('--rust-toolchain',type=Path,required=True)
p.add_argument('--jobs',type=int,default=4)
a=p.parse_args()
source,inputs,O,rust=[path.resolve() for path in [a.source,a.inputs,a.output,a.rust_toolchain]]
assert 1<=a.jobs<=8 and not O.exists()
read=lambda path:json.loads(path.read_text())
def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
manifest=read(inputs/'manifest.json')
assert manifest['files']=={str(f.relative_to(inputs)):sha(f) for f in inputs.rglob('*') if f.is_file() and f.name!='manifest.json'}
assert not any(f.is_symlink() for f in inputs.rglob('*'))
expected=read(inputs/'expected-build.json')
tree=read(inputs/'source-manifest.json')
assert tree['source_head']==expected['source_head'] and tree['source_tree']==expected['source_tree']
assert not (source/'.git').exists()
actual={str(f.relative_to(source)) for f in source.rglob('*') if f.is_file() or f.is_symlink()}
assert actual==set(tree['files']), 'Source contains missing or untracked files'
for file,row in tree['files'].items():
    f=source/file
    assert f.resolve().is_relative_to(source)
    if row['mode']=='120000':
        assert f.is_symlink() and os.readlink(f)==row['target'],file
    else:
        assert not f.is_symlink() and sha(f)==row['SHA256'],file
assert sha(rust/'bin/rustc')==expected['public_Rust_compiler_SHA256']
assert b'PRIVATE KEY' not in (inputs/'module-verification.pem').read_bytes()
O.mkdir()
out=O/'out'
out.mkdir()
(out/'tmp').mkdir(mode=0o700)
shutil.copyfile(inputs/'kernel.config',out/'.config')
assert sha(out/'.config')==expected['config_SHA256']
record=dict(passed=False,state='prepared',started_UTC=datetime.now(timezone.utc).isoformat(),
    source_head=expected['source_head'],source_tree=expected['source_tree'],source_paths_verified=len(actual),
    input_manifest_SHA256=sha(inputs/'manifest.json'),source_and_inputs_read_only=True,
    exact_tracked_source_without_Git=True,network_namespace_isolated=True,
    home_boot_run_sys_and_USB_not_mounted=True,environment_cleared=True,
    private_signing_key_read_hashed_copied_or_generated=False,
    normal_APK_update_recovery_or_physical_acceptance=False,phone_access=False,published=False,stages=[])
child=None
def save():(O/'controller.json').write_text(json.dumps(record,indent=2)+'\n')
def interrupted(sig,frame):raise InterruptedError(str(sig))
signal.signal(signal.SIGTERM,interrupted)
sandbox=['bwrap','--unshare-all','--die-with-parent','--new-session','--cap-drop','ALL',
    '--ro-bind','/usr','/usr','--ro-bind','/etc','/etc',
    '--symlink','usr/bin','/bin','--symlink','usr/sbin','/sbin',
    '--symlink','usr/lib','/lib','--symlink','usr/lib64','/lib64',
    '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
    '--ro-bind',str(rust),'/toolchains/rust','--ro-bind',str(source),'/src/linux',
    '--ro-bind',str(inputs),'/inputs','--bind',str(out),'/build/out','--clearenv']
for key,value in expected['environment'].items():sandbox+=['--setenv',key,value]
sandbox+=['--chdir','/src/linux','--']
maps='-fdebug-prefix-map=/src/linux=/usr/src/linux -fdebug-prefix-map=/build/out=/usr/src/linux-build'
make=['make','O=/build/out','ARCH=arm','RUSTC=/toolchains/rust/bin/rustc','LLVM=-21','W=1',
    'KCFLAGS=-Werror=incompatible-function-pointer-types '+maps,'KAFLAGS='+maps,
    'LOCALVERSION=-g'+expected['source_head'][:12],'--jobserver-style=pipe','-j'+str(a.jobs)]
def run(label,command,timeout=900):
    global child
    log=O/(label+'.log')
    with log.open('xb') as stream:
        child=subprocess.Popen(sandbox+command,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        record.update(state='running '+label,active_PID=child.pid)
        save()
        code=child.wait(timeout=timeout)
    record.pop('active_PID',None)
    record['stages'].append(dict(label=label,returncode=code,log_SHA256=sha(log)))
    save()
    assert code==0,(label,code,log.read_text(errors='replace')[-1600:])
try:
    probe=('from pathlib import Path;import json;'
      'assert not any(Path(p).exists() for p in ["/home","/root","/run","/sys","/boot","/dev/bus/usb"]);'
      'interfaces=[s.split(":",1)[0].strip() for s in Path("/proc/net/dev").read_text().splitlines()[2:]];'
      'assert interfaces==["lo"],interfaces;print(json.dumps({"isolated":True,"interfaces":interfaces}))')
    run('isolation-probe',['python3','-B','-c',probe],30)
    run('config',make+['olddefconfig'],180)
    assert sha(out/'.config')==expected['config_SHA256']
    cfg=(out/'.config').read_text()
    assert 'CONFIG_MODULE_SIG=y\n' in cfg and '# CONFIG_MODULE_SIG_ALL is not set\n' in cfg
    assert 'CONFIG_MODULE_SIG_KEY="/inputs/module-verification.pem"\n' in cfg
    assert 'CONFIG_INITRAMFS_SOURCE=""\n' in cfg and 'CONFIG_EXTRA_FIRMWARE=""\n' in cfg
    assert 'CONFIG_CFI=y\n' in cfg and '# CONFIG_CFI_PERMISSIVE is not set\n' in cfg
    run('kernel-modules',make+['zImage','modules'],7200)
    for file,h in expected['core_artifacts'].items():assert sha(out/file)==h,file
    raw={str(f.relative_to(out)):sha(f) for f in out.rglob('*.ko')}
    assert raw==expected['module_hashes']
    assert all(not f.read_bytes().endswith(b'~Module signature appended~\n') for f in out.rglob('*.ko'))
    assert not (out/'certs/signing_key.pem').exists()
    run('DTBs',make+['dtbs'],1800)
    dtbs={str(f.relative_to(out/'arch/arm/boot/dts')):sha(f) for f in (out/'arch/arm/boot/dts').rglob('*.dtb')}
    assert dtbs==expected['DTB_hashes']
    run('modules-install',make+['INSTALL_MOD_PATH=/build/out/stage','modules_install'],900)
    release=expected['kernel_release']
    module_dir='/build/out/stage/lib/modules/'+release
    run('module-dependencies',['python3','-B','/inputs/verify_kernel_module_dependencies.py',
        '--modules',module_dir,'--expected-count',str(expected['module_count']),
        '--report','/build/out/module-dependencies.json'],600)
    assert sha(out/'.config')==expected['config_SHA256']
    assert not (out/'certs/signing_key.pem').exists()
    record.update(passed=True,state='terminal success',kernel_release=release,
        full_public_input_replay_passed=True,all_core_artifacts_exact=True,
        exact_unsigned_modules=len(raw),exact_DTBS=len(dtbs),module_dependency_metadata_passed=True,
        config_SHA256=expected['config_SHA256'],all_modules_unsigned=True,
        private_key_generated=False)
except BaseException as error:
    record.update(state='terminal failure',error_type=type(error).__name__,error=str(error))
    raise
finally:
    if child is not None and child.poll() is None:
        os.killpg(child.pid,signal.SIGTERM)
        try:child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid,signal.SIGKILL)
            child.wait(timeout=5)
    record.pop('active_PID',None)
    record['owned_child_terminal_and_reaped']=child is None or child.returncode is not None
    record['finished_UTC']=datetime.now(timezone.utc).isoformat()
    save()
print(json.dumps({k:record[k] for k in ['passed','kernel_release','exact_unsigned_modules','exact_DTBS']}))
