#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise panel references through extracted DRM/regulator core functions.

This models a last-user regulator hardware-disable rejection before the real
consumer reference decrement. It does not execute the kernel driver core,
actual GPIO/DSI/regulator hardware, coupled supplies or late parent failures.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import subprocess


def function(text, name):
    pattern = r'^(?:static\s+)?(?:inline\s+)?(?:int|void|struct\s+\w+\s*\*)\s*' + re.escape(name) + r'\([^;{}]*\)\n\{'
    m = re.search(pattern, text, re.M)
    assert m, name
    brace = text.index('{', m.start())
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[m.start():end]


STUBS = r'''
// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#define container_of(p,t,f) ((t *)((char *)(p)-offsetof(t,f)))
struct device {int unused;};
struct mutex {bool held;};
static void mutex_lock(struct mutex *m) {assert(!m->held);m->held=true;}
static void mutex_unlock(struct mutex *m) {assert(m->held);m->held=false;}
static unsigned logs;
#define dev_warn(...) ((void)logs++)
#define dev_info(...) ((void)logs++)
#define dev_err(...) ((void)logs++)
#define rdev_err(...) ((void)logs++)
#define WARN(condition,...) (condition)
#define lockdep_assert_held_once(...) ((void)0)
#define REGULATOR_CHANGE_STATUS 1
#define REGULATOR_EVENT_PRE_DISABLE 1
#define REGULATOR_EVENT_ABORT_DISABLE 2
#define REGULATOR_EVENT_DISABLE 3
#define NOTIFY_STOP_MASK 0x8000
#define PM_SUSPEND_ON 0
struct regulator;
struct regulation_constraints {bool always_on;};
struct regulator_dev {
 unsigned use_count;
 struct regulation_constraints *constraints;
 struct {unsigned n_coupled;} coupling_desc;
 struct regulator *supply;
};
struct regulator {struct regulator_dev *rdev;unsigned enable_count,uA_load;};
static int disable_error,enable_error,dsi_error;
static unsigned hardware_disables,gpio_calls,gpio_error_at;
static int _notifier_call_chain(struct regulator_dev *d,int event,void *arg)
{(void)d;(void)event;(void)arg;return 0;}
static bool regulator_ops_is_valid(struct regulator_dev *d,int op)
{(void)d;assert(op==REGULATOR_CHANGE_STATUS);return true;}
static int _regulator_do_disable(struct regulator_dev *d)
{assert(d->use_count==1);hardware_disables++;return disable_error;}
static int drms_uA_update(struct regulator_dev *d) {(void)d;return 0;}
static int regulator_balance_voltage(struct regulator_dev *d,int state)
{(void)d;(void)state;assert(false);return -EINVAL;}
struct drm_panel;
struct drm_panel_follower;
struct drm_panel_follower_funcs {
 int (*panel_prepared)(struct drm_panel_follower *);
 int (*panel_unpreparing)(struct drm_panel_follower *);
};
struct drm_panel_follower {const struct drm_panel_follower_funcs *funcs;};
struct drm_panel_funcs {int (*prepare)(struct drm_panel *);int (*unprepare)(struct drm_panel *);};
struct drm_panel {struct device *dev;const struct drm_panel_funcs *funcs;bool prepared;struct mutex follower_lock;int followers;};
#define list_for_each_entry(f,head,member) for((void)(head),(f)=NULL;(f);(f)=NULL)
struct mipi_dsi_device {struct device dev;unsigned long mode_flags;};
struct gpio_desc {int value;};
static int gpiod_direction_output(struct gpio_desc *g,int value)
{gpio_calls++;if(gpio_calls==gpio_error_at)return -EREMOTEIO;g->value=value;return 0;}
static void gpiod_set_value_cansleep(struct gpio_desc *g,int value) {g->value=value;}
static void usleep_range(unsigned low,unsigned high) {assert(low<=high);}
static void msleep(unsigned delay) {(void)delay;}
'''

REGULATOR_BRIDGE = r'''
/* Consumer-enable helper is real; rail enable itself is a contract stub. */
static int regulator_enable(struct regulator *r)
{
 if(enable_error)return enable_error;
 unsigned before=r->enable_count;int ret=_regulator_handle_consumer_enable(r);
 if(!ret && !before)r->rdev->use_count++;
 return ret;
}
static int regulator_disable(struct regulator *r) {return _regulator_disable(r);}
'''

