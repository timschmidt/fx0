#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the charge-duration setup and real charger vote functions with a PMIC model."""
import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

HEAD = r'''
#include <assert.h>
#include <errno.h>
#include <limits.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#define BIT(n) (1U << (n))
#define GENMASK(hi, lo) (((~0U) >> (31U - (hi))) & ~((1U << (lo)) - 1U))
typedef uint32_t u32;
struct device_node {
    bool present, supported, malformed;
    u32 minutes;
};
struct device {
    struct device_node *of_node;
};
struct regmap {
    unsigned int values[0x300];
    unsigned int accesses, fail_access, control_writes, force_writes;
    unsigned int ignore_write;
    bool fail_on_charge_enable;
};
struct smbb_charger {
    struct device *dev;
    struct regmap *regmap;
    unsigned int addr, charge_lock, charge_inhibit;
    bool software_control, charge_timer_enabled;
    uint64_t policy_valid_until_ns;
};
static bool of_property_present(struct device_node *node, const char *property) {
    assert(!strcmp(property, "qcom,tchg-mins"));
    return node->present;
}
static bool of_device_is_compatible(struct device_node *node, const char *compatible) {
    assert(!strcmp(compatible, "qcom,pm8226-charger"));
    return node->supported;
}
static int of_property_read_u32(struct device_node *node, const char *property, u32 *value) {
    assert(of_property_present(node, property));
    *value = node->minutes;
    return node->malformed ? -EINVAL : 0;
}
static int regmap_read(struct regmap *map, unsigned int reg, unsigned int *value) {
    assert(reg < 0x300);
    *value = map->values[reg];
    return ++map->accesses == map->fail_access ? -ETIMEDOUT : 0;
}
static int write_masked(struct regmap *map, unsigned int reg, unsigned int mask,
                        unsigned int value, bool force) {
    assert(reg < 0x300 && !(value & ~mask));
    if (++map->accesses == map->fail_access)
        return -ETIMEDOUT;
    if (!force && (map->values[reg] & mask) == value)
        return 0;
    if (reg == SMBB_CHG_CTRL) {
        assert(mask == CTRL_EN);
        map->control_writes++;
        if (force)
            map->force_writes++;
        if (value && map->fail_on_charge_enable)
            map->values[SMBB_CHG_FAILED] |= CHG_FAILED_LATCHED;
    }
    if (reg != map->ignore_write)
        map->values[reg] = (map->values[reg] & ~mask) | value;
    return 0;
}
static int regmap_write_bits(struct regmap *map, unsigned int reg, unsigned int mask,
                             unsigned int val) {
    return write_masked(map, reg, mask, val, true);
}
static int regmap_update_bits(struct regmap *map, unsigned int reg, unsigned int mask,
                              unsigned int val) {
    return write_masked(map, reg, mask, val, false);
}
#define dev_err(dev, ...) assert((dev)->of_node)
static uint64_t ktime_get_boottime_ns(void) { return 1; }
static void mutex_lock(unsigned int *lock) {
    assert(!*lock);
    *lock = 1;
}
static void mutex_unlock(unsigned int *lock) {
    assert(*lock);
    *lock = 0;
}
'''

