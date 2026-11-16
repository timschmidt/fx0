# SPDX-License-Identifier: GPL-2.0-only
"""Replay synchronous SLIMbus response and TX ownership offline."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,shutil,subprocess,sys
p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=Path);a=p.parse_args();packet=Path(__file__).resolve().parent;out=a.output.resolve();assert not out.exists() and not out.is_relative_to(packet)
manifest=json.loads((packet/'manifest.json').read_text());files={str(p.relative_to(packet)):p for p in packet.rglob('*') if p.is_file() and p.name!='manifest.json'};assert set(files)==set(manifest)
for name,path in files.items():assert not path.is_symlink() and hashlib.sha256(path.read_bytes()).hexdigest()==manifest[name],name
out.mkdir(mode=0o700);env=os.environ|{'PYTHONDONTWRITEBYTECODE':'1','ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
def command(label,args,cwd=None):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=180);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,(label,r.stdout[-1000:],r.stderr[-1000:])
 if '-patch-' in label:assert 'fuzz' not in r.stdout.lower() and 'offset' not in r.stdout.lower()
topics=json.loads((packet/'source-topics.json').read_text());patches=0
for name,topic in topics.items():
 tree=out/name;shutil.copytree(packet/'baseline'/name,tree)
 for i,patch in enumerate(sorted((packet/'patches'/name).glob('*.patch'))):
  command(name+'-patch-'+str(i),['patch','--batch','--forward','--fuzz=0','-p1','-i',str(patch)],cwd=tree);patches+=1
  prefix='TX-baseline' if i==10 else ('response-baseline' if i==11 else None)
  if name=='maintainer' and prefix:
   for p in (packet/prefix).rglob('*'):
    if p.is_file():assert (tree/p.relative_to(packet/prefix)).read_bytes()==p.read_bytes()
 for path in topic['snapshot_paths']:assert (tree/path).read_bytes()==(packet/'candidate'/name/path).read_bytes(),path
assert patches==14
def load(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
response=load('response',packet/'tools/check-response.py');tx=load('tx',packet/'tools/TX/check-tx.py')
assert response.model(out/'maintainer')[0]==response.model(out/'runtime')[0]
assert tx.model(out/'maintainer')[0]==tx.model(out/'runtime')[0]
for label,source,before in [('response-before',packet/'response-baseline',True),('response-candidate',out/'maintainer',False)]:
 command(label,[sys.executable,'-B',str(packet/'tools/check-response.py'),str(source),str(out/label)]+(['--baseline'] if before else []));j=json.loads((out/label/'qualification.json').read_text());assert (j['cases'],j['checks'],j['failures'])==(1022,41774,2061 if before else 0);assert len(j['actual_function_bindings'])==(12 if before else 13)
command('response-controls',[sys.executable,'-B',str(packet/'tools/check-controls.py'),str(out/'maintainer'),str(out/'response-controls')]);j=json.loads((out/'response-controls/qualification.json').read_text());assert j['passed'] and [c['failures'] for c in j['controls']]==[12,2,258,8,192,30,588,3,252,192,362,863,131,414,414,9]
for label,source,before in [('TX-before',packet/'TX-baseline',True),('TX-candidate',out/'maintainer',False)]:
 command(label,[sys.executable,'-B',str(packet/'tools/TX/check-tx.py'),str(source),str(out/label)]+(['--baseline'] if before else []));j=json.loads((out/label/'qualification.json').read_text());assert (j['cases'],j['checks'],j['failures'])==(1093,47497,2757 if before else 0);assert len(j['actual_function_bindings'])==(6 if before else 7)
command('TX-controls',[sys.executable,'-B',str(packet/'tools/TX/check-controls.py'),str(out/'maintainer'),str(out/'TX-controls')]);j=json.loads((out/'TX-controls/qualification.json').read_text());assert j['passed'] and [c['failures'] for c in j['controls']]==[960,1024,1796,1091,1090,576,960,450,1796,770,801,128]
before=(out/'TX-before/wire.bin').read_bytes();after=(out/'TX-candidate/wire.bin').read_bytes();assert before==after and len(after)==41147
assert hashlib.sha256(after).hexdigest()=='2a559250271d63398ebfc2ba805da62d0417a7520bf8725ead3c209ab67015ca'
report=dict(passed=True,source_topics=2,patches=14,response_cases=1022,response_checks=41774,response_before_failures=2061,response_candidate_failures=0,response_controls_rejected=16,TX_cases=1093,TX_checks=47497,TX_before_failures=2757,TX_candidate_failures=0,TX_controls_rejected=12,total_controls_rejected=28,
 actual_callback_bodies_message_helpers_types_and_constants_bound=True,maintainer_and_runtime_models_byte_identical=True,
 packet_trace_bytes=41147,packet_trace_SHA256=hashlib.sha256(after).hexdigest(),packet_trace_bytes_identical=True,
 normal_LSan_and_failfast_ASan_UBSan=True,IDR_PM_completion_DMA_response_services_synthetic=True,
 real_kernel_framework_DMA_audio_phone_or_network_execution=False,native_full_kernel_module_or_DTB_build_repeated=False,
 exported_async_stack_transaction_wire_generation_and_full_transport_quiescence_qualified=False,Git_required=False)
(out/'replay.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
