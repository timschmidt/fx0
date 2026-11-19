#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise actual child probe/PM callbacks with modeled devres and IIO lifetime."""
import argparse
import ast
from pathlib import Path
import resource
import subprocess
import sys
import tempfile


API = r'''
#include <stdint.h>
#include <stdlib.h>
#define GFP_KERNEL 0
#define DL_FLAG_AUTOREMOVE_CONSUMER 1
#define ERR_PTR(error) ((void *)(intptr_t)(error))
#define PTR_ERR(pointer) ((int)(intptr_t)(pointer))
#define IS_ERR(pointer) ((uintptr_t)(pointer) >= (uintptr_t)-4095)
#define IS_ERR_OR_NULL(pointer) (!(pointer) || IS_ERR(pointer))
#define dev_err_probe(dev,error,...) (error)
#define INIT_DELAYED_WORK(job,callback) do { (job)->initialized=true; } while (0)
struct power_supply_battery_info {
 int constant_charge_voltage_max_uv,charge_full_design_uah;
};
struct iio_dev {struct device dev;};
struct platform_device {struct device dev;};
struct dentry {int dummy;};
static struct dentry debug_entry;
static int smbb_policy_status_fops;
static struct device *consumer,*supplier;
static struct iio_channel therm,voltage;
static struct iio_dev adc,other_adc;
static struct smbb_policy *allocated_policy;
static bool allocation_fail,link_fail,bound,action_fail,debug_fail;
static int therm_error,voltage_error,type_error;
static unsigned int links,channel_releases,initializations;
static char release_order[32];
static unsigned int order_count;
static void event(char c) {assert(order_count+1<sizeof(release_order));release_order[order_count++]=c;}
static void add_action(struct device *dev,void (*fn)(void *),void *data)
{assert(dev->action_count<8);unsigned int n=dev->action_count++;dev->actions[n]=fn;dev->action_data[n]=data;}
static void free_policy(void *data)
{assert(data==allocated_policy);event('F');allocated_policy=NULL;free(data);}
static void *devm_kzalloc(struct device *dev,size_t size,int flags)
{assert(dev==consumer && !flags);if(allocation_fail)return NULL;void *p=calloc(1,size);assert(p);allocated_policy=p;add_action(dev,free_policy,p);return p;}
static void release_channel(void *data)
{
 assert(data==&therm || data==&voltage);
 assert(!allocated_policy || (!allocated_policy->sample_work.pending && !allocated_policy->age_work.pending));
 channel_releases++;event('R');
}
static struct iio_channel *devm_iio_channel_get(struct device *dev,const char *name)
{
 assert(dev==consumer);
 struct iio_channel *p;int error;
 if(!strcmp(name,"thermistor")){p=&therm;error=therm_error;}
 else {assert(!strcmp(name,"voltage"));p=&voltage;error=voltage_error;}
 if(error)return ERR_PTR(error);add_action(dev,release_channel,p);return p;
}
static void *device_link_add(struct device *dev,struct device *provider,unsigned int flags)
{assert(dev==consumer && provider==supplier && flags==DL_FLAG_AUTOREMOVE_CONSUMER);links++;return link_fail?NULL:&links;}
static bool device_is_bound(struct device *dev) {assert(dev==supplier);return bound;}
static int iio_get_channel_type(struct iio_channel *channel,enum iio_chan_type *type)
{assert(channel==&therm || channel==&voltage);if(type_error)return type_error;*type=channel->kind;return 0;}
static int of_property_read_string(struct device_node *node,const char *name,const char **value)
{assert(!strcmp(name,"lg,battery-charge-profile"));if(node->profile_error)return node->profile_error;*value=node->profile;return 0;}
static void *dev_get_drvdata(struct device *dev) {return dev->drvdata;}
static void platform_set_drvdata(struct platform_device *pdev,void *data) {pdev->dev.drvdata=data;}
static void *platform_get_drvdata(struct platform_device *pdev) {return pdev->dev.drvdata;}
static int devm_add_action_or_reset(struct device *dev,void (*fn)(void *),void *data)
{assert(dev==consumer);if(action_fail){fn(data);return -ENOMEM;}add_action(dev,fn,data);return 0;}
static struct dentry *debugfs_create_dir(const char *name,void *parent)
{assert(!parent && !strcmp(name,"qcom-smbb-policy"));return debug_fail?ERR_PTR(-ENODEV):&debug_entry;}
static void debugfs_create_file(const char *name,unsigned int mode,struct dentry *dir,void *data,void *ops)
{assert(!strcmp(name,"status") && mode==0400 && dir==&debug_entry && data==allocated_policy && ops==&smbb_policy_status_fops);}
static void debugfs_remove_recursive(struct dentry *dir)
{assert(!dir || dir==&debug_entry);assert(allocated_policy && !allocated_policy->running);assert(!allocated_policy->sample_work.pending && !allocated_policy->age_work.pending);event('S');}
static void release_devres(struct device *dev)
{while(dev->action_count){unsigned int n=--dev->action_count;dev->actions[n](dev->action_data[n]);}dev->drvdata=NULL;}
'''

