#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create fresh signed Alpine native/ARM build roots without a helper image.

The initial apk.static uses Alpine's detached RSA/SHA256 signature, as in
pmbootstrap's apk_static bootstrap protocol. No existing private root or key is
copied. Native/target caches contain public APKs and signed indexes only.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import ssl
import subprocess
import sys
import tarfile


SETUP_SUFFIX='\n# Preserve independent build workspaces for source and output qualification.\nCLEANUP=""\nERROR_CLEANUP=""\n'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def database(path):
    result={}
    for block in path.read_text().split('\n\n'):
        fields={line[0]:line[2:] for line in block.splitlines() if len(line)>1 and line[1]==':' and line[0] in 'PVc'}
        if fields:
            result[fields['P']]={'version':fields['V'],'source_commit':fields['c']}
    return result


def package_payload_audit(root, native):
    """Resolve directory links inside the root; never follow a host absolute link."""
    def parent(name):
        parts=list(PurePosixPath(name).parts);filename=parts.pop();current=[];steps=0
        while parts:
            part=parts.pop(0)
            if part in ['','.','/']:continue
            if part=='..':
                if not current:raise ValueError('Package path escapes build root')
                current.pop();continue
            path=root.joinpath(*current,part)
            if path.is_symlink():
                steps+=1
                if steps>64:raise ValueError('Package directory symlink loop')
                target=os.readlink(path)
                if target.startswith('/'):current=[]
                parts=list(PurePosixPath(target).parts)+parts
            else:current.append(part)
        return root.joinpath(*current,filename)
    records=[];package=folder=filename=None
    for line in (root/'lib/apk/db/installed').read_text().splitlines():
        if line.startswith('P:'):package=line[2:]
        elif line.startswith('F:'):folder=line[2:]
        elif line.startswith('R:'):filename=line[2:]
        elif line.startswith('Z:'):records.append((package,'/'+folder+'/'+filename,line[2:]))
    checked=links=0;excluded=[];mismatches=[]
    for package,name,expected in records:
        if name in ['/etc/shadow','/etc/gshadow'] or '/ssl/private/' in name or name.startswith(('/home/','/root/')) or name.endswith(('.rsa','.key')):
            excluded.append(name);continue
        path=parent(name)
        if path.is_symlink():
            digest=hashlib.sha1(os.fsencode(os.readlink(path))).digest();links+=1
        else:
            with path.open('rb') as stream:digest=hashlib.file_digest(stream,'sha1').digest()
        actual='Q1'+base64.b64encode(digest).decode()
        if actual!=expected:mismatches.append(name)
        checked+=1
    allowed={'/etc/passwd','/etc/group','/etc/abuild.conf'} if native else set()
    if not set(mismatches)<=allowed:raise ValueError('Installed payload mismatch: '+repr(mismatches))
    return {'checked_paths':checked,'symlinks_checked':links,'credential_paths_excluded':excluded,'configuration_mismatches':mismatches,'all_other_package_payloads_exact':True}


