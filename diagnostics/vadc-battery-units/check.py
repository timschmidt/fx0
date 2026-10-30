#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise actual VADC read and IIO consumer scaling functions."""
import argparse
from pathlib import Path
import subprocess
import tempfile

STUBS = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <errno.h>
typedef uint16_t u16;
typedef int64_t s64;
#define MICRO 1000000
#define NANO 1000000000
#define IIO_VAL_INT 1
#define IIO_VAL_INT_PLUS_MICRO 2
#define IIO_VAL_INT_PLUS_NANO 3
#define IIO_VAL_FRACTIONAL 4
#define IIO_VAL_FRACTIONAL_LOG2 5
#define IIO_CHAN_INFO_RAW 0
#define IIO_CHAN_INFO_PROCESSED 1
#define VADC_CALIB_ABSOLUTE 0
#define VADC_CALIB_RATIOMETRIC 1
#define VADC_VBAT_SNS 6
#define VADC_LR_MUX1_BAT_THERM 48
struct vadc_channel_prop { int scale_fn_type, calibration, prescale; };
struct vadc_priv { struct vadc_channel_prop *chan_props; int graph[2]; };
struct iio_dev { struct vadc_priv *chip; };
struct iio_chan_spec { int channel, address; };
#define iio_priv(d) ((d)->chip)
static const int vadc_prescale_ratios[] = {1};
static int conversion_error, scaling_error, scaled_input;
static int vadc_do_conversion(struct vadc_priv *v, struct vadc_channel_prop *p, u16 *raw)
{ (void)v; (void)p; *raw=45678; return conversion_error; }
static int qcom_vadc_scale(int kind, const int *graph, const int *prescale,
                           bool absolute, u16 raw, int *value)
{ (void)kind; (void)graph; (void)prescale; (void)absolute; (void)raw;
  *value=scaled_input; return scaling_error; }
static s64 div_s64(s64 value, int denominator) { return value/denominator; }
'''
MAIN = r'''
int main(void)
{
    struct vadc_channel_prop prop={0};
    struct vadc_priv chip={.chan_props=&prop};
    struct iio_dev dev={.chip=&chip};
    const int channels[]={6,48,7,8,9,49};
    const int inputs[]={0,625001,1800000,3941583};
    int count=0;
    for (unsigned int c=0;c<sizeof(channels)/sizeof(channels[0]);c++) {
        struct iio_chan_spec chan={.channel=channels[c]};
        for (int cal=0;cal<2;cal++) {
            prop.calibration=cal;
            for (unsigned int j=0;j<sizeof(inputs)/sizeof(inputs[0]);j++) {
                int value=-1,value2=-1,processed=-1;
                scaled_input=inputs[j];
                int ret=vadc_read_raw(&dev,&chan,&value,&value2,IIO_CHAN_INFO_PROCESSED);
                bool fractional=cal==VADC_CALIB_ABSOLUTE && (chan.channel==6 || chan.channel==48);
                if (value!=scaled_input || ret!=(fractional?IIO_VAL_FRACTIONAL:IIO_VAL_INT)) return 1;
                if (fractional) {
                    if (value2!=1000) return 2;
                    if (iio_multiply_value(&processed,1000,ret,value,value2)!=IIO_VAL_INT || processed!=scaled_input) return 3;
                    if (iio_multiply_value(&processed,1,ret,value,value2)!=IIO_VAL_INT || processed!=scaled_input/1000) return 4;
                }
                count++;
            }
            int value=-1,value2=-1;
            if (vadc_read_raw(&dev,&chan,&value,&value2,IIO_CHAN_INFO_RAW)!=IIO_VAL_INT || value!=45678) return 5;
            count++;
            conversion_error=-ETIMEDOUT;
            if (vadc_read_raw(&dev,&chan,&value,&value2,IIO_CHAN_INFO_PROCESSED)!=-ETIMEDOUT) return 6;
            conversion_error=0;scaling_error=-EINVAL;
            if (vadc_read_raw(&dev,&chan,&value,&value2,IIO_CHAN_INFO_PROCESSED)!=-EINVAL) return 7;
            scaling_error=0;count+=2;
        }
    }
    printf("%d battery-unit/consumer-precision/legacy/raw/error cases pass\n",count);
    return 0;
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--driver', type=Path)
    args = parser.parse_args()
    text = (args.driver or args.kernel/'drivers/iio/adc/qcom-spmi-vadc.c').read_text()
    driver = text[text.index('static int vadc_read_raw('):text.index('\nstatic int vadc_fwnode_xlate(')]
    core = (args.kernel/'drivers/iio/inkern.c').read_text()
    multiply = core[core.index('int iio_multiply_value('):core.index('\nEXPORT_SYMBOL_NS_GPL(iio_multiply_value,')]
    with tempfile.TemporaryDirectory(prefix='fx0-vadc-units-') as temporary:
        root = Path(temporary)
        (root/'check.c').write_text(STUBS+multiply+driver+MAIN)
        subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined,address','-fno-sanitize-recover=all',
                        str(root/'check.c'),'-o',str(root/'check')],check=True)
        subprocess.run([str(root/'check')],check=True)

if __name__ == '__main__':
    main()
