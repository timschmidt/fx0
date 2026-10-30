#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual policy workers/actuators/PM quiesce with faulted I/O and time."""
import argparse
import ast
from pathlib import Path
import re
import resource
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('linux', type=Path)
args = parser.parse_args()
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
root = Path(__file__).resolve().parents[2]
driver = args.linux.resolve()/'drivers/power/supply/qcom_smbb.c'
source = driver.read_text()
base = ast.parse((root/'diagnostics/smbb-charge-guard/check.py').read_text())
strings = {node.targets[0].id: ast.literal_eval(node.value) for node in base.body
           if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name)
           and node.targets[0].id in ['stubs', 'tests']}
stubs = strings['stubs']
stubs = stubs.replace('#include <assert.h>', '#include <assert.h>\n#include <stddef.h>')
stubs = stubs.replace('struct regmap {', r'''
typedef unsigned long long u64;
static u64 clock_ns=10000000000ULL,bus_delay_ns;
static bool audit_warm;
static bool smbb_pack_identity_lost;
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define IRQCHIP_STATE_LINE_LEVEL 0
static int irq_error;
static bool irq_level;
static int irq_get_irqchip_state(int irq,int which,bool *level)
{assert(irq==7 && which==IRQCHIP_STATE_LINE_LEVEL);if(irq_error)return irq_error;*level=irq_level;return 0;}
static u64 ktime_get_boottime_ns(void) {return clock_ns;}
#define NSEC_PER_MSEC 1000000ULL
#define min(a,b) ((a)<(b)?(a):(b))
#define min3(a,b,c) min(min(a,b),c)
#define container_of(p,t,f) ((t *)((char *)(p)-offsetof(t,f)))
struct work_struct {int dummy;};
struct delayed_work {struct work_struct work;};
#define to_delayed_work(p) container_of(p,struct delayed_work,work)
static unsigned int queued,canceled;
static void *system_wq,*system_highpri_wq;
static unsigned int msecs_to_jiffies(unsigned int value) {return value;}
static void queue_delayed_work(void *queue,struct delayed_work *work,unsigned int delay)
{(void)queue;(void)work;(void)delay;queued++;}
static void cancel_delayed_work_sync(struct delayed_work *work) {(void)work;canceled++;}
struct iio_channel {int value,error;u64 latency_ns;};
static int iio_read_channel_processed(struct iio_channel *channel,int *value)
{clock_ns+=channel->latency_ns;if(channel->error)return channel->error;*value=channel->value;return 0;}
static int iio_read_channel_processed_scale(struct iio_channel *channel,int *value,int scale)
{assert(scale==1000);return iio_read_channel_processed(channel,value);}
struct device_node {bool marker,request;int marker_length,request_length;};
struct device {struct device_node *of_node;};
static bool of_property_read_bool(struct device_node *node,const char *name)
{assert(!strcmp(name,"qcom,software-charge-control"));return node->request;}
static const void *of_get_property(struct device_node *node,const char *name,int *length)
{
 static char present;
 if(!strcmp(name,"qcom,boot-charge-inhibited")) {
  *length=node->marker_length;return node->marker?&present:NULL;
 }
 assert(!strcmp(name,"qcom,software-charge-control"));
 *length=node->request_length;return node->request?&present:NULL;
}
struct regmap {''')
stubs = stubs.replace('unsigned long status;', '''unsigned long status;
 bool software_control,battery_present_sampled;
 unsigned int board_current,board_voltage,user_current,user_voltage,thermal_current;
 u64 policy_valid_until_ns;
 struct power_supply *bat_psy;''')
stubs = stubs.replace('void *dev;', 'struct device *dev;')
stubs = stubs.replace('m->operations++;', 'm->operations++;clock_ns+=bus_delay_ns;')
stubs = stubs.replace('assert(value < 256);', 'assert(value < 256);if(audit_warm && reg==0x1044)assert(value<=9);')
defines = '\n'.join(re.findall(r'^#define (?:SMBB_\w+|STATUS_\w+|CTRL_EN|PRES_STATUS_BAT_PRES)\s+.*$', source, re.M))
attrs = source[source.index('enum smbb_attr {'):source.index('struct smbb_charger {')]
limits = source[source.index('static int smbb_vbat_weak_fn('):source.index('static int smbb_charger_attr_read(')]
controls = source[source.index('/* Caller holds charge_lock.'):source.index('static enum power_supply_property smbb_charger_properties')]

def definition(name):
    start = source.index(name)
    brace = source.index('{', start)
    depth, end = 1, brace+1
    while depth:
        depth += (source[end] == '{')-(source[end] == '}')
        end += 1
    return source[start:end]

