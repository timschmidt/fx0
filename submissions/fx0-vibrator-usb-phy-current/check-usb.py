# SPDX-License-Identifier: GPL-2.0-only
"""Run actual USB HS probe/power paths with counted init-sequence fixtures."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['zero-sentinel', 'no-odd-check', 'short-count'])
a = p.parse_args()
b = Path(__file__).resolve().parent
a.output.mkdir(mode=0o700)
s = a.source.read_text()
soc_data = []
soc_hashes = {}
for f in sorted((b/'SoC').rglob('*.dtsi')):
    soc_hashes[str(f.relative_to(b/'SoC'))] = hashlib.sha256(f.read_bytes()).hexdigest()
    for seq in re.findall(r'qcom,init-seq\s*=\s*/bits/\s*8\s*([^;]+);', f.read_text(), re.S):
        data = [int(n, 0) for n in re.findall(r'0x[0-9a-fA-F]+|\b[0-9]+\b', seq)]
        assert len(data) % 2 == 0 and all(0 <= n <= 255 for n in data)
        soc_data.append(data)
assert len(soc_data) == 3
soc_c = 'struct soc_fixture { unsigned size; const u8 *bytes; };\n'
for i, data in enumerate(soc_data):
    soc_c += 'static const u8 soc_'+str(i)+'[] = {'+','.join(map(str, data))+'};\n'
soc_c += 'static const struct soc_fixture soc_fixtures[] = {'
soc_c += ','.join('{sizeof(soc_'+str(i)+'),soc_'+str(i)+'}' for i in range(len(soc_data)))+'};\n'
if a.mutation == 'zero-sentinel':
    s = s.replace('i < uphy->num_init_seq;', 'i < uphy->num_init_seq && uphy->init_seq[i].addr;')
elif a.mutation == 'no-odd-check':
    s = s.replace('\tif (size % sizeof(struct ulpi_seq))\n\t\treturn -EINVAL;\n', '')
elif a.mutation == 'short-count':
    s = s.replace('i < uphy->num_init_seq;', 'i + 1 < uphy->num_init_seq;')


def function(name):
    m = re.search(r'^(?=[A-Za-z_])[^\n]*?\b'+name+r'\(', s, re.M)
    assert m, name
    start = m.start()
    if s[start:].startswith(name):
        previous = s[:start].rstrip('\n').rsplit('\n', 1)[-1]
        assert previous == 'static int'
        start -= len(previous) + 1
    return s[start:s.index('\n}', m.start())+2]+'\n'


definitions = s[s.index('#define ULPI_PWR_CLK_MNG_REG'):s.index('static int qcom_usb_hs_phy_set_mode')]
body = definitions
# These two unchanged callbacks have unused API parameters under host -Wextra.
# Scope only that diagnostic to those exact bodies; native W=1 is unchanged.
body += '#pragma GCC diagnostic push\n#pragma GCC diagnostic ignored "-Wunused-parameter"\n'
body += function('qcom_usb_hs_phy_set_mode')+function('qcom_usb_hs_phy_vbus_notifier')
body += '#pragma GCC diagnostic pop\n'
body += function('qcom_usb_hs_phy_power_on')+function('qcom_usb_hs_phy_power_off')
ops = re.search(r'^static const struct phy_ops qcom_usb_hs_phy_ops = \{.*?^};', s, re.M | re.S)[0]
body += ops+'\n'+function('qcom_usb_hs_phy_probe')
program = (b/'usb-head.c').read_text()+soc_c+'\n#define HAS_COUNT '+str(int('num_init_seq' in definitions))+'\n'+body+(b/'usb-tail.c').read_text()
(a.output/'actual-functions.c').write_text(body); (a.output/'model.c').write_text(program)
cmd = ['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-O1', '-g',
       '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I'+str(b),
       str(a.output/'model.c'), '-o', str(a.output/'model')]
c = subprocess.run(cmd, capture_output=True, text=True)
(a.output/'compile.stderr').write_text(c.stderr); assert c.returncode == 0, c.stderr
r = subprocess.run([str(a.output/'model')], capture_output=True, text=True)
(a.output/'run.stdout').write_text(r.stdout); (a.output/'run.stderr').write_text(r.stderr)
result = json.loads(r.stdout.splitlines()[-1]) if r.stdout else {}
result.update(returncode=r.returncode, mutation=a.mutation,
              source_SHA256=hashlib.sha256(a.source.read_bytes()).hexdigest(),
              body_SHA256=hashlib.sha256(body.encode()).hexdigest(),
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              SoC_sources=soc_hashes, actual_SoC_sequences=len(soc_data),
              sanitizer_diagnostics=bool(r.stderr), core_resources_properties_ULPI_and_notifiers_modeled=True,
              inherited_unused_callback_parameter_diagnostic_scoped_to_two_unchanged_functions=True,
              actual_USB_electrical_tuning_data_or_physical_acceptance=False)
(a.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result)); assert r.returncode in [0, 1] and not r.stderr
