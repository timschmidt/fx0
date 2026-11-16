# SPDX-License-Identifier: GPL-2.0-only
"""Reject modeled provider dispatch, scope, ordering and locking regressions."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('bam',B/'check-bam.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir()
code,_,_=m.model(a.source);changes=[]
def change(name,old,new,expected):
 assert code.count(old)==1,(name,code.count(old));assert old!=new;changes.append((name,code.replace(old,new),expected))
helper=m.function(code,'bam_dma_synchronize');sync=m.function(code,'vchan_synchronize');getall=m.function(code,'vchan_get_all_descriptors');api=m.function(code,'dmaengine_terminate_sync')
active='selected-0-api-0-state-0-descriptors-0-active-1-peer-0'
change('missing-provider-registration','\tbdev->common.device_synchronize = bam_dma_synchronize;','',active)
change('missing-provider-barrier',helper,helper.replace('\tvchan_synchronize(to_virt_chan(chan));',''),active)
change('wrong-channel-barrier',helper,helper.replace('to_virt_chan(chan)','&channels[selected_channel ^ 1].vc'),active)
change('shared-tasklet-instead-of-channel',helper,helper.replace('vchan_synchronize(to_virt_chan(chan))','tasklet_kill(&to_bam_chan(chan)->bdev->task)'),active)
change('missing-tasklet-drain',sync,sync.replace('\ttasklet_kill(&vc->task);\n',''),active)
change('barrier-under-channel-lock',helper,helper.replace('\tvchan_synchronize(to_virt_chan(chan));','\tunsigned long flags;\n\tspin_lock_irqsave(&to_virt_chan(chan)->lock, flags);\n\tvchan_synchronize(to_virt_chan(chan));\n\tspin_unlock_irqrestore(&to_virt_chan(chan)->lock, flags);'),active)
change('issued-descriptors-not-terminated',getall,getall.replace('\tlist_splice_tail_init(&vc->desc_issued, head);\n',''),'selected-0-api-0-state-3-descriptors-1-active-0-peer-0')
reordered=api.replace('\tdmaengine_synchronize(chan);\n','').replace('\tret = dmaengine_terminate_async(chan);','\tdmaengine_synchronize(chan);\n\tret = dmaengine_terminate_async(chan);')
change('synchronization-before-termination',api,reordered,'selected-0-api-0-state-3-descriptors-1-active-0-peer-0')
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for name,text,expected in changes:
 src=a.output/(name+'.c');src.write_text(text);binary=a.output/name
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60)
 (a.output/(name+'-build.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(name+'.stdout')).write_text(r.stdout);(a.output/(name+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);assert (j['cases'],j['checks'])==(256,3328) and j['failures']>0 and expected+':' in r.stderr,(name,j)
 records.append(dict(control=name,failures=j['failures'],expected_case=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,unsafe_lock_contract_logged_without_intentional_deadlock=True,all_kernel_services_and_DMA_synthetic=True,hardware_audio_network_or_phone_execution=False),indent=2)+'\n');print(json.dumps(records))
