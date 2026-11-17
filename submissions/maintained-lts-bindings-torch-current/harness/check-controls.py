# SPDX-License-Identifier: GPL-2.0-only
"""Reject shutdown-abort and regulator-ownership regressions by intended checks."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
B=Path(__file__).resolve().parent;p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();a.output.mkdir();file='drivers/leds/flash/leds-qcom-flash-v1.c';s=(a.source/file).read_text();rows=[]
variants=[('early-off-return','\t/* Try every off path even if an earlier register access failed. */','\tif (ret)\n\t\treturn ret;\n\t/* Try every off path even if an earlier register access failed. */'),('release-failed-regulator-ownership','\t\tif (!err)\n\t\t\tflash->vin_on = false;','\t\tflash->vin_on = false;')]
for name,before,after in variants:
 assert s.count(before)==1;tree=a.output/name/'tree';target=tree/file;target.parent.mkdir(parents=True);target.write_text(s.replace(before,after));out=a.output/name/'result';r=subprocess.run([sys.executable,'-B',str(B/'check-torch-errors.py'),'--source',str(tree),'--output',str(out),'--expect','fixed'],capture_output=True,text=True,timeout=90);j=json.loads((out/'controller.json').read_text());stderr=(out/'execute.stderr').read_text();assert r.returncode!=0 and j['compile_returncode']==0 and j['execute_returncode']<0 and 'Assertion' in stderr and 'okay' in stderr and not any(x in stderr for x in ['AddressSanitizer','LeakSanitizer','runtime error:']), (name,r.returncode,j,stderr)
 rows.append(dict(name=name,rejected_by_intended_assertion=True,source_SHA256=hashlib.sha256(target.read_bytes()).hexdigest(),assertion=stderr.strip()))
(a.output/'qualification.json').write_text(json.dumps(dict(passed=True,controls=rows,compiler_or_sanitizer_failure_counted=False,phone_access=False,all_services_synthetic=True),indent=2)+'\n');print(json.dumps(dict(passed=True,controls=len(rows))))
