# SPDX-License-Identifier: GPL-2.0-only
"""Compose exact core/NGD callbacks with logical response, IDR, PM and DMA services."""
from pathlib import Path
import argparse,hashlib,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('extract',B/'extract-tx.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
function=m.function

def model(source):
 code,bindings=m.model(source);core=(source/'drivers/slimbus/messaging.c').read_text();driver=(source/'drivers/slimbus/qcom-ngd-ctrl.c').read_text();header=(source/'drivers/slimbus/slimbus.h').read_text();new='int slim_prepare_txn(' in core
 names=['slim_alloc_txn_tid','slim_free_txn_tid']+(['slim_prepare_txn'] if new else [])+['slim_msg_response','slim_do_transfer']
 for marker,text,group in [('CORE',core,names),('SYNC',driver,['qcom_slim_ngd_xfer_msg_sync'])]:
  assert code.count('/* ACTUAL_'+marker+' */')==1;code=code.replace('/* ACTUAL_'+marker+' */',''.join(function(text,n) for n in group))
  for n in group:assert function(text,n)==function(code,n);bindings[n]=hashlib.sha256(function(text,n).encode()).hexdigest()
 code='#define FIXTURE_PREPARED_API '+str(int(new))+'\n'+code;return code,bindings

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);p.add_argument('--baseline',action='store_true');a=p.parse_args();assert not a.output.exists();a.output.mkdir();code,bindings=model(a.source);src=a.output/'model.c';src.write_text(code);binary=a.output/'model'
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60);(a.output/'build.log').write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);j.update(actual_function_bindings=bindings,actual_callbacks_byte_exact=True,generated_model_SHA256=hashlib.sha256(code.encode()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,IDR_PM_completion_DMA_and_response_services_synthetic=True,all_transaction_storage_retained_until_logical_lifetime_audit=True,completion_tokens_never_dereferenced=True,exported_async_stack_transaction_and_late_wire_TID_reuse_qualified=False,full_NGD_teardown_qualified=False,hardware_audio_phone_or_network_execution=False);(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');assert (j['failures']>0 if a.baseline else j['failures']==0),j;print(json.dumps({k:j[k] for k in ['cases','checks','failures']}))