CASES = r'''
struct device_node node;
struct device dev = {&node};
struct regmap map;
struct smbb_charger chg;
static void reset(void) {
    node = (struct device_node){.present = true, .supported = true, .minutes = 480};
    map = (struct regmap){0};
    chg = (struct smbb_charger){.dev = &dev,
                                .regmap = &map,
                                .software_control = true,
                                .charge_inhibit = SMBB_INHIBIT_INIT,
                                .policy_valid_until_ns = 2};
    map.values[SMBB_CHG_TCHG_MAX] = 0x80;
    map.values[SMBB_CHG_TCHG_MAX_EN] = 0x20;
    map.values[SMBB_CHG_CTRL] = BIT(0);
    map.values[SMBB_BAT_BTC_CTRL] = BTC_CTRL_CONSERVATIVE;
}
static void verify_setup(void) {
    reset();
    node.present = false;
    assert(!smbb_configure_charge_timer(&chg) && !map.accesses && !chg.charge_timer_enabled);
    reset();
    node.supported = false;
    assert(smbb_configure_charge_timer(&chg) == -EINVAL && !map.accesses);
    reset();
    chg.software_control = false;
    assert(smbb_configure_charge_timer(&chg) == -EINVAL && !map.accesses);
    reset();
    node.malformed = true;
    assert(smbb_configure_charge_timer(&chg) == -EINVAL && !map.accesses);
    for (unsigned int n = 0; n <= 520; n++) {
        reset();
        node.minutes = n;
        if (n < 4 || n > 512 || n % 4) {
            assert(smbb_configure_charge_timer(&chg) == -EINVAL && !map.accesses);
            continue;
        }
        assert(!smbb_configure_charge_timer(&chg) && chg.charge_timer_enabled);
        assert(map.values[SMBB_CHG_TCHG_MAX] == (0x80U | (n / 4 - 1)));
        assert(map.values[SMBB_CHG_TCHG_MAX_EN] == (0x20U | TCHG_MAX_EN));
        assert(!map.control_writes && chg.charge_inhibit == SMBB_INHIBIT_INIT);
    }
    reset();
    node.minutes = UINT_MAX;
    assert(smbb_configure_charge_timer(&chg) == -EINVAL && !chg.charge_timer_enabled);
    for (unsigned int failure = 1; failure <= 5; failure++) {
        reset();
        map.fail_access = failure;
        assert(smbb_configure_charge_timer(&chg) == -ETIMEDOUT && !chg.charge_timer_enabled);
        assert(!map.control_writes);
    }
    reset();
    map.ignore_write = SMBB_CHG_TCHG_MAX;
    assert(smbb_configure_charge_timer(&chg) == -EIO && !chg.charge_timer_enabled);
    reset();
    map.ignore_write = SMBB_CHG_TCHG_MAX_EN;
    assert(smbb_configure_charge_timer(&chg) == -EIO && !chg.charge_timer_enabled);
    reset();
    map.values[SMBB_CHG_TCHG_MAX_EN] |= TCHG_MAX_EN;
    assert(smbb_configure_charge_timer(&chg) == -EIO && !chg.charge_timer_enabled);
}
static void verify_votes(void) {
    reset();
    assert(!smbb_configure_charge_timer(&chg));
    assert(!smbb_charge_vote(&chg, SMBB_INHIBIT_INIT, false));
    assert(map.values[SMBB_CHG_CTRL] == (CTRL_EN | BIT(0)));
    unsigned int writes = map.control_writes;
    assert(!smbb_charge_vote(&chg, SMBB_INHIBIT_INIT, false) && map.control_writes == writes);
    assert(!smbb_charge_vote(&chg, SMBB_INHIBIT_USER, true));
    assert(map.values[SMBB_CHG_CTRL] == BIT(0));
    assert(!smbb_charge_vote(&chg, SMBB_INHIBIT_USER, false));
    map.values[SMBB_CHG_FAILED] = CHG_FAILED_LATCHED;
    writes = map.control_writes;
    assert(smbb_charge_vote(&chg, SMBB_INHIBIT_USER, false) == -EIO);
    assert(map.control_writes == writes + 1 && map.values[SMBB_CHG_CTRL] == BIT(0));
    assert(map.values[SMBB_CHG_FAILED] == CHG_FAILED_LATCHED);
    assert(map.values[SMBB_BAT_BTC_CTRL] == BTC_CTRL_CONSERVATIVE &&
           chg.charge_inhibit == SMBB_INHIBIT_FAULT);
    assert(!smbb_charge_vote(&chg, SMBB_INHIBIT_USER, true));
    assert(!smbb_charge_vote(&chg, SMBB_INHIBIT_USER, false));
    assert(map.values[SMBB_CHG_CTRL] == BIT(0) && chg.charge_inhibit == SMBB_INHIBIT_FAULT);

    reset();
    assert(!smbb_configure_charge_timer(&chg));
    map.fail_on_charge_enable = true;
    assert(smbb_charge_vote(&chg, SMBB_INHIBIT_INIT, false) == -EIO);
    assert(map.values[SMBB_CHG_CTRL] == BIT(0) && chg.charge_inhibit == SMBB_INHIBIT_FAULT);
    assert(map.values[SMBB_BAT_BTC_CTRL] == BTC_CTRL_CONSERVATIVE);

    reset();
    assert(!smbb_configure_charge_timer(&chg));
    map.values[SMBB_CHG_FAILED] = CHG_FAILED_LATCHED;
    assert(smbb_charge_enable(&chg, true) == -EIO && !map.control_writes);
    assert(!smbb_charge_enable(&chg, false) && map.control_writes == 1 &&
           map.force_writes == 1);

    reset();
    assert(!smbb_configure_charge_timer(&chg));
    for (unsigned int failing_read = 1; failing_read <= 4; failing_read++) {
        const unsigned int first = map.accesses;
        map.fail_access = first + failing_read;
        assert(smbb_charge_enable(&chg, true) == -ETIMEDOUT);
        map.fail_access = 0;
        assert(!smbb_charge_enable(&chg, false));
    }
    reset();
    node.present = false;
    chg.software_control = false;
    assert(!smbb_configure_charge_timer(&chg) && !map.accesses);
    assert(!smbb_charge_enable(&chg, true) && !smbb_charge_enable(&chg, true));
    assert(map.control_writes == 2 && map.force_writes == 2);
}
int main(void) {
    verify_setup();
    verify_votes();
    return 0;
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    args = parser.parse_args()
    source = args.source.read_text()
    constants = '\n'.join(row for row in source.splitlines() if re.match(
        r'#define (SMBB_CHG_|CTRL_EN\b|CHG_FAILED_LATCHED\b|TCHG_|SMBB_BAT_BTC_CTRL\b|BTC_CTRL_|SMBB_INHIBIT_)',
        row))
    votes = source[source.index('static int smbb_read_charge_failure('):
                   source.index('static int smbb_get_charge_behaviour(')]
    setup = source[source.index('static int smbb_configure_charge_timer('):
                   source.index('static int smbb_charger_probe(')]
    with TemporaryDirectory(prefix='fx0-smbb-timer-check-') as scratch:
        fixture = Path(scratch) / 'check.c'
        fixture.write_text(constants + '\n' + HEAD + votes + setup + CASES)
        binary = Path(scratch) / 'check'
        subprocess.run(['clang-21', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        str(fixture), '-o', str(binary)], check=True)
        subprocess.run([str(binary)], check=True)
    print('Charger-duration controls passed for all 521 duration values, I/O faults, expiry races and legacy operation.')

if __name__ == '__main__':
    main()
