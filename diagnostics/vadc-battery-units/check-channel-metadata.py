#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile real VADC channel tables and check the two new voltage interfaces."""
import argparse
import json
from pathlib import Path
import subprocess
import tempfile


PREFIX = r'''
#include <stdio.h>
#include <dt-bindings/iio/qcom,spmi-vadc.h>
#define BIT(n) (1UL << (n))
#define __stringify_1(x) #x
#define __stringify(x) __stringify_1(x)
#define IIO_CHAN_INFO_RAW 0
#define IIO_CHAN_INFO_PROCESSED 1
enum iio_chan_type { IIO_VOLTAGE, IIO_TEMP };
'''
MAIN = r'''
int main(void)
{
    for (unsigned int i = 0; i < sizeof(vadc_chans) / sizeof(vadc_chans[0]); i++) {
        const struct vadc_channels *c = &vadc_chans[i];
        if (c->datasheet_name)
            printf("%u %s %u %d %ld %d\n", i, c->datasheet_name,
                   c->prescale_index, c->type, c->info_mask, c->scale_fn_type);
    }
    return 0;
}
'''


def table(driver, common_header):
    text = driver.read_text()
    start = text.index('struct vadc_channels {')
    end = text.index('\nstatic int vadc_get_fw_channel_data(', start)
    header = common_header.read_text()
    first = header.index('enum vadc_scale_fn_type {')
    last = header.index('\n};', first) + 3
    return PREFIX + header[first:last] + '\n' + text[start:end] + MAIN


def compile_table(driver, kernel, temporary, label):
    source = temporary / (label + '.c')
    executable = temporary / label
    source.write_text(table(driver, kernel / 'include/linux/iio/adc/qcom-vadc-common.h'))
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    '-I', str(kernel / 'include'), str(source), '-o', str(executable)],
                   check=True)
    output = subprocess.check_output([str(executable)], text=True)
    result = {}
    for line in output.splitlines():
        number, name, prescale, kind, mask, scale = line.split()
        number = int(number)
        if number in result:
            raise ValueError('duplicate registered channel')
        result[number] = (name, int(prescale), int(kind), int(mask), int(scale))
    return result


def verify(before, after):
    # The contract adds processed millivolt interfaces to the two existing raw
    # voltage channels, preserving names, prescale, type and every other entry.
    if before.keys() != after.keys():
        raise ValueError('channel inventory changed')
    expected_before = {6: ('VBAT_SNS', 1, 0, 1, 0),
                       48: ('LR_MUX1_BAT_THERM', 0, 0, 1, 0)}
    for number, row in before.items():
        if number in expected_before:
            if row != expected_before[number]:
                raise ValueError('unexpected original battery channel')
            expected = (row[0], row[1], row[2], 3, row[4])
        else:
            expected = row
        if after[number] != expected:
            raise ValueError('channel metadata contract failed at channel ' + str(number))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--before-driver', required=True, type=Path)
    parser.add_argument('--driver', type=Path)
    args = parser.parse_args()
    driver = args.driver or args.kernel / 'drivers/iio/adc/qcom-spmi-vadc.c'
    with tempfile.TemporaryDirectory(prefix='fx0-vadc-metadata-') as directory:
        temporary = Path(directory)
        before = compile_table(args.before_driver, args.kernel, temporary, 'before')
        after = compile_table(driver, args.kernel, temporary, 'after')
        verify(before, after)
    print(json.dumps({'registered_channels': len(after),
                      'new_processed_voltage_channels': [6, 48],
                      'other_channel_records_preserved': len(after) - 2,
                      'battery_raw_name_type_and_prescale_preserved': True,
                      'physical_conversions_or_probe_executed': False}))


if __name__ == '__main__':
    main()
