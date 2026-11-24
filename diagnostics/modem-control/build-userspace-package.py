#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build one pinned modem package with normal abuild in a rootless namespace.

Inputs are read-only verified build roots, immutable Git recipe objects, one
public release archive, public keys and an in-place APK signer. Only the new
output home/tmp are writable. No container image, network or phone is used.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shlex
import shutil
import subprocess
import sys
import tarfile


def sha(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2)+'\n')
    temporary.replace(path)


def check_roots(plan):
    for role in ['native', 'target']:
        if role not in plan['roots']:
            continue
        path=Path(plan['roots'][role])
        if sha(path/'lib/apk/db/installed') != plan['root_DB_SHA256'][role]:
            raise ValueError(role+' package database changed')
    for name, expected in plan['native_config_SHA256'].items():
        if sha(Path(plan['roots']['native'])/name) != expected:
            raise ValueError('Native setup changed: '+name)


def inside_user_namespace(plan_path):
    """Podman's existing full subuid map permits the normal pmos su step."""
    plan=json.loads(plan_path.read_text())
    output=plan_path.parent
    check_roots(plan)
    for directory, mode in [('pmos-home', 0o2755), ('native-tmp', 0o1777), ('native-tmp/source-cache', 0o755)]:
        path=output/directory
        os.chown(path, 12345, 12345)
        path.chmod(mode)
    native=Path(plan['roots']['native'])
    command=['bwrap', '--die-with-parent', '--unshare-pid', '--unshare-net',
             '--unshare-ipc', '--unshare-uts', '--clearenv',
             '--ro-bind', str(native), '/',
             '--bind', str(output/'pmos-home'), '/home/pmos',
             '--bind', str(output/'native-tmp'), '/tmp',
             '--ro-bind', str(output/'inputs'), '/tmp/build-inputs',
             '--ro-bind', str(output/'public-keys'), '/etc/apk/keys',
             '--ro-bind', plan['signer_directory'], '/tmp/apk-signers',
             '--ro-bind', plan['archive_path'], '/tmp/source-cache/'+plan['source_filename'],
             '--dev', '/dev', '--tmpfs', '/dev/shm', '--proc', '/proc',
             '--cap-add', 'CAP_SETUID', '--cap-add', 'CAP_SETGID',
             '--setenv', 'PATH', '/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
             '--setenv', 'HOME', '/home/pmos']
    if 'target' in plan['roots']:
        command+=['--ro-bind', plan['roots']['target'], '/mnt/sysroot']
    command+=['/bin/su', 'pmos', '-s', '/bin/sh', '-c',
              '/bin/sh /tmp/build-inputs/build-native.sh']
    return subprocess.run(command).returncode


