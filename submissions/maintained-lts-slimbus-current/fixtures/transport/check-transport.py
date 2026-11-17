# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact NGD callbacks with logical DMA, work, PM and lifetime services."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
B=Path(__file__).resolve().parent
def block(text,pattern):
 m=re.search(pattern,text,re.M);assert m,pattern;end=text.index('{',m.start())+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 if text[end:end+1]==';':end+=1
 return text[m.start():end]+'\n'
def function(text,name):return block(text,r'^(?:(?:static|inline) )*(?:int|void|bool|u32 \*)\s*(?:__maybe_unused )?'+re.escape(name)+r'\([^;{}]*\)\n\{')
def model(source):
 driver=(source/'drivers/slimbus/qcom-ngd-ctrl.c').read_text();internal=(source/'drivers/slimbus/slimbus.h').read_text();public=(source/'include/linux/slimbus.h').read_text();code=(B/'transport-model.c').read_text();bindings={};defines=[]
 for text in [driver,internal,public]:
  for m in re.finditer(r'^#define[ \t]+([A-Za-z_]\w*)(?:[^\n]*\\\n)*[^\n]*',text,re.M):
   name=m.group(1)
   if name.startswith(('SLIM_','NGD_','SAT_')) or name in ['QCOM_SLIM_NGD_DESC_NUM','INIT_MX_RETRIES','DEF_RETRY_MS']:defines.append(m.group(0))
 code=code.replace('/* ACTUAL_DEFINES */','\n'.join(defines))
 types=[block(driver,r'^struct qcom_slim_ngd_dma_desc \{'),block(driver,r'^enum qcom_slim_ngd_state \{'),block(internal,r'^struct slim_msg_txn \{'),block(public,r'^struct slim_val_inf \{')];code=code.replace('/* ACTUAL_TYPES */',''.join(types))
 groups={'LOW':['qcom_slim_ngd_tx_msg_get','qcom_slim_ngd_tx_msg_put','qcom_slim_ngd_tx_msg_dma_cb','qcom_slim_ngd_tx_msg_post'],'RX':['qcom_slim_ngd_rx','qcom_slim_ngd_rx_msgq_cb','qcom_slim_ngd_post_rx_msgq'],'INIT':['qcom_slim_ngd_init_rx_msgq','qcom_slim_ngd_init_tx_msgq','qcom_slim_ngd_init_dma'],'XFER':['qcom_slim_ngd_xfer_msg'],'LIFE':['qcom_slim_ngd_exit_dma','qcom_slim_ngd_setup'],'MASTER':['qcom_slim_ngd_master_worker'],'RESUME':['qcom_slim_ngd_runtime_resume'],'DOWN':['qcom_slim_ngd_down'],'NOTIFY':['qcom_slim_ngd_ssr_pdr_notify'],'REMOVE':['qcom_slim_ngd_remove']}
 groups['SLAVE']=['qcom_slim_ngd_slave_worker'] if 'static void qcom_slim_ngd_slave_worker(' in driver else []
 for marker,names in groups.items():
  assert code.count('/* ACTUAL_'+marker+' */')==1;code=code.replace('/* ACTUAL_'+marker+' */',''.join(function(driver,n) for n in names))
  for name in names:assert function(code,name)==function(driver,name);bindings[name]=hashlib.sha256(function(driver,name).encode()).hexdigest()
 for name in ['slim_tid_txn','slim_ec_txn']:
  body=function(internal,name);code=code.replace('/* ACTUAL_'+name+' */',body);bindings[name]=hashlib.sha256(body.encode()).hexdigest()
 code='#define FIXTURE_ADMISSION '+str(int('struct mutex dma_lock;' in driver))+'\n'+code;return code,bindings
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();assert not a.output.exists();a.output.mkdir();code,bindings=model(a.source);src=a.output/'model.c';src.write_text(code)
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(a.output/'model')],capture_output=True,text=True,timeout=60);(a.output/'build.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);r=subprocess.run([str(a.output/'model')],capture_output=True,text=True,env=env,timeout=45);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr[-1600:];assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);j.update(actual_function_bindings=bindings,actual_callback_bodies_byte_exact=True,generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,DMA_PM_MMIO_workqueue_and_TID_services_synthetic=True,record_and_completion_storage_kept_physically_live_for_logical_audit=True,no_real_kernel_DMA_firmware_audio_phone_or_network_execution=True,attached_hardware_engine_stop_or_full_transport_recovery_qualified=False);(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');assert j['failures']>0 if a.baseline else j['failures']==0,j;print(json.dumps({k:j[k] for k in ['cases','checks','failures']}))
