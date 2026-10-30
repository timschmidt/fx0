#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check actual IADC raw-reference reads and hardware-number translation."""
import argparse
import importlib.util
from pathlib import Path
import subprocess
import tempfile

EXTRA = r'''
struct fwnode_reference_args { int nargs; uint64_t args[2]; };
'''
MAIN = r'''
static struct iadc_chip *cache_target;
static void change_cache(void) { cache_target->gain=40000;cache_target->offset[1]=0; }
int main(void)
{
    struct iadc_chip c = {.calibration_valid=true};
    const struct iio_chan_spec channels[] = {
        {.channel=0,.type=IIO_CURRENT}, {.channel=1,.type=IIO_CURRENT},
        {.channel=3,.type=IIO_VOLTAGE}, {.channel=5,.type=IIO_VOLTAGE},
        {.channel=6,.type=IIO_VOLTAGE}
    };
    struct iio_dev d = {.chip=&c,.channels=channels,.num_channels=5};
    int value, value2, cases=0;
    const u16 samples[] = {0,32768,65535};
    for (int i=2;i<5;i++) {
        for (int j=0;j<3;j++) {
            injected_sample=samples[j]; value=-123;
            int ret=iadc_read_raw(&d,&channels[i],&value,&value2,IIO_CHAN_INFO_RAW);
            if (ret!=IIO_VAL_INT || value!=samples[j]) return 1;
            cases++;
        }
        if (iadc_read_raw(&d,&channels[i],&value,&value2,IIO_CHAN_INFO_SCALE)!=-EINVAL) return 2;
        cases++;
    }
    const uint64_t valid[]={0,1,3,5,6};
    struct fwnode_reference_args spec={.nargs=1};
    for (int i=0;i<5;i++) {
        spec.args[0]=valid[i];
        if (iadc_fwnode_xlate(&d,&spec)!=i) return 3;
        cases++;
    }
    const uint64_t invalid[]={2,4,7,UINT64_MAX};
    for (int i=0;i<4;i++) {
        spec.args[0]=invalid[i];
        if (iadc_fwnode_xlate(&d,&spec)!=-EINVAL) return 4;
        cases++;
    }
    spec.args[0]=0;
    for (int count=0;count<=2;count+=2) {
        spec.nargs=count;
        if (iadc_fwnode_xlate(&d,&spec)!=-EINVAL) return 5;
        cases++;
    }
    c.gain=47857;c.offset[1]=30000;c.rsense[1]=10000;
    injected_sample=31000;cache_target=&c;unlock_hook=change_cache;
    if (iadc_read_raw(&d,&channels[1],&value,&value2,IIO_CHAN_INFO_RAW)!=IIO_VAL_INT || value!=100000) return 6;
    unlock_hook=NULL;cases++;
    c.calibration_valid=false;
    for (int i=0;i<2;i++) {
        if (iadc_read_raw(&d,&channels[i],&value,&value2,IIO_CHAN_INFO_RAW)!=-EIO) return 7;
        cases++;
    }
    injected_sample=32000;
    if (iadc_read_raw(&d,&channels[2],&value,&value2,IIO_CHAN_INFO_RAW)!=IIO_VAL_INT || value!=32000) return 8;
    cases++;
    printf("%d raw-reference/scale/translation/cache/invalid-state cases pass\n",cases);
    return 0;
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('driver', type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location('conversion', Path(__file__).parent.parent/'iadc-conversion/check.py')
    base = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    text = args.driver.read_text()
    start = text.index('static int iadc_fwnode_xlate(')
    end = text.index('\nstatic const struct iio_info', start)
    with tempfile.TemporaryDirectory(prefix='fx0-iadc-refs-') as temporary:
        root = Path(temporary)
        (root/'check.c').write_text(base.STUBS + EXTRA + text[start:end] + MAIN)
        subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror',
                        '-fsanitize=undefined,address','-fno-sanitize-recover=all',
                        str(root/'check.c'),'-o',str(root/'check')], check=True)
        subprocess.run([str(root/'check')], check=True)

if __name__ == '__main__':
    main()
