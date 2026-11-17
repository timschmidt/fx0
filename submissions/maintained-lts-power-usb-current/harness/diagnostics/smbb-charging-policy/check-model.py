#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Compare actual policy conversion/transitions with the original LG functions."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('linux', type=Path)
parser.add_argument('vendor', type=Path)
args = parser.parse_args()

def function(text, name):
    start = text.index(name)
    brace = text.index('{', start)
    end, depth = brace+1, 1
    while depth:
        depth += (text[end] == '{')-(text[end] == '}')
        end += 1
    return text[start:end]

header = (args.vendor/'arch/arm/mach-msm/include/mach/lge_charging_scenario.h').read_text()
vendor = (args.vendor/'arch/arm/mach-msm/lge/lge_charging_scenario.c').read_text()
adc = (args.vendor/'drivers/hwmon/qpnp-adc-common.c').read_text()
table = adc.split('static const struct qpnp_vadc_map_pt adcmap_btm_threshold[] = {', 1)[1].split('};', 1)[0]
original = [(int(t), int(v)) for t, v in re.findall(r'\{\s*(-?\d+),\s*(\d+)\s*\}', table)]
policy = args.linux.resolve()/'drivers/power/supply/qcom_smbb_policy.h'
actual = [(int(t), int(v)) for t, v in re.findall(r'\{\s*(-?\d+),\s*(\d+)\s*\}', policy.read_text())]
assert actual == original and len(actual) == 83
prelude = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <errno.h>
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define pr_err(...) ((void)0)
#define CONFIG_LGE_PM_CHARGING_TEMP_SCENARIO_V1_8 1
struct qpnp_vadc_map_pt {int32_t x,y;};
'''
tests = r'''
int main(void)
{
 unsigned int cases=0;
 for(int mv=-1;mv<=1801;mv++) {
  int temperature=12345;int64_t expected;
  int ret=smbb_policy_temperature(mv,&temperature);
  if(mv<=407 || mv>=1627)assert(ret==-ERANGE && temperature==12345);
  else {
   assert(!ret);assert(!qpnp_adc_map_temp_voltage(adcmap_btm_threshold,83,mv,&expected));
   assert(temperature==expected);
  }
  cases++;
 }
 const int extremes[]={INT_MIN,INT_MAX};
 for(unsigned int i=0;i<ARRAY_SIZE(extremes);i++) {
  int value=12345;assert(smbb_policy_temperature(extremes[i],&value)==-ERANGE && value==12345);cases++;
 }
 const enum lge_charging_states old[]={CHG_BATT_NORMAL_STATE,CHG_BATT_DECCUR_STATE,CHG_BATT_STPCHG_STATE};
 const enum smbb_policy_state states[]={SMBB_POLICY_NORMAL,SMBB_POLICY_REDUCED,SMBB_POLICY_STOP};
 const int voltages[]={2100000,3999999,4000000,4000001,4350000,4500000};
 for(unsigned int state=0;state<3;state++)for(int temp=-301;temp<=791;temp++)
 for(unsigned int v=0;v<ARRAY_SIZE(voltages);v++) {
  charging_state=old[state];
  enum lge_charging_states result=determine_lge_charging_state(determine_batt_temp_state(temp),voltages[v]);
  enum smbb_policy_state expected=result==CHG_BATT_NORMAL_STATE?SMBB_POLICY_NORMAL:
   result==CHG_BATT_DECCUR_STATE?SMBB_POLICY_REDUCED:SMBB_POLICY_STOP;
  assert(smbb_policy_next(states[state],temp,voltages[v])==expected);cases++;
 }
 const int sweep[]={250,450,451,520,521,550,551,550,521,520,450,419,-101,-100,-50,-49,250};
 charging_state=CHG_BATT_NORMAL_STATE;enum smbb_policy_state current=SMBB_POLICY_NORMAL;
 for(unsigned int i=0;i<ARRAY_SIZE(sweep);i++) {
  charging_state=determine_lge_charging_state(determine_batt_temp_state(sweep[i]),3900000);
  current=smbb_policy_next(current,sweep[i],3900000);
  assert((current==SMBB_POLICY_NORMAL && charging_state==CHG_BATT_NORMAL_STATE) ||
         (current==SMBB_POLICY_REDUCED && charging_state==CHG_BATT_DECCUR_STATE) ||
         (current==SMBB_POLICY_STOP && charging_state==CHG_BATT_STPCHG_STATE));cases++;
 }
 printf("PASS: 83 exact stock NTC points; %u actual conversion/LG transition cases ASan/UBSan\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='fx0-smbb-policy-model-') as directory:
    directory = Path(directory)
    code = prelude+'\n'+re.sub(r'^#include.*$', '', header, flags=re.M)
    code += '\n'+re.sub(r'^#include.*$', '', vendor, flags=re.M)
    code += '\nstatic const struct qpnp_vadc_map_pt adcmap_btm_threshold[] = {'+table+'};\n'
    code += function(adc, 'static int32_t qpnp_adc_map_temp_voltage(')
    code += '\n#include "'+str(policy)+'"\n'+tests
    (directory/'check.c').write_text(code)
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                    '-Wno-unused-but-set-variable', '-Wno-unused-variable', '-fsanitize=address,undefined',
                    '-fno-sanitize-recover=all', str(directory/'check.c'), '-o', str(directory/'check')], check=True)
    subprocess.run([str(directory/'check')], check=True, timeout=10)
