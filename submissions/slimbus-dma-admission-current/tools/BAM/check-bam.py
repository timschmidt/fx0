# SPDX-License-Identifier: GPL-2.0-only
"""Qualify exact BAM termination/synchronization callbacks with logical tasklets."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
B=Path(__file__).resolve().parent

def function(text,name):
 m=re.search(r'^(?:(?:static|inline) )*(?:int|void) '+re.escape(name)+r'\([^;{}]*\)\n\{',text,re.M);assert m,name
 end=text.index('{',m.start())+1;depth=1
 while depth:
  depth+=(text[end]=='{')-(text[end]=='}');end+=1
 return text[m.start():end]+'\n'

def model(source):
 bam=(source/'drivers/dma/qcom/bam_dma.c').read_text();virt=(source/'drivers/dma/virt-dma.h').read_text();vc=(source/'drivers/dma/virt-dma.c').read_text();api=(source/'include/linux/dmaengine.h').read_text()
 groups={'API':(api,['dmaengine_terminate_async','dmaengine_synchronize','dmaengine_terminate_sync']),'VCHAN_GET_ALL':(virt,['vchan_get_all_descriptors']),'VCHAN_FREE':(vc,['vchan_dma_desc_free_list']),'VCHAN_SYNC':(virt,['vchan_synchronize']),'BAM_TERMINATE':(bam,['bam_dma_terminate_all']),'BAM_SYNC':(bam,['bam_dma_synchronize'] if 'static void bam_dma_synchronize(' in bam else [])}
 code=(B/'bam-model.c').read_text();bindings={}
 for marker,(text,names) in groups.items():
  bodies=''.join(function(text,n) for n in names);assert code.count('/* ACTUAL_'+marker+' */')==1;code=code.replace('/* ACTUAL_'+marker+' */',bodies)
  for name in names:assert function(code,name)==function(text,name);bindings[name]=hashlib.sha256(function(text,name).encode()).hexdigest()
 probe=function(bam,'bam_dma_probe');assignments=[]
 for op in ['terminate_all','synchronize']:
  lines=re.findall(r'^\tbdev->common\.device_'+op+r' = [a-z_]+;$',probe,re.M);assert len(lines)==(1 if op=='terminate_all' or groups['BAM_SYNC'][1] else 0),(op,lines)
  assignments+=lines
 code=code.replace('/* ACTUAL_PROBE_OPS */','\n'.join(assignments));return code,bindings,assignments

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();assert not a.output.exists();a.output.mkdir()
 code,bindings,ops=model(a.source);src=a.output/'model.c';src.write_text(code);binary=a.output/'model'
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60);(a.output/'build.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(s in r.stderr for s in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);j.update(actual_function_bindings=bindings,actual_probe_assignments=ops,callback_bodies_byte_exact=True,generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,tasklet_scheduler_and_DMA_hardware_synthetic=True,callback_storage_retained_until_logical_audit=True,unsafe_lock_mutation_logged_without_intentional_deadlock=True,real_hardware_DMA_callback_audio_network_or_phone_execution=False)
 (a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');assert (j['failures']>0 if a.baseline else j['failures']==0),j;print(json.dumps({k:j[k] for k in ['cases','checks','failures']}))
