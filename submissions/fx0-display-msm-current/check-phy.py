# SPDX-License-Identifier: GPL-2.0-only
"""Compare actual before/after PHY register traces using pinned vendor lane data."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser()
p.add_argument('source', type=Path)
p.add_argument('before', type=Path)
p.add_argument('vendor', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['unconditional', 'lane-value'])
args = p.parse_args()
base = Path(__file__).resolve().parent
args.output.mkdir(mode=0o700)
source = args.source.read_text()
before = args.before.read_text()


def function(text, name):
    m = re.search(r'^static[^\n]*\b' + name + r'\(', text, re.M)
    assert m, name
    return text[m.start():text.index('\n}', m.start()) + 2] + '\n'


vendor = args.vendor.read_text()
lane = re.search(r'qcom,platform-lane-config\s*=\s*\[([^]]+)\]', vendor, re.S)
assert lane
data = bytes.fromhex(lane[1])
assert len(data) == 45
values = [data[i * 9 + 4] for i in range(4)]
pieces = [line for line in source.splitlines() if line.startswith('#define DSI_PHY_28NM_QUIRK_')]
pieces.append('static const u32 vendor_lane_cfg4[4] = {' + ','.join(map(str, values)) + '};')
for name in ['dsi_28nm_dphy_set_timing', 'dsi_28nm_phy_regulator_enable_dcdc',
             'dsi_28nm_phy_regulator_enable_ldo', 'dsi_28nm_phy_regulator_ctrl',
             'dsi_28nm_phy_disable']:
    assert function(source, name) == function(before, name), name
    pieces.append(function(source, name))
pieces += ['#define dsi_28nm_phy_enable baseline_dsi_28nm_phy_enable',
           function(before, 'dsi_28nm_phy_enable'), '#undef dsi_28nm_phy_enable']
enable = function(source, 'dsi_28nm_phy_enable')
if args.mutation == 'unconditional':
    enable = enable.replace('phy->cfg->quirks & DSI_PHY_28NM_QUIRK_PHY_8226 ?', 'true ?')
if args.mutation == 'lane-value':
    enable = enable.replace('(i << 2) | i', '(i << 1) | i')
pieces.append(enable)
body = '\n'.join(pieces)
(args.output / 'actual-functions.c').write_text(body)
program = (base/'phy-head.c').read_text() + '\n' + body + '\n' + (base/'phy-tail.c').read_text()
(args.output/'model.c').write_text(program)
command = ['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
           '-fsanitize=address,undefined', '-fno-omit-frame-pointer', '-I'+str(base/'generated'),
           str(args.output/'model.c'), '-o', str(args.output/'model')]
c = subprocess.run(command, capture_output=True, text=True)
(args.output/'compile.stderr').write_text(c.stderr)
assert c.returncode == 0, c.stderr
run = subprocess.run([str(args.output/'model')], capture_output=True, text=True)
(args.output/'run.stdout').write_text(run.stdout)
(args.output/'run.stderr').write_text(run.stderr)
result = json.loads(run.stdout.splitlines()[-1]) if run.stdout else {}
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
result.update(returncode=run.returncode, source_SHA256=sha(args.source), before_SHA256=sha(args.before),
              vendor_SHA256=sha(args.vendor), generated_header_SHA256=sha(base/'generated/dsi_phy_28nm.xml.h'),
              body_SHA256=hashlib.sha256(body.encode()).hexdigest(), program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              vendor_lane_CFG4=values, timing_calculation_and_MMIO_mocked=True, PLL_not_executed=True,
              mutation=args.mutation, sanitizer_diagnostics=bool(run.stderr), physical_acceptance=False)
(args.output/'qualification.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
assert not run.stderr, run.stderr
assert run.returncode in [0, 1]
