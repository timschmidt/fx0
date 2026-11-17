# SPDX-License-Identifier: GPL-2.0-only
"""Exercise ownership fault controls with stable logical storage only."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('owned',B/'check-response.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir();code,_=m.model(a.source);changes=[]
def mutate(name,function,old,new,expected):
 body=m.function(code,function);assert body.count(old)==1,(name,body.count(old));assert old!=new;changes.append((name,code.replace(body,body.replace(old,new)),expected))
mutate('record-leak-on-response','slim_msg_response','\tkfree(pending);','\t(void)pending;','all core-owned records are retired exactly once')
mutate('record-leak-on-internal-cancel','slim_free_txn_tid','\t\tkfree(pending);','\t\t(void)pending;','all core-owned records are retired exactly once')
mutate('record-leak-on-IDR-failure','slim_alloc_txn_tid','\t\tkfree(pending);','\t\t(void)pending;','all core-owned records are retired exactly once')
mutate('record-leak-on-public-cancel','slim_cancel_msg','\t\tkfree(pending);','\t\t(void)pending;','all core-owned records are retired exactly once')
mutate('record-leak-on-controller-stop','slim_stop_transactions','\t\tkfree(pending);','\t\t(void)pending;','all core-owned records are retired exactly once')
mutate('controller-stop-does-not-close-admission','slim_stop_transactions','\tctrl->transactions_stopped = true;','\tctrl->transactions_stopped = false;','controller stop closes transaction admission')
mutate('allocation-ignores-closed-controller','slim_alloc_txn_tid','if (ctrl->transactions_stopped)','if (false && ctrl->transactions_stopped)','a closed controller rejects new TID allocation')
mutate('controller-stop-forgets-response-PM-pins','slim_stop_transactions','\t\trefs += pending->prepared;','\t\trefs += 0;','stop releases only prepared response PM references')
mutate('controller-stop-forgets-IDR-destruction','slim_stop_transactions','\tidr_destroy(&ctrl->tid_idr);','\t(void)ctrl->tid_idr;','controller unregister destroys the empty IDR allocation tree')
mutate('response-buffer-snapshot-shifted','slim_prepare_txn','pending->rbuf = txn->msg->rbuf;','pending->rbuf = txn->msg->rbuf ? txn->msg->rbuf + 1 : NULL;','response uses original buffer independent of reused sender metadata')
mutate('response-completion-not-snapshotted','slim_prepare_txn','pending->comp = txn->comp;','pending->comp = NULL;','the late response completes the external caller token')
mutate('software-owner-identity-ignored','slim_free_txn_tid','if (pending && pending->owner == txn)','if (pending)','an old owner cannot cancel its replacement')
mutate('duplicate-active-descriptor-accepted','slim_prepare_txn','if (txn->msg->comp) {','if (false && txn->msg->comp) {','duplicate active descriptor is rejected before transmission')
mutate('transaction-domain-reinitialized','slim_init_transactions','\tif (ctrl->transactions_initialized)\n\t\treturn;\n','\t(void)ctrl->transactions_initialized;\n','registration does not erase an existing response record')
mutate('response-drops-no-PM-pin','slim_msg_response','\tpm_runtime_put_autosuspend(ctrl->dev);','\t(void)ctrl->dev;','late response or failed send retires its TID and PM reference')
mutate('public-cancel-drops-another-PM-pin','slim_cancel_msg','if (!ret) {','if (true) {','cancelled response drops only its own PM reference')
mutate('public-cancel-matches-another-descriptor','slim_cancel_msg','pending->msg_key != msg','false','wrong descriptor cannot consume response ownership')
mutate('public-cancel-retires-synchronous-message','slim_cancel_msg','!pending->asynchronous || ','','public async cancellation ignores synchronous requests')
mutate('controller-start-does-not-reopen','slim_start_transactions','ctrl->transactions_stopped = false;','ctrl->transactions_stopped = true;','serialized re-registration reopens transaction admission')
mutate('response-size-bound-removed','slim_msg_response',' || len > pending->num_bytes','','response copy and completion stay within their logical lifetimes')
mutate('response-copy-outside-lock','slim_msg_response','\tmemcpy(pending->rbuf, reply, len);','\tspin_unlock_irqrestore(&ctrl->txn_lock, flags);\n\tmemcpy(pending->rbuf, reply, len);\n\tspin_lock_irqsave(&ctrl->txn_lock, flags);','public cancel or stop waits for admitted copy and completion')
mutate('response-has-no-own-PM-reference','slim_prepare_txn','\t\tpm_runtime_get_noresume(ctrl->dev);\n','','kind-0-reply-1-fault-0-external-0')
mutate('duplicate-preparation-acquires-another-pin','slim_prepare_txn','\t} else if (pending->prepared) {\n\t\tret = -EALREADY;\n','','duplicate-preparation-does-not-add-PM-pin')
mutate('cancellation-does-not-release-its-pin','slim_free_txn_tid','\t\tpm_runtime_put_autosuspend(ctrl->dev);\n','','kind-0-reply-0-fault-0-external-0')
mutate('core-caller-vote-not-released','slim_do_transfer','\t\tpm_runtime_put_autosuspend(ctrl->dev);\n','','kind-0-reply-1-fault-0-external-0')
mutate('NGD-caller-vote-not-released','qcom_slim_ngd_xfer_msg_sync','\tpm_runtime_put_autosuspend(ctrl->dev);\n','','kind-5-reply-3-fault-0-external-0')
mutate('driver-ACK-TID-survives-local-return','qcom_slim_ngd_xfer_msg','\tif (usr_msg && tid_allocated && ret)\n\t\tslim_free_txn_tid(sctrl, txn);\n','\t(void)tid_allocated;\n','kind-2-reply-0-fault-1-external-0')
mutate('submission-errors-ignored','qcom_slim_ngd_tx_msg_post','\tret = dma_submit_error(desc->cookie);\n\tif (ret) {\n\t\tspin_unlock_irqrestore(&ctrl->tx_buf_lock, flags);\n\t\treturn ret;\n\t}\n','\tret = dma_submit_error(desc->cookie);\n\t(void)ret;\n','submit-error--12-kind-0')
mutate('submission-error-collapsed-to-EIO','qcom_slim_ngd_tx_msg_post','\t\treturn ret;\n','\t\treturn -EIO;\n','submit-error--12-kind-0')
changes=changes[21:]
assert len(changes)==8
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for name,text,expected in changes:
 src=a.output/(name+'.c');src.write_text(text);binary=a.output/name
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-missing-field-initializers','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60);(a.output/(name+'-build.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(name+'.stdout')).write_text(r.stdout);(a.output/(name+'.stderr')).write_text(r.stderr);assert r.returncode==0,(name,r.stderr[-1200:])
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);assert j['cases']==1149 and j['failures']>0 and expected in r.stderr,(name,j,expected)
 records.append(dict(control=name,failures=j['failures'],expected_assertion=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,heap_record_and_sender_storage_kept_physically_live_until_logical_audit=True,IDR_PM_completion_DMA_response_and_device_services_synthetic=True,hardware_audio_phone_or_network_execution=False),indent=2)+'\n');print(json.dumps(records))
