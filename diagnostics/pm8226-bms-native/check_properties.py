#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify actual property routing keeps live and background current distinct."""
import argparse
from pathlib import Path
import resource
import subprocess
import tempfile

STUBS = r'''
#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
#define NSEC_PER_SEC 1000000000ULL
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
enum power_supply_property { POWER_SUPPLY_PROP_PRESENT, POWER_SUPPLY_PROP_STATUS,
 POWER_SUPPLY_PROP_HEALTH, POWER_SUPPLY_PROP_VOLTAGE_NOW, POWER_SUPPLY_PROP_CURRENT_NOW,
 POWER_SUPPLY_PROP_CURRENT_AVG, POWER_SUPPLY_PROP_CHARGE_COUNTER, POWER_SUPPLY_PROP_TEMP };
enum { POWER_SUPPLY_STATUS_UNKNOWN, POWER_SUPPLY_STATUS_CHARGING, POWER_SUPPLY_STATUS_DISCHARGING };
union power_supply_propval { int intval; };
struct pm8226_bms {
 int lock, present_error, voltage_error, current_error, average_error, charge_error, temperature_error;
 int voltage_uv, current_ua, average_ua, temperature_decic;
 bool present; uint64_t last_sample_ns;
 struct { int64_t charge_uah; } counter;
};
struct power_supply { struct pm8226_bms *bms; };
static uint64_t now=100;
static int samples;
static struct pm8226_bms *power_supply_get_drvdata(struct power_supply *p) { return p->bms; }
static uint64_t ktime_get_boottime_ns(void) { return now; }
static void bms_sample(struct pm8226_bms *b) { (void)b;samples++; }
static int power_supply_get_property_from_supplier(struct power_supply *p, enum power_supply_property prop,
 union power_supply_propval *value) { (void)p;(void)prop;(void)value;return -ENODEV; }
'''
MAIN = r'''
int main(void)
{
 int count=0;union power_supply_propval v;
 struct pm8226_bms b={.present=true,.last_sample_ns=100};
 struct power_supply p={.bms=&b};
 const int currents[]={-250000,0,250000};
 for (unsigned int i=0;i<3;i++) for(int live_error=0;live_error<2;live_error++)
  for(int avg_error=0;avg_error<2;avg_error++) {
   b.current_ua=currents[i];b.average_ua=-currents[i]+155000;
   b.current_error=live_error?-EIO:0;b.average_error=avg_error?-ENODATA:0;
   int ret=bms_get_property(&p,POWER_SUPPLY_PROP_CURRENT_NOW,&v);
   assert(ret==b.current_error && v.intval==b.current_ua);count++;
   ret=bms_get_property(&p,POWER_SUPPLY_PROP_CURRENT_AVG,&v);
   assert(ret==b.average_error && v.intval==b.average_ua);count++;
  }
 b.present_error=-EIO;
 assert(bms_get_property(&p,POWER_SUPPLY_PROP_CURRENT_NOW,&v)==-EIO);count++;
 assert(bms_get_property(&p,POWER_SUPPLY_PROP_CURRENT_AVG,&v)==-EIO);count++;
 b.present_error=0;b.current_error=0;
 for(unsigned int i=0;i<3;i++) {
  b.current_ua=currents[i];b.average_ua=-currents[i];
  int expected=i==0?POWER_SUPPLY_STATUS_DISCHARGING:i==1?POWER_SUPPLY_STATUS_UNKNOWN:POWER_SUPPLY_STATUS_CHARGING;
  assert(bms_get_property(&p,POWER_SUPPLY_PROP_STATUS,&v)==0 && v.intval==expected);count++;
 }
 b.charge_error=0;b.counter.charge_uah=(int64_t)INT_MAX+1;
 assert(bms_get_property(&p,POWER_SUPPLY_PROP_CHARGE_COUNTER,&v)==-ERANGE);count++;
 b.counter.charge_uah=-123;
 assert(bms_get_property(&p,POWER_SUPPLY_PROP_CHARGE_COUNTER,&v)==0 && v.intval==-123);count++;
 b.charge_error=-ENODATA;
 assert(bms_get_property(&p,POWER_SUPPLY_PROP_CHARGE_COUNTER,&v)==-ENODATA);count++;
 assert(samples==0);
 now=NSEC_PER_SEC+101;
 assert(bms_get_property(&p,POWER_SUPPLY_PROP_CURRENT_NOW,&v)==0 && samples==1);count++;
 printf("%d actual live/average current, property error, status and cache cases pass\n",count);
 return 0;
}
'''

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('driver', type=Path)
args = parser.parse_args()
text = args.driver.read_text()
source = text[text.index('static int bms_get_property('):text.index('static const enum power_supply_property bms_properties')]
with tempfile.TemporaryDirectory(prefix='fx0-bms-properties-') as temporary:
    root = Path(temporary)
    (root / 'check.c').write_text(STUBS + source + MAIN)
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(root / 'check.c'), '-o', str(root / 'check')], check=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    subprocess.run([str(root / 'check')], check=True)
