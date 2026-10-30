#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile the real iadc_read_raw with an injected conversion result.

The fixture replaces hardware/IIO plumbing only. Expected values exercise signed
current, the IIO microamp scale, synthetic wrap examples and int-range rejection.
No device access; do not interpret these as calibrated hardware measurements.
"""
import argparse
from pathlib import Path
import subprocess
import tempfile

STUBS = r'''
#include <stdint.h>
#include <stdbool.h>
#include <limits.h>
#include <errno.h>
#include <stdio.h>
typedef int32_t s32;
typedef long long s64;
typedef uint16_t u16;
#define IADC_REF_GAIN_MICRO_VOLTS 17857
#define IIO_VOLTAGE 0
#define IIO_CURRENT 1
#define IIO_CHAN_INFO_RAW 0
#define IIO_CHAN_INFO_SCALE 1
#define IIO_VAL_INT 1
#define IIO_VAL_INT_PLUS_MICRO 2
struct iadc_chip { int lock; int dev; u16 offset[2]; u16 gain; uint32_t rsense[2]; bool calibration_valid; };
struct iio_chan_spec { int channel; int type; };
struct iio_dev { struct iadc_chip *chip; const struct iio_chan_spec *channels; int num_channels; };
static u16 injected_sample;
#define iio_priv(d) ((d)->chip)
#define mutex_lock(p) ((void)(p))
static void (*unlock_hook)(void);
#define mutex_unlock(p) do { (void)(p); if (unlock_hook) unlock_hook(); } while (0)
#define dev_dbg(...) ((void)0)
static int iadc_do_conversion(struct iadc_chip *chip, int channel, u16 *sample)
{ (void)chip; (void)channel; *sample = injected_sample; return 0; }
static inline __attribute__((unused)) s64 div64_s64(s64 n, s64 d) { return n / d; }
'''
VECTORS = [
    # sample, offset, gain, resistor uohm, expected microamps, expected status
    (30000, 30000, 47857, 10000, 0, 1),
    (31000, 30000, 47857, 10000, 100000, 1),
    (29000, 30000, 47857, 10000, -100000, 1),
    (30001, 30000, 47857, 10000, 100, 1),
    (29999, 30000, 47857, 10000, -100, 1),
    (31000, 30000, 47857, 10800, 92592, 1),
    (29000, 30000, 47857, 10800, -92592, 1),
    # Synthetic wrap examples yielding the observed baseline's 40/36 outputs.
    # All calibration inputs here are invented; actual unit captures stay private.
    (47500, 48000, 51200, 9000, -310000, 1),
    (47450, 48000, 51200, 10000, -306900, 1),
    # No 16-bit subtraction wrap at either end.
    (0, 65534, 65535, 1000000, -1170240638, 1),
    (65535, 0, 1, 1000000, 1170258495, 1),
    # Report overflow instead of truncating an impossible IIO int result.
    (65535, 0, 1, 1, 0, -34),
    (0, 65534, 65535, 1, 0, -34),
]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    parser.add_argument('--cc', default='clang')
    args = parser.parse_args()
    text = args.driver.read_text()
    start = text.index('static int iadc_read_raw(')
    end = text.index('\nstatic const struct iio_info', start)
    function = text[start:end]
    checks = []
    for index, (sample, offset, gain, resistor, expected, status) in enumerate(VECTORS):
        checks.append(f'''c.offset[channel.channel] = {offset}; c.gain = {gain}; c.rsense[channel.channel] = {resistor};
        injected_sample = {sample}; value = 123;
        result = iadc_read_raw(&d, &channel, &value, &value2, IIO_CHAN_INFO_RAW);
        if (result != {status} || (result == IIO_VAL_INT && value != {expected})) {{
            fprintf(stderr, "vector {index}: status=%d value=%d expected={status}/{expected}\\n", result, value);
            failures++;
        }}''')
    main_c = '''int main(void) {
    struct iadc_chip c = {.calibration_valid=true}; struct iio_dev d = {.chip = &c};
    struct iio_chan_spec channel = {.channel = 0, .type = IIO_CURRENT};
    int value, value2, result, failures = 0;
    for (channel.channel = 0; channel.channel < 2; channel.channel++) {
    ''' + '\n'.join(checks) + '''
    result = iadc_read_raw(&d, &channel, &value, &value2, IIO_CHAN_INFO_SCALE);
    if (result != IIO_VAL_INT_PLUS_MICRO || value != 0 || value2 != 1000) failures++;
    }
    return failures ? 1 : 0;
    }
    '''
    with tempfile.TemporaryDirectory(prefix='fx0-iadc-') as temporary:
        root = Path(temporary)
        (root/'check.c').write_text(STUBS + function + main_c)
        subprocess.run([args.cc, '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=undefined', '-fno-sanitize-recover=all',
                        str(root/'check.c'), '-o', str(root/'check')], check=True)
        subprocess.run([str(root/'check')], check=True)
    print(f'{len(VECTORS)} conversion vectors on both channels and the unchanged IIO scale pass')

if __name__ == '__main__':
    main()
