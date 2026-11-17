#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run actual SMBB control/limit/property functions against faulted bus I/O."""
import argparse
import hashlib
from pathlib import Path
import re
import resource
import subprocess
import sys
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("driver", type=Path)
parser.add_argument("--cc", default="cc", help="host C compiler executable")
parser.add_argument("--negative-controls", action="store_true", help="require five deliberately broken variants to fail")
args = parser.parse_args()
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
source = args.driver.read_text()
defines = "\n".join(re.findall(r"^#define (?:SMBB_\w+|STATUS_\w+|CTRL_EN)\s+.*$", source, re.M))
attrs = source[source.index("enum smbb_attr {"):source.index("struct smbb_charger {")]
limits = source[source.index("static int smbb_vbat_weak_fn("):source.index("static int smbb_charger_attr_read(")]
controls = source[source.index("/* Caller holds charge_lock."):source.index("static enum power_supply_property smbb_charger_properties")]

stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdio.h>
#include <string.h>
#define BIT(n) (1U << (n))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_dbg(...) ((void)0)
struct mutex { pthread_mutex_t gate; pthread_t owner; bool held; };
static void mutex_init(struct mutex *m)
{ assert(!pthread_mutex_init(&m->gate, NULL)); m->held = false; }
static void mutex_lock(struct mutex *m)
{ assert(!pthread_mutex_lock(&m->gate)); assert(!m->held); m->held=true; m->owner=pthread_self(); }
static void locked(struct mutex *m)
{ assert(m->held && pthread_equal(m->owner, pthread_self())); }
static void mutex_unlock(struct mutex *m)
{ locked(m); m->held=false; assert(!pthread_mutex_unlock(&m->gate)); }
enum power_supply_property { POWER_SUPPLY_PROP_STATUS, POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_CHARGE_TYPE, POWER_SUPPLY_PROP_PRESENT, POWER_SUPPLY_PROP_CURRENT_MAX,
 POWER_SUPPLY_PROP_VOLTAGE_MAX, POWER_SUPPLY_PROP_TECHNOLOGY, POWER_SUPPLY_PROP_VOLTAGE_MIN_DESIGN,
 POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR };
enum { POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO, POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE,
 POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE_AWAKE, POWER_SUPPLY_CHARGE_BEHAVIOUR_FORCE_DISCHARGE };
enum { POWER_SUPPLY_STATUS_DISCHARGING, POWER_SUPPLY_STATUS_FULL, POWER_SUPPLY_STATUS_CHARGING,
 POWER_SUPPLY_STATUS_NOT_CHARGING, POWER_SUPPLY_HEALTH_GOOD, POWER_SUPPLY_HEALTH_OVERHEAT,
 POWER_SUPPLY_HEALTH_COLD, POWER_SUPPLY_CHARGE_TYPE_FAST, POWER_SUPPLY_CHARGE_TYPE_TRICKLE,
 POWER_SUPPLY_CHARGE_TYPE_NONE, POWER_SUPPLY_TECHNOLOGY_LION };