MAIN = r'''
static void setup(struct lg_fx0 *p,struct regulator *reg,struct regulator_dev *rd,
                  struct regulation_constraints *constraints,struct gpio_desc *gp)
{
 memset(p,0,sizeof(*p));memset(reg,0,sizeof(*reg));memset(rd,0,sizeof(*rd));
 memset(gp,0,4*sizeof(*gp));*constraints=(struct regulation_constraints){0};
 rd->constraints=constraints;rd->coupling_desc.n_coupled=1;reg->rdev=rd;
 p->vdd=reg;p->reset=&gp[0];p->io_enable=&gp[1];p->positive_enable=&gp[2];p->negative_enable=&gp[3];
 static struct mipi_dsi_device dsi;static struct device dev;
 static const struct drm_panel_funcs funcs={.prepare=lg_fx0_prepare,.unprepare=lg_fx0_unprepare};
 p->dsi=&dsi;p->panel.dev=&dev;p->panel.funcs=&funcs;
 disable_error=enable_error=dsi_error=0;gpio_calls=gpio_error_at=hardware_disables=0;
}
int main(void)
{
 unsigned cases=0,broken=0;
 struct lg_fx0 p;struct regulator reg;struct regulator_dev rd;struct regulation_constraints constraints;struct gpio_desc gp[4];
 const unsigned cycles[]={1,2,5,10};
 for(unsigned c=0;c<4;c++) {
  setup(&p,&reg,&rd,&constraints,gp);
  for(unsigned i=0;i<cycles[c];i++) {
   drm_panel_prepare(&p.panel);assert(p.panel.prepared && reg.enable_count==1 && rd.use_count==1);
   drm_panel_unprepare(&p.panel);assert(!p.panel.prepared && !reg.enable_count && !rd.use_count);
  }
  cases++;
 }
 setup(&p,&reg,&rd,&constraints,gp);rd.use_count=1; /* One other consumer. */
 drm_panel_prepare(&p.panel);disable_error=-EIO;drm_panel_unprepare(&p.panel);
 assert(!p.panel.prepared && !reg.enable_count && rd.use_count==1 && !hardware_disables);cases++;

 setup(&p,&reg,&rd,&constraints,gp);drm_panel_prepare(&p.panel);disable_error=-EIO;
 drm_panel_unprepare(&p.panel);assert(reg.enable_count==1 && rd.use_count==1 && hardware_disables==1);
 bool lost=!p.panel.prepared;
 disable_error=0;drm_panel_unprepare(&p.panel); /* Retry a rejected unprepare. */
 drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
 broken+=lost || reg.enable_count!=0 || rd.use_count!=0;cases++;

 for(unsigned kind=0;kind<2;kind++) {
  setup(&p,&reg,&rd,&constraints,gp);disable_error=-EIO;
  if(kind==0)dsi_error=-ETIMEDOUT;else gpio_error_at=2;
  drm_panel_prepare(&p.panel);
  assert(!p.panel.prepared && reg.enable_count==1 && rd.use_count==1 && hardware_disables==1);
  disable_error=dsi_error=0;gpio_error_at=0;
  drm_panel_prepare(&p.panel);assert(p.panel.prepared);
  drm_panel_unprepare(&p.panel);
  broken+=reg.enable_count!=0 || rd.use_count!=0;cases++;
 }
 printf("cases=%u broken=%u\n",cases,broken);return broken?1:0;
}
'''

