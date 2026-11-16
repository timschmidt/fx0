# SPDX-License-Identifier: GPL-2.0-only
"""Replay BAM callback synchronization from public source snapshots offline."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();packet=Path(__file__).resolve().parent;out=a.output.resolve();assert not out.exists() and not out.is_relative_to(packet)
manifest=json.loads((packet/'manifest.json').read_text());files={str(p.relative_to(packet)):p for p in packet.rglob('*') if p.is_file() and p.name!='manifest.json'};assert set(files)==set(manifest)
for name,path in files.items():assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==manifest[name],name
out.mkdir(mode=0o700);env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
def command(label,args,cwd=None):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=120);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,(label,r.stdout[-1000:],r.stderr[-1000:])
 if '-patch-' in label:assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()
topics=json.loads((packet/'source-topics.json').read_text());patches=0
for name,topic in topics.items():
 tree=out/name;shutil.copytree(packet/'baseline'/name,tree)
 for i,patch in enumerate(sorted((packet/'patches'/name).glob('*.patch'))):command(name+'-patch-'+str(i),['patch','--batch','--forward','--fuzz=0','-p1','-i',str(patch)],cwd=tree);patches+=1
 for path in topic['snapshot_paths']:assert (tree/path).read_bytes()==(packet/'candidate'/name/path).read_bytes(),path
assert patches==2
spec=importlib.util.spec_from_file_location('bam',packet/'tools/check-bam.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
assert m.model(out/'maintainer')[0]==m.model(out/'runtime')[0]
for label,source,before in [('before',packet/'baseline/maintainer',True),('candidate',out/'maintainer',False)]:
 command(label,[sys.executable,'-B',str(packet/'tools/check-bam.py'),str(source),str(out/label)]+(['--baseline'] if before else []));j=json.loads((out/label/'qualification.json').read_text());assert (j['cases'],j['checks'],j['failures'])==(256,3328,536 if before else 0);assert len(j['actual_function_bindings'])==(7 if before else 8)
command('controls',[sys.executable,'-B',str(packet/'tools/check-controls.py'),str(out/'maintainer'),str(out/'controls')]);j=json.loads((out/'controls/qualification.json').read_text());assert j['passed'] and [c['failures'] for c in j['controls']]==[536,536,664,792,536,536,288,120]
report=dict(passed=True,source_topics=2,patches=2,cases=256,checks=3328,before_failures=536,candidate_failures=0,controls_rejected=8,actual_callback_bodies_and_probe_assignments_bound=True,maintainer_and_runtime_models_byte_identical=True,normal_LSan_and_failfast_ASan_UBSan=True,all_tasklets_callbacks_DMA_and_owner_services_synthetic=True,actual_virt_dma_completion_body_executed=False,physical_DMA_hardware_callback_audio_phone_or_network_execution=False,native_full_kernel_module_or_DTB_build_repeated=False,full_NGD_client_or_transport_teardown_qualified=False,Git_required=False)
(out/'replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
