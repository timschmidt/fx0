#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual SMBB charge-behaviour helpers/callbacks against faulted I/O."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("driver", type=Path)
args = parser.parse_args()
text = args.driver.read_text()
code = text[text.index("static int smbb_get_charge_behaviour("):text.index("static enum power_supply_property smbb_charger_properties")]
defines = "\n".join(re.findall(r"^#define (?:STATUS_\w+|CTRL_EN|SMBB_CHG_CTRL)\s+.*$", text, re.M))
stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <errno.h>
#include <stdio.h>
#define BIT(n) (1U<<(n))
#define mutex_lock(p) ((void)(p))
#define mutex_unlock(p) ((void)(p))
enum power_supply_property { POWER_SUPPLY_PROP_STATUS,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_CHARGE_TYPE,POWER_SUPPLY_PROP_PRESENT,POWER_SUPPLY_PROP_CURRENT_MAX,
 POWER_SUPPLY_PROP_VOLTAGE_MAX,POWER_SUPPLY_PROP_TECHNOLOGY,POWER_SUPPLY_PROP_VOLTAGE_MIN_DESIGN,
 POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR };
enum {POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO,POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE,
 POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE_AWAKE,POWER_SUPPLY_CHARGE_BEHAVIOUR_FORCE_DISCHARGE};
enum {POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_FULL,POWER_SUPPLY_STATUS_CHARGING,
 POWER_SUPPLY_STATUS_NOT_CHARGING,POWER_SUPPLY_HEALTH_GOOD,POWER_SUPPLY_HEALTH_OVERHEAT,
 POWER_SUPPLY_HEALTH_COLD,POWER_SUPPLY_CHARGE_TYPE_FAST,POWER_SUPPLY_CHARGE_TYPE_TRICKLE,
 POWER_SUPPLY_CHARGE_TYPE_NONE,POWER_SUPPLY_TECHNOLOGY_LION,ATTR_BAT_IMAX,ATTR_BAT_VMAX};
struct regmap {unsigned int control;int reads,writes,read_error,write_error;bool after;};
struct smbb_charger {struct regmap *regmap;unsigned int addr;unsigned long status;int statlock,attr[32];};
struct power_supply {struct smbb_charger *charger;int notifications;};
union power_supply_propval {int intval;};
static struct smbb_charger *power_supply_get_drvdata(struct power_supply *p) {return p->charger;}
static void power_supply_changed(struct power_supply *p) {p->notifications++;}
static int smbb_charger_attr_write(struct smbb_charger *c,int attr,int value)
{c->attr[attr]=value;return 0;}
static int regmap_read(struct regmap *m,unsigned int reg,unsigned int *value)
{assert(reg==0x1049);m->reads++;if(m->read_error)return m->read_error;*value=m->control;return 0;}
static int regmap_update_bits(struct regmap *m,unsigned int reg,unsigned int mask,unsigned int value)
{assert(reg==0x1049 && mask==0x80 && !(value&~mask));m->writes++;
 if(m->write_error&&!m->after)return m->write_error;
 m->control=(m->control&~mask)|value;return m->write_error;}
'''
main = r'''
int main(void)
{
 unsigned count=0;struct regmap io={0};struct smbb_charger c={.regmap=&io,.addr=0x1000};
 struct power_supply p={.charger=&c};union power_supply_propval v;
 for(unsigned control=0;control<256;control++)for(int mode=0;mode<2;mode++) {
  io=(struct regmap){.control=control};p.notifications=0;v.intval=mode;
  assert(smbb_battery_set_property(&p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==0);
  assert((io.control&0x7f)==(control&0x7f) && !!(io.control&0x80)==!mode);
  assert(p.notifications==1);count++;
  assert(smbb_battery_get_property(&p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==0 && v.intval==mode);count++;
 }
 const int invalid[]={-1,2,3,4,256};
 for(unsigned i=0;i<sizeof(invalid)/sizeof(invalid[0]);i++) {
  io=(struct regmap){.control=0x55};p.notifications=0;v.intval=invalid[i];
  assert(smbb_battery_set_property(&p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==-EINVAL);
  assert(io.control==0x55 && !io.writes && !io.reads && !p.notifications);count++;
 }
 for(int after=0;after<2;after++)for(int mode=0;mode<2;mode++) {
  io=(struct regmap){.control=0x55,.write_error=-EIO,.after=after};p.notifications=0;v.intval=mode;
  assert(smbb_battery_set_property(&p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==-EIO);
  assert((io.control&0x7f)==0x55 && !p.notifications);count++;
 }
 io=(struct regmap){.read_error=-EIO};v.intval=12345;
 assert(smbb_battery_get_property(&p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR,&v)==-EIO && v.intval==12345);count++;
 struct {unsigned long flags;int automatic,inhibited;} cases[]={
  {STATUS_USBIN_VALID|STATUS_BAT_OK|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_CHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING},
  {STATUS_DCIN_VALID|STATUS_BAT_OK|STATUS_CHG_TRKL,POWER_SUPPLY_STATUS_CHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING},
  {STATUS_USBIN_VALID|STATUS_BAT_OK,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING},
  {STATUS_BAT_OK|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_DISCHARGING},
  {STATUS_USBIN_VALID|STATUS_CHG_GONE|STATUS_BAT_OK|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_DISCHARGING},
  {STATUS_USBIN_VALID|STATUS_BAT_HOT|STATUS_CHG_FAST,POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_DISCHARGING},
  {STATUS_USBIN_VALID|STATUS_CHG_DONE|STATUS_BAT_OK,POWER_SUPPLY_STATUS_FULL,POWER_SUPPLY_STATUS_FULL},
 };
 for(unsigned i=0;i<sizeof(cases)/sizeof(cases[0]);i++)for(int inhibit=0;inhibit<2;inhibit++) {
  io=(struct regmap){.control=inhibit?0:0x80};c.status=cases[i].flags;
  assert(smbb_battery_get_property(&p,POWER_SUPPLY_PROP_STATUS,&v)==0);
  assert(v.intval==(inhibit?cases[i].inhibited:cases[i].automatic));count++;
 }
 c.status=STATUS_USBIN_VALID|STATUS_BAT_OK|STATUS_CHG_FAST;io.read_error=-EIO;
 assert(smbb_battery_get_property(&p,POWER_SUPPLY_PROP_STATUS,&v)==-EIO);count++;
 c.status=0;assert(smbb_battery_get_property(&p,POWER_SUPPLY_PROP_STATUS,&v)==0 && v.intval==POWER_SUPPLY_STATUS_DISCHARGING);count++;
 assert(smbb_battery_writable_property(&p,POWER_SUPPLY_PROP_CHARGE_BEHAVIOUR)==1);count++;
 printf("PASS: %u actual control-mask/property/status/fault cases under ASan/UBSan\n",count);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="fx0-smbb-control-") as temporary:
    root = Path(temporary)
    (root / "check.c").write_text(stubs + defines + "\n" + code + main)
    subprocess.run(["clang", "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter", "-fsanitize=address,undefined", "-fno-sanitize-recover=all", str(root / "check.c"), "-o", str(root / "check")], check=True)
    subprocess.run([str(root / "check")], check=True)
