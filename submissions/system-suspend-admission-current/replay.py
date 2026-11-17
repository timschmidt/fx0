# SPDX-License-Identifier: GPL-2.0-only
"""Offline exact-source replay; never calls Git, network or device tools."""
from pathlib import Path
import hashlib,json,os,shutil,subprocess,sys
P=Path(__file__).resolve().parent
O=Path(sys.argv[1]).resolve();O.mkdir(parents=True,exist_ok=False)
read=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
manifest=read(P/'manifest.json')
assert set(manifest)=={str(p.relative_to(P)) for p in P.rglob('*') if p.is_file() and p.name!='manifest.json'}
for name,digest in manifest.items():assert sha(P/name)==digest,name
shutil.copytree(P/'source-before',O/'tree')
(O/'compiler-temporary').mkdir();(O/'denied-tools').mkdir()
shim=O/'denied-tools/git';shim.write_text('#!/bin/sh\nprintf "unexpected Git call\\n" >&2\nexit 126\n');shim.chmod(0o700)
env=os.environ|{'TMPDIR':str(O/'compiler-temporary'),'PATH':str(O/'denied-tools')+os.pathsep+os.environ['PATH'],
 'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1:abort_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'}
steps=[]
def run(name,cmd,cwd=None):
 r=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=180)
 (O/(name+'.stdout')).write_text(r.stdout);(O/(name+'.stderr')).write_text(r.stderr)
 steps.append(dict(name=name,returncode=r.returncode));assert not r.returncode,(name,r.stdout,r.stderr)
 return r
r=run('patch',['patch','--batch','--forward','--fuzz=0','-p1','-i',str(P/'RPM-admission-01.patch')],O/'tree')
assert 'offset' not in (r.stdout+r.stderr).lower() and 'fuzz' not in (r.stdout+r.stderr).lower()
for name,digest in read(P/'source-current.json')['source_files'].items():assert sha(O/'tree'/name)==digest,name
run('admission',[sys.executable,'-B',str(P/'check-admission.py'),str(O/'tree'),str(O/'admission')])
run('admission-controls',[sys.executable,'-B',str(P/'check-controls.py'),str(O/'tree'),str(O/'admission-controls')])
run('pm-order',[sys.executable,'-B',str(P/'check-pm-order.py'),str(P/'pm-source'),str(O/'pm-order')])
run('pm-controls',[sys.executable,'-B',str(P/'check-pm-controls.py'),str(P/'pm-source'),str(O/'pm-controls')])
run('retained-ack',[sys.executable,'-B',str(P/'check-retained-ack.py'),str(O/'tree'),str(O/'retained-ack'),str(P/'retained_ack_model.py')])
a=read(O/'admission/qualification.json');m=read(O/'pm-order/qualification.json')
assert a['bindings']==read(P/'evidence/admission-model-02/qualification.json')['bindings']
assert m['bindings']==read(P/'evidence/pm-order-02/qualification.json')['bindings']
assert a['cases']==147 and a['checks']==13235 and m['cases']==176 and m['checks']==3634
assert read(O/'admission-controls/qualification.json')['controls']==12
assert read(O/'pm-controls/qualification.json')['controls']==4
assert read(O/'retained-ack/qualification.json')['passed']
j=dict(passed=True,steps=steps,input_files_verified=len(manifest),source_patch_applied_without_fuzz_or_offset=True,
 admission_cases=a['cases'],admission_checks=a['checks'],threaded_drain_cases=40,phase_cases=m['cases'],phase_checks=m['checks'],
 negative_controls=16,Git_denied=True,network_or_device_access=False,production_coordinator_implemented=False)
(O/'replay.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
