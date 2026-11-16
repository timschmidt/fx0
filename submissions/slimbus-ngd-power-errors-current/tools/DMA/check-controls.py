# SPDX-License-Identifier: GPL-2.0-only
"""Reject independently broken DMA setup variants in logical services."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('dma',B/'check-dma.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir()
code,_=module.model(a.source);controls=[]
def change(label,old,new,expected):
 assert code.count(old)==1,(label,code.count(old));assert old!=new;controls.append((label,code.replace(old,new),expected))
rx=module.function(code,'qcom_slim_ngd_init_rx_msgq');tx=module.function(code,'qcom_slim_ngd_init_tx_msgq');init=module.function(code,'qcom_slim_ngd_init_dma');post=module.function(code,'qcom_slim_ngd_post_rx_msgq');setup=module.function(code,'qcom_slim_ngd_setup');power=module.function(code,'qcom_slim_ngd_power_up')
controls.append(('unmanaged-buffers',code.replace('dmam_alloc_coherent(dev,','dma_alloc_coherent(dev,'),'setup-success'))
controls.append(('buffers-reallocated-every-session',code.replace('\tif (!ctrl->rx_base)\n\t\tctrl->rx_base','\tctrl->rx_base').replace('\tif (!ctrl->tx_base)\n\t\tctrl->tx_base','\tctrl->tx_base'),'suspend-resume-buffer-reuse'))
change('RX-before-TX',init,init.replace('qcom_slim_ngd_init_tx_msgq','swap').replace('qcom_slim_ngd_init_rx_msgq','qcom_slim_ngd_init_tx_msgq').replace('swap','qcom_slim_ngd_init_rx_msgq'),'setup-success')
change('missing-TX-unwind',init,init.replace('\t\tqcom_slim_ngd_exit_dma(ctrl);\n',''),'allocation-error-1')
change('stale-RX-channel',rx,rx.replace('\tctrl->dma_rx_channel = NULL;\n\treturn ret;','\treturn ret;'),'RX-error-5-0')
change('stale-TX-channel',tx,tx.replace('\tctrl->dma_tx_channel = NULL;\n\treturn ret;','\treturn ret;'),'allocation-error-4')
change('queued-RX-not-terminated',rx,rx.replace('\tdmaengine_terminate_sync(ctrl->dma_rx_channel);\n',''),'RX-error-5-1')
change('RX-submit-errors-ignored',post,post.replace('\t\tif (dma_submit_error(desc->desc->cookie))\n\t\t\treturn desc->desc->cookie;\n',''),'RX-error-6-0')
change('setup-errors-discarded',setup,setup.replace('\tint ret;\n','').replace('\t\tret = qcom_slim_ngd_init_dma(ctrl);\n\t\tif (ret)\n\t\t\treturn ret;','\t\tqcom_slim_ngd_init_dma(ctrl);'),'power-setup-error-1-retained-0')
change('retained-status-errors-discarded',power,power.replace('\t\treturn qcom_slim_ngd_setup(ctrl);','\t\tqcom_slim_ngd_setup(ctrl);\n\t\treturn 0;'),'power-setup-error-1-retained-1')
change('capability-path-errors-discarded',power,power.replace('\tret = qcom_slim_ngd_setup(ctrl);\n\tif (ret)\n\t\treturn ret;','\tqcom_slim_ngd_setup(ctrl);'),'power-setup-error-1-retained-0')
change('live-pair-not-reused',init,init.replace('\tif (ctrl->dma_rx_channel && ctrl->dma_tx_channel)\n\t\treturn 0;\n',''),'repeated-setup')
change('wrong-TX-allocation-error',tx,tx.replace('ret = -ENOMEM;','ret = -EINVAL;'),'allocation-error-4')
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for label,text,expected in controls:
 assert text!=code;src=a.output/(label+'.c');src.write_text(text);binary=a.output/label
 c=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-but-set-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60)
 (a.output/(label+'-build.log')).write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(label+'.stdout')).write_text(r.stdout);(a.output/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);assert j['cases']==85 and j['checks']==1150 and j['failures']>0 and expected+':' in r.stderr
 records.append(dict(control=label,failures=j['failures'],expected_case=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,all_services_synthetic=True,hardware_audio_firmware_or_phone_execution=False),indent=2)+'\n');print(json.dumps(records))
