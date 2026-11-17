# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the production WCNSS regulator selector with owned host interfaces."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
import os

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
parser.add_argument('--expect', required=True, choices=['broken', 'fixed'])
args = parser.parse_args()
args.output.mkdir(mode=0o700)
(args.output / "tmp").mkdir(mode=0o700)
path = args.source / 'drivers/remoteproc/qcom_wcnss.c'
source = path.read_text()
start = source.index('static int wcnss_init_regulators(')
end = source.index('\n}\n', start) + len('\n}')
function = source[start:end]
data_struct = re.search(r'struct wcnss_data \{.*?\n\};', source, re.S)
assert data_struct
tables = []
for name in ['riva', 'pronto_v1', 'pronto_v2', 'pronto_v3']:
    match = re.search(r'static const struct wcnss_data ' + name + r'_data = \{.*?\n\};', source, re.S)
    assert match
    tables.append(match[0])
header = (args.source / 'drivers/remoteproc/qcom_wcnss.h').read_text()
vreg = re.search(r'struct wcnss_vreg_info \{.*?\n\};', header, re.S)
assert vreg
prefix = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define WCNSS_MAX_PDS 2
#define GFP_KERNEL 0
struct regulator { const char *name; int lo, hi, load, calls; };
struct regulator_bulk_data { const char *supply; struct regulator *consumer; };
struct device { int unused; };
struct qcom_wcnss { struct device *dev; size_t num_pds; struct regulator_bulk_data *vregs; size_t num_vregs; };
static void *allocation;
static bool fail_alloc, fail_get;
static struct regulator consumers[8];
static void *devm_kcalloc(struct device *dev, size_t n, size_t size, int flags)
{
    (void)dev; (void)flags;
    assert(!allocation);
    if (fail_alloc) return NULL;
    allocation = calloc(n, size);
    return allocation;
}
static int devm_regulator_bulk_get(struct device *dev, size_t n, struct regulator_bulk_data *bulk)
{
    (void)dev;
    if (fail_get) return -EIO;
    assert(n <= 8);
    for (size_t i = 0; i < n; i++) {
        consumers[i].name = bulk[i].supply;
        bulk[i].consumer = &consumers[i];
    }
    return 0;
}
static int regulator_set_voltage(struct regulator *reg, int lo, int hi)
{
    reg->lo = lo; reg->hi = hi; reg->calls++;
    return 0;
}
static int regulator_set_load(struct regulator *reg, int load)
{
    reg->load = load;
    return 0;
}
'''
suffix = r'''
struct expected { const char *name; int lo, hi; };
static const struct expected riva_expected[] = {
    {"vddmx", 1050000, 1150000}, {"vddcx", 1050000, 1150000}, {"vddpx", 1800000, 1800000}
};
static const struct expected v1_expected[] = {
    {"vddcx", 0, 0}, {"vddmx", 950000, 1150000}, {"vddpx", 1800000, 1800000}
};
static const struct expected v2_expected[] = {
    {"vddcx", 0, 0}, {"vddmx", 1287500, 1287500}, {"vddpx", 1800000, 1800000}
};
static const struct expected v3_expected[] = {{"vddpx", 1800000, 1800000}};
static void reset(void)
{
    free(allocation); allocation = NULL;
    fail_alloc = fail_get = false;
    memset(consumers, 0, sizeof(consumers));
}
int main(void)
{
    const struct { const struct wcnss_data *data; const struct expected *expected; size_t total, pds; } cases[] = {
        {&riva_data, riva_expected, 3, 0},
        {&pronto_v1_data, v1_expected, 3, 0},
        {&pronto_v1_data, v1_expected + 1, 2, 1},
        {&pronto_v1_data, v1_expected + 2, 1, 2},
        {&pronto_v2_data, v2_expected, 3, 0},
        {&pronto_v2_data, v2_expected + 1, 2, 1},
        {&pronto_v2_data, v2_expected + 2, 1, 2},
        {&pronto_v3_data, v3_expected, 1, 2},
    };
    unsigned correct = 0, errors = 0;
    struct device dev = {0};
    for (size_t c = 0; c < sizeof(cases) / sizeof(cases[0]); c++) {
        struct qcom_wcnss wcnss = {.dev = &dev, .num_pds = cases[c].pds};
        assert(wcnss_init_regulators(&wcnss, cases[c].data) == 0);
        bool match = wcnss.num_vregs == cases[c].total;
        for (size_t i = 0; match && i < wcnss.num_vregs; i++) {
            const struct expected *exp = &cases[c].expected[i];
            struct regulator *got = wcnss.vregs[i].consumer;
            match = !strcmp(wcnss.vregs[i].supply, exp->name) &&
                    got->lo == exp->lo && got->hi == exp->hi && !got->load &&
                    got->calls == (exp->hi != 0);
        }
        correct += match;
        printf("case=%zu pds=%zu requested=%zu expected=%zu correct=%d\n", c, cases[c].pds, wcnss.num_vregs, cases[c].total, match);
        reset();
        for (int failure = 0; failure < 2; failure++) {
            wcnss.vregs = NULL; wcnss.num_vregs = 999;
            fail_alloc = failure == 0; fail_get = failure == 1;
            int code = wcnss_init_regulators(&wcnss, cases[c].data);
            assert(code == (failure == 0 ? -ENOMEM : -EIO));
            assert(!wcnss.vregs && wcnss.num_vregs == 999);
            errors++; reset();
        }
    }
    assert(correct == (EXPECT_BROKEN ? 2 : 8));
    printf("{\"cases\":8,\"correct\":%u,\"wrong\":%u,\"error_controls\":%u}\n", correct, 8-correct, errors);
    return 0;
}
'''
c = args.output / 'regulators.c'
c.write_text(prefix + '\n' + vreg[0] + '\n' + data_struct[0] + '\n' + '\n'.join(tables) + '\n' + function + '\n' + suffix)
binary = args.output / 'regulators'
commands = [
    ['clang-21', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-missing-field-initializers', '-g', '-O1',
     '-fsanitize=address,undefined', '-fno-omit-frame-pointer',
     '-DEXPECT_BROKEN=' + str(int(args.expect == 'broken')), str(c), '-o', str(binary)],
    [str(binary)],
]
record = dict(source_SHA256=hashlib.sha256(path.read_bytes()).hexdigest(),
              executed_helper_SHA256=hashlib.sha256(function.encode()).hexdigest(),
              fixture_SHA256=hashlib.sha256(c.read_bytes()).hexdigest(), commands=commands,
              expectation=args.expect, host_interfaces_emulated=True, hardware_qualified=False, phone_access=False)
for index, command in enumerate(commands):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=os.environ | {"ASAN_OPTIONS":"detect_leaks=1:halt_on_error=1", "UBSAN_OPTIONS":"halt_on_error=1", "TMPDIR":str(args.output / "tmp")})
    (args.output / f'{index}.stdout').write_bytes(result.stdout)
    (args.output / f'{index}.stderr').write_bytes(result.stderr)
    record[f'stage_{index}_returncode'] = result.returncode
    (args.output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
    assert result.returncode == 0 and not result.stderr, (command, result.returncode, result.stderr.decode())
record.update(passed=True, result=json.loads(result.stdout.decode().splitlines()[-1]))
(args.output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record['result']))
