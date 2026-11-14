# SPDX-License-Identifier: MIT
from pathlib import Path
import os,sys,runpy,json
sys.path.insert(0,'/pmbootstrap')
import pmb,pmb.chroot
head=os.environ['EXPECTED_RECIPE']
results=[]
def one(label,key,expected_code):
 calls=[]
 def capture(command,*args,**kwargs):
  calls.append(dict(command=command,kwargs=kwargs));return 'captured'
 pmb.chroot.user=capture
 def main():
  assert pmb.chroot.user(['abuild','-d'],env={'EXISTING':'preserved'})=='captured'
  assert pmb.chroot.user(['echo','noop'],env={'UNCHANGED':'value'})=='captured'
  return 7
 pmb.main=main
 if key is None:os.environ.pop('FX0_KERNEL_MODULE_SIGNING_KEY',None)
 else:os.environ['FX0_KERNEL_MODULE_SIGNING_KEY']=key
 sys.argv=['wrapper.py',head,'--as-root','build']
 try:runpy.run_path('/test-inputs/wrapper.py',run_name='__main__')
 except SystemExit as exc:code=exc.code
 except AssertionError:code='assertion'
 else:raise AssertionError('Expected wrapper exit')
 assert code==expected_code,(label,code)
 if expected_code==7:
  assert len(calls)==2
  env=calls[0]['kwargs']['env'];assert env['ABUILD_LAST_COMMIT']==head and env['SOURCE_DATE_EPOCH'].isdecimal() and env['EXISTING']=='preserved'
  assert env.get('FX0_KERNEL_MODULE_SIGNING_KEY')==key
  assert calls[1]['kwargs']['env']=={'UNCHANGED':'value'}
 else:assert calls==[]
 results.append(dict(case=label,passed=True,key_bodies_opened=False))
one('optional_absent',None,7)
one('absolute_path_with_spaces','/run/private signing/module key.pem',7)
one('relative_path_rejected','relative/key.pem','assertion')
one('newline_path_rejected','/run/key\n.pem','assertion')
Path('/results/verification.json').write_text(json.dumps(dict(cases=results,real_pmbootstrap_imported=True,actual_wrapper_executed=True,only_final_pmbootstrap_main_and_underlying_chroot_dispatch_stubbed=True,no_build_or_key_reads=True),indent=2)+'\n')
print('Actual provenance wrapper: four forwarding/default/refusal cases pass; return status and non-abuild calls preserved.')
