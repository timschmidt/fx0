# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import json,subprocess,sys
B=Path(__file__).resolve().parent;R=B.parents[1];S=Path(sys.argv[1]) if len(sys.argv)>1 else R/'worktrees/linux-qcom-spm-rpm-current-01'
O=Path(sys.argv[2]) if len(sys.argv)>2 else B/'admission-controls-01';O.mkdir(exist_ok=False)
s=(S/'drivers/soc/qcom/smd-rpm.c').read_text();h=(S/'include/linux/soc/qcom/smd-rpm.h').read_text()
mutations=[
 ('ignore-freeze', 'if (rpm->sleep_owner) {\n\t\tret = -EBUSY;\n\t\tgoto unlock;', 'if (false) {\n\t\tret = -EBUSY;\n\t\tgoto unlock;'),
 ('forget-uncertainty', 'if (ret)\n\t\trpm->uncertain = true;', 'if (false)\n\t\trpm->uncertain = true;'),
 ('clear-on-success', 'if (ret)\n\t\trpm->uncertain = true;', 'rpm->uncertain = !!ret;'),
 ('admit-uncertain', '} else if (rpm->uncertain) {', '} else if (false) {'),
 ('copy-token-releases', 'rpm->sleep_owner != token || !token->cookie ||', '!rpm->sleep_owner || !token->cookie ||'),
 ('ignore-cookie', 'token->cookie != rpm->sleep_sequence)', 'false)'),
 ('reuse-cookie', 'token->cookie = ++rpm->sleep_sequence;', 'token->cookie = 1; rpm->sleep_sequence = 1;'),
 ('retain-token', 'token->cookie = 0;', 'token->cookie = rpm->sleep_sequence;'),
 ('retain-owner', 'rpm->sleep_owner = NULL;', 'rpm->sleep_owner = token;'),
 ('ignore-irq-freeze', 'if (irqs_disabled())\n\t\treturn -EPERM;', 'if (false)\n\t\treturn -EPERM;'),
 ('allow-wrap', 'rpm->sleep_sequence == U64_MAX', 'false'),
 ('steal-existing-owner', 'if (rpm->sleep_owner) {\n\t\tret = -EBUSY;\n\t} else', 'if (false) {\n\t\tret = -EBUSY;\n\t} else'),
]
records=[]
for name,before,after in mutations:
 assert before in s,name
 t=O/name/'tree';(t/'drivers/soc/qcom').mkdir(parents=True);(t/'include/linux/soc/qcom').mkdir(parents=True)
 (t/'drivers/soc/qcom/smd-rpm.c').write_text(s.replace(before,after,1));(t/'include/linux/soc/qcom/smd-rpm.h').write_text(h)
 out=O/name/'result'
 r=subprocess.run([sys.executable,'-B',str(B/'check-admission.py'),str(t),str(out)],capture_output=True,text=True,timeout=80)
 (O/name/'controller.stdout').write_text(r.stdout);(O/name/'controller.stderr').write_text(r.stderr)
 j=json.loads((out/'qualification.json').read_text())
 stderr=(out/'run.stderr').read_text()
 assert j['returncode']==1 and ': ' in stderr and not any(x in stderr for x in ['AddressSanitizer','UndefinedBehaviorSanitizer','runtime error:','LeakSanitizer']), (name,j,stderr)
 records.append(dict(name=name,rejected_by_intended_assertion=True,returncode=j['returncode'],assertion=stderr.strip()))
(O/'qualification.json').write_text(json.dumps(dict(passed=True,controls=len(records),records=records,compile_crash_or_sanitizer_failure_counted=False),indent=2)+'\n')
print(json.dumps(dict(passed=True,controls=len(records))))
