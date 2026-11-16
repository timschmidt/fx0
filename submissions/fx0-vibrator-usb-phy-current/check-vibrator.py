# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual voltage selection and both drive-register fields."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['wrong-range', 'missing-limit', 'stale-drive', 'upper-left'])
a = p.parse_args()
b = Path(__file__).resolve().parent
a.output.mkdir(mode=0o700)
s = a.source.read_text()
if a.mutation == 'wrong-range':
    s = s.replace('(vib)->regs->drv2_mask ?', '(vib)->drv2_addr ?')
elif a.mutation == 'missing-limit':
    s = s.replace('\tvib->level = min(vib->level, VIB_MAX_LEVEL_mV(vib));\n', '')
elif a.mutation == 'stale-drive':
    s = s.replace('\t\tval = (val & ~regs->drv_mask) |\n\t\t      ((vib->level << regs->drv_shift) & regs->drv_mask);',
                  '\t\tval |= (vib->level << regs->drv_shift) & regs->drv_mask;')
elif a.mutation == 'upper-left':
    s = s.replace('vib->level >> regs->drv2_shift', 'vib->level << regs->drv2_shift')


def function(name):
    m = re.search(r'^static (?:int|void) '+name+r'\([^)]*\)\n\{.*?^}', s, re.M | re.S)
    assert m, name
    return m[0]


definitions = s[s.index('#define VIB_MAX_LEVEL_mV'):s.index('/**')]
declaration = re.search(r'^struct pm8xxx_vib \{.*?^};', s, re.M | re.S)[0]
body = definitions+declaration+'\n'+function('pm8xxx_vib_set')+'\n'+function('pm8xxx_work_handler')+'\n'
program = (b/'vibrator-head.c').read_text()+body+(b/'vibrator-tail.c').read_text()
(a.output/'actual-functions.c').write_text(body)
(a.output/'model.c').write_text(program)
cmd = ['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
       '-fsanitize=address,undefined', '-fno-omit-frame-pointer', str(a.output/'model.c'), '-o', str(a.output/'model')]
c = subprocess.run(cmd, capture_output=True, text=True)
(a.output/'compile.stderr').write_text(c.stderr)
assert c.returncode == 0, c.stderr
r = subprocess.run([str(a.output/'model')], capture_output=True, text=True)
(a.output/'run.stdout').write_text(r.stdout); (a.output/'run.stderr').write_text(r.stderr)
result = json.loads(r.stdout.splitlines()[-1])
result.update(returncode=r.returncode, mutation=a.mutation,
              source_SHA256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
              body_SHA256=hashlib.sha256(body.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              sanitizer_diagnostics=bool(r.stderr), core_regmap_work_services_modeled=True,
              full_FF_IOCTL_or_physical_acceptance=False)
(a.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert r.returncode in [0, 1] and not r.stderr
