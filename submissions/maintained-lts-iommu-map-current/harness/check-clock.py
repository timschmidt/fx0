# SPDX-License-Identifier: GPL-2.0-only
"""Exercise current production MMCC data, RCG programming and CCF rounding."""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import json
import os
import re
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--expect-mnd', required=True, choices=['broken', 'fixed'])
parser.add_argument('--expect-axi', required=True, choices=['broken', 'fixed'])
args = parser.parse_args()
args.output.mkdir(mode=0o700)
root = args.source
paths = ['drivers/clk/qcom/mmcc-msm8974.c', 'drivers/clk/qcom/clk-rcg2.c',
         'drivers/clk/qcom/common.c', 'drivers/clk/clk.c',
         'drivers/clk/qcom/clk-rcg.h', 'drivers/clk/qcom/clk-branch.c']
text = {p: (root / p).read_text() for p in paths}
mmcc, rcg, common, core, header, branch = [text[p] for p in paths]

def balanced(value, start):
    opened = value.index('{', start)
    depth = 0
    for end in range(opened, len(value)):
        if value[end] == '{': depth += 1
        elif value[end] == '}':
            depth -= 1
            if depth == 0: return value[start:end + 1]
    raise ValueError(start)

def function(value, name):
    match = re.search(r'(?m)^(?:static\s+)?(?:unsigned long|int|bool|const\s+struct freq_tbl\s*\*)\s*' + re.escape(name) + r'\([^;{}]*\)\s*\{', value)
    assert match, name
    return balanced(value, match.start())

def declaration(value, name):
    match = re.search(r'(?m)^static (?:const )?struct \w+ ' + re.escape(name) + r'(?:\[\])? = \{', value)
    assert match, name
    return balanced(value, match.start()) + ';'

macros = []
needed = ['CMD_REG', 'CMD_UPDATE', 'CFG_REG', 'CFG_SRC_DIV_SHIFT', 'CFG_SRC_SEL_SHIFT',
          'CFG_SRC_SEL_MASK', 'CFG_MODE_SHIFT', 'CFG_MODE_MASK', 'CFG_MODE_DUAL_EDGE',
          'CFG_HW_CLK_CTRL_MASK', 'M_REG', 'N_REG', 'D_REG', 'RCG_CFG_OFFSET',
          'RCG_M_OFFSET', 'RCG_N_OFFSET', 'RCG_D_OFFSET']
for name in needed:
    match = re.search(r'(?m)^#define ' + name + r'(?:\([^\n]*?\))?\s+[^\n]+', rcg)
    assert match, name
    macros.append(match[0])
macro_f = re.search(r'(?m)^#define F\([^\n]+', header)[0]
enum = balanced(mmcc, mmcc.index('enum {')) + ';'
data_names = ['mmcc_xo_mmpll0_mmpll1_gpll0_map', 'mmcc_xo_mmpll0_mmpll1_gpll0',
              'ftbl_camss_mclk0_3_clk', 'ftbl_camss_mclk0_3_clk_msm8226',
              'ftbl_mmss_axi_clk', 'ftbl_mmss_axi_clk_msm8226',
              'mclk0_clk_src', 'mclk1_clk_src', 'mclk2_clk_src', 'mclk3_clk_src',
              'mmss_axi_clk_src', 'camss_vfe_vfe_axi_clk']
data = '\n\n'.join(declaration(mmcc, n) for n in data_names)
ops = declaration(branch.replace('const struct clk_ops clk_branch2_ops', 'static const struct clk_ops clk_branch2_ops'), 'clk_branch2_ops')
helpers = '\n\n'.join([
    function(common, 'qcom_find_src_index'), function(common, 'qcom_find_freq'),
    *[function(rcg, n) for n in ['calc_rate', '__clk_rcg2_recalc_rate', 'clk_rcg2_recalc_rate',
       'update_config', '__clk_rcg2_configure_parent', '__clk_rcg2_configure_mnd',
       '__clk_rcg2_configure', 'clk_rcg2_configure']],
    function(core, 'clk_core_determine_round_nolock'), function(core, 'clk_core_can_round'),
    function(core, 'clk_core_round_rate_nolock')])