struct regmap {
 unsigned int registers[0x800], operations, writes, control_writes, enables;
 unsigned int fail_at, drop_at, corrupt_at;
 int error;
 bool fail_after, persistent;
 struct mutex *lock;
};
struct smbb_charger {
 struct regmap *regmap;
 unsigned int addr, attr[32], charge_inhibit;
 unsigned long status;
 struct mutex statlock, charge_lock;
 void *dev;
};
struct power_supply { struct smbb_charger *charger; unsigned int notifications; };
union power_supply_propval { int intval; };
static struct smbb_charger *power_supply_get_drvdata(struct power_supply *p) { return p->charger; }
static void power_supply_changed(struct power_supply *p)
{ assert(!p->charger->charge_lock.held); p->notifications++; }
static bool bus_fails(struct regmap *m)
{ return m->fail_at && (m->persistent ? m->operations >= m->fail_at : m->operations == m->fail_at); }
static int regmap_read(struct regmap *m, unsigned int reg, unsigned int *value)
{
 locked(m->lock); assert(reg >= 0x1000 && reg < 0x1800); m->operations++;
 if (bus_fails(m)) return m->error;
 *value=m->registers[reg-0x1000];
 if (m->operations == m->corrupt_at) *value ^= 0x80;
 return 0;
}
static int regmap_write(struct regmap *m, unsigned int reg, unsigned int value)
{
 bool failed;
 locked(m->lock); assert(reg >= 0x1000 && reg < 0x1800); assert(value < 256);
 m->operations++; m->writes++; failed=bus_fails(m);
 if ((!failed || m->fail_after) && m->operations != m->drop_at) {
  m->registers[reg-0x1000]=value;
  if (reg == 0x1049) { m->control_writes++; if (value & 0x80) m->enables++; }
 }
 return failed ? m->error : 0;
}
static int regmap_write_bits(struct regmap *m, unsigned int reg, unsigned int mask, unsigned int value)
{
 unsigned int old; int ret;
 assert(reg == 0x1049 && mask == 0x80 && !(value & ~mask));
 ret=regmap_read(m, reg, &old); if (ret) return ret;
 return regmap_write(m, reg, (old & ~mask) | value);
}
'''

tests = r'''
static unsigned int cases;
static void reset(struct smbb_charger *c, struct regmap *m, unsigned int control, unsigned int votes)
{
 memset(m, 0, sizeof(*m)); m->lock=&c->charge_lock; m->error=-EIO;
 m->registers[0x49]=control; m->registers[0x45]=40; m->registers[0x41]=120;
 c->regmap=m; c->addr=0x1000; c->charge_inhibit=votes;
 memset(c->attr, 0, sizeof(c->attr)); c->attr[ATTR_BAT_IMAX]=300000; c->attr[ATTR_BAT_VMAX]=4200000;
}
static void user_votes(struct smbb_charger *c, struct regmap *m, struct power_supply *p)
{
 union power_supply_propval v;
 for (unsigned int control=0; control<256; control++)
 for (unsigned int votes=0; votes<8; votes++)
 for (int mode=0; mode<2; mode++) {
  unsigned int remaining=(votes & ~SMBB_INHIBIT_USER) | (mode ? SMBB_INHIBIT_USER : 0);
  reset(c,m,control,votes); p->notifications=0; v.intval=mode;
  assert(!smbb_battery_set_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v));
  assert(c->charge_inhibit == remaining && p->notifications == 1);
  assert(m->operations == 3 && m->control_writes == 1);
  assert((m->registers[0x49] & 0x7f) == (control & 0x7f));
  assert(!!(m->registers[0x49] & 0x80) == !remaining);
  assert(!smbb_battery_get_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v));
  assert(v.intval == (remaining ? POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE : POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO));
  cases++;
 }
 const int bad[]={INT_MIN,-1,2,3,4,INT_MAX};
 for (unsigned int i=0;i<ARRAY_SIZE(bad);i++) {
  reset(c,m,0xd5,SMBB_INHIBIT_INIT); p->notifications=0; v.intval=bad[i];
  assert(smbb_battery_set_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==-EINVAL);
  assert(!m->operations && !p->notifications && c->charge_inhibit==SMBB_INHIBIT_INIT); cases++;
 }
}
static void fault_votes(struct smbb_charger *c, struct regmap *m, struct power_supply *p)
{
 union power_supply_propval v;
 const int errors[]={-EIO,-ETIMEDOUT,-EINVAL,-ENODEV};
 for (unsigned int e=0;e<ARRAY_SIZE(errors);e++)
 for (unsigned int at=1;at<=3;at++)
 for (int after=0;after<2;after++)
 for (int mode=0;mode<2;mode++) {
  reset(c,m,0xd5,0); p->notifications=0; m->fail_at=at; m->fail_after=after; m->error=errors[e]; v.intval=mode;
  assert(smbb_battery_set_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==errors[e]);
  assert(c->charge_inhibit & SMBB_INHIBIT_FAULT); assert(!p->notifications);
  assert(m->registers[0x49]==0x55); /* Recovery write succeeds for a one-shot failure. */
  m->fail_at=0; v.intval=POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO;
  assert(!smbb_battery_set_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v));
  assert(c->charge_inhibit==SMBB_INHIBIT_FAULT && m->registers[0x49]==0x55); cases++;
 }
 for (int mode=0;mode<2;mode++)
 for (int corruption=0;corruption<2;corruption++) {
  reset(c,m,mode ? 0xd5 : 0x55,0); v.intval=mode;
  if (corruption) m->corrupt_at=3; else m->drop_at=2;
  assert(smbb_battery_set_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==-EIO);
  assert(c->charge_inhibit & SMBB_INHIBIT_FAULT); assert(m->registers[0x49]==0x55); cases++;
 }
 for (int after=0;after<2;after++) {
  reset(c,m,0xd5,0); m->persistent=true; m->fail_at=2; m->fail_after=after;
  assert(smbb_set_charge_behaviour(c,POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE)==-EIO);
  assert(c->charge_inhibit==(SMBB_INHIBIT_USER|SMBB_INHIBIT_FAULT));
  /* Permanent bus loss may leave charging on. A software vote is no proof of inhibition. */
  assert(m->registers[0x49]==(after ? 0x55 : 0xd5)); cases++;
 }
 reset(c,m,0xd5,0); m->fail_at=1; v.intval=12345;
 assert(smbb_battery_get_property(p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==-EIO);
 assert(v.intval==12345 && c->charge_inhibit==SMBB_INHIBIT_FAULT && m->registers[0x49]==0x55); cases++;
 reset(c,m,0xd5,SMBB_INHIBIT_USER); v.intval=12345;
 assert(smbb_get_charge_behaviour(c,&v.intval)==-EIO && v.intval==12345);
 assert(c->charge_inhibit==(SMBB_INHIBIT_USER|SMBB_INHIBIT_FAULT) && m->registers[0x49]==0x55); cases++;
}
static void battery_limits(struct smbb_charger *c, struct regmap *m, struct power_supply *p)
{
 union power_supply_propval v;
 const struct {enum power_supply_property property; unsigned int attr, reg; int requested, expected, encoded;} good[]={
  {POWER_SUPPLY_PROP_CURRENT_MAX,ATTR_BAT_IMAX,0x44,450000,450000,9},
  {POWER_SUPPLY_PROP_CURRENT_MAX,ATTR_BAT_IMAX,0x44,499999,450000,9},
  {POWER_SUPPLY_PROP_CURRENT_MAX,ATTR_BAT_IMAX,0x44,2100000,2000000,40},
  {POWER_SUPPLY_PROP_VOLTAGE_MAX,ATTR_BAT_VMAX,0x40,4350000,4350000,111},
  {POWER_SUPPLY_PROP_VOLTAGE_MAX,ATTR_BAT_VMAX,0x40,4359999,4350000,111},
  {POWER_SUPPLY_PROP_VOLTAGE_MAX,ATTR_BAT_VMAX,0x40,4500000,4440000,120},
 };
 for (unsigned int i=0;i<ARRAY_SIZE(good);i++) {
  reset(c,m,0xd5,0); v.intval=good[i].requested;
  assert(!smbb_battery_set_property(p,good[i].property,&v));
  assert(c->attr[good[i].attr]==(unsigned int)good[i].expected);
  assert(m->registers[good[i].reg]==(unsigned int)good[i].encoded && m->registers[0x49]==0xd5);
  assert(!c->charge_inhibit && m->operations==3); cases++;
 }
 const int errors[]={-EIO,-ETIMEDOUT,-EINVAL,-ENODEV};
 for (unsigned int which=0;which<2;which++)
 for (unsigned int e=0;e<ARRAY_SIZE(errors);e++)
 for (unsigned int at=1;at<=3;at++)
 for (int after=0;after<2;after++) {
  unsigned int i=which ? 3 : 0;
  reset(c,m,0xd5,0); unsigned int old=c->attr[good[i].attr];
  m->error=errors[e]; m->fail_at=at; m->fail_after=after; v.intval=good[i].requested;
  assert(smbb_battery_set_property(p,good[i].property,&v)==errors[e]);
  assert(c->attr[good[i].attr]==old); assert(c->charge_inhibit==SMBB_INHIBIT_FAULT);
  assert(m->registers[0x49]==0x55);
  v.intval=12345;
  assert(smbb_battery_get_property(p,good[i].property,&v)==-EIO && v.intval==12345);
  cases++;
 }
 for (unsigned int which=0;which<2;which++)
 for (int corrupt=0;corrupt<2;corrupt++) {
  unsigned int i=which ? 3 : 0;
  reset(c,m,0xd5,0); unsigned int old=c->attr[good[i].attr];
  if (corrupt) m->corrupt_at=3; else m->drop_at=2;
  v.intval=good[i].requested;
  assert(smbb_battery_set_property(p,good[i].property,&v)==-EIO);
  assert(c->attr[good[i].attr]==old && c->charge_inhibit==SMBB_INHIBIT_FAULT);
  assert(m->registers[0x49]==0x55); cases++;
 }
 const int invalid[]={INT_MIN,-1,0,1,INT_MAX};
 for (unsigned int which=0;which<2;which++)
 for (unsigned int i=0;i<ARRAY_SIZE(invalid);i++) {
  reset(c,m,0xd5,0); v.intval=invalid[i];
  assert(smbb_battery_set_property(p,which ? POWER_SUPPLY_PROP_VOLTAGE_MAX : POWER_SUPPLY_PROP_CURRENT_MAX,&v)==-EINVAL);
  assert(!m->operations && !c->charge_inhibit && m->registers[0x49]==0xd5); cases++;
 }
}
static void status_paths(struct smbb_charger *c, struct regmap *m, struct power_supply *p)
{
 union power_supply_propval v;
 const struct {unsigned long flags; int automatic,inhibited;} paths[]={
  {STATUS_USBIN_VALID|STATUS_BAT_OK|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_CHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING},
  {STATUS_DCIN_VALID|STATUS_BAT_OK|STATUS_CHG_TRKL,POWER_SUPPLY_STATUS_CHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING},
  {STATUS_USBIN_VALID|STATUS_BAT_OK,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING},
  {STATUS_BAT_OK|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_DISCHARGING},
  {STATUS_USBIN_VALID|STATUS_CHG_GONE|STATUS_BAT_OK|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_DISCHARGING},
  {STATUS_USBIN_VALID|STATUS_CHG_DONE|STATUS_BAT_OK,POWER_SUPPLY_STATUS_FULL,POWER_SUPPLY_STATUS_FULL},
  {STATUS_USBIN_VALID|STATUS_BAT_HOT|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_DISCHARGING},
 };
 for (unsigned int i=0;i<ARRAY_SIZE(paths);i++) for (int inhibit=0;inhibit<2;inhibit++) {
  reset(c,m,inhibit ? 0x55 : 0xd5,inhibit ? SMBB_INHIBIT_USER : 0); c->status=paths[i].flags;
  assert(!smbb_battery_get_property(p,POWER_SUPPLY_PROP_STATUS,&v));
  assert(v.intval==(inhibit ? paths[i].inhibited : paths[i].automatic)); cases++;
 }
}
struct worker {struct smbb_charger *charger; unsigned int id;};
static void *concurrent(void *data)
{
 struct worker *w=data;
 for (unsigned int i=0;i<500;i++) {
  if (w->id < 2) assert(!smbb_set_charge_behaviour(w->charger,(i+w->id)%2));
  else assert(!smbb_set_battery_limit(w->charger,ATTR_BAT_IMAX,450000+(i%5)*50000));
 }
 return NULL;
}
static void concurrency(struct smbb_charger *c, struct regmap *m)
{
 pthread_t threads[4]; struct worker workers[4];
 reset(c,m,0x55,SMBB_INHIBIT_INIT);
 for (unsigned int i=0;i<4;i++) { workers[i]=(struct worker){c,i}; assert(!pthread_create(&threads[i],NULL,concurrent,&workers[i])); }
 for (unsigned int i=0;i<4;i++) assert(!pthread_join(threads[i],NULL));
 assert(!m->enables && m->registers[0x49]==0x55 && (c->charge_inhibit & SMBB_INHIBIT_INIT));
 assert(c->attr[ATTR_BAT_IMAX]==650000); cases+=2000;
 /* Releasing setup cannot erase an independently requested user inhibition. */
 assert(!smbb_set_charge_behaviour(c,POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE));
 assert(!smbb_charge_vote(c,SMBB_INHIBIT_INIT,false));
 assert(c->charge_inhibit==SMBB_INHIBIT_USER && m->registers[0x49]==0x55); cases++;
 assert(!smbb_set_charge_behaviour(c,POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO));
 assert(m->registers[0x49]==0xd5 && !c->charge_inhibit); cases++;
}
int main(void)
{
 struct regmap io; struct smbb_charger c={0}; struct power_supply p={.charger=&c};
 mutex_init(&c.charge_lock); mutex_init(&c.statlock);
 user_votes(&c,&io,&p); fault_votes(&c,&io,&p); battery_limits(&c,&io,&p);
 status_paths(&c,&io,&p); concurrency(&c,&io);
 assert(!pthread_mutex_destroy(&c.charge_lock.gate)); assert(!pthread_mutex_destroy(&c.statlock.gate));
 printf("%u actual-function cases PASS (including 2000 concurrent requests)\n",cases);
 return 0;
}
'''

with tempfile.TemporaryDirectory(prefix="fx0-smbb-charge-guard-") as directory:
    directory = Path(directory)
    cfile, binary = directory / "check.c", directory / "check"
    cfile.write_text(stubs + "\n" + defines + "\n" + attrs + limits + controls + tests)
    subprocess.run([args.cc, "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                    "-Wno-unused-function", "-Wno-unused-parameter", "-Wno-sign-compare", "-g", "-O1",
                    "-fsanitize=address,undefined", "-fno-omit-frame-pointer", "-no-pie",
                    "-pthread", str(cfile), "-o", str(binary)], check=True)
    subprocess.run([str(binary)], check=True)
print("Driver SHA256:", hashlib.sha256(args.driver.read_bytes()).hexdigest())

if args.negative_controls:
    mutations = {
        "missing-enable-readback-check": ("return (control & CTRL_EN) == value ? 0 : -EIO;", "return 0;"),
        "user-auto-erases-other-votes": ("inhibit = false;", "inhibit = false;\n\t\tchg->charge_inhibit = 0;"),
        "missing-fault-latch": ("chg->charge_inhibit |= SMBB_INHIBIT_FAULT;", "/* deliberately omit the fault latch */"),
        "premature-limit-cache": ("rc = regmap_read(chg->regmap, chg->addr + prop->reg, &out);",
                                  "chg->attr[which] = prop->hw_fn(wval);\n\trc = regmap_read(chg->regmap, chg->addr + prop->reg, &out);"),
        "untrusted-cached-limit-returned": ("if (chg->charge_inhibit & SMBB_INHIBIT_FAULT)\n\t\t\trc = -EIO;\n\t\telse\n\t\t\tval->intval = chg->attr[ATTR_BAT_IMAX];",
                                            "val->intval = chg->attr[ATTR_BAT_IMAX];"),
    }
    with tempfile.TemporaryDirectory(prefix="fx0-smbb-guard-negative-") as directory:
        for name, (original, replacement) in mutations.items():
            assert source.count(original) == 1
            candidate = Path(directory) / (name + ".c")
            candidate.write_text(source.replace(original, replacement))
            result = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--cc", args.cc, str(candidate)],
                                    capture_output=True, text=True)
            assert result.returncode != 0 and "Assertion" in result.stderr, (name, result.stdout, result.stderr)
            print("Negative control rejected:", name)
