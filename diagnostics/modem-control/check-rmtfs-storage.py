#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile actual storage.c and run isolated synthetic backing-file cases."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import tempfile

CASES=['shadow','partition-labels','read-write-control','unknown','closed','negative-caller',
       'negative-read','negative-write','growth-hole','short-read','interrupted-read','early-eof',
       'read-io-error','limit-errno','large-read-count','large-write-count','far-read','far-write',
       'invalid-handle','pread-io-error']


def main():
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True,type=Path)
    parser.add_argument('--qrtr-includes',required=True,type=Path)
    parser.add_argument('--harness',required=True,type=Path)
    parser.add_argument('--compiler-json',required=True,help='JSON argv prefix, never passed through a shell')
    parser.add_argument('--runner-json',default='[]',help='JSON sandbox/emulator argv prefix')
    parser.add_argument('--cflags-json',default='[]')
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args();args.output.mkdir(mode=0o700,exist_ok=False)
    out=args.output.resolve();source=args.source.resolve();binary=out/'storage-harness'
    command=json.loads(args.compiler_json)+json.loads(args.cflags_json)+[
        '-I'+str(source),'-I'+str(args.qrtr_includes.resolve()),str(args.harness.resolve()),str(source/'storage.c'),
        '-Wl,--wrap=open','-Wl,--wrap=read','-Wl,--wrap=pread','-Wl,--wrap=pwrite',
        '-Wl,--wrap=fdatasync','-Wl,--wrap=realloc','-o',str(binary)]
    build=subprocess.run(command,capture_output=True,text=True)
    (out/'build.log').write_text(build.stdout+build.stderr);build.check_returncode()
    names=['modem_fs1','modem_fs2','modem_fsg','modem_fsc','modemst1','modemst2','fsg','fsc']
    results=[]
    for case in CASES:
        with tempfile.TemporaryDirectory(dir=out) as directory:
            root=Path(directory)
            for name in names:(root/name).write_bytes(b'\x21'*4096)
            try:
                run=subprocess.run(json.loads(args.runner_json)+[str(binary),case,str(root)],capture_output=True,text=True,
                                   env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:abort_on_error=0'},timeout=15)
                stdout,stderr,code=run.stdout,run.stderr,run.returncode
            except subprocess.TimeoutExpired as exc:
                stdout,stderr,code=str(exc.stdout),str(exc.stderr),'timeout'
            (out/(case+'.log')).write_text(stdout+stderr)
            expected={name:b'\x21'*4096 for name in names}
            if case=='read-write-control':expected['modem_fs1']=b'\x5a'*32+b'\x21'*(4096-32)
            backing_unchanged=all((root/name).read_bytes()==data for name,data in expected.items())
            passed=code==0 and 'STORAGE_CASE_PASS '+case in stdout and backing_unchanged
            results.append({'case':case,'returncode':code,'passed':passed,'backing_files_match_expected':backing_unchanged})
    record={'cases':results,'passed':sum(row['passed'] for row in results),'failed':sum(not row['passed'] for row in results),
            'storage_source_sha256':hashlib.sha256((source/'storage.c').read_bytes()).hexdigest(),
            'harness_sha256':hashlib.sha256(args.harness.read_bytes()).hexdigest(),
            'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'compiler_command':command,
            'runner':json.loads(args.runner_json),'actual_phone_QRTR_or_modem_operations':0,
            'scope':'Actual storage.c API and synthetic regular files, with guarded open/read/write/sync calls; no server/QMI/shared-memory/physical qualification'}
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({'passed':record['passed'],'failed':record['failed'],'actual_phone_operations':0}))
    raise SystemExit(bool(record['failed']))


if __name__=='__main__':main()
