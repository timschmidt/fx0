#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the real SMBB battery-temperature interrupt handler."""
import argparse
from pathlib import Path
import re
import resource
import subprocess
import tempfile

NAMES = (
    'SMBB_BAT_TEMP_STATUS', 'TEMP_STATUS_OK', 'TEMP_STATUS_HOT',
    'STATUS_BAT_OK', 'STATUS_BAT_HOT',
)
STUBS = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdio.h>

#define BIT(n) (1UL << (n))
#define IRQ_HANDLED 1
typedef int irqreturn_t;

struct fixture {
    unsigned int register_value;
    int read_error;
    unsigned int reads;
    unsigned int locks;
    unsigned int notifications;
    bool locked;
};

struct smbb_charger {
    struct fixture *regmap;
    struct fixture *statlock;
    struct fixture *bat_psy;
    unsigned int addr;
    unsigned long status;
};

static int regmap_read(struct fixture *test, unsigned int address, unsigned int *value)
{
    assert(address == 0x1000 + SMBB_BAT_TEMP_STATUS);
    assert(!test->locked);
    test->reads++;
    if (test->read_error)
        return test->read_error;
    *value = test->register_value;
    return 0;
}

/* The model uses one observation object for the register map and lock. */
static void mutex_lock(struct fixture **lock)
{
    assert(!(*lock)->locked);
    (*lock)->locked = true;
    (*lock)->locks++;
}

static void mutex_unlock(struct fixture **lock)
{
    assert((*lock)->locked);
    (*lock)->locked = false;
}

static void power_supply_changed(struct fixture *test)
{
    assert(!test->locked);
    test->notifications++;
}
"""
TESTS = r"""
static unsigned long flags_for(unsigned int value)
{
    if (value & TEMP_STATUS_OK)
        return STATUS_BAT_OK;
    if (value & TEMP_STATUS_HOT)
        return STATUS_BAT_HOT;
    return 0;
}

int main(void)
{
    const unsigned long unchanged = BIT(16) | BIT(18);
    const unsigned long previous[] = {
        0, STATUS_BAT_OK, STATUS_BAT_HOT, STATUS_BAT_OK | STATUS_BAT_HOT,
    };
    struct fixture observed = {0};
    struct smbb_charger chip = {
        .regmap = &observed,
        .statlock = &observed,
        .bat_psy = &observed,
        .addr = 0x1000,
    };

    /* A COOL interrupt must clear the cached HOT flag from the last IRQ. */
    observed.register_value = TEMP_STATUS_HOT;
    assert(smbb_bat_temp_handler(0, &chip) == IRQ_HANDLED);
    assert(chip.status == STATUS_BAT_HOT);
    observed.register_value = 0;
    assert(smbb_bat_temp_handler(0, &chip) == IRQ_HANDLED);
    if (chip.status != 0) {
        fprintf(stderr, "Stale HOT flag on direct hot-to-cold transition\n");
        return 1;
    }

    for (unsigned int initial = 0; initial < 4; initial++) {
        for (unsigned int value = 0; value < 256; value++) {
            chip.status = unchanged | previous[initial];
            observed.register_value = value;
            assert(smbb_bat_temp_handler(0, &chip) == IRQ_HANDLED);
            assert(chip.status == (unchanged | flags_for(value)));
        }
    }

    assert(observed.reads == 1026);
    assert(observed.locks == observed.reads);
    assert(observed.notifications == observed.reads);

    observed.read_error = -EIO;
    for (unsigned int initial = 0; initial < 4; initial++) {
        chip.status = unchanged | previous[initial];
        assert(smbb_bat_temp_handler(0, &chip) == IRQ_HANDLED);
        assert(chip.status == (unchanged | previous[initial]));
    }
    assert(observed.reads == 1030);
    assert(observed.locks == 1026 && observed.notifications == 1026);
    puts("PASS: 1026 temperature IRQ cases and four read failures");
    return 0;
}
"""

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('--cc', default='clang')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    source = args.driver.read_text()
    defines = []
    for name in NAMES:
        line, = re.findall(r'^#define ' + name + r'\s+[^\n]+$', source, re.M)
        defines.append(line)
    handler, = re.findall(
        r'^static irqreturn_t smbb_bat_temp_handler\([^\n]+\)\n\{.*?^\}', source, re.M | re.S)
    with tempfile.TemporaryDirectory(prefix='fx0-temp-irq-') as directory:
        directory = Path(directory)
        probe = directory / 'temperature.c'
        binary = directory / 'temperature'
        probe.write_text('\n'.join(defines) + '\n' + STUBS + '\n' + handler + '\n' + TESTS)
        subprocess.run([args.cc, '-std=c99', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        probe, '-o', binary], check=True)
        subprocess.run([binary], check=True)

if __name__ == '__main__':
    main()
