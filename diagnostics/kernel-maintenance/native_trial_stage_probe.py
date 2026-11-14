# SPDX-License-Identifier: MIT
"""Read-only exact staged-r2 module and free-space check."""
from pathlib import Path
import argparse,sys
import hashlib,json,os,stat

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--baseline-boot-id',required=True);args=parser.parse_args()
    if sys.flags.optimize:raise RuntimeError('Optimized Python is forbidden')
    assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==args.baseline_boot_id
    root=Path('/var/lib/fx0-diagnostics/kernel-reproducible-r2-01/candidate/lib/modules/6.18.63-fx0-vibrator-alpine')
    assert root.is_dir() and not root.is_symlink()
    all_paths=list(root.rglob('*'))
    for item in [root,*all_paths]:
     info=item.lstat();assert (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode)) and info.st_uid==0 and not info.st_mode&0o022
    paths=sorted(p for p in all_paths if p.is_file())
    assert len(paths)==478 and sum(p.name.endswith('.ko.zst') for p in paths)==464
    rows=[]
    for p in paths:
     s=p.lstat();assert stat.S_ISREG(s.st_mode) and s.st_uid==0 and not s.st_mode&0o022
     rows.append(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(root))+'\n')
    digest=hashlib.sha256(''.join(rows).encode()).hexdigest()
    assert digest=='e5844d5ba3b12935b73a3517d7be67a9d18e6013ac5f59d547c4177b1fd8cdfb'
    free=os.statvfs(root).f_bavail*os.statvfs(root).f_frsize
    assert free>536870912
    print(json.dumps(dict(module_manifest_SHA256=digest,all478_staged_files_exact=True,staged_files_root_owned_and_not_group_world_writable=True,free_bytes=free,read_only=True)))

if __name__ == "__main__":
    main()
