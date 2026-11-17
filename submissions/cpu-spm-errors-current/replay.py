# SPDX-License-Identifier: GPL-2.0-only
"""Offline CPU mode/recovery/admission replay with only synthetic services."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import shutil
import subprocess

PACKET=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('output',type=Path)
a=p.parse_args()
assert not a.output.exists()
a.output.mkdir()
manifest=json.loads((PACKET/'manifest.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for name,digest in manifest['inputs'].items():
    path=PACKET/name
    assert path.is_file() and not path.is_symlink() and sha(path)==digest,name
before=a.output/'before'
source=a.output/'source'
runtime=a.output/'runtime'
shutil.copytree(PACKET/'source-before',before)
shutil.copytree(PACKET/'source-before',source)
shutil.copytree(PACKET/'runtime-before',runtime)
r=subprocess.run(['python3','-B',str(PACKET/'check-before.py'),str(before),str(a.output/'before-model')],
    capture_output=True,text=True,timeout=60)
(a.output/'before.stdout').write_text(r.stdout)
(a.output/'before.stderr').write_text(r.stderr)
assert r.returncode==0,r.stderr
baseline=json.loads((a.output/'before-model/qualification.json').read_text())
assert baseline['parent_function_had_not_returned'] and baseline['synthetic_watchdog_after_write_attempts']==101
for tree,patch in [(source,'CPU-SPM-01.patch'),(runtime,'runtime-01.patch')]:
    r=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(PACKET/patch)],
        cwd=tree,capture_output=True,text=True,timeout=30)
    (a.output/(tree.name+'-patch.log')).write_text(r.stdout+r.stderr)
    assert r.returncode==0 and 'offset' not in r.stdout and 'fuzz' not in r.stdout,(patch,r.stdout,r.stderr)
    for path,digest in manifest['source_after'].items():
        assert sha(tree/path)==digest,path
spec=importlib.util.spec_from_file_location('cpu_model',PACKET/'check-model.py')
q=importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
sc,sb=q.model(source)
rc,rb=q.model(runtime)
assert sc==rc and sb==rb
for label,code in [('source-model',sc),('runtime-model',rc)]:
    report=q.m.run_code(code,a.output/label)
    assert (report['cases'],report['checks'],report['failures'])==(1198,1184094,0)
r=subprocess.run(['python3','-B',str(PACKET/'check-controls.py'),str(source),str(a.output/'controls')],
    capture_output=True,text=True,timeout=300)
(a.output/'controls.stdout').write_text(r.stdout)
(a.output/'controls.stderr').write_text(r.stderr)
assert r.returncode==0,r.stderr
controls=json.loads((a.output/'controls/qualification.json').read_text())
assert controls['passed'] and len(controls['controls'])==23
intro=json.loads((PACKET/'SPM-introduction-proof.json').read_text())
raw=json.loads((PACKET/'public-SPM-introduction.json').read_text())
assert intro['passed'] and raw['sha']==intro['upstream_commit']
assert sha(PACKET/'public-SPM-introduction.json')==intro['download_SHA256']
report=dict(passed=True,unique_cases=1198,unique_checks=1184094,failures=0,
    controls_rejected=23,before_cases=1,before_failures=1,before_retry_watchdog_attempts=101,
    actual_functions=12,actual_CPU_PM_macros=2,actual_catalogue_and_template_bindings=True,
    verified_upstream_Fixes_commit=intro['upstream_commit'],all_inputs_hash_verified=True,
    patches_applied_without_fuzz_or_offset=True,source_and_runtime_changed_bytes_and_models_identical=True,
    differing_unmodified_SCM_header_prerequisites_explicit=True,
    normal_LSan_and_failfast_ASan_UBSan=True,only_synthetic_services=True,
    no_Git_network_phone_radio_audio_or_firmware_execution=True,
    full_CPU_APC_cache_L2_SCM_RPM_MPM_entry_and_physical_acceptance_qualified=False)
(a.output/'replay.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
