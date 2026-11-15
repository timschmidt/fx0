#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real VADC scaling, IIO wrappers and SMBB sampling in one process.

ADC conversion results, calibration reference readings, work queues and PMIC
registers are synthetic. Kernel registration, driver core and hardware are not
executed. Extracted functions and channel metadata remain unchanged.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess


def definition(text, name):
    start = text.index(name)
    brace = text.index('{', start)
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end]


IIO_STUBS = r'''
typedef uint16_t u16;
typedef int32_t s32;
typedef int64_t s64;
#define MICRO 1000000
#define NANO 1000000000
#define INDIO_MAX_RAW_ELEMENTS 4
struct u32_fract { unsigned int numerator, denominator; };
struct iio_chan_spec {
 int channel, address, type, indexed;
 const char *datasheet_name;
 unsigned long info_mask_separate, info_mask_shared_by_type;
 unsigned long info_mask_shared_by_dir, info_mask_shared_by_all;
};
struct vadc_priv;
struct iio_dev;
struct iio_info {
 int (*read_raw)(struct iio_dev *,const struct iio_chan_spec *,int *,int *,long);
 int (*read_raw_multi)(struct iio_dev *,const struct iio_chan_spec *,int,int *,int *,long);
};
struct iio_dev_opaque {struct mutex info_exist_lock;};
struct iio_dev {struct vadc_priv *chip;const struct iio_info *info;struct iio_dev_opaque *opaque;};
struct iio_channel {struct iio_dev *indio_dev;const struct iio_chan_spec *channel;};
static struct iio_dev_opaque *to_iio_dev_opaque(struct iio_dev *d) {return d->opaque;}
#define iio_priv(d) ((d)->chip)
static s64 div_s64(s64 value,int denominator) {return value/denominator;}
static s64 div64_s64(s64 value,s64 denominator) {return value/denominator;}
static struct mutex *guard_acquire(struct mutex *m) {mutex_lock(m);return m;}
static void guard_release(struct mutex **m) {mutex_unlock(*m);}
#define guard(kind) TEST_GUARD_##kind
#define TEST_GUARD_mutex(p) struct mutex *const_guard __attribute__((cleanup(guard_release))) = guard_acquire(p)
#define __stringify_inner(x) #x
#define __stringify(x) __stringify_inner(x)
'''

HARDWARE_STUBS = r'''
struct vadc_priv {
 struct vadc_channel_prop *chan_props;
 struct vadc_linear_graph graph[2];
 struct smbb_charger *consumer;
 struct iio_dev_opaque *opaque;
};
static u16 injected_raw[2];
static int conversion_error[2];
static u64 conversion_latency[2];
static unsigned int conversions[2];
static int vadc_do_conversion(struct vadc_priv *v,struct vadc_channel_prop *p,u16 *raw)
{
 unsigned int index=p-v->chan_props;assert(index<2);
 assert(!v->consumer->charge_lock.held);locked(&v->opaque->info_exist_lock);
 conversions[index]++;clock_ns+=conversion_latency[index];
 if(conversion_error[index])return conversion_error[index];
 *raw=injected_raw[index];return 0;
}
#define UNUSED_SCALE(name) \
static int name(const struct vadc_linear_graph *g,const struct u32_fract *p,bool a,u16 c,int *v) \
{(void)g;(void)p;(void)a;(void)c;(void)v;abort();}
UNUSED_SCALE(qcom_vadc_scale_therm)
UNUSED_SCALE(qcom_vadc_scale_die_temp)
UNUSED_SCALE(qcom_vadc_scale_chg_temp)
'''