policy = '#include "'+str(driver.with_name('qcom_smbb_policy.h'))+'"\n'
policy += definition('struct smbb_policy {')+';\n'
for name in ['static int smbb_policy_handoff(', 'static void smbb_policy_setup(', 'static int smbb_policy_apply(',
             'static void smbb_policy_sample_work(', 'static void smbb_policy_age_work(',
             'static int smbb_policy_quiesce(', 'static int smbb_set_line_flag(',
             'static irqreturn_t smbb_bat_present_handler(']:
    policy += definition(name)+'\n'
tests = strings['tests'].replace('int main(void)', 'static int legacy_cases(void)')
extra = r'''
static void setup(struct smbb_charger *c,struct regmap *m,struct power_supply *p,struct smbb_policy *policy)
{
 reset(c,m,0x55,SMBB_INHIBIT_POLICY);clock_ns=10000000000ULL;bus_delay_ns=0;queued=canceled=0;
 c->battery_present_sampled=false;
 m->registers[0x208]=0x80;c->software_control=true;c->board_current=c->user_current=1200000;
 m->registers[0x44]=24;m->registers[0x40]=111;
 c->board_voltage=c->user_voltage=4350000;c->thermal_current=1200000;c->policy_valid_until_ns=0;
 c->attr[ATTR_BAT_IMAX]=1200000;c->attr[ATTR_BAT_VMAX]=4350000;c->bat_psy=p;
 *policy=(struct smbb_policy){.chg=c,.state=SMBB_POLICY_STOP,.running=true};p->notifications=0;
}
static int apply(struct smbb_policy *policy,int error,int temp,int uv,u64 started)
{mutex_lock(&policy->chg->charge_lock);int ret=smbb_policy_apply(policy,error,temp,uv,started);mutex_unlock(&policy->chg->charge_lock);return ret;}
static int handoff(struct smbb_charger *c)
{mutex_lock(&c->charge_lock);int ret=smbb_policy_handoff(c);mutex_unlock(&c->charge_lock);return ret;}
static void *warm_worker(void *data)
{
 struct smbb_policy *policy=data;
 for(unsigned int i=0;i<500;i++) {
  mutex_lock(&policy->chg->charge_lock);
  assert(!smbb_policy_apply(policy,0,451,3900000,clock_ns));
  mutex_unlock(&policy->chg->charge_lock);
 }
 return NULL;
}
int main(void)
{
 setbuf(stdout,NULL);
 assert(!legacy_cases());
 struct regmap io;struct smbb_charger c={0};struct power_supply p={.charger=&c};struct smbb_policy policy;
 mutex_init(&c.charge_lock);mutex_init(&c.statlock);unsigned int count=0;
 for(unsigned int others=0;others<32;others++) {
  setup(&c,&io,&p,&policy);
  const unsigned int flags[]={SMBB_INHIBIT_USER,SMBB_INHIBIT_FAULT,SMBB_INHIBIT_PACK,SMBB_INHIBIT_HANDOFF,SMBB_INHIBIT_INIT};
  unsigned int expected=0;for(unsigned int bit=0;bit<5;bit++)if(others & (1U<<bit))expected|=flags[bit];
  c.charge_inhibit|=expected;
  assert(!apply(&policy,0,250,3900000,clock_ns));
  assert(c.charge_inhibit==expected && !!(io.registers[0x49]&0x80)==!expected);
  assert(io.registers[0x49]==(expected?0x55:0xd5));count++;
 }
 setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));
 assert(!c.charge_inhibit && io.registers[0x49]==0xd5 && policy.last_error==0);count++;
 assert(!apply(&policy,0,451,3900000,clock_ns));
 assert(c.attr[ATTR_BAT_IMAX]==450000 && c.thermal_current==450000 && policy.state==SMBB_POLICY_REDUCED);count++;
 assert(!smbb_set_battery_limit(&c,ATTR_BAT_IMAX,1200000));assert(c.attr[ATTR_BAT_IMAX]==450000);count++;
 assert(!apply(&policy,0,450,4000001,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_THERMAL);count++;
 assert(!smbb_set_charge_behaviour(&c,POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO));assert(!(io.registers[0x49]&0x80));count++;
 assert(!apply(&policy,0,419,4300000,clock_ns));assert(io.registers[0x49]==0xd5 && c.attr[ATTR_BAT_IMAX]==1200000);count++;
 assert(!smbb_set_battery_limit(&c,ATTR_BAT_IMAX,2000000));assert(c.attr[ATTR_BAT_IMAX]==1200000);count++;
 assert(!smbb_set_battery_limit(&c,ATTR_BAT_VMAX,4500000));assert(c.attr[ATTR_BAT_VMAX]==4350000);count++;
 assert(!smbb_set_battery_limit(&c,ATTR_BAT_IMAX,300000));
 assert(!apply(&policy,0,451,3900000,clock_ns));assert(c.attr[ATTR_BAT_IMAX]==300000);count++;
 const int bad[]={-ENODEV,-EIO,-ERANGE,-EPROBE_DEFER};
 for(unsigned int i=0;i<ARRAY_SIZE(bad);i++) {
  setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));
  assert(!apply(&policy,bad[i],250,3900000,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);
  assert(!(io.registers[0x49]&0x80) && policy.last_error==bad[i]);
  assert(!smbb_set_charge_behaviour(&c,POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO));assert(!(io.registers[0x49]&0x80));
  assert(!apply(&policy,0,250,3900000,clock_ns));assert(io.registers[0x49]==0xd5);count++;
 }
 const int invalid_uv[]={INT_MIN,-1,0,2099999,4500001,INT_MAX};
 for(unsigned int i=0;i<ARRAY_SIZE(invalid_uv);i++) {
  setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,invalid_uv[i],clock_ns));
  assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);assert(!(io.registers[0x49]&0x80));count++;
 }
 setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,4350001,clock_ns));
 assert(c.charge_inhibit & SMBB_INHIBIT_THERMAL);assert(!(io.registers[0x49]&0x80));count++;
 setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));
 clock_ns+=3000000000ULL;assert(!smbb_set_charge_behaviour(&c,POWER_SUPPLY_CHARGE_BEHAVIOUR_AUTO));
 assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);assert(!(io.registers[0x49]&0x80));count++;
 setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));
 clock_ns+=3000000000ULL;int behaviour=-1;
 assert(!smbb_get_charge_behaviour(&c,&behaviour) && behaviour==POWER_SUPPLY_CHARGE_BEHAVIOUR_INHIBIT_CHARGE);
 assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);assert(!(io.registers[0x49]&0x80));count++;
 setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));
 clock_ns+=3000000001ULL;smbb_policy_age_work(&policy.age_work.work);
 assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);assert(policy.last_error==-ESTALE && !(io.registers[0x49]&0x80));count++;
 setup(&c,&io,&p,&policy);bus_delay_ns=500000000ULL;
 assert(!apply(&policy,0,451,3900000,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_SAMPLE);
 assert(!(io.registers[0x49]&0x80));bus_delay_ns=0;count++;
 for(unsigned int absent=0;absent<2;absent++) {
  setup(&c,&io,&p,&policy);if(absent)io.fail_at=1;else io.registers[0x208]=0;
  assert(!apply(&policy,0,250,3900000,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_PACK);
  io.fail_at=0;io.registers[0x208]=0x80;
  assert(!apply(&policy,0,250,3900000,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_PACK);
  assert(!(io.registers[0x49]&0x80));count++;
 }
 for(unsigned int at=2;at<=13;at++)for(int after=0;after<2;after++) {
  setup(&c,&io,&p,&policy);io.fail_at=at;io.fail_after=after;
  int ret=apply(&policy,0,451,3900000,clock_ns);
  assert(ret==-EIO && (c.charge_inhibit & SMBB_INHIBIT_FAULT) && !(io.registers[0x49]&0x80));count++;
 }
 setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));
 assert(!smbb_policy_quiesce(&policy,SMBB_INHIBIT_SUSPEND));
 assert(!policy.running && canceled==2 && !(io.registers[0x49]&0x80));count++;
 assert(!apply(&policy,0,250,3900000,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_SUSPEND);count++;
 policy.running=true;assert(!apply(&policy,-ENODEV,0,0,clock_ns));assert(c.charge_inhibit & SMBB_INHIBIT_SUSPEND);
 assert(!apply(&policy,0,250,3900000,clock_ns));assert(io.registers[0x49]==0xd5);count++;
 for(int after=0;after<2;after++) {
  setup(&c,&io,&p,&policy);assert(!apply(&policy,0,250,3900000,clock_ns));io.operations=0;io.fail_at=2;io.fail_after=after;
  assert(smbb_policy_quiesce(&policy,SMBB_INHIBIT_SUSPEND)==-EIO);
  assert(!policy.running && canceled==2 && (c.charge_inhibit & SMBB_INHIBIT_FAULT));count++;
 }
 setup(&c,&io,&p,&policy);struct iio_channel therm={.value=737},voltage={.value=3900000};
 policy.thermistor=&therm;policy.voltage=&voltage;smbb_policy_sample_work(&policy.sample_work.work);
 assert(policy.temperature==250 && policy.microvolts==3900000 && io.registers[0x49]==0xd5);count++;
 therm.value=1800;smbb_policy_sample_work(&policy.sample_work.work);
 assert(policy.last_error==-ERANGE && !(io.registers[0x49]&0x80));count++;
 therm.value=737;voltage.error=-EIO;smbb_policy_sample_work(&policy.sample_work.work);
 assert(policy.last_error==-EIO && !(io.registers[0x49]&0x80));count++;
 voltage.error=0;therm.latency_ns=4000000000ULL;smbb_policy_sample_work(&policy.sample_work.work);
 assert(policy.last_error==-ESTALE && !(io.registers[0x49]&0x80));count++;
 struct device_node node={.marker=true,.request=true};struct device dev={.of_node=&node};
 setup(&c,&io,&p,&policy);c.dev=&dev;io.registers[0x249]=0x81;io.registers[0x49]=0;
 assert(!handoff(&c));count++;
 for(unsigned int bad_case=0;bad_case<8;bad_case++) {
  setup(&c,&io,&p,&policy);c.dev=&dev;node=(struct device_node){.marker=true,.request=true};io.registers[0x249]=0x81;io.registers[0x49]=0;
  if(bad_case==0)node.marker=false;if(bad_case==1)node.marker_length=4;
  if(bad_case==2)node.request=false;if(bad_case==3)node.request_length=4;
  if(bad_case==4)io.registers[0x49]|=0x80;if(bad_case==5)io.registers[0x49]|=1;
  if(bad_case==6)io.registers[0x249]=0x82;if(bad_case==7)io.fail_at=1;
  assert(handoff(&c)<0 && !io.writes);count++;
 }
 setup(&c,&io,&p,&policy);c.charge_inhibit|=SMBB_INHIBIT_HANDOFF;
 assert(!apply(&policy,0,451,3900000,clock_ns));audit_warm=true;io.enables=0;
 pthread_t threads[5];struct worker workers[4];
 for(unsigned int i=0;i<4;i++) {workers[i]=(struct worker){&c,i};assert(!pthread_create(&threads[i],NULL,concurrent,&workers[i]));}
 assert(!pthread_create(&threads[4],NULL,warm_worker,&policy));
 for(unsigned int i=0;i<5;i++)assert(!pthread_join(threads[i],NULL));
 audit_warm=false;assert(!io.enables && (c.charge_inhibit & SMBB_INHIBIT_HANDOFF));
 assert(c.attr[ATTR_BAT_IMAX]==450000 && c.thermal_current==450000);count+=2500;
 for(unsigned int event=0;event<3;event++) {
  setup(&c,&io,&p,&policy);smbb_pack_identity_lost=false;irq_error=0;irq_level=true;
  assert(smbb_bat_present_handler(7,&c)==IRQ_HANDLED && !smbb_pack_identity_lost);
  if(event==0)irq_level=false;else if(event==1)irq_error=-EIO;
  assert(smbb_bat_present_handler(7,&c)==IRQ_HANDLED && smbb_pack_identity_lost);
  assert(c.charge_inhibit & SMBB_INHIBIT_PACK);
  irq_error=0;irq_level=true;smbb_bat_present_handler(7,&c);
  assert(!apply(&policy,0,250,3900000,clock_ns));
  assert(smbb_pack_identity_lost && (c.charge_inhibit & SMBB_INHIBIT_PACK) && !(io.registers[0x49]&0x80));count++;
 }
 setup(&c,&io,&p,&policy);node=(struct device_node){.marker=true,.request=true};c.dev=&dev;
 io.registers[0x49]=0;io.registers[0x249]=0x81;
 assert(smbb_pack_identity_lost);smbb_policy_setup(&c);
 assert((c.charge_inhibit & SMBB_INHIBIT_PACK) && !(c.charge_inhibit & SMBB_INHIBIT_HANDOFF));count++;
 assert(!pthread_mutex_destroy(&c.charge_lock.gate));assert(!pthread_mutex_destroy(&c.statlock.gate));
 printf("PASS: %u actual policy worker/actuator/fault/stale/PM/handoff cases (including 2500 concurrent requests) plus 6242 legacy control cases\n",count);
}
'''
with tempfile.TemporaryDirectory(prefix='fx0-smbb-policy-control-') as directory:
    directory = Path(directory)
    (directory/'check.c').write_text(stubs+'\n#define EPROBE_DEFER 517\n'+defines+'\n'+attrs+limits+controls+policy+tests+extra)
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-function',
                    '-Wno-unused-parameter', '-Wno-sign-compare', '-Wno-misleading-indentation',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-pthread',
                    str(directory/'check.c'), '-o', str(directory/'check')], check=True)
    subprocess.run([str(directory/'check')], check=True, timeout=15)
