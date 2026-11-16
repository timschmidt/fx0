# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact NGD DMA setup/power callbacks with logical DMA and devres services."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
B=Path(__file__).resolve().parent
def block(text,pattern):
 m=re.search(pattern,text,re.M);assert m,pattern
 end=text.index('{',m.start())+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 if text[end:end+1]==';':end+=1
 return text[m.start():end]+'\n'
def function(text,name):return block(text,r'^static (?:int|void) '+re.escape(name)+r'\([^;{}]*\)\n\{')
def model(source):
 text=(source/'drivers/slimbus/qcom-ngd-ctrl.c').read_text();code=(B/'dma-model.c').read_text();bindings={}
 defines=[];continuing=False
 for line in text.splitlines():
  if line.startswith('#define') or continuing:defines.append(line);continuing=line.endswith('\\')
 groups={'DEFINES':'\n'.join(defines)+'\n','DMA_TYPE':block(text,r'^struct qcom_slim_ngd_dma_desc \{'),'STATE_TYPE':block(text,r'^enum qcom_slim_ngd_state \{')}
 names=['qcom_slim_ngd_post_rx_msgq','qcom_slim_ngd_init_rx_msgq','qcom_slim_ngd_init_tx_msgq','qcom_slim_ngd_init_dma','qcom_slim_ngd_exit_dma']
 groups['DMA']=''.join(function(text,n) for n in names)
 groups['POWER']=''.join(function(text,n) for n in ['qcom_slim_ngd_setup','qcom_slim_ngd_power_up'])
 groups['SETUP_ADAPTER']='static int setup(struct qcom_slim_ngd_ctrl *c) { '+('return qcom_slim_ngd_setup(c);' if 'static int qcom_slim_ngd_setup(' in text else 'qcom_slim_ngd_setup(c); return 0;')+' }\n'
 for k,v in groups.items():assert code.count('/* ACTUAL_'+k+' */')==1;code=code.replace('/* ACTUAL_'+k+' */',v)
 for n in names+['qcom_slim_ngd_setup','qcom_slim_ngd_power_up']:
  assert function(code,n)==function(text,n);bindings[n]=hashlib.sha256(function(text,n).encode()).hexdigest()
 return code,bindings
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();assert not a.output.exists();a.output.mkdir()
 code,bindings=model(a.source);src=a.output/'model.c';src.write_text(code);binary=a.output/'model'
 c=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-but-set-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60)
 (a.output/'build.log').write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None)
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);j.update(actual_callback_bodies_preserved=True,actual_function_bindings=bindings,generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,DMA_MMIO_devres_completions_QMI_and_hardware_services_synthetic=True,no_callbacks_or_kernel_DMA_executed=True,fixture_keeps_allocations_alive_until_after_logical_audit=True,audio_execution=False,phone_access=False)
 (a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');assert j['failures']>0 if a.baseline else j['failures']==0,j
 print(json.dumps({k:j[k] for k in ['cases','checks','failures']}))