def prepare(args):
    lock=json.loads(args.lock.read_text())
    profile=lock['packages'][args.package]
    output=args.output.resolve()
    if output.exists():
        raise ValueError('Output must be a new directory; retain previous attempts')
    if re.fullmatch('[a-f0-9]{40}', profile['recipe_commit']) is None:
        raise ValueError('Recipe must be pinned to a full commit')
    if re.fullmatch('[A-Za-z0-9@_.+-]+\\.rsa', args.signing_key.name) is None:
        raise ValueError('Expected an APK RSA signer filename')
    # Only stat the private key. The normal abuild signer alone reads its body.
    if not args.signing_key.is_file():
        raise ValueError('In-place signer is missing')
    public_key=args.signing_key.with_name(args.signing_key.name+'.pub')
    if not public_key.is_file():
        raise ValueError('Adjacent public signer key is missing')
    if args.archive.name != profile['source_filename'] or sha(args.archive, 'sha512') != profile['source_SHA512']:
        raise ValueError('Release archive name or checksum mismatch')
    roots={'native':str(args.native_root.resolve())}
    if profile['architecture']=='armv7':
        if args.target_root is None:
            raise ValueError('ARM build requires a verified target sysroot')
        roots['target']=str(args.target_root.resolve())
    plan={'package':args.package, 'architecture':profile['architecture'],
          'recipe_commit':profile['recipe_commit'], 'SOURCE_DATE_EPOCH':profile['SOURCE_DATE_EPOCH'],
          'roots':roots, 'root_DB_SHA256':profile['root_DB_SHA256'],
          'native_config_SHA256':profile['native_config_SHA256'],
          'archive_path':str(args.archive.resolve()), 'source_filename':profile['source_filename'],
          'source_SHA512':profile['source_SHA512'],
          'signer_directory':str(args.signing_key.resolve().parent),
          'signing_key_name':args.signing_key.name,
          'signing_public_key_SHA256':sha(public_key),
          'private_key_body_read_hashed_or_copied_by_launcher':False,
          'network_or_phone_access':False}
    check_roots(plan)
    keys=sorted(args.public_keys.iterdir())
    if not keys or any(not path.is_file() or not path.name.endswith('.pub') for path in keys):
        raise ValueError('Public-key fixture must contain public .pub files only')
    roster={path.name:sha(path) for path in keys}
    if roster != lock['public_keys_SHA256'] or roster.get(public_key.name) != sha(public_key):
        raise ValueError('Public trust/signer fixture differs from the audited profile')
    output.mkdir(parents=True, mode=0o700)
    for name in ['inputs', 'public-keys', 'pmos-home', 'native-tmp', 'tmp']:
        (output/name).mkdir()
    (output/'native-tmp/source-cache').mkdir()
    for path in keys:
        shutil.copy2(path, output/'public-keys'/path.name)
    prefix='main/'+args.package+'/'
    archive=subprocess.check_output(['git', '-C', str(args.aports), 'archive', profile['recipe_commit'], prefix[:-1]])
    files={}
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        for member in tar:
            if member.isdir():
                continue
            if not member.isfile() or not member.name.startswith(prefix):
                raise ValueError('Recipe archive contains unexpected member')
            name=member.name[len(prefix):]
            if len(PurePosixPath(name).parts)!=1 or name not in profile['recipe_files_SHA256']:
                raise ValueError('Unexpected recipe file: '+name)
            data=tar.extractfile(member).read()
            if hashlib.sha256(data).hexdigest()!=profile['recipe_files_SHA256'][name]:
                raise ValueError('Recipe source mismatch: '+name)
            path=output/'inputs'/name
            path.write_bytes(data)
            path.chmod(member.mode&0o777)
            files[name]=hashlib.sha256(data).hexdigest()
    if files != profile['recipe_files_SHA256']:
        raise ValueError('Incomplete immutable recipe snapshot')
    native_script=['#!/bin/sh', 'set -eu', 'export LC_ALL=C LANG=C TZ=UTC',
                   'export ABUILD_LAST_COMMIT='+shlex.quote(profile['recipe_commit']),
                   'export SOURCE_DATE_EPOCH='+str(profile['SOURCE_DATE_EPOCH'])]
    if profile['architecture']=='armv7':
        native_script+=['export CHOST=armv7 CBUILDROOT=/mnt/sysroot PMB_CROSS=cross-native2',
                        'export CROSS_COMPILE=armv7-alpine-linux-musleabihf-',
                        'export CC="clang --target=armv7-alpine-linux-musleabihf --sysroot=/mnt/sysroot --gcc-toolchain=/mnt/sysroot/usr"',
                        'export CXX="clang++ --target=armv7-alpine-linux-musleabihf --sysroot=/mnt/sysroot --gcc-toolchain=/mnt/sysroot/usr"',
                        'export LD=ld.lld',
                        'export LDFLAGS="-Wl,-rpath-link=/mnt/sysroot/usr/lib -fuse-ld=lld"',
                        'unset CFLAGS CXXFLAGS CPPFLAGS']
    else:
        native_script+=['export CARCH=x86_64 CC=gcc',
                        'unset CFLAGS CXXFLAGS CPPFLAGS LDFLAGS CROSS_COMPILE PMB_CROSS']
    native_script+=['export CCACHE_DISABLE=1 JOBS=2 MAKEFLAGS=-j2',
                    "export SUDO_APK='abuild-apk --no-progress'",
                    'export PACKAGER_PRIVKEY='+shlex.quote('/tmp/apk-signers/'+args.signing_key.name),
                    'export PACKAGER_PUBKEY='+shlex.quote('/tmp/apk-signers/'+public_key.name),
                    'export SRCDEST=/tmp/source-cache REPODEST=/home/pmos/packages',
                    'cd /home/pmos', 'mkdir build',
                    'cp /tmp/build-inputs/* build/', 'cd build',
                    'abuild -d -D postmarketOS -f']
    (output/'inputs/build-native.sh').write_text('\n'.join(native_script)+'\n')
    plan['inputs_SHA256']={path.name:sha(path) for path in (output/'inputs').iterdir()}
    plan['public_keys_SHA256']=roster
    plan['launcher_SHA256']=sha(Path(__file__))
    shutil.copyfile(Path(__file__), output/'launcher.py')
    if sha(output/'launcher.py') != plan['launcher_SHA256']:
        raise ValueError('Launcher changed while snapshotting inputs')
    plan_path=output/'plan.private.json'
    write_json(plan_path, plan)
    plan_path.chmod(0o600)
    return output, plan


def main():
    if len(sys.argv)==3 and sys.argv[1]=='_inside':
        return inside_user_namespace(Path(sys.argv[2]))
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['lock', 'aports', 'native-root', 'archive', 'public-keys', 'signing-key', 'output', 'podman-root', 'podman-runroot']:
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--target-root', type=Path)
    parser.add_argument('--package', choices=['qmic','qrtr','rmtfs'], required=True)
    args=parser.parse_args()
    output, plan=prepare(args)
    command=['podman', '--root', str(args.podman_root.resolve()), '--runroot', str(args.podman_runroot.resolve()),
             '--storage-driver', 'vfs', '--cgroup-manager', 'cgroupfs',
             'unshare', sys.executable, str(output/'launcher.py'), '_inside', str(output/'plan.private.json')]
    record={'started_UTC':now(), 'package':args.package, 'recipe_commit':plan['recipe_commit'],
            'source_SHA512':plan['source_SHA512'], 'root_DB_SHA256':plan['root_DB_SHA256'],
            'public_keys_SHA256':plan['public_keys_SHA256'], 'inputs_SHA256':plan['inputs_SHA256'],
            'launcher_SHA256':plan['launcher_SHA256'], 'private_signer_mounted_readonly_in_place':True,
            'phone_or_network_access':False}
    with (output/'build.log').open('xb') as log:
        process=subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
                                 env=os.environ|{'TMPDIR':str(output/'tmp')})
        record['PID']=process.pid
        write_json(output/'result.json', record)
        record['returncode']=process.wait()
    record['finished_UTC']=now()
    check_roots(plan)
    write_json(output/'result.json', record)
    print(args.package+' normal abuild terminal: '+str(record['returncode']))
    return record['returncode']


if __name__=='__main__':
    raise SystemExit(main())