TESTS = r'''
struct fixture {
 struct regmap io;struct smbb_charger chg;struct power_supply battery;
 struct power_supply_battery_info info;struct device_node node;struct device parent,provider;
 struct platform_device child;
};
static struct fixture f;
static unsigned int cases;
static void setup(void)
{
 memset(&f,0,sizeof(f));clock_ns=10000000000ULL;bus_delay_ns=0;queued=canceled=0;
 allocation_fail=link_fail=action_fail=debug_fail=false;bound=true;
 therm_error=voltage_error=type_error=0;links=channel_releases=order_count=initializations=0;
 memset(release_order,0,sizeof(release_order));assert(!allocated_policy);
 f.node.profile="tocad-madai";f.parent.of_node=&f.node;f.parent.drvdata=&f.chg;
 f.child.dev.parent=&f.parent;consumer=&f.child.dev;supplier=&f.provider;
 f.chg.dev=&f.parent;f.chg.regmap=&f.io;f.chg.addr=0x1000;
 f.chg.software_control=true;f.chg.charge_inhibit=SMBB_INHIBIT_POLICY;
 f.chg.board_current=f.chg.user_current=f.chg.thermal_current=1200000;
 f.chg.board_voltage=f.chg.user_voltage=4350000;
 f.chg.board_recharge_voltage=4280000; f.chg.attr[ATTR_CHG_VDET]=4280000;
 f.chg.attr[ATTR_BAT_IMAX]=1200000;f.chg.attr[ATTR_BAT_VMAX]=4350000;
 mutex_init(&f.chg.charge_lock);mutex_init(&f.chg.statlock);
 f.io.lock=&f.chg.charge_lock;f.io.error=-EIO;
 f.io.registers[0x49]=0x55;f.io.registers[0x208]=0x80;f.io.registers[0x249]=0x81;
 f.io.registers[0x44]=24;f.io.registers[0x40]=111;f.io.registers[0x5d]=52;
 f.info.constant_charge_voltage_max_uv=4350000;f.info.charge_full_design_uah=2370000;
 f.battery.charger=&f.chg;f.battery.battery_info=&f.info;f.chg.bat_psy=&f.battery;
 adc=(struct iio_dev){.dev={.parent=supplier}};other_adc=adc;
 therm=(struct iio_channel){.value=737,.indio_dev=&adc,.kind=IIO_VOLTAGE};
 voltage=(struct iio_channel){.value=3900000,.indio_dev=&adc,.kind=IIO_VOLTAGE};
}
static void finish(void)
{
 release_devres(consumer);assert(!allocated_policy && !(f.io.registers[0x49]&0x80));
#ifdef BTC_CTRL_STOCK
 assert(f.io.registers[0x249] == 0x81);
#endif
 assert(!pthread_mutex_destroy(&f.chg.charge_lock.gate));
 assert(!pthread_mutex_destroy(&f.chg.statlock.gate));
}
static struct smbb_policy *probe(void)
{
 assert(!smbb_policy_probe(&f.child));
 struct smbb_policy *p=platform_get_drvdata(&f.child);assert(p==allocated_policy && p->running);
 assert(p->state==SMBB_POLICY_STOP && (f.chg.charge_inhibit&SMBB_INHIBIT_SAMPLE));
 assert(p->sample_work.pending && p->age_work.pending && queued==2 && links==1);
 assert(!f.io.operations);return p;
}
int main(void)
{
 setbuf(stdout,NULL);
 unsigned int rejected_probes=20;
#ifdef TEST_MANAGED_RECHARGE
 rejected_probes++;
#endif
 for(unsigned int fault=0;fault<rejected_probes;fault++) {
  setup();int expected=-EINVAL;
  switch(fault) {
  case 0:f.parent.drvdata=NULL;expected=-ENODEV;break;
  case 1:f.chg.software_control=false;expected=-ENODEV;break;
  case 2:f.chg.charge_inhibit|=SMBB_INHIBIT_HANDOFF;expected=-EPROTO;break;
  case 3:f.node.profile_error=-ENODATA;expected=-ENODEV;break;
  case 4:f.node.profile="unknown";expected=-ENODEV;break;
  case 5:f.battery.battery_info=NULL;break;
  case 6:f.info.constant_charge_voltage_max_uv=4400000;break;
  case 7:f.info.charge_full_design_uah=2440000;break;
  case 8:f.chg.board_voltage=4400000;break;
  case 9:f.chg.board_current=1500000;break;
  case 10:allocation_fail=true;expected=-ENOMEM;break;
  case 11:therm_error=-EPROBE_DEFER;expected=-EPROBE_DEFER;break;
  case 12:voltage_error=-EIO;expected=-EIO;break;
  case 13:voltage.indio_dev=&other_adc;break;
  case 14:link_fail=true;break;
  case 15:bound=false;expected=-EPROBE_DEFER;break;
  case 16:therm.kind=IIO_TEMP;break;
  case 17:voltage.kind=IIO_TEMP;break;
  case 18:type_error=-EIO;break;
  case 19:action_fail=true;expected=-ENOMEM;break;
  case 20:f.chg.board_recharge_voltage=f.chg.board_voltage;break;
  }
  assert(smbb_policy_probe(&f.child)==expected);
  assert(!queued && !(f.io.registers[0x49]&0x80));
  finish();cases++;
 }
 setup();struct smbb_policy *p=probe();smbb_policy_sample_work(&p->sample_work.work);
 assert(!f.chg.charge_inhibit && (f.io.registers[0x49]&0x80));
 assert(!smbb_policy_suspend(&f.child.dev));
 assert(!p->running && !p->sample_work.pending && !p->age_work.pending && canceled==2);
 assert(f.chg.charge_inhibit&SMBB_INHIBIT_SUSPEND);assert(!(f.io.registers[0x49]&0x80));
#ifdef BTC_CTRL_STOCK
 assert(f.io.registers[0x249] == 0x81);
#endif
 assert(!smbb_policy_resume(&f.child.dev));
 assert(p->running && !p->last_valid_ns && p->sample_work.pending && p->age_work.pending);
 assert((f.chg.charge_inhibit&(SMBB_INHIBIT_SAMPLE|SMBB_INHIBIT_SUSPEND))==(SMBB_INHIBIT_SAMPLE|SMBB_INHIBIT_SUSPEND));
 therm.error=-EIO;smbb_policy_sample_work(&p->sample_work.work);assert(!(f.io.registers[0x49]&0x80));
 therm.error=0;smbb_policy_sample_work(&p->sample_work.work);assert(f.io.registers[0x49]&0x80);
 smbb_policy_shutdown(&f.child);assert(!p->running && !(f.io.registers[0x49]&0x80));
#ifdef BTC_CTRL_STOCK
 assert(f.io.registers[0x249] == 0x81);
#endif
 finish();assert(!strcmp(release_order,"SRRF"));cases++;
 setup();p=probe();smbb_policy_sample_work(&p->sample_work.work);
 f.io.fail_at=f.io.operations+1;assert(smbb_policy_suspend(&f.child.dev)==-EIO);
 assert(!p->running && !p->sample_work.pending && !p->age_work.pending);
 assert(f.chg.charge_inhibit&SMBB_INHIBIT_FAULT);finish();cases++;
 setup();debug_fail=true;probe();finish();assert(!strcmp(release_order,"SRRF"));cases++;
 for(unsigned int cycle=0;cycle<3;cycle++) {
  setup();p=probe();smbb_policy_sample_work(&p->sample_work.work);
  assert(f.io.registers[0x49]&0x80);finish();assert(channel_releases==2);
  assert(!strcmp(release_order,"SRRF"));cases++;
 }
 setup();f.chg.charge_inhibit|=SMBB_INHIBIT_PACK;p=probe();
 smbb_policy_sample_work(&p->sample_work.work);assert(f.chg.charge_inhibit&SMBB_INHIBIT_PACK);
 assert(!(f.io.registers[0x49]&0x80));finish();cases++;
 printf("PASS: %u actual child-probe/PM/devres-order model cases; no real device-core or hardware execution\n",cases);
}
'''


