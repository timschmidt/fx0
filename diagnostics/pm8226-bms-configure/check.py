#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check actual BMS configuration helpers, protection and rollback faults."""
import argparse
from pathlib import Path
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
struct bms_config { u8 channel, sense, trim[2]; };
struct regmap { u8 regs[0x5000]; int calls, fail_at; bool after_write, unlocked[2], reject_mirror, ignore_mirror, permanent_error, fail_after_assert, clear_reads_zero, latched_disable; };
static void udelay(unsigned int us) { assert(us==100); }
static int regmap_read(struct regmap *map, unsigned int reg, unsigned int *v)
{ if (++map->calls==map->fail_at || map->permanent_error) return -EIO; *v=map->regs[reg]; return 0; }
static int regmap_bulk_read(struct regmap *map, unsigned int reg, void *v, unsigned int n)
{ if (++map->calls==map->fail_at || map->permanent_error) return -EIO; memcpy(v,map->regs+reg,n); return 0; }
static int update_bits(struct regmap *map, unsigned int reg, unsigned int mask, unsigned int v, bool force)
{
 assert((reg==0x3848 && mask==7) || (reg==0x3849 && mask==3) || (reg==0x4043 && mask==0xc0));
 bool fail=++map->calls==map->fail_at;
 if (map->permanent_error || (fail && !map->after_write)) return -EIO;
 if (force || (map->regs[reg]&mask)!=(v&mask)) {
  if (reg==0x4043) map->latched_disable=!!(v&0xc0);
  map->regs[reg]=(map->regs[reg]&~mask)|(v&mask);
  if (reg==0x4043 && map->clear_reads_zero) map->regs[reg]&=~0xc0;
 }
 if (reg==0x4043 && (v&0xc0) && map->fail_after_assert) map->permanent_error=true;
 return fail?-EIO:0;
}
static int regmap_update_bits(struct regmap *map, unsigned int reg, unsigned int mask, unsigned int v)
{ return update_bits(map,reg,mask,v,false); }
static int __attribute__((unused)) regmap_write_bits(struct regmap *map, unsigned int reg, unsigned int mask, unsigned int v)
{ return update_bits(map,reg,mask,v,true); }
static int regmap_write(struct regmap *map, unsigned int reg, unsigned int v)
{
 unsigned int bank=reg&0xff00, offset=reg&255, b=bank==0x3800;
 assert(bank==0x3600 || bank==0x3800);
 if (b && map->reject_mirror) return -EIO;
 if (b && map->ignore_mirror) return 0;
 bool fail=++map->calls==map->fail_at;
 if (map->permanent_error || (fail && !map->after_write)) return -EIO;
 if (offset==0xd0) { assert(v==0xa5); map->unlocked[b]=true; }
 else {
  assert((offset==0xf2 || offset==0xf3) && map->unlocked[b]);
  map->unlocked[b]=false;map->regs[0x3600+offset]=v;map->regs[0x3800+offset]=v;
 }
 return fail?-EIO:0;
}
'''
MAIN = r'''
static void setup(struct regmap *m)
{
 memset(m,0,sizeof(*m));m->regs[0x3848]=0xa0;m->regs[0x3849]=0x40;
 m->regs[0x36f2]=m->regs[0x38f2]=0x12;m->regs[0x36f3]=m->regs[0x38f3]=0x34;
}
static void assert_restored(struct regmap *m, const struct bms_config *before)
{
 struct bms_config after;
 assert(bms_read_config(m,&after)==0 && !memcmp(&after,before,sizeof(after)));
}
int main(void)
{
 struct regmap map;
 struct bms_config before,after;
 int count=0;
 for (int mode=0;mode<3;mode++) {
  bool sense=mode!=2,calibrate=mode!=1;
  for (int bank=0x3600;bank<=0x3800;bank+=0x200) {
  setup(&map);assert(bms_read_config(&map,&before)==0);map.calls=0;
  assert(bms_apply_config(&map,bank,0x5678,sense,calibrate)==0);
  int apply_calls=map.calls;
  assert(bms_read_config(&map,&after)==0 && after.channel==(sense?0xa1:0xa0) && after.sense==(sense?0x42:0x40));
  assert(after.trim[0]==(calibrate?0x56:0x12) && after.trim[1]==(calibrate?0x78:0x34));
  assert(bms_restore_config(&map,&before)==0);assert_restored(&map,&before);count++;
  for (int op=1;op<=apply_calls;op++) for (int after_write=0;after_write<2;after_write++) {
   setup(&map);map.fail_at=op;map.after_write=after_write;
   assert(bms_apply_config(&map,bank,0x5678,sense,calibrate)<0);
   assert(bms_restore_config(&map,&before)==0);assert_restored(&map,&before);count++;
  }
  setup(&map);assert(bms_apply_config(&map,bank,0x5678,sense,calibrate)==0);map.calls=0;
  assert(bms_restore_config(&map,&before)==0);int restore_calls=map.calls;
  for (int op=1;op<=restore_calls;op++) for (int after_write=0;after_write<2;after_write++) {
   setup(&map);assert(bms_apply_config(&map,bank,0x5678,sense,calibrate)==0);
   map.calls=0;map.fail_at=op;map.after_write=after_write;
   assert(bms_restore_config(&map,&before)==0);assert_restored(&map,&before);count++;
  }
  }
 }
 setup(&map);map.regs[0x38f2]^=1;
 assert(bms_read_config(&map,&after)==-EIO);count++;
 for (int failure=0;failure<2;failure++) {
  setup(&map);map.reject_mirror=failure==0;map.ignore_mirror=failure==1;
  assert(bms_apply_config(&map,0x3800,0x5678,true,true)==-EIO);
  assert(bms_restore_config(&map,&before)==0);assert_restored(&map,&before);count++;
 }
 setup(&map);assert(bms_apply_config(&map,0x3600,0x5678,true,true)==0);
 map.permanent_error=true;map.calls=0;
 assert(bms_restore_config(&map,&before)==-EIO && map.calls==2);count++;
 setup(&map);map.regs[0x4043]=0x2a;
 assert(bms_start_epoch(&map)==0 && map.regs[0x4043]==0x2a);int epoch_calls=map.calls;count++;
 for (int op=1;op<=epoch_calls;op++) for (int after_write=0;after_write<2;after_write++) {
  setup(&map);map.regs[0x4043]=0x2a;map.fail_at=op;map.after_write=after_write;
  int ret=bms_start_epoch(&map);
  assert(map.regs[0x4043]==0x2a);
  if (op<=2) assert(ret==-EIO); else assert(ret==0);
  count++;
 }
 setup(&map);map.regs[0x4043]=0xc0;
 assert(bms_start_epoch(&map)==-EBUSY && map.calls==1 && map.regs[0x4043]==0xc0);count++;
 setup(&map);map.fail_after_assert=true;
 assert(bms_start_epoch(&map)==-EIO && map.regs[0x4043]==0xc0);count++;
 setup(&map);map.clear_reads_zero=true;
 assert(bms_start_epoch(&map)==0 && !map.latched_disable);count++;
 printf("%d protected-write/alias/rollback/epoch/fault cases pass\n",count);
 return 0;
}
'''

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source',type=Path,default=Path(__file__).with_name('fx0-pm8226-bms-configure.c'))
source=parser.parse_args().source.read_text()
helpers=source.split('/* BEGIN TESTED CONFIGURATION HELPERS */',1)[1].split('/* END TESTED CONFIGURATION HELPERS */',1)[0]
with tempfile.TemporaryDirectory(prefix='fx0-bms-config-') as temporary:
    root=Path(temporary)
    (root/'check.c').write_text(STUBS+helpers+MAIN)
    subprocess.run(['clang','-std=c11','-Wall','-Wextra','-Werror',
                    '-fsanitize=undefined,address','-fno-sanitize-recover=all',
                    str(root/'check.c'),'-o',str(root/'check')],check=True)
    subprocess.run([str(root/'check')],check=True)
