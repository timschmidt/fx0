# SPDX-License-Identifier: GPL-2.0-only
"""Execute exact TX callbacks with logical completion and DMA ownership services."""
from pathlib import Path
import argparse,hashlib,json,os,re,subprocess
B=Path(__file__).resolve().parent

def block(text,pattern):
 m=re.search(pattern,text,re.M);assert m,pattern;end=text.index('{',m.start())+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 if text[end:end+1]==';':end+=1
 return text[m.start():end]+'\n'
def function(text,name):return block(text,r'^(?:(?:static|inline) )*(?:int|void|bool|u32 \*)\s*'+re.escape(name)+r'\([^;{}]*\)\n\{')
def model(source):
 driver=(source/'drivers/slimbus/qcom-ngd-ctrl.c').read_text();internal=(source/'drivers/slimbus/slimbus.h').read_text();public=(source/'include/linux/slimbus.h').read_text();code=(B/'tx-model.c').read_text();bindings={}
 defines=[]
 for text in [driver,internal,public]:
  for m in re.finditer(r'^#define[ \t]+([A-Za-z_]\w*)(?:[^\n]*\\\n)*[^\n]*',text,re.M):
   name=m.group(1)
   if name.startswith(('SLIM_MSG_','SLIM_USR_')) or name in ['SLIM_LA_MGR','SLIM_MSGQ_BUF_LEN','QCOM_SLIM_NGD_DESC_NUM']:defines.append(m.group(0))
 code=code.replace('/* ACTUAL_DEFINES */','\n'.join(defines))
 types=[block(driver,r'^struct qcom_slim_ngd_dma_desc \{'),block(internal,r'^struct slim_msg_txn \{'),block(public,r'^struct slim_val_inf \{')];code=code.replace('/* ACTUAL_TYPES */',''.join(types))
 names=['qcom_slim_ngd_tx_msg_get']+(['qcom_slim_ngd_tx_msg_put'] if 'static void qcom_slim_ngd_tx_msg_put(' in driver else [])+['qcom_slim_ngd_tx_msg_dma_cb','qcom_slim_ngd_tx_msg_post']
 groups={'LOW':(driver,names),'TX':(driver,['qcom_slim_ngd_xfer_msg']),'MESSAGE_HELPERS':(internal,['slim_tid_txn','slim_ec_txn'])}
 for marker,(text,names) in groups.items():
  code=code.replace('/* ACTUAL_'+marker+' */',''.join(function(text,n) for n in names))
  for name in names:assert function(code,name)==function(text,name);bindings[name]=hashlib.sha256(function(text,name).encode()).hexdigest()
 return code,bindings
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();assert not a.output.exists();a.output.mkdir();code,bindings=model(a.source);src=a.output/'model.c';src.write_text(code);binary=a.output/'model'
 c=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60);(a.output/'build.log').write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);r=subprocess.run([str(binary),str(a.output/'wire.bin')],env=env,capture_output=True,text=True,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 assert (a.output/'wire.bin').stat().st_size>10000
 j=json.loads(r.stdout);j.update(wire_trace_SHA256=hashlib.sha256((a.output/'wire.bin').read_bytes()).hexdigest(),wire_trace_bytes=(a.output/'wire.bin').stat().st_size,actual_function_bindings=bindings,actual_callback_bodies_preserved=True,generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,completions_and_DMA_are_logical_services=True,completion_tokens_never_dereferenced_after_or_before_logical_frame_retirement=True,real_TID_response_core_PM_hardware_audio_network_or_phone_execution=False,whole_TX_TID_submission_failure_and_transport_quiescence_qualified=False)
 (a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');assert (j['failures']>0 if a.baseline else j['failures']==0),j;print(json.dumps({k:j[k] for k in ['cases','checks','failures']}))
