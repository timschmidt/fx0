# SPDX-License-Identifier: GPL-2.0-only
"""Reject logical reservation, completion and descriptor handoff regressions."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent;spec=importlib.util.spec_from_file_location('tx',B/'check-tx.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir();code,_=m.model(a.source);changes=[]
def change(label,old,new,expected):
 assert old!=new and code.count(old)==1,(label,code.count(old));changes.append((label,code.replace(old,new),expected))
put=m.function(code,'qcom_slim_ngd_tx_msg_put');send=m.function(code,'qcom_slim_ngd_xfer_msg');post=m.function(code,'qcom_slim_ngd_tx_msg_post');get=m.function(code,'qcom_slim_ngd_tx_msg_get');callback=m.function(code,'qcom_slim_ngd_tx_msg_dma_cb')
change('completion-not-detached',put,put.replace('\tctrl->txdesc[index].comp = NULL;\n',''),'ring-0-type-0-failure-3')
change('unsubmitted-reservation-not-returned',put,put.replace('\tif (!submitted)\n\t\tctrl->tx_tail = index;\n',''),'ring-0-type-0-failure-2')
change('submitted-buffer-returned-early',put,put.replace('if (!submitted)','if (true)'),'pipeline-full-at-0')
late=send.replace('\tmutex_lock(&ctrl->tx_lock);\n','').replace('\tif (!pbuf) {','\tmutex_lock(&ctrl->tx_lock);\n\tif (!pbuf) {')
change('reservation-before-transfer-mutex',send,late,'concurrent-reservation')
late=send.replace('put:\n\tqcom_slim_ngd_tx_msg_put(ctrl, pbuf, submitted);','put:\n\tmutex_unlock(&ctrl->tx_lock);\n\tqcom_slim_ngd_tx_msg_put(ctrl, pbuf, submitted);\n\treturn ret;')
change('cleanup-after-transfer-unlock',send,late,'ring-0-type-0-failure-0')
old='\t\t\tdev_err(ctrl->dev, "Unable to allocate TID\\n");\n\t\t\tgoto put;'
change('TID-error-skips-reservation-cleanup',send,send.replace(old,old.replace('goto put;','mutex_unlock(&ctrl->tx_lock);\n\t\t\treturn ret;')),'ring-0-type-1-failure-1')
old='\tif (ret)\n\t\tgoto put;\n\tsubmitted = true;'
change('prepare-error-skips-reservation-cleanup',send,send.replace(old,'\tif (ret) {\n\t\tmutex_unlock(&ctrl->tx_lock);\n\t\treturn ret;\n\t}\n\tsubmitted = true;'),'ring-0-type-0-failure-2')
old='\t\tret = -ETIMEDOUT;\n\t\tgoto put;'
change('TX-timeout-skips-completion-cleanup',send,send.replace(old,'\t\tmutex_unlock(&ctrl->tx_lock);\n\t\treturn -ETIMEDOUT;',1),'timeout-races-active-callback')
change('submission-ownership-never-recorded',send,send.replace('\tsubmitted = true;\n',''),'pipeline-full-at-0')
change('cookie-written-through-DMA-descriptor',post,post.replace('desc->cookie = dmaengine_submit','desc->desc->cookie = dmaengine_submit'),'ring-0-type-0-failure-0')
change('callback-does-not-retire-ring-owner',callback,callback.replace('\tctrl->tx_head = (ctrl->tx_head + 1) % QCOM_SLIM_NGD_DESC_NUM;\n',''),'pipeline-full-at-0')
change('ring-capacity-not-enforced',get,get.replace('if ((ctrl->tx_tail + 1) % QCOM_SLIM_NGD_DESC_NUM == ctrl->tx_head)','if (false)'),'pipeline-full-at-0')
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for label,text,expected in changes:
 src=a.output/(label+'.c');src.write_text(text);binary=a.output/label
 r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-sign-compare','-pthread','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60);(a.output/(label+'-build.log')).write_text(r.stdout+r.stderr);assert r.returncode==0,r.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(label+'.stdout')).write_text(r.stdout);(a.output/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);assert (j['cases'],j['checks'])==(1093,47497) and j['failures']>0 and expected+':' in r.stderr,(label,j)
 records.append(dict(control=label,failures=j['failures'],expected_case=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,invalid_callback_tokens_logged_without_executing_nonexistent_or_retired_memory=True,all_completion_DMA_and_TID_services_synthetic=True,hardware_audio_phone_or_network_execution=False),indent=2)+'\n');print(json.dumps(records))