def fixture_parts(root, linux):
    # Reuse only the established fixture's source-generation prefix. Its sole
    # TemporaryDirectory block compiles/runs tests and is explicitly excluded.
    path = root / 'diagnostics/smbb-charging-policy/check-control.py'
    tree = ast.parse(path.read_text())
    blocks = [i for i, node in enumerate(tree.body) if isinstance(node, ast.With)]
    if len(blocks) != 1 or blocks[0] != len(tree.body) - 1:
        raise RuntimeError('control fixture layout changed')
    prefix = ast.Module(body=tree.body[:blocks[0]], type_ignores=[])
    namespace = {'__file__': str(path), '__name__': 'source_generation_only'}
    saved = sys.argv
    try:
        sys.argv = [str(path), str(linux)]
        exec(compile(prefix, str(path), 'exec'), namespace)
    finally:
        sys.argv = saved
    return namespace


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('linux', type=Path)
    parser.add_argument('--negative-controls', action='store_true')
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    root = Path(__file__).resolve().parents[2]
    parts = fixture_parts(root, args.linux.resolve())
    stubs = parts['stubs']
    stubs = stubs.replace('struct iio_channel {', 'enum iio_chan_type {IIO_VOLTAGE,IIO_TEMP};\nstruct iio_dev;\nstruct iio_channel {struct iio_dev *indio_dev;enum iio_chan_type kind;')
    stubs = stubs.replace('struct delayed_work {struct work_struct work;};', 'struct delayed_work {struct work_struct work;bool initialized,pending;};')
    stubs = stubs.replace('(void)queue;(void)work;(void)delay;queued++;', '(void)queue;(void)delay;assert(work->initialized);work->pending=true;queued++;')
    stubs = stubs.replace('(void)work;canceled++;', 'assert(work->initialized);work->pending=false;canceled++;')
    stubs = stubs.replace('struct device_node {', 'struct device_node {const char *profile;int profile_error;')
    stubs = stubs.replace('struct device {struct device_node *of_node;};', 'struct device {struct device_node *of_node;struct device *parent;void *drvdata;void (*actions[8])(void *);void *action_data[8];unsigned int action_count;};')
    stubs = stubs.replace('struct power_supply {', 'struct power_supply {struct power_supply_battery_info *battery_info;')
    definition = parts['definition']
    functions = {name: definition('static ' + kind + ' ' + name + '(') for name, kind in
                 [('smbb_policy_stop', 'void'), ('smbb_policy_probe', 'int'),
                  ('smbb_policy_suspend', 'int'), ('smbb_policy_resume', 'int'),
                  ('smbb_policy_shutdown', 'void')]}
    prefix = stubs + '\n#define EPROBE_DEFER 517\n' + parts['defines'] + '\n'
    prefix += parts['attrs'] + parts['limits'] + parts['controls'] + parts['policy'] + API
    variants = [('actual', functions)]
    if args.negative_controls:
        mutations = [
            ('missing-cleanup-action', 'smbb_policy_probe',
             'devm_add_action_or_reset(dev, smbb_policy_stop, policy)', '0'),
            ('lost-resume-votes', 'smbb_policy_resume',
             'chg->charge_inhibit |= SMBB_INHIBIT_SAMPLE;', 'chg->charge_inhibit = 0;'),
            ('unknown-profile-accepted', 'smbb_policy_probe',
             'if (ret || strcmp(profile, "tocad-madai"))', 'if (ret)'),
        ]
        for label, name, before, after in mutations:
            changed = dict(functions)
            if changed[name].count(before) != 1:
                raise RuntimeError('mutation anchor changed')
            changed[name] = changed[name].replace(before, after)
            variants.append((label, changed))
    with tempfile.TemporaryDirectory(prefix='fx0-smbb-lifetime-') as directory:
        temporary = Path(directory)
        for label, bodies in variants:
            source = temporary / (label + '.c')
            binary = temporary / label
            source.write_text(prefix + '\n'.join(bodies.values()) + TESTS)
            subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-function', '-Wno-unused-parameter', '-Wno-sign-compare',
                            '-Wno-misleading-indentation', '-fsanitize=address,undefined',
                            '-fno-sanitize-recover=all', '-pthread', str(source), '-o', str(binary)], check=True)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=15)
            if label == 'actual':
                if result.returncode or result.stderr:
                    sys.stderr.write(result.stderr)
                    raise RuntimeError('lifetime fixture failed')
                print(result.stdout.strip(), flush=True)
            elif result.returncode != -6 or 'Assertion' not in result.stderr:
                raise RuntimeError('negative control was not rejected by its contract assertion')
            else:
                print('PASS: rejected ' + label, flush=True)


if __name__ == '__main__':
    main()
