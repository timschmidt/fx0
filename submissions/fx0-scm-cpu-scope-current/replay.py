# SPDX-License-Identifier: GPL-2.0-only
"""Git-free SCM source/transport replay; no actual SMC or device access."""
from pathlib import Path
import argparse
import hashlib
import json
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
assert 'int qcom_scm_legacy_fuse_read(' not in (source/'drivers/firmware/qcom/qcom_scm.c').read_text()
def command(label,args):
    r=subprocess.run(args,capture_output=True,text=True,timeout=120,cwd=source)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    assert r.returncode==0,(label,r.stdout[-2000:],r.stderr[-2000:])
    return r
patches=list((packet/'patches').glob('*.patch'));assert len(patches)==1
r=command('apply',['patch','--batch','--forward','--fuzz=0','-p1','-i',str(patches[0])]);assert 'fuzz' not in r.stdout.lower()
for f in (packet/'candidate').rglob('*'):
    if f.is_file():assert (source/f.relative_to(packet/'candidate')).read_bytes()==f.read_bytes(),f
expected=json.loads((packet/'qualification.json').read_text())['models'];results={}
variants=[('wire','check-SCM-wire.py',[]),('API','check-SCM-API.py',[])]
variants += [(m,'check-SCM-wire.py',['--mutation',m]) for m in ['wrong-command','swapped-words','ignored-status','early-output','nonlegacy','alignment']]
for label,script,options in variants:
    directory=out/label;command(label,[sys.executable,'-B',str(packet/script),str(source),str(directory)]+options)
    j=json.loads((directory/'qualification.json').read_text());ref=expected[label]
    assert j['returncode']==ref['returncode'] and not j['sanitizer_diagnostics'],label
    assert j['program_SHA256']==ref['program_SHA256'],label
    if label!='API':assert (j['cases'],j['checks'],j['failures'])==(ref['cases'],ref['checks'],ref['failures']),label
    results[label]=j
report=dict(passed=True,model_variants=len(results),wire_cases=667,wire_checks=34017,
            captured_API_cases=13,regression_controls_rejected=6,models=results,
            Git_required=False,network_or_phone_access=False,actual_SMC_or_DMA=False,
            native_builds_repeated=False,full_CPU_CPR_qualification=False)
(out/'replay.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='models'}))
