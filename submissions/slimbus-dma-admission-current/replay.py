# SPDX-License-Identifier: GPL-2.0-only
"""Replay NGD software shutdown with its BAM callback-barrier prerequisite."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys
sys.dont_write_bytecode=True
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();packet=Path(__file__).resolve().parent;out=a.output.resolve();assert not out.exists() and not out.is_relative_to(packet)
read=lambda p:json.loads(p.read_text());manifest=read(packet/'manifest.json');files={str(p.relative_to(packet)):p for p in packet.rglob('*') if p.is_file() and p.name!='manifest.json'};assert set(files)==set(manifest)
for name,path in files.items():assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==manifest[name],name
out.mkdir(mode=0o700);env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
def command(label,args,cwd=None):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=240);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,(label,r.stdout[-1000:],r.stderr[-1000:])
 if '-patch-' in label:assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()
topics=read(packet/'source-topics.json');patches=0
for name,topic in topics.items():
 tree=out/name;shutil.copytree(packet/'baseline'/name,tree)
 for i,patch in enumerate(sorted((packet/'patches'/name).glob('*.patch'))):
  command(name+'-patch-'+str(i),['patch','--batch','--forward','--fuzz=0','-p1','-i',str(patch)],cwd=tree);patches+=1
  prefix={10:'TX-baseline',12:'response-baseline',13:'transport-baseline'}.get(i)
  if name=='maintainer' and prefix:
   for p in (packet/prefix).rglob('*'):
    if p.is_file():assert (tree/p.relative_to(packet/prefix)).read_bytes()==p.read_bytes()
 for path in topic['snapshot_paths']:assert (tree/path).read_bytes()==(packet/'candidate'/name/path).read_bytes(),path
assert patches==17
models=[('transport','check-transport.py'),('response','response/check-response.py'),('TX','TX/check-tx.py'),('QMI','QMI/check-qmi.py'),('power','power/check-power.py'),('DMA','DMA/check-dma.py'),('bookkeeping','bookkeeping/check-lifecycle.py'),('ownership','ownership/check-ownership.py')]
for name,path in models:
 spec=importlib.util.spec_from_file_location(name,packet/'tools'/path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);assert m.model(out/'maintainer')[0]==m.model(out/'runtime')[0]
spec=importlib.util.spec_from_file_location('BAM',packet/'tools/BAM/check-bam.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);assert m.model(out/'BAM')[0]==m.model(out/'runtime')[0]
def qualify(label,script,source,expected,extra=[]):
 command(label,[sys.executable,'-B',str(packet/'tools'/script),str(source),str(out/label)]+extra);j=read(out/label/'qualification.json');assert (j['cases'],j['checks'],j['failures'])==expected,(label,j);return j
before=qualify('transport-before','check-transport.py',packet/'transport-baseline',(96,1369,241),['--baseline']);after=qualify('transport-candidate','check-transport.py',out/'maintainer',(96,1375,0));assert len(before['actual_function_bindings'])==20 and len(after['actual_function_bindings'])==21
qualify('response-before','response/check-response.py',packet/'response-baseline',(1149,44421,102),['--baseline']);qualify('response-candidate','response/check-response.py',out/'maintainer',(1149,44419,0))
qualify('QMI','QMI/check-qmi.py',out/'maintainer',(71,1079,0));qualify('power','power/check-power.py',out/'maintainer',(626,13284,0));qualify('power-LTS-PM','power/check-power.py',out/'maintainer',(626,12708,0),['--PM-source',str(packet/'PM-LTS-source')]);qualify('DMA','DMA/check-dma.py',out/'maintainer',(85,1150,0));qualify('bookkeeping','bookkeeping/check-lifecycle.py',out/'maintainer',(21,153,0));qualify('ownership','ownership/check-ownership.py',out/'maintainer',(10,114,0))
qualify('TX-before','TX/check-tx.py',packet/'TX-baseline',(1093,47497,2757),['--baseline']);qualify('TX-candidate','TX/check-tx.py',out/'maintainer',(1093,47497,0));qualify('BAM-before','BAM/check-bam.py',packet/'baseline/BAM',(256,3328,536),['--baseline']);qualify('BAM-candidate','BAM/check-bam.py',out/'BAM',(256,3328,0))
controls=0
for label,script,evidence,tree in [('transport-controls','check-controls.py','controls-02','maintainer'),('response-controls','response/check-controls.py','response-controls-01','maintainer'),('QMI-controls','QMI/check-controls.py','QMI-controls-01','maintainer'),('power-controls','power/check-controls.py','power-controls-02','maintainer'),('DMA-controls','DMA/check-controls.py','DMA-controls-03','maintainer'),('bookkeeping-controls','bookkeeping/check-controls.py','bookkeeping-controls-01','maintainer'),('TX-controls','TX/check-controls.py','TX-controls-01','maintainer'),('ownership-controls','ownership/check-controls.py','ownership-controls-01','maintainer'),('BAM-controls','BAM/check-controls.py','BAM-controls-02','BAM')]:
 command(label,[sys.executable,'-B',str(packet/'tools'/script),str(out/tree),str(out/label)]);j=read(out/label/'qualification.json');expected=read(packet/'evidence'/(evidence+'.json'));assert j['passed'] and len(j['controls'])==len(expected['controls'])
 if label=='transport-controls':
  assert [c['control'] for c in j['controls']]==[c['control'] for c in expected['controls']]
  assert all(c['rejected'] and c['failures_observed']>0 and not c['sanitizer_diagnostics'] for c in j['controls'])
 else:assert [c['failures'] for c in j['controls']]==[c['failures'] for c in expected['controls']]
 controls+=len(j['controls'])
assert controls==133
before=(out/'TX-before/wire.bin').read_bytes();after=(out/'TX-candidate/wire.bin').read_bytes();assert before==after and len(after)==41147;digest=hashlib.sha256(after).hexdigest();assert digest=='2a559250271d63398ebfc2ba805da62d0417a7520bf8725ead3c209ab67015ca'
report=dict(passed=True,source_topics=3,patches=17,transport_cases=96,transport_checks=1375,transport_before_checks=1369,transport_before_failures=241,transport_candidate_failures=0,transport_controls_rejected=28,total_controls_rejected=133,prior_response_readiness_PM_DMA_bookkeeping_reference_and_TX_regressions_pass=True,BAM_provider_prerequisite_replayed=True,maintainer_runtime_and_BAM_generated_model_bindings_verified=True,packet_trace_bytes=41147,packet_trace_SHA256=digest,packet_trace_bytes_identical=True,normal_LSan_and_failfast_ASan_UBSan=True,all_kernel_services_and_lifetime_observations_synthetic=True,unsafe_control_waits_or_invalid_provider_access_detected_without_execution=True,real_kernel_framework_DMA_audio_phone_or_network_execution=False,native_full_kernel_module_or_DTB_build_repeated=False,attached_hardware_engine_stop_full_failure_recovery_and_wire_generation_qualified=False,Git_required=False)
(out/'replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
