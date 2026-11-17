# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import importlib.util,os,json,unittest,hashlib,sys
B=Path(__file__).resolve().parent;R=B.parents[1]
p=Path(sys.argv[3]) if len(sys.argv)>3 else R/'local/fx0-spm-rpm-current-01/fixtures/tests/test_smd_rpm_ack.py'
spec=importlib.util.spec_from_file_location('rpm_ack',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
m.SOURCE=(Path(sys.argv[1]) if len(sys.argv)>1 else R/'worktrees/linux-qcom-spm-rpm-current-01')/'drivers/soc/qcom/smd-rpm.c'
m.PREFIX=m.PREFIX.replace('typedef uint32_t u32;','typedef uint32_t u32;\ntypedef uint64_t u64;').replace('#define EIO 5','#define EIO 5\n#define EBUSY 16')
# The new private struct contains u64; only this synthetic type adapter changes.
out=Path(sys.argv[2]) if len(sys.argv)>2 else B/'retained-ack-02';out.mkdir(exist_ok=False)
os.environ['TMPDIR']=str(out.resolve())
with (out/'run.log').open('w') as stream:
 result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(m.RpmAckTests))
j=dict(passed=result.wasSuccessful(),testsRun=result.testsRun,failures=len(result.failures),errors=len(result.errors),
 original_model_SHA256=hashlib.sha256(p.read_bytes()).hexdigest(),actual_request_callback_qualified=result.wasSuccessful(),
 adapter='Add u64 typedef and EBUSY errno constant for actual source; retained cases unchanged',phone_access=False)
(out/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j));assert j['passed']
