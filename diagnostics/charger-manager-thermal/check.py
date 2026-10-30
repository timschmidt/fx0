#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real Charger Manager temperature, duration and regulator decisions."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("driver", type=Path)
parser.add_argument("--expect-vulnerable", action="store_true")
args = parser.parse_args()
source = args.driver.read_text()
header = (args.driver.resolve().parents[3] / "include/linux/power/charger-manager.h").read_text()
enum = re.search(r"enum cm_batt_temp \{.*?\n\};", header, re.S).group()


def function(name):
    match = re.search(r"^static (?:int|bool) " + name + r"\(.*?^\}", source, re.M | re.S)
    assert match, name
    return match.group() + "\n"


stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <errno.h>
#include <stdio.h>
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define fallthrough __attribute__((fallthrough))
typedef uint64_t u64;
enum {POWER_SUPPLY_STATUS_DISCHARGING, POWER_SUPPLY_STATUS_NOT_CHARGING,
 POWER_SUPPLY_STATUS_CHARGING, POWER_SUPPLY_STATUS_FULL};
enum power_supply_property {POWER_SUPPLY_PROP_STATUS,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_PRESENT,POWER_SUPPLY_PROP_VOLTAGE_NOW,POWER_SUPPLY_PROP_CURRENT_NOW,
 POWER_SUPPLY_PROP_TEMP,POWER_SUPPLY_PROP_CAPACITY,POWER_SUPPLY_PROP_ONLINE,
 POWER_SUPPLY_PROP_CHARGE_FULL,POWER_SUPPLY_PROP_CHARGE_NOW};
enum {POWER_SUPPLY_HEALTH_UNKNOWN,POWER_SUPPLY_HEALTH_GOOD,
 POWER_SUPPLY_HEALTH_OVERHEAT,POWER_SUPPLY_HEALTH_COLD};
union power_supply_propval {int intval;};
struct regulator {bool enabled;unsigned enables,disables;};
struct charger_regulator {bool externally_control;struct regulator *consumer;const char *regulator_name;};
struct charger_desc {int num_charger_regulators;struct charger_regulator *charger_regulators;
 int temp_min,temp_max,temp_diff;bool measure_battery_temp;
 unsigned charging_max_duration_ms,discharging_max_duration_ms;
 const char *psy_fuel_gauge;int fullbatt_uV;};
struct charger_manager;
struct power_supply {unsigned changes;struct charger_manager *cm;};
struct charger_manager {struct charger_desc *desc;bool charger_enabled;
 int emergency_stop,battery_status;u64 charging_start_time,charging_end_time;
 struct power_supply *charger_psy;void *dev;};
static int sensor_error,sensor_temp,sensor_reads;
static bool external_power,full;
static u64 now_ms=1000;
static u64 ktime_get(void) {return now_ms;}
static u64 ktime_to_ms(u64 time) {return time;}
static int regulator_enable(struct regulator *r) {r->enabled=true;r->enables++;return 0;}
static int regulator_disable(struct regulator *r) {r->enabled=false;r->disables++;return 0;}
static int regulator_force_disable(struct regulator *r) {r->enabled=false;r->disables++;return 0;}
static bool regulator_is_enabled(struct regulator *r) {return r->enabled;}
static void power_supply_changed(struct power_supply *p) {p->changes++;}
static bool is_ext_pwr_online(struct charger_manager *cm) {(void)cm;return external_power;}
static bool is_full_charged(struct charger_manager *cm) {(void)cm;return full;}
static bool is_batt_present(struct charger_manager *cm) {(void)cm;return true;}
static bool is_charging(struct charger_manager *cm) {return cm->charger_enabled;}
static int get_batt_uV(struct charger_manager *cm,int *voltage) {(void)cm;(void)voltage;return -ENODATA;}
static struct charger_manager *power_supply_get_drvdata(struct power_supply *p) {return p->cm;}
static struct power_supply *power_supply_get_by_name(const char *name) {(void)name;return NULL;}
static void power_supply_put(struct power_supply *p) {(void)p;}
static int power_supply_get_property(struct power_supply *p,enum power_supply_property property,
 union power_supply_propval *value) {(void)p;(void)property;(void)value;return -ENODATA;}
