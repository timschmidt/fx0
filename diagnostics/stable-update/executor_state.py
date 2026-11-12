"""Restore owned APK executor files after the caller has reaped all hooks."""
import hashlib
import os
from pathlib import Path
import stat

EXECUTOR='/usr/lib/apk/exec'

def _directory(root,manifest):
    root=Path(root).resolve(strict=True)
    assert root!=Path('/'), 'Live-root activation requires a separate controller'
    assert manifest['directory_membership'][EXECUTOR]==[]
    parent=root
    for part in Path(EXECUTOR).parts[1:]:
        parent=parent/part
        assert not parent.is_symlink(), 'Symlink in executor path'
        assert parent.is_dir(), 'Executor path must be a directory'
    st=parent.lstat();row=manifest['paths'][EXECUTOR]
    assert st.st_uid==row['uid'] and st.st_gid==row['gid']
    assert not (stat.S_IMODE(st.st_mode)&0o022), 'Executor directory must not be group/world writable'
    return parent

def verify_membership(root,manifest):
    directory=_directory(root,manifest)
    assert sorted(p.name for p in directory.iterdir())==[], 'Unrestored APK executor entries remain'

def cleanup_owned_scripts(root,manifest,owned_scripts,*,hooks_terminal):
    assert hooks_terminal, 'All owned hooks must be reaped before executor cleanup'
    directory=_directory(root,manifest)
    assert all(Path(name).name==name and name not in {'','.','..'} for name in owned_scripts)
    entries=sorted(directory.iterdir())
    assert all(p.name in owned_scripts for p in entries), 'Unknown executor entry; preserve all files'
    identities={}
    owner=manifest['paths'][EXECUTOR]
    for path in entries:
        expected=owned_scripts[path.name]
        assert 0<expected['size']<=65536
        st=path.lstat()
        assert stat.S_ISREG(st.st_mode) and st.st_nlink==1, 'Executor entry must be a regular unlinked-to-other-files script'
        assert (st.st_uid,st.st_gid)==(owner['uid'],owner['gid'])
        assert st.st_size==expected['size'], 'Executor size differs from the signed script'
        identities[path.name]=(st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)
    for path in entries:
        fd=os.open(path,os.O_RDONLY|os.O_CLOEXEC|os.O_NOFOLLOW)
        try:
            st=os.fstat(fd)
            assert (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==identities[path.name]
            data=os.read(fd,st.st_size+1)
            assert len(data)==st.st_size
            assert hashlib.sha256(data).hexdigest()==owned_scripts[path.name]['sha256'], 'Executor contents differ from the signed script'
        finally:
            os.close(fd)
    removed=[]
    for path in entries:
        st=path.lstat()
        assert (st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns)==identities[path.name], 'Executor entry changed during cleanup'
        path.unlink()
        removed.append(path.name)
    verify_membership(root,manifest)
    return removed


def verify_all_memberships(root,manifest):
    root=Path(root).resolve(strict=True)
    assert root!=Path('/'), 'Live-root activation requires a separate controller'
    for name,expected in manifest['directory_membership'].items():
        assert name.startswith('/') and name!='/' and '..' not in Path(name).parts
        directory=root
        for part in Path(name).parts[1:]:
            directory=directory/part
            assert not directory.is_symlink() and directory.is_dir(), 'Invalid membership directory'
        assert sorted(p.name for p in directory.iterdir())==expected, 'Unrestored directory membership: '+name
