#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fault-inject the actual native BMS snapshot, restart and sense helpers."""
import argparse
from pathlib import Path
import resource
import subprocess
import tempfile

STUBS = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
#define BIT(n) (1U << (n))
#define BMS_HOLD BIT(0)
#define BMS_CLEAR_MASK (BIT(7) | BIT(6))
struct bms_outputs { u8 vsense[2], counter[5]; };
struct regmap {
 u8 regs[0x5000]; int calls, fail_at, bulk_calls;
 unsigned int ignored_write_reg, blocked_write_reg, clear_assertions;
 bool after_write, permanent, corrupt_output, ignore_hold, clear_reads_zero, stopped;
};
struct pm8226_bms {
 struct regmap *regmap; unsigned int base, iadc_base;
 struct { bool initialized; } counter;
 unsigned int saved_channel, saved_sense, warnings;
 unsigned int *dev;
 bool sense_owned, stopping, hold_during_calibration, lock;
 bool configured; int calibration_error, calibrations;
};
static int bms_calibrate(struct pm8226_bms *bms)
{
 bms->calibrations++;
 if (bms->hold_during_calibration) bms->regmap->regs[0x4042] |= BMS_HOLD;
 return bms->calibration_error;
}
#ifdef SENSE_LIFECYCLE
static void mutex_lock(bool *lock) { assert(!*lock); *lock=true; }
static void mutex_unlock(bool *lock) { assert(*lock); *lock=false; }
#define ERR_PTR(error) (error)
#define dev_warn(dev, message, error) do { assert((error) < 0); (*(dev))++; } while (0)
#endif
static void udelay(unsigned int us) { assert(us == 100); }
static int regmap_read(struct regmap *m, unsigned int reg, unsigned int *out)
{
 assert(reg==0x4042 || reg==0x4043 || reg==0x3848 || reg==0x3849);
 if (++m->calls==m->fail_at || m->permanent) return -EIO;
 *out=m->regs[reg]; return 0;
}
static int regmap_bulk_read(struct regmap *m, unsigned int reg, void *out, unsigned int len)
{
 assert((reg==0x4098 && len==2) || (reg==0x40a8 && len==5));
 if (++m->calls==m->fail_at || m->permanent) return -EIO;
 memcpy(out,m->regs+reg,len);
 if (m->corrupt_output && ++m->bulk_calls==4) ((u8 *)out)[0]^=1;
 return 0;
}
static int update_bits(struct regmap *m, unsigned int reg, unsigned int mask,
                       unsigned int value, bool force)
{
 assert((reg==0x4042 && mask==1) || (reg==0x4043 && mask==0xc0) ||
        (reg==0x3848 && mask==7) || (reg==0x3849 && mask==3));
 bool fail=++m->calls==m->fail_at;
 if (m->permanent || reg==m->blocked_write_reg || (fail && !m->after_write)) return -EIO;
 if (force || (m->regs[reg]&mask)!=(value&mask)) {
  if (reg==0x4043) {
   m->stopped=!!(value&mask);
   if (m->stopped) m->clear_assertions++;
  }
  if (reg!=m->ignored_write_reg && !(reg==0x4042 && m->ignore_hold))
   m->regs[reg]=(m->regs[reg]&~mask)|(value&mask);
  if (reg==0x4043 && m->clear_reads_zero) m->regs[reg]&=~mask;
 }
 return fail?-EIO:0;
}
static int regmap_update_bits(struct regmap *m, unsigned int r, unsigned int mask, unsigned int v)
{ return update_bits(m,r,mask,v,false); }
static int regmap_write_bits(struct regmap *m, unsigned int r, unsigned int mask, unsigned int v)
{ return update_bits(m,r,mask,v,true); }
'''

MAIN = r'''
static void setup(struct regmap *m, struct pm8226_bms *bms)
{
 *m=(struct regmap){};
 m->regs[0x4042]=0x80; m->regs[0x4043]=0x20;
 m->regs[0x3848]=0xa0; m->regs[0x3849]=0x40;
 for (int i=0;i<2;i++) m->regs[0x4098+i]=i+1;
 for (int i=0;i<5;i++) m->regs[0x40a8+i]=i+3;
 *bms=(struct pm8226_bms){.regmap=m,.base=0x4000,.iadc_base=0x3800};
 bms->dev=&bms->warnings;
}
int main(void)
{
 struct regmap m; struct pm8226_bms bms; struct bms_outputs out;
 int count=0, operations;
 setup(&m,&bms);assert(bms_snapshot(&bms,&out)==0);
 assert(m.regs[0x4042]==0x80 && out.vsense[0]==1 && out.counter[4]==7);
 operations=m.calls;count++;
 for (int i=1;i<=operations;i++) for (int after=0;after<2;after++) {
  setup(&m,&bms);m.fail_at=i;m.after_write=after;
  int ret=bms_snapshot(&bms,&out);
  assert(ret==0 || ret==-EIO); assert(m.regs[0x4042]==0x80);count++;
 }
 setup(&m,&bms);m.regs[0x4042]|=1;
 assert(bms_snapshot(&bms,&out)==-EBUSY && m.calls==1 && m.regs[0x4042]==0x81);count++;
 setup(&m,&bms);m.corrupt_output=true;
 assert(bms_snapshot(&bms,&out)==-EIO && m.regs[0x4042]==0x80);count++;
 setup(&m,&bms);m.ignore_hold=true;
 assert(bms_snapshot(&bms,&out)==-EIO && m.regs[0x4042]==0x80);count++;
 setup(&m,&bms);m.permanent=true;
 assert(bms_snapshot(&bms,&out)==-EIO && m.calls==1);count++;
 for (int zero=0;zero<2;zero++) {
  setup(&m,&bms);m.clear_reads_zero=zero;
  assert(bms_restart_counter(&bms)==0 && !m.stopped && m.regs[0x4043]==0x20);
  operations=m.calls;count++;
  for (int i=1;i<=operations;i++) for (int after=0;after<2;after++) {
   setup(&m,&bms);m.clear_reads_zero=zero;m.fail_at=i;m.after_write=after;
   int ret=bms_restart_counter(&bms);
   assert(ret==0 || ret==-EIO);assert(!m.stopped && m.regs[0x4043]==0x20);count++;
  }
 }
 setup(&m,&bms);m.regs[0x4043]|=0xc0;
 assert(bms_restart_counter(&bms)==-EBUSY && !m.clear_assertions);count++;
#ifdef SENSE_LIFECYCLE
 setup(&m,&bms);m.regs[0x4042]|=BMS_HOLD;
 assert(bms_restart_counter(&bms)==-EBUSY && m.calls==1 && !m.clear_assertions);count++;
#endif
 setup(&m,&bms);bms.counter.initialized=true;
 assert(bms_configure(&bms)==0 && bms.configured && !bms.counter.initialized);
 assert(m.regs[0x3848]==0xa1 && m.regs[0x3849]==0x42 && !m.stopped);
 operations=m.calls;count++;
 for (int i=1;i<=operations;i++) for (int after=0;after<2;after++) {
  setup(&m,&bms);m.fail_at=i;m.after_write=after;
  int ret=bms_configure(&bms);
  assert(ret==0 || ret==-EIO);
  if (ret) assert(!bms.configured && !bms.sense_owned &&
                  m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);
  assert(!m.stopped);count++;
 }
 setup(&m,&bms);bms.calibration_error=-EIO;
 assert(bms_configure(&bms)==-EIO && !bms.configured && !m.clear_assertions);
 assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
 setup(&m,&bms);m.regs[0x3848]=0xa1;m.regs[0x3849]=0x42;
 assert(bms_restore_sense(&bms,0xa0,0x40)==0);operations=m.calls;count++;
 for (int i=1;i<=operations;i++) for (int after=0;after<2;after++) {
  setup(&m,&bms);m.regs[0x3848]=0xa1;m.regs[0x3849]=0x42;
  m.fail_at=i;m.after_write=after;
  assert(bms_restore_sense(&bms,0xa0,0x40)==0);
  assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
 }
 setup(&m,&bms);m.permanent=true;
 assert(bms_restore_sense(&bms,0xa0,0x40)==-EIO && m.calls==2);count++;
#ifdef SENSE_LIFECYCLE
 for (unsigned int reg=0x4042;reg<=0x4043;reg++) {
  setup(&m,&bms);m.regs[reg]|=reg==0x4042?BMS_HOLD:BMS_CLEAR_MASK;
  assert(bms_configure(&bms)==-EBUSY && !bms.calibrations && !m.clear_assertions);
  assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
 }
 setup(&m,&bms);bms.hold_during_calibration=true;
 assert(bms_configure(&bms)==-EBUSY && bms.calibrations==1 && !m.clear_assertions);
 assert(m.regs[0x4042]==0x81 && m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
 for (unsigned int reg=0x3848;reg<=0x3849;reg++) {
  setup(&m,&bms);m.ignored_write_reg=reg;
  assert(bms_configure(&bms)==-EIO && !m.clear_assertions && !bms.sense_owned);
  assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
 }
 setup(&m,&bms);assert(bms_configure(&bms)==0);
 assert(bms.sense_owned);
 bms_cleanup(&bms);
 assert(bms.stopping && !bms.sense_owned && !bms.warnings);
 assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);
 operations=m.calls;bms_cleanup(&bms);assert(m.calls==operations);count++;
 setup(&m,&bms);bms_cleanup(&bms);
 assert(bms.stopping && !m.calls && !bms.warnings);count++;
 setup(&m,&bms);assert(bms_configure(&bms)==0);
 m.blocked_write_reg=0x3849;bms_cleanup(&bms);
 assert(bms.stopping && bms.sense_owned && bms.warnings==1);
 m.blocked_write_reg=0;bms_cleanup(&bms);
 assert(!bms.sense_owned && bms.warnings==1);
 assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
 setup(&m,&bms);assert(bms_configure(&bms)==0);
 bms.configured=false;m.blocked_write_reg=0x3849;
 assert(bms_configure(&bms)==-EIO && bms.sense_owned && bms.calibrations==1);
 m.blocked_write_reg=0;assert(bms_configure(&bms)==0);
 bms_cleanup(&bms);assert(m.regs[0x3848]==0xa0 && m.regs[0x3849]==0x40);count++;
#endif
 printf("%d native BMS snapshot/restart/sense lifecycle fault cases pass\n",count);
 return 0;
}
'''

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('driver', type=Path)
parser.add_argument('--require-sense-lifecycle', action='store_true')
args = parser.parse_args()
text = args.driver.read_text()
source = text[text.index('static int bms_read_outputs('):text.index('static int bms_refresh_calibration(')]
source += text[text.index('static int bms_restore_sense('):text.index('static void bms_sample(')]
definitions = ''
if 'static void bms_cleanup(' in text:
    definitions = '#define SENSE_LIFECYCLE\n'
    source += text[text.index('static void bms_cleanup('):text.index('static int bms_link_channel(')]
elif args.require_sense_lifecycle:
    parser.error('driver lacks the companion sense cleanup callback')
with tempfile.TemporaryDirectory(prefix='fx0-bms-io-') as temporary:
    root = Path(temporary)
    (root / 'check.c').write_text(definitions + STUBS + source + MAIN)
    subprocess.run(['clang', '-std=c11', '-Wall', '-Wextra', '-Werror',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(root / 'check.c'), '-o', str(root / 'check')], check=True)
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    subprocess.run([str(root / 'check')], check=True)