EXTRA = r'''
 for(unsigned offset=1;offset<=4;offset++) {
  setup(&p,&reg,&rd,&constraints,gp);drm_panel_prepare(&p.panel);
  gpio_error_at=gpio_calls+offset;drm_panel_unprepare(&p.panel);
  bool lost=!p.panel.prepared;
  gpio_error_at=0;drm_panel_unprepare(&p.panel);
  drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
  broken+=lost || reg.enable_count!=0 || rd.use_count!=0;cases++;
 }
 setup(&p,&reg,&rd,&constraints,gp);dsi_error=-ETIMEDOUT;disable_error=-EIO;
 drm_panel_prepare(&p.panel);
 bool excess=reg.enable_count!=1;
 for(unsigned retry=0;retry<2;retry++) {
  drm_panel_prepare(&p.panel);excess|=reg.enable_count!=1;
 }
 dsi_error=disable_error=0;drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
 broken+=excess || reg.enable_count!=0 || rd.use_count!=0;cases++;

 setup(&p,&reg,&rd,&constraints,gp);enable_error=-EIO;
 drm_panel_prepare(&p.panel);
 assert(!p.panel.prepared && !reg.enable_count && !rd.use_count && !gpio_calls);
 enable_error=0;drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
 assert(!reg.enable_count && !rd.use_count);cases++;
 for(unsigned kind=0;kind<2;kind++) {
  setup(&p,&reg,&rd,&constraints,gp);
  if(kind==0)dsi_error=-ETIMEDOUT;else gpio_error_at=2;
  drm_panel_prepare(&p.panel);assert(!p.panel.prepared && !reg.enable_count && !rd.use_count);
  dsi_error=0;gpio_error_at=0;drm_panel_prepare(&p.panel);drm_panel_unprepare(&p.panel);
  assert(!reg.enable_count && !rd.use_count);cases++;
 }
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--driver', type=Path, required=True)
    parser.add_argument('--expected-broken', type=int, required=True)
    parser.add_argument('--extended', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    args.output.mkdir(mode=0o700)
    driver = args.driver.read_text()
    regulator = (args.kernel / 'drivers/regulator/core.c').read_text()
    drm = (args.kernel / 'drivers/gpu/drm/drm_panel.c').read_text()
    text = STUBS
    for name in ['_regulator_handle_consumer_enable', '_regulator_handle_consumer_disable', '_regulator_disable']:
        text += '\n' + function(regulator, name)
    text += REGULATOR_BRIDGE
    start = driver.index('struct lg_fx0 {')
    text += driver[start:driver.index('\n};', start) + 3]
    text += function(driver, 'to_lg_fx0')
    text += '\nstatic int lg_fx0_on(struct lg_fx0 *p) {(void)p;return dsi_error;}\n'
    for name in ['lg_fx0_power_off', 'lg_fx0_prepare', 'lg_fx0_unprepare']:
        text += '\n' + function(driver, name)
    text += '\n' + function(drm, 'drm_panel_prepare') + '\n' + function(drm, 'drm_panel_unprepare')
    text += MAIN.replace(' printf("cases=%u broken=%u\\n",cases,broken);',
                         (EXTRA if args.extended else '') + ' printf("cases=%u broken=%u\\n",cases,broken);')
    cfile, binary = args.output / 'fixture.c', args.output / 'fixture'
    cfile.write_text(text)
    p = subprocess.run(['clang-21', '-std=c11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                        '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                        str(cfile), '-o', str(binary)], capture_output=True, timeout=60)
    (args.output / 'compile.stdout').write_bytes(p.stdout)
    (args.output / 'compile.stderr').write_bytes(p.stderr)
    assert p.returncode == 0
    p = subprocess.run([str(binary)], capture_output=True, timeout=15,
        env=os.environ | {'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'})
    (args.output / 'run.stdout').write_bytes(p.stdout)
    (args.output / 'run.stderr').write_bytes(p.stderr)
    assert not p.stderr
    m = re.fullmatch(rb'cases=(\d+) broken=(\d+)\n', p.stdout)
    assert m and int(m[2]) == args.expected_broken and p.returncode == bool(args.expected_broken)
    result = {'recorded_UTC': datetime.now(timezone.utc).isoformat(), 'cases': int(m[1]),
              'extended_cleanup_controls': args.extended,
              'broken': int(m[2]), 'expected_result_verified': True,
              'driver_SHA256': hashlib.sha256(args.driver.read_bytes()).hexdigest(),
              'DRM_core_SHA256': hashlib.sha256(drm.encode()).hexdigest(),
              'regulator_core_SHA256': hashlib.sha256(regulator.encode()).hexdigest(),
              'fixture_SHA256': hashlib.sha256(text.encode()).hexdigest(),
              'actual_extracted_DRM_and_regulator_disable_functions_executed': True,
              'full_kernel_core_registration_locking_hardware_or_DSI_commands_executed': False,
              'fault_scope': 'Last-user hardware-disable rejection before consumer decrement; other regulator failures are not modeled.',
              'phone_access': False}
    (args.output / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
