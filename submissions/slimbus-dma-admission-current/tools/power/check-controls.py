# SPDX-License-Identifier: GPL-2.0-only
"""Reject broken resume-error and ownership variants using logical services."""
from pathlib import Path
import argparse,importlib.util,json,os,subprocess
B=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('power',B/'check-power.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=argparse.ArgumentParser(description=__doc__);p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();assert not a.output.exists();a.output.mkdir()
code,_=m.model(a.source);controls=[]
def change(label,old,new,expected):
 assert code.count(old)==1,(label,code.count(old));assert old!=new;controls.append((label,code.replace(old,new),expected))
resume=m.function(code,'qcom_slim_ngd_runtime_resume');enable=m.function(code,'qcom_slim_ngd_enable');dma=m.function(code,'qcom_slim_ngd_init_dma')
error='\t\tif (ret < 0) {\n\t\t\tif (!ctrl->registered)\n\t\t\t\tqcom_slim_qmi_exit(ctrl);\n\t\t\treturn ret;\n\t\t}'
assert error in enable
first='initial-mode0-fault1-at0-error-5';registered='registered-mode0-fault1-at0-error-5'
change('runtime-swallow-error',resume,resume.replace('\treturn ret;','\treturn 0;'),first)
change('direct-resume-result-ignored',enable,enable.replace('ret = qcom_slim_ngd_runtime_resume(ctrl->ctrl.dev);','ret = (qcom_slim_ngd_runtime_resume(ctrl->ctrl.dev), 0);'),first)
change('framework-resume-result-ignored',enable,enable.replace('ret = pm_runtime_resume(ctrl->ctrl.dev);','ret = (pm_runtime_resume(ctrl->ctrl.dev), 0);'),'initial-mode3-fault1-at0-error-5')
change('new-client-not-unwound',enable,enable.replace(error,error.replace('\t\t\tif (!ctrl->registered)\n\t\t\t\tqcom_slim_qmi_exit(ctrl);\n','')),first)
change('registered-client-dropped',enable,enable.replace(error,error.replace('\t\t\tif (!ctrl->registered)\n\t\t\t\tqcom_slim_qmi_exit(ctrl);','\t\t\tqcom_slim_qmi_exit(ctrl);')),registered)
change('bootstrap-dropped-on-error',enable,enable.replace(error,error.replace('\t\t\treturn ret;','\t\t\tif (!ctrl->registered) {\n\t\t\t\tpm_runtime_put(ctrl->ctrl.dev);\n\t\t\t\tctrl->pm_ref_held = false;\n\t\t\t}\n\t\t\treturn ret;')),first)
change('registration-after-failed-wake',enable,enable.replace('if (ret < 0)','if (false && ret < 0)'),first)
change('positive-PM-result-rejected',enable,enable.replace('if (ret < 0)','if (ret)'),'positive-framework-success-noio0')
change('registered-runtime-wake-skipped',enable,enable.replace('\t\tif (ctrl->registered)\n\t\t\treturn 0;\n','').replace('\t\tcomplete(&ctrl->qmi.qmi_comp);','\t\tif (ctrl->registered)\n\t\t\treturn 0;\n\t\tcomplete(&ctrl->qmi.qmi_comp);'),registered)
change('enable-error-flattened',enable,enable.replace(error,error.replace('return ret;','return -EIO;')),'initial-mode0-fault3-at0-error-5')
change('runtime-error-flattened',resume,resume.replace('\treturn ret;','\treturn ret ? -EIO : 0;'),'initial-mode0-fault3-at0-error-5')
env=os.environ|{'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1:print_stacktrace=1'};env.pop('LSAN_OPTIONS',None);records=[]
for label,text,expected in controls:
 src=a.output/(label+'.c');src.write_text(text);binary=a.output/label
 c=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-parameter','-Wno-unused-function','-Wno-unused-but-set-variable','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer',str(src),'-o',str(binary)],capture_output=True,text=True,timeout=60)
 (a.output/(label+'-build.log')).write_text(c.stdout+c.stderr);assert c.returncode==0,c.stderr
 r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/(label+'.stdout')).write_text(r.stdout);(a.output/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr
 assert not any(t in r.stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:','fixture invariant']),r.stderr
 j=json.loads(r.stdout);assert j['cases']==626 and j['checks']==13284 and j['failures']>0 and expected+':' in r.stderr,(label,j,expected)
 records.append(dict(control=label,failures=j['failures'],expected_case=expected,rejected=True,sanitizer_diagnostics=False))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=records,normal_LSan_and_failfast_ASan_UBSan=True,all_services_synthetic=True,hardware_audio_firmware_or_phone_execution=False),indent=2)+'\n');print(json.dumps(records))
