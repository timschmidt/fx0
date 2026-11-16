# SPDX-License-Identifier: GPL-2.0-only
"""Replay the complete CPU source and actual-function models without Git/device."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys

p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args()
packet=Path(__file__).resolve().parent;out=a.output.resolve()
assert not out.exists() and not out.is_relative_to(packet)
manifest=json.loads((packet/'manifest.json').read_text())
files={str(f.relative_to(packet)):f for f in packet.rglob('*') if f.is_file() and f.name!='manifest.json'}
assert set(files)==set(manifest)
for name,f in files.items():assert not f.is_symlink() and hashlib.sha256(f.read_bytes()).hexdigest()==manifest[name],name
out.mkdir(mode=0o700);source=out/'source';shutil.copytree(packet/'baseline',source)
def command(label,cmd,*,env=None,cwd=None):
    r=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=240)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    assert r.returncode==0,(label,r.stdout[-2000:],r.stderr[-2000:]);return r
patches=sorted((packet/'patches').glob('*.patch'));assert len(patches)==11
for i,patch in enumerate(patches):
    r=command('patch-'+str(i),['patch','--batch','--forward','--fuzz=0','-p1','-i',str(patch)],cwd=source)
    assert 'fuzz' not in r.stdout.lower()
command('companion-runtime',['patch','--batch','--forward','--fuzz=0','-p1','-i',
        str(packet/'companion/patches/runtime.patch')],cwd=source)
maintainer=out/'media-next';shutil.copytree(packet/'companion/media-next-baseline',maintainer)
command('companion-media-next',['patch','--batch','--forward','--fuzz=0','-p1','-i',
        str(packet/'companion/patches/media-next.patch')],cwd=maintainer)
for f in (packet/'companion/media-next-candidate').rglob('*'):
    if f.is_file():assert (maintainer/f.relative_to(packet/'companion/media-next-candidate')).read_bytes()==f.read_bytes(),f
for f in (packet/'candidate').rglob('*'):
    if f.is_file():assert (source/f.relative_to(packet/'candidate')).read_bytes()==f.read_bytes(),f
# ctypes numerical oracles load into Python and are labeled unsanitized;
# all standalone C models receive normal address/undefined/leak sanitizers.
toolchain=out/'toolchain';toolchain.mkdir();compiler=toolchain/'cc'
compiler.write_text('''#!/usr/bin/python3
import json,subprocess,sys
from pathlib import Path
args=sys.argv[1:];shared='-shared' in args
flags=[] if shared else ['-fsanitize=address,undefined','-fno-omit-frame-pointer','-g']
r=subprocess.run(['clang-21']+flags+args)
with (Path(__file__).resolve().parents[1]/'compilations.jsonl').open('a') as f:
 f.write(json.dumps(dict(standalone_sanitizers=not shared,ctypes_oracle_unsanitized=shared,returncode=r.returncode))+'\\n')
sys.exit(r.returncode)
''');compiler.chmod(0o700)
run=out/'run-models.py'
run.write_text('''from pathlib import Path
import json,sys,unittest
packet=Path(sys.argv[1]);out=Path(sys.argv[2]);sys.path.insert(0,str(packet/'tests'))
suite=unittest.TestLoader().loadTestsFromNames(json.loads((packet/'test-modules.json').read_text()))
r=unittest.TextTestRunner(verbosity=2).run(suite)
j=dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),passed=r.wasSuccessful())
(out/'model-results.json').write_text(json.dumps(j,indent=2)+'\\n');sys.exit(not r.wasSuccessful())
''')
env=os.environ|{'PATH':str(toolchain)+os.pathsep+os.environ['PATH'],'FX0_KERNEL_SOURCE':str(source)}
command('models',[sys.executable,'-B',str(run),str(packet),str(out)],env=env)
result=json.loads((out/'model-results.json').read_text());assert result['tests']==45 and result['skipped']==0
numeric={}
for mutation in [None,'clock-selector','conditional-minimum','read-error']:
    label='calibration-'+str(mutation or 'candidate');directory=out/label
    args=[sys.executable,'-B',str(packet/'check-calibration-sanitized.py'),str(source),str(directory)]
    if mutation:args+=['--mutation',mutation]
    command(label,args)
    j=json.loads((directory/'qualification.json').read_text())
    assert j['returncode']==(1 if mutation else 0) and not j['sanitizer_diagnostics'];numeric[label]=j
compiles=[json.loads(line) for line in (out/'compilations.jsonl').read_text().splitlines()]
assert all(j['returncode']==0 for j in compiles)
report=dict(passed=True,patches=11,model_test_methods=45,model_results=result,
 companion_runtime_and_media_next_patches=2,
 standalone_sanitizer_compilations=sum(j['standalone_sanitizers'] for j in compiles),
 ctypes_shared_oracles_unsanitized=sum(j['ctypes_oracle_unsanitized'] for j in compiles),
 calibration_cases=4068,calibration_checks=178907,calibration_controls_rejected=3,numeric=numeric,
 Git_required=False,network_or_phone_access=False,unit_fuse_data=False,
 native_full_kernel_or_schema_builds_repeated=False,physical_CPU_or_PM_acceptance=False)
(out/'replay.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['numeric','model_results']}))
