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
module_signer=os.environ.get('FX0_KERNEL_MODULE_SIGNING_KEY')
if module_signer is not None:
 assert module_signer and Path(module_signer).is_absolute(), 'Module signer must be an absolute path inside the build chroot'
 assert '\n' not in module_signer and '\r' not in module_signer
sys.path.insert(0,'/pmbootstrap')
import pmb,pmb.chroot
original=pmb.chroot.user
@functools.wraps(original)
def with_provenance(command,*args,**kwargs):
 if command and Path(str(command[0])).name=='abuild':
  env=dict(kwargs.get('env') or {})
  assert not env.get('ABUILD_LAST_COMMIT') or env['ABUILD_LAST_COMMIT']==head
  env.update(ABUILD_LAST_COMMIT=head,SOURCE_DATE_EPOCH=epoch)
  if module_signer is not None:
   assert not env.get('FX0_KERNEL_MODULE_SIGNING_KEY') or env['FX0_KERNEL_MODULE_SIGNING_KEY']==module_signer
   env['FX0_KERNEL_MODULE_SIGNING_KEY']=module_signer
  kwargs['env']=env
  print('Verified recipe snapshot passed to abuild: '+head+'; SOURCE_DATE_EPOCH='+epoch,flush=True)
 return original(command,*args,**kwargs)
pmb.chroot.user=with_provenance
sys.argv=['/pmbootstrap/pmbootstrap.py',*sys.argv[2:]]
raise SystemExit(pmb.main())
