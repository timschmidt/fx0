# SPDX-License-Identifier: GPL-2.0-only
"""Execute extracted production halt helpers with owned host MMIO emulation."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', required=True, type=Path)
parser.add_argument('--output', required=True, type=Path)
args = parser.parse_args()
args.output.mkdir(mode=0o700)
data = (args.source / 'drivers/iommu/arm/arm-smmu/qcom_iommu.c').read_text()

def extract(name):
    start = data.index('static void ' + name + '(')
    opened = data.index('{', start)
    depth = 0
    for end in range(opened, len(data)):
        if data[end] == '{':
            depth += 1
        elif data[end] == '}':
            depth -= 1
            if depth == 0:
                return data[start:end + 1]
    raise ValueError(name)

helpers = '\n\n'.join(extract(n) for n in ['qcom_iommu_halt', 'qcom_iommu_unhalt'])
definitions = '\n'.join(line for line in data.splitlines() if any(
    line.startswith('#define ' + name + '\t') for name in
    ['QCOM_IOMMU_IMPL_DEF', 'QCOM_IOMMU_MICRO_MMU_CTRL',
     'MICRO_MMU_CTRL_HALT_REQ', 'MICRO_MMU_CTRL_IDLE']))
assert len(definitions.splitlines()) == 4
fixture = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define __iomem
#define BIT(x) (1U << (x))
typedef uint32_t u32;
struct qcom_iommu_cfg { bool halt; };
struct qcom_iommu_dev { struct qcom_iommu_cfg *cfg; void *global_base; void *dev; };
static unsigned char registers[0x3000];
static unsigned reads, writes, polls, errors;
static bool timeout;
static u32 readl_relaxed(void *p) {
    assert(p == registers + 0x2000);
    u32 value;
    memcpy(&value, p, sizeof(value));
    reads++;
    return timeout ? value : value | BIT(3);
}
static void writel_relaxed(u32 value, void *p) {
    assert(p == registers + 0x2000);
    memcpy(p, &value, sizeof(value));
    writes++;
}
#define readl_poll_timeout(reg, val, cond, delay, limit) \
    (polls++, assert((delay) == 0 && (limit) == 100000), \
     (val = readl_relaxed(reg)), timeout ? -110 : ((cond) ? 0 : -110))
#define dev_err(dev, text) ((void)(dev), (void)(text), errors++)
'''
main = r'''
int main(int argc, char **argv) {
    struct qcom_iommu_dev dev = {0};
    if (argc == 2) {
        if (!strcmp(argv[1], "halt")) qcom_iommu_halt(&dev);
        else if (!strcmp(argv[1], "unhalt")) qcom_iommu_unhalt(&dev);
        else assert(0);
        return 0;
    }
    assert(argc == 1);
    qcom_iommu_halt(&dev);
    qcom_iommu_unhalt(&dev);
    assert(reads == 0 && writes == 0 && polls == 0 && errors == 0);
    struct qcom_iommu_cfg config = {0};
    dev.cfg = &config;
    qcom_iommu_halt(&dev);
    qcom_iommu_unhalt(&dev);
    assert(reads == 0 && writes == 0 && polls == 0 && errors == 0);
    config.halt = true;
    dev.global_base = registers;
    u32 value = 0x80;
    memcpy(registers + 0x2000, &value, sizeof(value));
    qcom_iommu_halt(&dev);
    memcpy(&value, registers + 0x2000, sizeof(value));
    assert((value & BIT(2)) && (value & 0x80));
    qcom_iommu_unhalt(&dev);
    memcpy(&value, registers + 0x2000, sizeof(value));
    assert(!(value & BIT(2)) && (value & 0x80));
    assert(writes == 2 && polls == 1 && errors == 0);
    timeout = true;
    qcom_iommu_halt(&dev);
    qcom_iommu_unhalt(&dev);
    memcpy(&value, registers + 0x2000, sizeof(value));
    assert(!(value & BIT(2)) && (value & 0x80));
    assert(writes == 4 && polls == 2 && errors == 1);
    puts("Four cases passed: absent cfg, disabled halt, enabled RMW, timeout diagnostic");
    return 0;
}
'''
original_address = '\tvoid __iomem *reg = qcom_iommu->global_base + QCOM_IOMMU_MICRO_MMU_CTRL;'
address = '\treg = qcom_iommu->global_base + QCOM_IOMMU_MICRO_MMU_CTRL;\n'
assert helpers.count(address) == 2
negative = helpers.replace('\tvoid __iomem *reg;', original_address).replace('\n' + address, '')
assert original_address in negative
env = os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:abort_on_error=1',
                    'UBSAN_OPTIONS': 'halt_on_error=1:print_stacktrace=1'}
record = dict(source_SHA256=hashlib.sha256(data.encode()).hexdigest(),
              helper_SHA256=hashlib.sha256(helpers.encode()).hexdigest(), stages=[],
              fixture_scope='Copied production helpers; minimal structs and owned emulated MMIO, no kernel ABI or hardware acceptance',
              phone_access=False)

def run(name, command):
    child = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           env=env, timeout=30)
    (args.output / (name + '.log')).write_bytes(child.stdout)
    record['stages'].append(dict(name=name, returncode=child.returncode))
    (args.output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
    return child

for name, functions in [('candidate', helpers), ('negative', negative)]:
    path = args.output / (name + '.c')
    path.write_text(fixture + definitions + '\n' + functions + main)
    code = run(name + '-compile', ['clang-21', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                                  '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                                  str(path), '-o', str(args.output / name)])
    assert code.returncode == 0 and not code.stdout.strip()
positive = run('candidate-run', [str(args.output / 'candidate')])
assert positive.returncode == 0 and b'Four cases passed' in positive.stdout
for which in ['halt', 'unhalt']:
    control = run('negative-' + which, [str(args.output / 'negative'), which])
    assert control.returncode != 0
    assert b'applying non-zero offset 8192 to null pointer' in control.stdout
record.update(passed=True, positive_cases=4, rejected_original_behavior_controls=2,
              ASan_UBSan=True, runtime_hardware_test=False)
(args.output / 'controller.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record))
