# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual SCM API, dispatcher and legacy wire transport with host services."""
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
p=argparse.ArgumentParser()
p.add_argument('source',type=Path);p.add_argument('output',type=Path)
p.add_argument('--mutation',choices=['wrong-command','swapped-words','ignored-status','early-output','nonlegacy','alignment'])
a=p.parse_args();a.output.mkdir(mode=0o700)
hashes={}
def read(name):
    data=(a.source/name).read_bytes();hashes[name]=hashlib.sha256(data).hexdigest();return data.decode()
h=read('drivers/firmware/qcom/qcom_scm.h')
c=read('drivers/firmware/qcom/qcom_scm.c')
legacy=read('drivers/firmware/qcom/qcom_scm-legacy.c')
arm=read('include/linux/arm-smccc.h')
declarations=[]
for kind,name in [('enum','qcom_scm_convention'),('enum','qcom_scm_arg_types'),('struct','qcom_scm_desc'),('struct','qcom_scm_res')]:
    declarations.append(re.search(r'^'+kind+' '+name+r' \{.*?^};',h,re.M|re.S)[0]+'\n')
for name in ['MAX_QCOM_SCM_ARGS','MAX_QCOM_SCM_RETS','QCOM_SCM_ARGS_IMPL','QCOM_SCM_ARGS',
             'SCM_LEGACY_FNID','scm_smc_call','QCOM_SCM_SVC_FUSE','QCOM_SCM_FUSE_READ_LEGACY',
             'QCOM_SCM_V2_EBUSY','QCOM_SCM_ENOMEM','QCOM_SCM_EOPNOTSUPP','QCOM_SCM_EINVAL_ADDR',
             'QCOM_SCM_EINVAL_ARG','QCOM_SCM_ERROR','QCOM_SCM_INTERRUPTED']:
    declarations.insert(0,parts.macro(h,name))
declarations.append(parts.macro(arm,'ARM_SMCCC_OWNER_SIP'))
declarations.append(parts.function(h,'qcom_scm_remap_error'))
for name in ['arm_smccc_args','scm_legacy_command','scm_legacy_response']:
    declarations.append(re.search(r'^struct '+name+r' \{.*?^};',legacy,re.M|re.S)[0]+'\n')
declarations.append('static DEFINE_MUTEX(qcom_scm_lock);\n')
declarations.append('static enum qcom_scm_convention qcom_scm_convention;\n')
transport=''
for name in ['scm_legacy_command_to_response','scm_legacy_get_command_buffer','scm_legacy_get_response_buffer','__scm_legacy_do','scm_legacy_call']:
    transport+=parts.function(legacy,name)
api=parts.function(c,'qcom_scm_legacy_fuse_read')
if a.mutation:
    changes={
      'wrong-command':('.cmd = QCOM_SCM_FUSE_READ_LEGACY,','.cmd = QCOM_SCM_FUSE_READ_LEGACY + 1,'),
      'swapped-words':('((u64)(u32)res.result[1] << 32) | (u32)res.result[0]','((u64)(u32)res.result[0] << 32) | (u32)res.result[1]'),
      'ignored-status':('if (res.result[2])','if (false && res.result[2])'),
      'nonlegacy':('__get_convention() != SMC_CONVENTION_LEGACY','false && __get_convention() != SMC_CONVENTION_LEGACY'),
      'alignment':('(address & 7)','false'),
    }
    if a.mutation=='early-output':
        old='\tif (res.result[2])\n\t\treturn -EIO;\n\n\t*value = ((u64)(u32)res.result[1] << 32) | (u32)res.result[0];'
        new='\t*value = ((u64)(u32)res.result[1] << 32) | (u32)res.result[0];\n\tif (res.result[2])\n\t\treturn -EIO;'
    else:old,new=changes[a.mutation]
    assert old in api;(a.output/'mutation-original.c').write_text(api);api=api.replace(old,new)
actual='\n'.join(declarations)+transport
actual+=parts.function(c,'qcom_scm_is_available')
actual+=parts.function(c,'qcom_scm_call')+api
head=(b/'SCM-model-head.c').read_text()
# The fixture service definitions use the actual wire declarations.
program=head+'\n'+'\n'.join(declarations)+(b/'SCM-model-services.c').read_text()+transport
program+=parts.function(c,'qcom_scm_is_available')+parts.function(c,'qcom_scm_call')+api
program+=(b/'SCM-model-main.c').read_text()
(a.output/'actual-functions.c').write_text(actual);(a.output/'model.c').write_text(program)
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror',
                  '-fsanitize=address,undefined','-fno-omit-frame-pointer',
                  str(a.output/'model.c'),'-o',str(a.output/'model')],capture_output=True,text=True,timeout=60)
(a.output/'compile.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
r=subprocess.run([str(a.output/'model')],capture_output=True,text=True,timeout=60)
(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr)
result=json.loads(r.stdout.splitlines()[-1]);result.update(returncode=r.returncode,
 actual_source_SHA256=hashlib.sha256(actual.encode()).hexdigest(),program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
 source_files=hashes,mutation=a.mutation,sanitizer_diagnostics=bool(r.stderr),
 actual_API_dispatcher_and_legacy_transport=True,allocation_DMA_SMC_PM_context_and_mutex_services_modeled=True,
 convention_detection_modeled=True,concurrency_or_real_firmware_acceptance=False,all_response_data_synthetic=True,phone_access=False)
(a.output/'qualification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
assert r.returncode==(1 if a.mutation else 0) and not r.stderr
