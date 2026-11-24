#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the actual driver voltage functions with a host register-map fixture."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

PRELUDE = r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
typedef uint8_t u8;
#define BIT(n) (1U << (n))
#define GENMASK(h, l) (((1U << ((h) + 1)) - 1) & ~((1U << (l)) - 1))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define mult_frac(x, n, d) (((x) / (d)) * (n) + ((x) % (d)) * (n) / (d))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
struct input_dev {};
struct work_struct { int unused; };
struct regmap { unsigned int values[0x10000]; };
static int regmap_read(struct regmap *map, unsigned int addr, unsigned int *value)
{
    assert(addr < 0x10000);
    *value = map->values[addr];
    return 0;
}
static int regmap_write(struct regmap *map, unsigned int addr, unsigned int value)
{
    assert(addr < 0x10000 && value <= 255);
    map->values[addr] = value;
    return 0;
}
static int regmap_update_bits(struct regmap *map, unsigned int addr, unsigned int mask, unsigned int value)
{
    return regmap_write(map, addr, (map->values[addr] & ~mask) | (value & mask));
}
#define regmap_write_bits regmap_update_bits
'''

HARNESS = r'''
int main(void)
{
    const struct pm8xxx_regs *variants[] = { &pm8058_regs, &pm8916_regs, &pmi632_regs };
    static struct regmap map;
    int checks = 0, index, speed;

    for (index = 0; index < 3; ++index) {
        const struct pm8xxx_regs *regs = variants[index];
        unsigned int base = index == 0 ? 0x4a : 0xc000;
        struct pm8xxx_vib vib = {
            .regmap = &map, .regs = regs,
            .enable_addr = base + regs->enable_offset,
            .drv_addr = base + regs->drv_offset,
            .drv2_addr = base + regs->drv2_offset,
        };
        int low = index == 2 ? 1504 : 1200;
        int high = index == 2 ? 3544 : 3100;
        int step = index == 2 ? 8 : 100;

        /* The absolute address is nonzero in all three variants. */
        assert(vib.drv2_addr != 0);
        for (speed = 0; speed < 256; ++speed) {
            int millivolts = low + ((high - low + step) * speed) / 255;
            int expected;
            unsigned int output;
            if (millivolts > high)
                millivolts = high;
            expected = regs->drv_in_step ? millivolts / step : millivolts;
            vib.speed = speed;
            pm8xxx_work_handler(&vib.work);
            if (!speed) {
                assert(!vib.active);
                assert(!(map.values[vib.drv_addr] & regs->drv_mask));
                if (regs->enable_mask)
                    assert(!(map.values[vib.enable_addr] & regs->enable_mask));
            } else {
                assert(vib.active);
                assert(vib.level == expected);
                output = map.values[vib.drv_addr] & regs->drv_mask;
                assert(output == ((expected << regs->drv_shift) & regs->drv_mask));
                if (index < 2)
                    assert((output >> regs->drv_shift) >= 12 && (output >> regs->drv_shift) <= 31);
                if (regs->enable_mask)
                    assert(map.values[vib.enable_addr] & regs->enable_mask);
            }
            checks++;
        }
        vib.speed = 0;
        pm8xxx_work_handler(&vib.work);
        assert(!vib.active);
    }
    printf("%d speed/variant cases passed\n", checks);
    return 0;
}
'''


def function(text, name):
    match = re.search(r'^static (?:int|void) ' + name + r'\([^)]*\)\n\{.*?^}',
                      text, re.MULTILINE | re.DOTALL)
    assert match, name
    return match[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    reports = {}
    fixed = args.candidate.read_text()
    clamp = '\tvib->level = min(vib->level, VIB_MAX_LEVEL_mV(vib));\n'
    masked = '\t\tval = (val & ~regs->drv_mask) |\n\t\t      ((vib->level << regs->drv_shift) & regs->drv_mask);'
    assert fixed.count(clamp) == 1 and fixed.count(masked) == 1
    assert fixed.count('(vib)->regs->drv2_mask ?') == 3
    controls = [
        ('control', args.control.read_text()), ('candidate', fixed),
        ('wrong-range', fixed.replace('(vib)->regs->drv2_mask ?', '(vib)->drv2_addr ?')),
        ('missing-limit', fixed.replace(clamp, '')),
        ('stale-drive', fixed.replace(masked, '\t\tval |= (vib->level << regs->drv_shift) & regs->drv_mask;')),
    ]
    for label, source in controls:
        definitions = source[source.index('#define VIB_MAX_LEVEL_mV'):source.index('/**')]
        declaration = re.search(r'^struct pm8xxx_vib \{.*?^};', source, re.MULTILINE | re.DOTALL)[0]
        code = PRELUDE + definitions + declaration + '\n'
        code += function(source, 'pm8xxx_vib_set') + '\n' + function(source, 'pm8xxx_work_handler') + '\n'
        code += HARNESS
        test_source = args.output / (label + '.c')
        test_source.write_text(code)
        executable = args.output / label
        build = subprocess.run(['clang', '-Wall', '-Wextra', '-Werror', '-O1', '-fsanitize=address,undefined',
                                '-fno-omit-frame-pointer', test_source, '-o', executable],
                               capture_output=True, text=True)
        (args.output / (label + '-build.log')).write_text(build.stdout + build.stderr)
        build.check_returncode()
        result = subprocess.run([executable], capture_output=True, text=True,
                                env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=0'})
        (args.output / (label + '.log')).write_text(result.stdout + result.stderr)
        assert (result.returncode == 0) == (label == 'candidate'), label
        reports[label] = {'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
                          'returncode': result.returncode, 'stdout': result.stdout.strip()}
    assert reports['candidate']['stdout'] == '768 speed/variant cases passed'
    record = {'host_ASan_UBSan_cases': 768, 'original_control_rejected': True,
              'independent_regression_controls_rejected': ['wrong-range', 'missing-limit', 'stale-drive'],
              'results': reports,
              'scope': 'Actual voltage selection, driver level and legacy drive fields. PMI632 high-byte encoding remains outside this check.'}
    (args.output / 'verification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