static int cm_get_battery_temperature(struct charger_manager *cm,int *temp) {
 if(!cm->desc->measure_battery_temp)return -ENODEV;
 sensor_reads++;if(sensor_error)return sensor_error;*temp=sensor_temp;return 0;
}
'''
main = r'''
int main(void)
{
 struct regulator regulator={0};struct charger_regulator actuator={.consumer=&regulator};
 struct charger_desc desc={.num_charger_regulators=1,.charger_regulators=&actuator,
  .temp_min=0,.temp_max=450,.temp_diff=30,.measure_battery_temp=true};
 struct power_supply psy={0};struct charger_manager cm={.desc=&desc,.charger_psy=&psy};
 unsigned count=0;
 psy.cm=&cm;
 const int temperatures[]={-1,0,1,29,30,31,250,419,420,421,449,450,451};
 const int errors[]={0,-EIO,-ENODEV,-ETIMEDOUT,-ENODATA};
 const int previous[]={CM_BATT_OK,CM_BATT_OVERHEAT,CM_BATT_COLD,-EIO};
 if(EXPECT_VULNERABLE) {
  external_power=true;full=false;sensor_temp=250;sensor_error=-EIO;
  cm.battery_status=POWER_SUPPLY_STATUS_CHARGING;cm.charger_enabled=true;regulator.enabled=true;
  _cm_monitor(&cm);
  assert(cm.battery_status==POWER_SUPPLY_STATUS_CHARGING && regulator.enabled);count++;
  sensor_error=0;sensor_temp=451;cm.emergency_stop=0;
  desc.charging_max_duration_ms=500;desc.discharging_max_duration_ms=500;
  cm.charging_start_time=100;cm.charger_enabled=true;cm.battery_status=POWER_SUPPLY_STATUS_CHARGING;
  _cm_monitor(&cm);
  assert(cm.battery_status==POWER_SUPPLY_STATUS_CHARGING && regulator.enabled);count++;
  printf("REPRODUCED: %u original fault/expired-duration cases leave charger enabled\n",count);
  return 0;
 }
 for(unsigned t=0;t<sizeof(temperatures)/sizeof(temperatures[0]);t++)
 for(unsigned e=0;e<sizeof(errors)/sizeof(errors[0]);e++)
 for(unsigned p=0;p<sizeof(previous)/sizeof(previous[0]);p++)
 for(int expired=0;expired<2;expired++)for(int enabled=0;enabled<2;enabled++)
 for(int status=POWER_SUPPLY_STATUS_DISCHARGING;status<=POWER_SUPPLY_STATUS_FULL;status++) {
  sensor_temp=temperatures[t];sensor_error=errors[e];sensor_reads=0;
  external_power=true;full=false;regulator=(struct regulator){.enabled=enabled};psy.changes=0;
  cm=(struct charger_manager){.desc=&desc,.charger_psy=&psy,.charger_enabled=enabled,
   .battery_status=status,.emergency_stop=previous[p],.charging_start_time=100,.charging_end_time=100};
  desc.charging_max_duration_ms=desc.discharging_max_duration_ms=expired?500:10000;
  bool unsafe=sensor_error || sensor_temp < (previous[p]?30:0) || sensor_temp > (previous[p]?420:450);
  bool stopped=_cm_monitor(&cm);assert(sensor_reads==1);
  if(unsafe) {
   assert(stopped && cm.battery_status==POWER_SUPPLY_STATUS_NOT_CHARGING);
   assert(!cm.charger_enabled && !regulator.enabled && cm.emergency_stop);
   assert(try_charger_enable(&cm,true)==-EAGAIN && !regulator.enabled);
  } else {
   assert(!cm.emergency_stop);
   assert(cm.battery_status==POWER_SUPPLY_STATUS_CHARGING || cm.battery_status==POWER_SUPPLY_STATUS_FULL);
   assert(regulator.enabled==(cm.battery_status==POWER_SUPPLY_STATUS_CHARGING));
  }
  count++;
  union power_supply_propval value;
  assert(charger_get_property(&psy,POWER_SUPPLY_PROP_HEALTH,&value)==0);
  int expected_health=sensor_error?POWER_SUPPLY_HEALTH_UNKNOWN:
   unsafe?(sensor_temp>250?POWER_SUPPLY_HEALTH_OVERHEAT:POWER_SUPPLY_HEALTH_COLD):POWER_SUPPLY_HEALTH_GOOD;
  assert(value.intval==expected_health);count++;
 }
 /* Faults persist until a fresh sample clears the hysteresis window. */
 desc.charging_max_duration_ms=desc.discharging_max_duration_ms=10000;
 cm=(struct charger_manager){.desc=&desc,.charger_psy=&psy};regulator.enabled=false;
 const int sequence_temp[]={250,250,250,450,250,-1,1,30};
 const int sequence_error[]={0,-EIO,-ENODEV,0,0,0,0,0};
 const bool sequence_allowed[]={true,false,false,false,true,false,false,true};
 for(unsigned i=0;i<sizeof(sequence_temp)/sizeof(sequence_temp[0]);i++) {
  sensor_temp=sequence_temp[i];sensor_error=sequence_error[i];_cm_monitor(&cm);
  assert(regulator.enabled==sequence_allowed[i]);count++;
 }
 /* Existing explicitly unmonitored configurations keep their behavior. */
 desc.measure_battery_temp=false;cm.emergency_stop=0;cm.battery_status=POWER_SUPPLY_STATUS_DISCHARGING;
 cm.charger_enabled=false;regulator.enabled=false;sensor_error=-ENODEV;sensor_reads=0;
 _cm_monitor(&cm);assert(regulator.enabled && !sensor_reads);count++;
 external_power=false;_cm_monitor(&cm);
 assert(!regulator.enabled && cm.battery_status==POWER_SUPPLY_STATUS_DISCHARGING);count++;
 printf("PASS: %u actual temperature/duration/regulator/fault/recovery cases under ASan/UBSan\n",count);
 return 0;
}
'''
functions = "\n".join(function(name) for name in
                      ("try_charger_enable", "check_charging_duration",
                       "cm_check_thermal_status", "cm_get_target_status", "_cm_monitor",
                       "charger_get_property"))
with tempfile.TemporaryDirectory(prefix="fx0-cm-thermal-") as temporary:
    root = Path(temporary)
    (root / "check.c").write_text(stubs + enum + "\n" + functions + main)
    subprocess.run(["clang", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                    "-fsanitize=address,undefined", "-fno-sanitize-recover=all",
                    f"-DEXPECT_VULNERABLE={int(args.expect_vulnerable)}",
                    str(root / "check.c"), "-o", str(root / "check")], check=True)
    subprocess.run([str(root / "check")], check=True)