def inner(plan_path):
    plan=json.loads(plan_path.read_text());base=plan_path.parent;lock=json.loads((base/'lock.json').read_text());spec=lock['bootstrap']
    results=[]
    for arch,role in [('x86_64','native'),('armv7','target')]:
        root=base/role
        command=['bwrap','--die-with-parent','--unshare-pid','--unshare-ipc','--unshare-uts',
                 '--clearenv','--setenv','PATH','/usr/bin:/bin','--setenv','LC_ALL','C']
        if plan['offline']:command+=['--unshare-net']
        command+=['--ro-bind',str(base/'apk.static'),'/apk.static','--bind',str(base),'/work',
                  '--ro-bind',str(base/'resolver.conf'),'/etc/resolv.conf',
                  '--ro-bind',str(base/'ca-certificates.crt'),'/etc/ssl/cert.pem',
                  '--dev','/dev','--proc','/proc','--tmpfs','/tmp',
                  '/apk.static','--no-progress','--root','/work/'+role,'--arch',arch,'--initdb','--cache-dir','/work/cache/'+arch]
        if plan['offline']:command+=['--no-network']
        if role=='target':command+=['--no-scripts']
        command+=['add',*spec[role+'_requests']]
        with (base/(role+'-bootstrap.log')).open('xb') as log:
            result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
        if result.returncode:return result.returncode
        extras=plan[role+'_extras']
        if extras:
            command=command[:command.index('add')]+['add',*['/work/extras/'+name for name in extras]]
            with (base/(role+'-extras.log')).open('xb') as log:
                result=subprocess.run(command,stdout=log,stderr=subprocess.STDOUT)
            if result.returncode:return result.returncode
        if role=='native':
            prefix=['bwrap','--die-with-parent','--unshare-pid','--unshare-net','--unshare-ipc','--unshare-uts',
                    '--clearenv','--setenv','PATH','/usr/bin:/bin','--setenv','LC_ALL','C',
                    '--bind',str(root),'/','--dev','/dev','--proc','/proc','--tmpfs','/tmp']
            for args in [['/usr/sbin/adduser','-D','-u','12345','-s','/bin/bash','pmos'],['/usr/sbin/addgroup','pmos','abuild']]:
                result=subprocess.run(prefix+args,capture_output=True)
                with (base/'native-user-setup.log').open('ab') as log:log.write(result.stdout+result.stderr)
                if result.returncode:return result.returncode
            with (root/'etc/abuild.conf').open('a') as stream:stream.write(SETUP_SUFFIX)
            for name,want in spec['native_config_SHA256'].items():
                if sha(root/name)!=want:raise ValueError('Source-defined native setup differs: '+name)
        expected=dict(spec[role+'_package_identities'])
        for filename in extras:
            name=plan['extra_package_names'][filename]
            row=spec['extras'][name];expected[name]={'version':row['version'],'source_commit':row['source_commit']}
        installed=database(root/'lib/apk/db/installed')
        if installed!=expected:raise ValueError('Signed package/source identities differ: '+role)
        audit=package_payload_audit(root,role=='native')
        results.append({'role':role,'package_count':len(installed),'package_identities':installed,'database_SHA256':sha(root/'lib/apk/db/installed'),'payload_audit':audit})
        (base/'root-verification.json').write_text(json.dumps({'roots':results,'phone_changes':False},indent=2)+'\n')
    return 0


