#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise actual provider calibration, cache publication and trim rollback."""
import argparse
from pathlib import Path
import resource
import subprocess
import tempfile

STUBS = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <assert.h>
#include <stdio.h>
typedef uint8_t u8;
typedef uint16_t u16;
#define IADC_GAIN_17P857MV 3
#define IADC_INT_OFFSET_CSP2_CSN2 6
#define IADC_EXT_OFFSET_CSP_CSN 5
#define IADC_INT_RSENSE 0
#define IADC_EXT_RSENSE 1
#define IADC_OFFSET_TRIM_MSB 0xf2
#define IADC_SEC_ACCESS 0xd0
#define IADC_SEC_ACCESS_DATA 0xa5
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
struct regmap { u8 trim[2];int calls,fail_at,writes;bool after_write,unlocked,permanent,fail_after_trim,ignore_write;u16 gain,offset[2]; };
struct iadc_chip { struct regmap *regmap;u16 base,gain,offset[2];bool calibration_valid; };
static int iadc_do_conversion(struct iadc_chip *chip,int channel,u16 *value)
{
 struct regmap *map=chip->regmap;
 if (++map->calls==map->fail_at || map->permanent) return -EIO;
 assert(channel==3 || channel==5 || channel==6);
 *value=channel==3?map->gain:map->offset[channel==5];return 0;
}
static int regmap_bulk_read(struct regmap *map,unsigned int reg,void *value,unsigned int bytes)
{
 assert(reg==0x36f2 && bytes==2);
 if (++map->calls==map->fail_at || map->permanent) return -EIO;
 memcpy(value,map->trim,2);return 0;
}
static int iadc_write(struct iadc_chip *chip,unsigned int reg,u8 value)
{
 struct regmap *map=chip->regmap;
 bool fail=++map->calls==map->fail_at;map->writes++;
 if (map->permanent || (fail && !map->after_write)) return -EIO;
 if (reg==0xd0) { assert(value==0xa5);map->unlocked=true; }
 else {
  assert((reg==0xf2 || reg==0xf3) && map->unlocked);map->unlocked=false;
  if (!map->ignore_write) map->trim[reg-0xf2]=value;
  if (map->fail_after_trim) map->permanent=true;
 }
 return fail?-EIO:0;
}
'''
MAIN = r'''
static void setup(struct regmap *map,struct iadc_chip *chip)
{
 *map=(struct regmap){.trim={0x12,0x34},.gain=47857,.offset={30000,30010}};
 *chip=(struct iadc_chip){.regmap=map,.base=0x3600,.gain=40000,.offset={20000,20010},.calibration_valid=true};
}
static void cache_old(struct iadc_chip *chip)
{ assert(chip->gain==40000 && chip->offset[0]==20000 && chip->offset[1]==20010); }
int main(void)
{
 struct regmap map;struct iadc_chip chip;int count=0;
 setup(&map,&chip);assert(iadc_calibrate_external(&chip)==0);
 int operations=map.calls;
 assert(chip.gain==47857 && chip.offset[0]==30000 && chip.offset[1]==30010 && chip.calibration_valid);
 assert(map.trim[0]==(30010>>8) && map.trim[1]==(30010&255));count++;
 for (int op=1;op<=operations;op++) for (int after=0;after<2;after++) {
  setup(&map,&chip);map.fail_at=op;map.after_write=after;
  assert(iadc_calibrate_external(&chip)==-EIO);cache_old(&chip);
  assert(chip.calibration_valid && map.trim[0]==0x12 && map.trim[1]==0x34);count++;
 }
 const u8 before[]={0x12,0x34};
 setup(&map,&chip);assert(iadc_calibrate_external(&chip)==0);map.calls=0;
 assert(iadc_restore_offset_trim(&chip,before)==0);int restore_ops=map.calls;
 for (int op=1;op<=restore_ops;op++) for (int after=0;after<2;after++) {
  setup(&map,&chip);map.trim[0]=0x56;map.trim[1]=0x78;
  map.fail_at=op;map.after_write=after;
  assert(iadc_restore_offset_trim(&chip,before)==0 && map.trim[0]==0x12 && map.trim[1]==0x34);count++;
 }
 setup(&map,&chip);map.fail_after_trim=true;
 assert(iadc_calibrate_external(&chip)==-EIO && !chip.calibration_valid);cache_old(&chip);count++;
 setup(&map,&chip);map.ignore_write=true;
 assert(iadc_calibrate_external(&chip)==-EIO && chip.calibration_valid);cache_old(&chip);count++;
 for (int channel=0;channel<2;channel++) {
  setup(&map,&chip);map.offset[channel]=map.gain;
  assert(iadc_calibrate_external(&chip)==-EINVAL && map.writes==0);cache_old(&chip);count++;
 }
 setup(&map,&chip);assert(iadc_update_offset(&chip)==0 && map.writes==0 && chip.gain==47857);count++;
 printf("%d provider calibration/cache/protected-write/rollback cases pass\n",count);
 return 0;
}
'''

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('driver',type=Path)
args=parser.parse_args()
text=args.driver.read_text()
source=text[text.index('struct iadc_calibration {'):text.index('/* END TESTED TRIM TRANSACTION */')]
with tempfile.TemporaryDirectory(prefix='fx0-iadc-cal-') as temporary:
    root=Path(temporary);(root/'check.c').write_text(STUBS+source+MAIN)
    subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror','-fsanitize=undefined,address',
                    '-fno-sanitize-recover=all',str(root/'check.c'),'-o',str(root/'check')],check=True)
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    subprocess.run([str(root/'check')],check=True)
