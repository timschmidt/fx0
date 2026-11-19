#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the SMBB battery-voltage setup and read callbacks from a kernel tree."""

import argparse
from pathlib import Path
import subprocess
import tempfile


STUBS = r'''
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#define IS_REACHABLE(option) REACHABLE
#define READ_ONCE(value) (value)
#define STATUS_BAT_PRESENT 0x10
#define IS_ERR(ptr) ((uintptr_t)(ptr) >= (uintptr_t)-4095)
#define PTR_ERR(ptr) ((intptr_t)(ptr))
struct device { void *of_node; };
struct iio_channel { int reserved; };
enum iio_chan_type { IIO_VOLTAGE, IIO_TEMP };
enum power_supply_property { PRESENT, HEALTH, POWER_SUPPLY_PROP_VOLTAGE_NOW };
struct power_supply_desc {
    const enum power_supply_property *properties;
    unsigned int num_properties;
};
static const enum power_supply_property smbb_battery_properties[] = { PRESENT, HEALTH };
struct smbb_charger {
    struct device *dev;
    struct iio_channel *vbat;
    struct power_supply_desc bat_desc;
    enum power_supply_property bat_properties[3];
    unsigned long status;
};

static struct iio_channel adc;
static struct smbb_charger *charger;
static bool described, remove_during_read;
static int probe_error, type_error, read_error, processed_microvolts;
static unsigned int gets, reads;
static enum iio_chan_type channel_type;

static int dev_err_probe(struct device *dev, int ret, const char *message)
{
    assert(dev == charger->dev && message);
    return ret;
}

static bool of_property_present(void *node, const char *name)
{
    assert(node == charger->dev->of_node && strcmp(name, "io-channels") == 0);
    return described;
}

static struct iio_channel *devm_iio_channel_get(struct device *dev, const char *name)
{
    assert(dev == charger->dev && strcmp(name, "battery-voltage") == 0);
    gets++;
    return probe_error ? (void *)(intptr_t)probe_error : &adc;
}

static int iio_get_channel_type(struct iio_channel *channel, enum iio_chan_type *type)
{
    assert(channel == &adc);
    *type = channel_type;
    return type_error;
}

static int iio_read_channel_processed_scale(struct iio_channel *channel, int *result,
                                            unsigned int scale)
{
    assert(channel == &adc && scale == 1000);
    reads++;
    if (remove_during_read)
        charger->status &= ~STATUS_BAT_PRESENT;
    *result = processed_microvolts;
    return read_error;
}
'''

MAIN = r'''
static void check_read(unsigned long status, int expected, bool read_expected)
{
    int voltage = -123;
    reads = 0;
    assert(smbb_battery_get_voltage(charger, status, &voltage) == expected);
    assert(reads == read_expected);
    assert(voltage == (expected ? -123 : processed_microvolts));
}

int main(void)
{
    const struct power_supply_desc base = { smbb_battery_properties, 2 };
    struct device dev = { &dev };
    struct smbb_charger state = { .dev = &dev, .bat_desc = base };
    charger = &state;

    assert(!smbb_battery_init_voltage(charger) && !gets);
    assert(state.bat_desc.properties == base.properties && state.bat_desc.num_properties == 2);
    check_read(STATUS_BAT_PRESENT, -ENODATA, false);
    described = true;
    if (!REACHABLE) {
        assert(!smbb_battery_init_voltage(charger) && !gets);
        assert(state.bat_desc.properties == base.properties && state.bat_desc.num_properties == 2);
        check_read(STATUS_BAT_PRESENT, -ENODATA, false);
        return 0;
    }

    probe_error = -517; /* EPROBE_DEFER */
    assert(smbb_battery_init_voltage(charger) == probe_error);
    probe_error = 0;
    type_error = -ENODEV;
    assert(smbb_battery_init_voltage(charger) == -ENODEV);
    type_error = 0;
    channel_type = IIO_TEMP;
    assert(smbb_battery_init_voltage(charger) == -EINVAL);
    assert(state.bat_desc.properties == base.properties && state.bat_desc.num_properties == 2);
    assert(!state.vbat);
    channel_type = IIO_VOLTAGE;
    assert(!smbb_battery_init_voltage(charger) && gets == 4);
    assert(state.vbat == &adc && state.bat_desc.num_properties == 3);
    assert(state.bat_desc.properties == state.bat_properties);
    assert(state.bat_properties[0] == PRESENT && state.bat_properties[1] == HEALTH);
    assert(state.bat_properties[2] == POWER_SUPPLY_PROP_VOLTAGE_NOW);

    check_read(0, -ENODATA, false);
    state.status = STATUS_BAT_PRESENT;
    processed_microvolts = 4228884;
    check_read(state.status, 0, true);
    processed_microvolts = 4229178;
    check_read(state.status, 0, true); /* Fresh read, with sub-mV precision. */
    read_error = -ETIMEDOUT;
    check_read(state.status, read_error, true);
    read_error = -ENODEV;
    check_read(state.status, read_error, true);
    read_error = 0;
    processed_microvolts = 0;
    check_read(state.status, -ENODATA, true);
    processed_microvolts = -1;
    check_read(state.status, -ENODATA, true);
    processed_microvolts = 4200000;
    remove_during_read = true;
    check_read(state.status, -ENODATA, true);
    assert(!state.status);
    return 0;
}
'''


def callback(source, name, next_name):
    start = source.index(f'static int {name}(')
    return source[start:source.index(f'\nstatic int {next_name}(', start)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--cc', default='clang')
    args = parser.parse_args()
    source = (args.kernel / 'drivers/power/supply/qcom_smbb.c').read_text()
    voltage = callback(source, 'smbb_battery_get_voltage', 'smbb_battery_get_property')
    setup = callback(source, 'smbb_battery_init_voltage', 'smbb_charger_probe')
    with tempfile.TemporaryDirectory(prefix='fx0-smbb-voltage-') as directory:
        root = Path(directory)
        test = root / 'check.c'
        test.write_text(STUBS + voltage + setup + MAIN)
        for reachable in (0, 1):
            binary = root / f'check-{reachable}'
            subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            f'-DREACHABLE={reachable}', str(test), '-o', str(binary)], check=True)
            subprocess.run([str(binary)], check=True)
    print('SMBB battery-voltage setup and read controls passed with and without IIO')


if __name__ == '__main__':
    main()