MAIN = r'''
int main(void)
{
 struct smbb_charger c={0};struct regmap bus;struct power_supply supply={.charger=&c};struct smbb_policy policy;
 mutex_init(&c.charge_lock);mutex_init(&c.statlock);
 struct iio_dev_opaque opaque={0};mutex_init(&opaque.info_exist_lock);
 struct vadc_channel_prop props[2]={0};struct vadc_priv chip={.chan_props=props,.consumer=&c,.opaque=&opaque};
 chip.graph[VADC_CALIB_ABSOLUTE]=(struct vadc_linear_graph){.dx=625000,.dy=10000,.gnd=25000};
 chip.graph[VADC_CALIB_RATIOMETRIC]=(struct vadc_linear_graph){.dx=1800,.dy=18000,.gnd=24576};
 struct iio_info info={.read_raw=vadc_read_raw};struct iio_dev dev={.chip=&chip,.info=&info,.opaque=&opaque};
 struct iio_chan_spec spec[2]={0};struct vadc_priv *vadc=&chip;
 const unsigned int numbers[]={VADC_VBAT_SNS,VADC_LR_MUX1_BAT_THERM};
 for(unsigned int index=0;index<2;) {
  struct vadc_channel_prop prop={.channel=numbers[index],.calibration=index?VADC_CALIB_RATIOMETRIC:VADC_CALIB_ABSOLUTE};
  const struct vadc_channels *vadc_chan=&vadc_chans[prop.channel];
  struct iio_chan_spec *iio_chan=&spec[index];
  prop.prescale=vadc_chan->prescale_index;
  /* Exact assignments extracted from the real firmware registration loop. */
  REGISTRATION_ASSIGNMENTS
 }
 assert(props[0].prescale==1 && props[1].prescale==0);
 struct iio_channel voltage={.indio_dev=&dev,.channel=&spec[0]};
 struct iio_channel therm={.indio_dev=&dev,.channel=&spec[1]};
 unsigned int cases=0;
 const struct {u16 raw;int microvolts;} precision[]={
  {26200,2100000},{35799,3899811},{35800,3900000},{35801,3900186},
  {36866,4099875},{37400,4200000},{38200,4350000},{38201,4350186},{39100,4518750}
 };
 for(unsigned int i=0;i<ARRAY_SIZE(precision);i++) {
  injected_raw[0]=precision[i].raw;int v=-1,m=-1,raw=-1;
  assert(!iio_read_channel_processed_scale(&voltage,&v,1000) && v==precision[i].microvolts);
  assert(!iio_read_channel_processed(&voltage,&m) && m==v/1000);
  assert(iio_read_channel_raw(&voltage,&raw)==IIO_VAL_INT && raw==injected_raw[0]);
  cases++;
 }
 const struct {int mv,temp;u16 raw;int uv,state,error;} rows[]={
  {737,250,35800,3900000,SMBB_POLICY_NORMAL,0},
  {540,450,35800,3900000,SMBB_POLICY_REDUCED,0},
  {533,460,35800,3900000,SMBB_POLICY_REDUCED,0},
  {533,460,36866,4099875,SMBB_POLICY_STOP,0},
  {570,410,37400,4200000,SMBB_POLICY_NORMAL,0},
  {737,250,38200,4350000,SMBB_POLICY_NORMAL,0},
  {737,250,38201,4350186,SMBB_POLICY_STOP,0},
  {737,250,39100,4518750,SMBB_POLICY_STOP,-ERANGE},
  {737,250,25400,1950000,SMBB_POLICY_STOP,-ERANGE},
  {1627,0,35800,3900000,SMBB_POLICY_STOP,-ERANGE},
  {407,0,35800,3900000,SMBB_POLICY_STOP,-ERANGE},
  {1800,0,35800,3900000,SMBB_POLICY_STOP,-ERANGE},
  {0,0,35800,3900000,SMBB_POLICY_STOP,-ERANGE}
 };
 for(unsigned int i=0;i<ARRAY_SIZE(rows);i++) {
  setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
  injected_raw[0]=rows[i].raw;injected_raw[1]=24576+rows[i].mv*10;
  conversions[0]=conversions[1]=0;
  smbb_policy_sample_work(&policy.sample_work.work);
  assert(policy.last_error==rows[i].error && policy.state==rows[i].state);
  if(!rows[i].error)assert(policy.microvolts==rows[i].uv && policy.temperature==rows[i].temp);
  assert(!!(bus.registers[0x49]&0x80)==(!rows[i].error && rows[i].state!=SMBB_POLICY_STOP));
  assert(supply.notifications==1 && conversions[1]==1);
  assert(conversions[0]==(rows[i].mv>407 && rows[i].mv<1627));
  assert(!opaque.info_exist_lock.held && !c.charge_lock.held);
  cases++;
 }
 const int errors[]={-EIO,-ETIMEDOUT,-ENODEV,-EINVAL};
 for(unsigned int channel=0;channel<2;channel++)for(unsigned int e=0;e<ARRAY_SIZE(errors);e++) {
  setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
  injected_raw[0]=35800;injected_raw[1]=31946;conversions[0]=conversions[1]=0;
  conversion_error[channel]=errors[e];
  smbb_policy_sample_work(&policy.sample_work.work);
  assert(policy.last_error==errors[e] && policy.state==SMBB_POLICY_STOP);
  assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);assert(!(bus.registers[0x49]&0x80));
  assert(conversions[1]==1 && conversions[0]==(channel==0));
  conversion_error[channel]=0;cases++;
 }
 for(unsigned int channel=0;channel<2;channel++) {
  setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
  injected_raw[0]=35800;injected_raw[1]=31946;props[channel].scale_fn_type=-1;
  smbb_policy_sample_work(&policy.sample_work.work);
  assert(policy.last_error==-EINVAL && !(bus.registers[0x49]&0x80));
  props[channel].scale_fn_type=SCALE_DEFAULT;cases++;
  setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
  conversion_latency[channel]=3001000000ULL;smbb_policy_sample_work(&policy.sample_work.work);
  assert(policy.last_error==-ESTALE && !(bus.registers[0x49]&0x80));
  conversion_latency[channel]=0;cases++;
 }
 setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
 dev.info=NULL;smbb_policy_sample_work(&policy.sample_work.work);
 assert(policy.last_error==-ENODEV && !(bus.registers[0x49]&0x80));dev.info=&info;cases++;
 setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
 smbb_policy_sample_work(&policy.sample_work.work);assert(!policy.last_error && (bus.registers[0x49]&0x80));cases++;
 for(unsigned int v=0;v<3;v++) {
  setup(&c,&bus,&supply,&policy);policy.thermistor=&therm;policy.voltage=&voltage;
  const unsigned int votes[]={SMBB_INHIBIT_USER,SMBB_INHIBIT_PACK,SMBB_INHIBIT_FAULT};
  c.charge_inhibit|=votes[v];smbb_policy_sample_work(&policy.sample_work.work);
  assert((c.charge_inhibit & votes[v]) && !(bus.registers[0x49]&0x80));cases++;
 }
 assert(!pthread_mutex_destroy(&opaque.info_exist_lock.gate));
 assert(!pthread_mutex_destroy(&c.charge_lock.gate));assert(!pthread_mutex_destroy(&c.statlock.gate));
 printf("%u actual VADC/IIO-wrapper/SMBB sampling chain cases pass\n",cases);
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kernel', type=Path)
    parser.add_argument('--support', type=Path, default=Path(__file__).with_name('chain-support.json'))
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--negative-controls', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    k, out = args.kernel.resolve(), args.output.resolve()
    out.mkdir(mode=0o700)
    support = json.loads(args.support.read_text())
    assert support['SPDX-License-Identifier'] == 'GPL-2.0-only'
    stubs = support['stubs']
    source = (k / 'drivers/power/supply/qcom_smbb.c').read_text()
    defines = '\n'.join(re.findall(r'^#define (?:SMBB_\w+|STATUS_\w+|CTRL_EN|PRES_STATUS_BAT_PRES)\s+.*$', source, re.M))
    attrs = source[source.index('enum smbb_attr {'):source.index('struct smbb_charger {')]
    limits = source[source.index('static int smbb_vbat_weak_fn('):source.index('static int smbb_charger_attr_read(')]
    controls = source[source.index('static int smbb_charge_verify('):source.index('static enum power_supply_property smbb_charger_properties')]
    vadc = (k / 'drivers/iio/adc/qcom-spmi-vadc.c').read_text()
    common = (k / 'drivers/iio/adc/qcom-vadc-common.c').read_text()
    core = (k / 'drivers/iio/inkern.c').read_text()
    types = (k / 'include/linux/iio/types.h').read_text()
    header = (k / 'include/linux/iio/adc/qcom-vadc-common.h').read_text()
    functions = ['static int iio_channel_read(', 'int iio_read_channel_raw(', 'int iio_multiply_value(',
                 'static int iio_convert_raw_to_processed_unlocked(',
                 'int iio_read_channel_processed_scale(', 'int iio_read_channel_processed(']
    types_text = '\n'.join(re.findall(r'^#define IIO_VAL_\w+ [0-9]+(?: /\*.*?\*/)?$', types, re.M)) + '\n'
    types_text += definition(types, 'enum iio_chan_info_enum {') + ';\n'
    types_text += definition((k / 'include/uapi/linux/iio/types.h').read_text(), 'enum iio_chan_type {') + ';\n'
    types_text += definition(header, 'enum vadc_calibration {') + ';\n'
    types_text += definition(header, 'enum vadc_scale_fn_type {') + ';\n'
    types_text += definition(header, 'struct vadc_linear_graph {') + ';\n'
    types_text += definition(vadc, 'struct vadc_channel_prop {') + ';\n'
    prescales = definition(vadc, 'static const struct u32_fract vadc_prescale_ratios[] =') + ';\n'
    table = vadc[vadc.index('struct vadc_channels {'):vadc.index('\nstatic int vadc_get_fw_channel_data(')]
    table = (k / 'include/dt-bindings/iio/qcom,spmi-vadc.h').read_text() + '\n' + table
    registrations = vadc[vadc.index('\t\tprop.scale_fn_type ='):vadc.index('\n\t\tiio_chan++;')]
    sample_main = MAIN.replace('REGISTRATION_ASSIGNMENTS', registrations)
    policy = '#include "' + str(k / 'drivers/power/supply/qcom_smbb_policy.h') + '"\n'
    policy += definition(source, 'struct smbb_policy {') + ';\n'
    for name in ['static int smbb_policy_handoff(', 'static void smbb_policy_setup(',
                 'static int smbb_policy_apply(', 'static void smbb_policy_sample_work(',
                 'static void smbb_policy_age_work(', 'static int smbb_policy_quiesce(',
                 'static int smbb_set_line_flag(', 'static irqreturn_t smbb_bat_present_handler(']:
        policy += definition(source, name) + '\n'
    text = stubs + IIO_STUBS + types_text + HARDWARE_STUBS + prescales + table
    text += definition((k / 'include/linux/iio/iio.h').read_text(), 'static inline bool iio_channel_has_info(')
    for name in ['static void qcom_vadc_scale_calib(', 'static int qcom_vadc_scale_volt(', 'int qcom_vadc_scale(']:
        text += '\n' + definition(common, name)
    text += '\n' + definition(vadc, 'static int vadc_read_raw(')
    text += '\n'.join(definition(core, name) for name in functions)
    text += '\n#define EPROBE_DEFER 517\n' + defines + '\n' + attrs
    text += limits + controls + policy + support['reset'] + support['setup'] + sample_main
    variants = [('candidate', text)]
    if args.negative_controls:
        # Each control changes one real implementation contract; successful
        # compilation plus a failing run is mandatory, never a compile failure.
        missing = text.replace('VADC_CHAN_VOLT(VBAT_SNS, 1, SCALE_DEFAULT)',
                               'VADC_CHAN_NO_SCALE(VBAT_SNS, 1)', 1)
        assert missing != text
        variants += [('missing-advertisement', missing),
                     ('wrong-processed-denominator', text.replace('*val2 = 1000;', '*val2 = 1;', 1)),
                     ('lost-consumer-precision', text.replace('policy->voltage, &microvolts, 1000)',
                                                             'policy->voltage, &microvolts, 1)', 1))]
        assert all(code != text for _, code in variants[1:])
    record = {'started_UTC': datetime.now(timezone.utc).isoformat(), 'variants': [],
              'checker_SHA256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'support_SHA256': hashlib.sha256(args.support.read_bytes()).hexdigest(),
              'phone_access': False, 'hardware_and_kernel_driver_core_executed': False,
              'conversion_IO_calibration_workqueues_and_PMIC_synthetic': True,
              'actual_default_scaling_IIO_wrappers_and_policy_sampling_executed': True,
              'source_file_SHA256': {p: hashlib.sha256((k / p).read_bytes()).hexdigest() for p in [
                  'drivers/iio/adc/qcom-spmi-vadc.c', 'drivers/iio/adc/qcom-vadc-common.c',
                  'drivers/iio/inkern.c', 'drivers/power/supply/qcom_smbb.c',
                  'drivers/power/supply/qcom_smbb_policy.h']}}
    try:
        for name, code in variants:
            cfile, binary = out / (name + '.c'), out / name
            cfile.write_text(code)
            compile_run = subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                         '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-sign-compare',
                         '-Wno-misleading-indentation',
                         '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-pthread',
                         str(cfile), '-o', str(binary)], capture_output=True, timeout=60)
            (out / (name + '-compile.stdout')).write_bytes(compile_run.stdout)
            (out / (name + '-compile.stderr')).write_bytes(compile_run.stderr)
            assert compile_run.returncode == 0, name
            run = subprocess.run([str(binary)], capture_output=True, timeout=15)
            (out / (name + '.stdout')).write_bytes(run.stdout)
            (out / (name + '.stderr')).write_bytes(run.stderr)
            if name == 'candidate':
                assert run.returncode == 0 and not run.stderr, name
                assert run.stdout == b'39 actual VADC/IIO-wrapper/SMBB sampling chain cases pass\n'
                record['cases'] = 39
            else:
                assert run.returncode != 0 and b'Assertion' in run.stderr, name
            record['variants'].append({'name': name, 'returncode': run.returncode,
                                       'expected_result_verified': True,
                                       'C_source_SHA256': hashlib.sha256(code.encode()).hexdigest()})
        record['passed'] = True
    finally:
        record['finished_UTC'] = datetime.now(timezone.utc).isoformat()
        (out / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record, indent=2))


if __name__ == '__main__':
    main()