rows = []
for table, clocks in [('ftbl_camss_mclk0_3_clk', range(4)), ('ftbl_camss_mclk0_3_clk_msm8226', range(2))]:
    entries = re.findall(r'F\(\s*(\d+),\s*(P_\w+),\s*([\d.]+),\s*(\d+),\s*(\d+)\)', declaration(mmcc, table))
    for clock in clocks:
        for index, (rate, parent, div, m, n) in enumerate(entries):
            parent_rate = {'P_XO': 19200000, 'P_GPLL0': 600000000, 'P_MMPLL0': 800000000}[parent]
            desired = Fraction(parent_rate) / Fraction(div)
            if int(n): desired *= Fraction(int(m), int(n))
            rows.append('{ &mclk%d_clk_src, %s, %d, %d, %d, %d }' % (clock, table, index, parent_rate, desired.numerator // desired.denominator, bool(int(n))))
assert len(rows) == 50
main = r'''
struct sample { struct clk_rcg2 *rcg; const struct freq_tbl *table; unsigned index; unsigned long parent, expected; bool fraction; };
static const struct sample samples[] = { ROWS };
static unsigned parent_calls;
static bool parent_error;
static int table_parent_determine(struct clk_hw *hw, struct clk_rate_request *req) {
    parent_calls++;
    if (parent_error) return -EIO;
    const struct freq_tbl *f = qcom_find_freq(to_clk_rcg2(hw)->freq_tbl, req->rate);
    req->rate = f->freq;
    return 0;
}
static const struct clk_ops parent_ops = { .determine_rate = table_parent_determine };
int main(void) {
    unsigned mismatches = 0, successes = 0;
    for (unsigned i = 0; i < ARRAY_SIZE(samples); i++) {
        const struct sample *s = &samples[i];
        struct regmap map = { .cmd = s->rcg->cmd_rcgr, .fail_reg = -1 };
        s->rcg->clkr.regmap = &map;
        map.words[RCG_CFG_OFFSET(s->rcg) / 4] = BIT(30);
        const struct freq_tbl *f = &s->table[s->index];
        assert(clk_rcg2_configure(s->rcg, f) == 0);
        unsigned long rate = clk_rcg2_recalc_rate(&s->rcg->clkr.hw, s->parent);
        assert(map.words[RCG_CFG_OFFSET(s->rcg) / 4] & BIT(30));
        if (rate == s->expected) successes++; else mismatches++;
        assert(map.mnd_writes == ((s->rcg->mnd_width && s->fraction) ? 3U : 0U));
        if (f->freq == 24000000 && s->rcg->mnd_width == 0) assert(rate == 120000000);
    }
    assert(successes == EXPECT_SUCCESS && mismatches == EXPECT_FAILURE);
    /* Failure propagation through each actual programming stage. */
    struct clk_rcg2 *r = &mclk0_clk_src;
    struct regmap map = { .cmd = r->cmd_rcgr, .fail_reg = -1 };
    r->clkr.regmap = &map;
    const struct freq_tbl *f = &ftbl_camss_mclk0_3_clk_msm8226[1];
    const unsigned offsets[] = { CFG_REG, M_REG, N_REG, D_REG, CMD_REG };
    unsigned io_cases = 0;
    for (unsigned i = 0; i < ARRAY_SIZE(offsets); i++) {
        if (!r->mnd_width && (offsets[i] == M_REG || offsets[i] == N_REG || offsets[i] == D_REG)) continue;
        map.fail_reg = r->cmd_rcgr + offsets[i];
        assert(clk_rcg2_configure(r, f) == -EIO);
        io_cases++;
    }
    map.fail_reg = -1;
    struct freq_tbl invalid = *f;
    invalid.src = 255;
    assert(clk_rcg2_configure(r, &invalid) == -ENOENT);
    unsigned width_controls = 0;
    struct clk_rcg2 *clocks[] = { &mclk0_clk_src, &mclk1_clk_src, &mclk2_clk_src, &mclk3_clk_src };
    if (EXPECT_FAILURE == 0) for (unsigned i = 0; i < ARRAY_SIZE(clocks); i++) {
        struct regmap control = { .cmd = clocks[i]->cmd_rcgr, .fail_reg = -1 };
        clocks[i]->clkr.regmap = &control;
        u8 width = clocks[i]->mnd_width;
        clocks[i]->mnd_width = 0;
        assert(clk_rcg2_configure(clocks[i], f) == 0);
        assert(clk_rcg2_recalc_rate(&clocks[i]->clkr.hw, 600000000) == 120000000);
        clocks[i]->mnd_width = width;
        width_controls++;
    }
    struct clk_core parent = { .name = "MMSS AXI", .hw = &mmss_axi_clk_src.clkr.hw, .ops = &parent_ops, .rate = 100000000 };
    struct clk_core child = { .name = "VFE AXI", .hw = &camss_vfe_vfe_axi_clk.clkr.hw,
        .ops = camss_vfe_vfe_axi_clk.clkr.hw.init->ops,
        .flags = camss_vfe_vfe_axi_clk.clkr.hw.init->flags, .rate = 100000000, .parent = &parent };
    mmss_axi_clk_src.freq_tbl = ftbl_mmss_axi_clk_msm8226;
    struct clk_rate_request req = { .rate = 266670000, .max_rate = ULONG_MAX };
    assert(clk_core_round_rate_nolock(&child, &req) == 0);
    assert(req.rate == EXPECT_AXI && parent_calls == EXPECT_PARENT_CALLS);
    parent_error = true;
    req.rate = 266670000;
    assert(clk_core_round_rate_nolock(&child, &req) == (EXPECT_PARENT_CALLS ? -EIO : 0));
    /* The original flag omission prevents forwarding even with the fixed data. */
    if (EXPECT_PARENT_CALLS) {
        child.flags &= ~CLK_SET_RATE_PARENT;
        parent_error = false; parent_calls = 0; req.rate = 266670000;
        assert(clk_core_round_rate_nolock(&child, &req) == 0);
        assert(req.rate == 100000000 && parent_calls == 0);
    }
    printf("{\"rate_cases\":50,\"correct\":%u,\"mismatches\":%u,\"IO_error_cases\":%u,\"width_controls\":%u,\"AXI_rate\":%lu}\n",
        successes, mismatches, io_cases, width_controls, (unsigned long)EXPECT_AXI);
    return 0;
}
'''
main = main.replace('ROWS', ',\n'.join(rows))
main = main.replace('EXPECT_SUCCESS', '50' if args.expect_mnd == 'fixed' else '28')
main = main.replace('EXPECT_FAILURE', '0' if args.expect_mnd == 'fixed' else '22')
main = main.replace('EXPECT_AXI', '266666666UL' if args.expect_axi == 'fixed' else '100000000UL')
main = main.replace('EXPECT_PARENT_CALLS', '1' if args.expect_axi == 'fixed' else '0')
code = (Path(__file__).with_name('fixture.h').read_text() + '\n' + '\n'.join(macros) + '\n' + macro_f + '\n' + enum + '\n' + ops + '\n' + data + '\n' + helpers + '\n' + main)
(args.output / 'fixture.c').write_text(code)
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
record = dict(source_files_SHA256={p: hashlib.sha256(v.encode()).hexdigest() for p, v in text.items()},
              expected_mnd=args.expect_mnd, expected_axi=args.expect_axi,
              fixtures_SHA256=hashlib.sha256(code.encode()).hexdigest(), stages=[], phone_access=False,
              scope='Production descriptor/RCG/CCF-rounding code; owned regmap and table-backed parent emulation, no hardware or full CCF rate-change acceptance')
for name, command in [('compile', ['clang-21', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', str(args.output / 'fixture.c'), '-o', str(args.output / 'fixture')]),
    ('run', [str(args.output / 'fixture')])]:
    c = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=60)
    (args.output / (name + '.log')).write_bytes(c.stdout)
    record['stages'].append(dict(name=name, returncode=c.returncode))
    (args.output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
    assert c.returncode == 0, c.stdout.decode()
    if name == 'compile': assert not c.stdout.strip()
    else: record['observed'] = json.loads(c.stdout)
record['passed'] = True
(args.output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
