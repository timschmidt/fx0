# SPDX-License-Identifier: GPL-2.0-only
from pathlib import Path
import json,subprocess,sys
B=Path(__file__).resolve().parent;R=B.parents[1];S=Path(sys.argv[1]) if len(sys.argv)>1 else R/'worktrees/linux-fx0-cpu-current-01'
O=Path(sys.argv[2]) if len(sys.argv)>2 else B/'pm-controls-01';O.mkdir(exist_ok=False)
s=(S/'kernel/power/suspend.c').read_text()
mutations=[
 ('mem-prepare-before-noirq','return state == PM_SUSPEND_TO_IDLE && s2idle_ops && s2idle_ops->prepare ?\n\t\ts2idle_ops->prepare() : 0;', 'return state == PM_SUSPEND_MEM ? suspend_ops->prepare_late() :\n\t\t(state == PM_SUSPEND_TO_IDLE && s2idle_ops && s2idle_ops->prepare ? s2idle_ops->prepare() : 0);'),
 ('drop-mem-prepare','return suspend_ops->prepare_late ? suspend_ops->prepare_late() : 0;','return 0;'),
 ('mem-early-restore','if (state == PM_SUSPEND_TO_IDLE && s2idle_ops && s2idle_ops->restore)','if (s2idle_ops && s2idle_ops->restore)'),
 ('finish-before-devices','\tdpm_resume_early(PMSG_RESUME);\n\n Platform_finish:', '\tplatform_resume_finish(state);\n\tdpm_resume_early(PMSG_RESUME);\n\n Platform_finish:'),
]
rows=[]
for name,before,after in mutations:
 assert s.count(before)==1,(name,s.count(before))
 tree=O/name/'tree';(tree/'kernel/power').mkdir(parents=True);(tree/'kernel/power/suspend.c').write_text(s.replace(before,after))
 out=O/name/'result';r=subprocess.run([sys.executable,'-B',str(B/'check-pm-order.py'),str(tree),str(out)],capture_output=True,text=True,timeout=45)
 (O/name/'controller.stdout').write_text(r.stdout);(O/name/'controller.stderr').write_text(r.stderr)
 j=json.loads((out/'qualification.json').read_text());stderr=(out/'run.stderr').read_text()
 assert j['returncode']==1 and ': ' in stderr and not any(t in stderr for t in ['AddressSanitizer','LeakSanitizer','runtime error:']), (name,j,stderr)
 rows.append(dict(name=name,rejected_by_intended_assertion=True,assertion=stderr.strip()))
(O/'qualification.json').write_text(json.dumps(dict(passed=True,controls=len(rows),records=rows,compile_crash_or_sanitizer_failure_counted=False),indent=2)+'\n');print(json.dumps(dict(passed=True,controls=len(rows))))
