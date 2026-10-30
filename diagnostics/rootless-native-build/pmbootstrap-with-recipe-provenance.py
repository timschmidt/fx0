# SPDX-License-Identifier: MIT
"""Run pinned pmbootstrap, passing verified source identity to abuild before signing."""
from pathlib import Path
import os,subprocess,sys,functools
assert len(sys.argv)>2
expected=sys.argv[1];repo=Path('/pmaports')
head=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
assert head==expected and len(head)==40
assert not subprocess.check_output(['git','-C',str(repo),'status','--porcelain'],text=True).strip()
epoch=subprocess.check_output(['git','-C',str(repo),'show','-s','--format=%ct',head],text=True).strip();assert epoch.isdecimal()
sys.path.insert(0,'/pmbootstrap')
import pmb,pmb.chroot
original=pmb.chroot.user
@functools.wraps(original)
def with_provenance(command,*args,**kwargs):
 if command and Path(str(command[0])).name=='abuild':
  env=dict(kwargs.get('env') or {})
  assert not env.get('ABUILD_LAST_COMMIT') or env['ABUILD_LAST_COMMIT']==head
  env.update(ABUILD_LAST_COMMIT=head,SOURCE_DATE_EPOCH=epoch)
  kwargs['env']=env
  print('Verified recipe snapshot passed to abuild: '+head+'; SOURCE_DATE_EPOCH='+epoch,flush=True)
 return original(command,*args,**kwargs)
pmb.chroot.user=with_provenance
sys.argv=['/pmbootstrap/pmbootstrap.py',*sys.argv[2:]]
raise SystemExit(pmb.main())
