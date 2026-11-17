# SPDX-License-Identifier: GPL-2.0-only
"""Supplement wire tests with captured transport status and upper-word contracts."""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import re
import subprocess

b=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('source_parts',b/'source-parts.py')
parts=importlib.util.module_from_spec(spec);spec.loader.exec_module(parts)
p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path)
a=p.parse_args();a.output.mkdir(mode=0o700)
header=(a.source/'drivers/firmware/qcom/qcom_scm.h').read_text()
source=(a.source/'drivers/firmware/qcom/qcom_scm.c').read_text()
enum=re.search(r'^enum qcom_scm_convention \{.*?^};',header,re.M|re.S)[0]
decl='\n'.join(parts.macro(header,n) for n in ['MAX_QCOM_SCM_ARGS','MAX_QCOM_SCM_RETS','QCOM_SCM_ARGS_IMPL','QCOM_SCM_ARGS','QCOM_SCM_SVC_FUSE','QCOM_SCM_FUSE_READ_LEGACY'])
stubs=(b/'SCM-api-stubs.c').read_text().replace('#define QCOM_SCM_ARGS(n) (n)','')
for name in ['qcom_scm_desc','qcom_scm_res']:
    actual=re.search(r'^struct '+name+r' \{.*?^};',header,re.M|re.S)[0]
    stubs=re.sub(r'^struct '+name+r' \{[^\n]*\};',actual,stubs,flags=re.M)
api=parts.function(source,'qcom_scm_legacy_fuse_read')
program=enum+'\n'+decl+stubs+api+(b/'SCM-api-cases.c').read_text()
(a.output/'actual-function.c').write_text(api);(a.output/'model.c').write_text(program)
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror',
                  '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                  str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,timeout=60)
(a.output/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
r=subprocess.run([str(a.output/'model')],capture_output=True,text=True,timeout=60)
(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
j=dict(cases=13,returncode=r.returncode,passed=r.returncode==0,
       actual_function_SHA256=hashlib.sha256(api.encode()).hexdigest(),program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
       sanitizer_diagnostics=bool(r.stderr),transport_captured_and_modeled=True,all_data_synthetic=True,phone_access=False)
(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j))
assert r.returncode==0 and '13 actual-API contracts passed' in r.stdout and not r.stderr
