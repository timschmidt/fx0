# SPDX-License-Identifier: GPL-2.0-only
"""Reject response publication, retirement and PM ownership regressions logically."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('response',B/'check-response.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir();code,_=m.model(a.source);changes=[]
def change(name,old,new,expected):
 assert old!=new and code.count(old)==1,(name,code.count(old));changes.append((name,code.replace(old,new),expected))
response=m.function(code,'slim_msg_response');alloc=m.function(code,'slim_alloc_txn_tid');prepare=m.function(code,'slim_prepare_txn');free=m.function(code,'slim_free_txn_tid');core=m.function(code,'slim_do_transfer');send=m.function(code,'qcom_slim_ngd_xfer_msg');sync=m.function(code,'qcom_slim_ngd_xfer_msg_sync');post=m.function(code,'qcom_slim_ngd_tx_msg_post')
early='kind-0-reply-1-fault-0-external-0'
change('response-accepts-unprepared-transaction',response,response.replace('!txn || !txn->prepared','!txn'),'unprepared-early-response-kind-0')
change('allocation-retains-old-ready-state',alloc,alloc.replace('\ttxn->prepared = false;\n',''),'reused-prepared-state-is-cleared')
change('cancellation-ignores-TID-identity',free,free.replace('if (idr_find(&ctrl->tid_idr, txn->tid) == txn)','if (true)'),'identity-preserving-retirement')
change('response-copy-outside-transaction-lock',response,response.replace('\tmemcpy(msg->rbuf, reply, len);','\tspin_unlock_irqrestore(&ctrl->txn_lock, flags);\n\tmemcpy(msg->rbuf, reply, len);\n\tspin_lock_irqsave(&ctrl->txn_lock, flags);'),'response-copy-versus-core-timeout')
change('response-completion-outside-transaction-lock',response,response.replace('\tif (txn->comp)\n\t\tcomplete(txn->comp);\n\tspin_unlock_irqrestore(&ctrl->txn_lock, flags);','\tspin_unlock_irqrestore(&ctrl->txn_lock, flags);\n\tif (txn->comp)\n\t\tcomplete(txn->comp);'),early)
change('response-size-not-checked',response,response.replace(' || len > msg->num_bytes',''),'kind-0-reply-7-fault-0-external-0')
change('response-has-no-own-PM-reference',prepare,prepare.replace('\t\tpm_runtime_get_noresume(ctrl->dev);\n',''),early)
change('duplicate-preparation-acquires-another-pin',prepare,prepare.replace('\t} else if (txn->prepared) {\n\t\tret = -EALREADY;\n',''),'duplicate-preparation-does-not-add-PM-pin')
change('cancellation-drops-another-winners-pin',free,free.replace('if (released && txn->prepared)','if (txn->prepared)'),'kind-0-reply-5-fault-0-external-0')
change('response-does-not-release-its-pin',response,response.replace('\tpm_runtime_put_autosuspend(ctrl->dev);\n',''),early)
change('cancellation-does-not-release-its-pin',free,free.replace('\t\tpm_runtime_put_autosuspend(ctrl->dev);\n',''),'kind-0-reply-0-fault-0-external-0')
change('core-caller-vote-not-released',core,core.replace('\t\tpm_runtime_put_autosuspend(ctrl->dev);\n',''),early)
change('NGD-caller-vote-not-released',sync,sync.replace('\tpm_runtime_put_autosuspend(ctrl->dev);\n',''),'kind-5-reply-3-fault-0-external-0')
change('driver-ACK-TID-survives-local-return',send,send.replace('\tif (usr_msg && tid_allocated && ret)\n\t\tslim_free_txn_tid(sctrl, txn);\n','\tif (usr_msg && tid_allocated && ret)\n\t\t(void)tid_allocated;\n'),'kind-2-reply-0-fault-1-external-0')
change('submission-errors-ignored',post,post.replace('\tret = dma_submit_error(desc->cookie);\n\tif (ret) {\n\t\tspin_unlock_irqrestore(&ctrl->tx_buf_lock, flags);\n\t\treturn ret;\n\t}\n','\tret = dma_submit_error(desc->cookie);\n\t(void)ret;\n'),'submit-error--12-kind-0')
change('submission-error-collapsed-to-EIO',post,post.replace('\t\treturn ret;\n','\t\treturn -EIO;\n'),'submit-error--12-kind-0')
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for name,text,expected in changes:
 src=a.output/(name+'.c');src.write_text(text);binary=a.output/name
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60);(a.output/(name+'-build.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(name+'.stdout')).write_text(r.stdout);(a.output/(name+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);assert (j['cases'],j['checks'])==(1022,41774) and j['failures']>0 and expected+':' in r.stderr,(name,j)
 records.append(dict(control=name,failures=j['failures'],expected_case=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,transaction_storage_kept_physically_live_and_invalid_copy_or_completion_logged=True,all_IDR_PM_completion_DMA_and_response_services_synthetic=True,hardware_audio_phone_or_network_execution=False),indent=2)+'\n');print(json.dumps(records))