def main():
    if len(sys.argv)==3 and sys.argv[1]=='_inside':return inner(Path(sys.argv[2]))
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['lock','public-keys','apk-static-package','output','podman-root','podman-runroot']:
        parser.add_argument('--'+name,type=Path,required=True)
    for name in ['native-cache','target-cache','native-pigz-apk','qmic-apk','qrtr-dev-apk','qrtr-libs-apk','ca-certificates']:
        parser.add_argument('--'+name,type=Path)
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args();base=args.output.resolve()
    if base.exists():raise ValueError('Output must be new; retain prior attempts')
    lock=json.loads(args.lock.read_text());spec=lock['bootstrap'];keys=sorted(args.public_keys.iterdir())
    if not keys or any(not p.is_file() or not p.name.endswith('.pub') for p in keys):raise ValueError('Expected public keys only')
    if {p.name:sha(p) for p in keys}!=lock['public_keys_SHA256']:raise ValueError('Public key fixture mismatch')
    if sha(args.apk_static_package)!=spec['apk_static']['APK_SHA256']:raise ValueError('Static APK archive mismatch')
    base.mkdir(parents=True,mode=0o700)
    for name in ['tmp','extras','cache/x86_64','cache/armv7']:(base/name).mkdir(parents=True)
    shutil.copyfile(args.lock,base/'lock.json');shutil.copyfile(Path(__file__),base/'bootstrap.py')
    shutil.copyfile('/etc/resolv.conf',base/'resolver.conf')
    ca=args.ca_certificates or Path(ssl.get_default_verify_paths().cafile)
    shutil.copyfile(ca,base/'ca-certificates.crt')
    with tarfile.open(args.apk_static_package,'r:gz',ignore_zeros=True) as archive:
        signature_name=spec['apk_static']['detached_signature_member']
        binary=archive.extractfile('sbin/apk.static').read();signature=archive.extractfile(signature_name).read()
    (base/'apk.static').write_bytes(binary);(base/'apk.static').chmod(0o755);(base/'apk.static.sig').write_bytes(signature)
    key=args.public_keys/spec['apk_static']['trusted_public_key']
    result=subprocess.run(['openssl','dgst','-sha256','-verify',str(key),'-signature',str(base/'apk.static.sig'),str(base/'apk.static')],capture_output=True)
    if result.returncode or sha(base/'apk.static')!=spec['apk_static']['binary_SHA256']:raise ValueError('Static APK signature or executable mismatch')
    for arch,role,cache in [('x86_64','native',args.native_cache),('armv7','target',args.target_cache)]:
        root=base/role
        for name in ['etc/apk/keys','var/cache/apk','usr/bin','usr/lib','home','tmp','dev','proc','sys','mnt/sysroot']:(root/name).mkdir(parents=True,exist_ok=True)
        for name,value in [('bin','usr/bin'),('sbin','usr/bin'),('lib','usr/lib'),('usr/sbin','bin')]: (root/name).symlink_to(value)
        (root/'etc/apk/repositories').write_text('\n'.join(spec[role+'_repositories'])+'\n')
        shutil.copyfile(base/'resolver.conf',root/'etc/resolv.conf')
        for key in keys:shutil.copyfile(key,root/'etc/apk/keys'/key.name)
        if cache:
            for path in cache.iterdir():
                if path.is_file() and not path.is_symlink() and (path.name.endswith('.apk') or path.name.startswith('APKINDEX.') and path.name.endswith('.tar.gz')):
                    shutil.copyfile(path,base/'cache'/arch/path.name)
        elif args.offline:raise ValueError('Offline bootstrap requires both public caches')
    native_extras=[];target_extras=[];names={}
    for name,path,selected in [('pigz',args.native_pigz_apk,native_extras),('qmic',args.qmic_apk,native_extras),('qrtr-dev',args.qrtr_dev_apk,target_extras),('qrtr-libs',args.qrtr_libs_apk,target_extras)]:
        if path is None:continue
        if sha(path)!=spec['extras'][name]['APK_SHA256']:raise ValueError('Signed extra APK mismatch: '+name)
        filename=path.name
        if filename in names:raise ValueError('Extra APK name collision')
        shutil.copyfile(path,base/'extras'/filename);selected.append(filename);names[filename]=name
    if bool(args.qrtr_dev_apk)!=bool(args.qrtr_libs_apk):raise ValueError('Provide both QRTR development and library APKs')
    plan={'offline':args.offline,'native_extras':native_extras,'target_extras':target_extras,'extra_package_names':names,'private_signers_or_credentials_used':False}
    (base/'plan.json').write_text(json.dumps(plan,indent=2)+'\n')
    command=['podman','--root',str(args.podman_root.resolve()),'--runroot',str(args.podman_runroot.resolve()),'--storage-driver','vfs','--cgroup-manager','cgroupfs','unshare',sys.executable,str(base/'bootstrap.py'),'_inside',str(base/'plan.json')]
    record={'started_UTC':datetime.now(timezone.utc).isoformat(),'source_snapshot_SHA256':sha(base/'bootstrap.py'),'lock_SHA256':sha(base/'lock.json'),'apk_static_SHA256':sha(base/'apk.static'),'offline':args.offline,'phone_changes':False}
    with (base/'bootstrap.log').open('xb') as log:
        process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,env=os.environ|{'TMPDIR':str(base/'tmp')})
        record['PID']=process.pid;(base/'result.json').write_text(json.dumps(record,indent=2)+'\n');record['returncode']=process.wait()
    record['finished_UTC']=datetime.now(timezone.utc).isoformat();(base/'result.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Signed native/ARM build-root bootstrap terminal:',record['returncode'])
    return record['returncode']


if __name__=='__main__':raise SystemExit(main())
