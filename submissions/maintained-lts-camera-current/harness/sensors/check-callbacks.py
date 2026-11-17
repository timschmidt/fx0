#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute sensor callbacks with real V4L2 stream/CCI/PM-counter helpers.

The bus, active-state locks, control-cache helpers and power resources are
synthetic. This does not execute the ioctl layer, full runtime PM, real
regulators, firmware parsing, the driver core or image capture.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def function(text, name):
    match = re.search(r'^(?:static\s+)?(?:inline\s+)?(?:int|void|bool|const void\s*\*|struct \w+\s*\*)\s*\n?' + re.escape(name) + r'\([^;{}]*\)\n\{', text, re.M)
    assert match, name
    brace = text.index('{', match.start())
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end]


def macro(text, name):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if re.match(r'#define ' + name + r'(?:\(|\s)', line))
    end = start
    while lines[end].endswith('\\'):
        end += 1
    return '\n'.join(lines[start:end + 1])


STUBS = r'''
// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <linux/v4l2-controls.h>
#include <linux/v4l2-subdev.h>
#include <linux/media-bus-format.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int32_t s32;
typedef uint64_t u64;
typedef int64_t s64;
#define U32_MAX UINT32_MAX
#define BIT(n) (1U<<(n))
#define BIT_ULL(n) (1ULL<<(n))
#define GENMASK(h,l) ((~0U<<(l)) & (~0U>>(31-(h))))
#define FIELD_GET(mask,x) (((x)&(mask))>>__builtin_ctz(mask))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BITS_PER_BYTE 8
#define BUILD_BUG_ON(c) _Static_assert(!(c),"build bug")
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define min(a,b) ((a)<(b)?(a):(b))
#define MEDIA_PAD_FL_SOURCE 2
#define V4L2_SUBDEV_FL_STREAMS 0x100
#define RPM_ACTIVE 0
static unsigned underflows;
#define dev_warn(...) ((void)underflows++)
#define dev_err(...) ((void)0)
#define dev_dbg(dev,...) ((void)(dev))
#define dev_get_drvdata(d) ((d)->driver_data)
#define spin_lock_irqsave(lock,flags) do {(void)(lock);(flags)=0;} while(0)
#define spin_unlock_irqrestore(lock,flags) do {(void)(lock);(void)(flags);} while(0)
#define trace_rpm_usage(...) ((void)0)
struct device {
 void *driver_data;
 struct {int usage_count,child_count,disable_depth,runtime_status,lock;bool ignore_children;} power;
};
static int atomic_sub_return(int value,int *p) {return *p-=value;}
static void atomic_inc(int *p) {++*p;}
static int atomic_read(const int *p) {return *p;}
static int atomic_inc_not_zero(int *p) {if(!*p)return 0;++*p;return 1;}
struct regmap {struct device *dev;u8 bytes[65536];};
struct clk {bool enabled;};
struct gpio_desc {int value;};
struct regulator_bulk_data {const char *supply;};
struct media_pad {unsigned flags;};
struct media_device {struct device *dev;};
struct media_entity {struct {struct media_device *mdev;} graph_obj;unsigned num_pads;struct media_pad *pads;const char *name;};
struct v4l2_subdev_client_info {int unused;};
struct v4l2_subdev_stream_config {u32 pad,stream;bool enabled;};
struct v4l2_subdev_state {
 bool locked;struct v4l2_mbus_framefmt format;
 struct {unsigned num_configs;struct v4l2_subdev_stream_config *configs;} stream_configs;
};
struct v4l2_subdev;
struct v4l2_ctrl;
struct v4l2_ctrl_handler {struct v4l2_ctrl *exposure,*vblank;};
struct v4l2_ctrl {unsigned id;int val,minimum,maximum,step;struct v4l2_ctrl_handler *handler;};
struct v4l2_subdev_pad_ops {
 int (*enable_streams)(struct v4l2_subdev *,struct v4l2_subdev_state *,u32,u64);
 int (*disable_streams)(struct v4l2_subdev *,struct v4l2_subdev_state *,u32,u64);
};
struct v4l2_subdev_video_ops {int (*s_stream)(struct v4l2_subdev *,int);};
struct v4l2_subdev_ops {const struct v4l2_subdev_pad_ops *pad;const struct v4l2_subdev_video_ops *video;};
struct v4l2_subdev {
 struct device *dev;struct media_entity entity;const struct v4l2_subdev_ops *ops;
 struct v4l2_subdev_state *active;u64 enabled_pads;unsigned flags;bool s_stream_enabled;
};
#define v4l2_subdev_has_op(sd,group,op) ((sd)->ops->group && (sd)->ops->group->op)
#define v4l2_subdev_call(sd,group,op,...) ((sd)->ops->group->op(sd,__VA_ARGS__))
static struct v4l2_subdev_state *v4l2_subdev_lock_and_get_active_state(struct v4l2_subdev *sd)
{assert(!sd->active->locked);sd->active->locked=true;return sd->active;}
static struct v4l2_subdev_state *v4l2_subdev_get_locked_active_state(struct v4l2_subdev *sd)
{assert(sd->active->locked);return sd->active;}
static void v4l2_subdev_unlock_state(struct v4l2_subdev_state *s) {assert(s->locked);s->locked=false;}
static void v4l2_subdev_enable_privacy_led(struct v4l2_subdev *sd) {(void)sd;}
static void v4l2_subdev_disable_privacy_led(struct v4l2_subdev *sd) {(void)sd;}
static struct v4l2_mbus_framefmt *v4l2_subdev_state_get_format(struct v4l2_subdev_state *s,unsigned pad)
{assert(!pad);return &s->format;}
static unsigned writes,fail_write_at;
static int resume_error,setup_error,bulk_error,clock_error;
static unsigned power_refs,bulk_calls,clock_calls,range_updates;
static void put_bytes(u64 val,u8 *p,unsigned size,bool le)
{for(unsigned i=0;i<size;i++)p[le?i:size-i-1]=(val>>(8*i))&0xff;}
#define put_unaligned_le16(v,p) put_bytes(v,p,2,true)
#define put_unaligned_be16(v,p) put_bytes(v,p,2,false)
#define put_unaligned_le24(v,p) put_bytes(v,p,3,true)
#define put_unaligned_be24(v,p) put_bytes(v,p,3,false)
#define put_unaligned_le32(v,p) put_bytes(v,p,4,true)
#define put_unaligned_be32(v,p) put_bytes(v,p,4,false)
#define put_unaligned_le64(v,p) put_bytes(v,p,8,true)
#define put_unaligned_be64(v,p) put_bytes(v,p,8,false)
static int regmap_bulk_write(struct regmap *m,unsigned reg,const void *p,unsigned len)
{writes++;assert(reg+len<=sizeof(m->bytes));if(writes==fail_write_at)return -EIO;memcpy(m->bytes+reg,p,len);return 0;}
static int pm_runtime_resume_and_get(struct device *dev)
{if(resume_error)return resume_error;dev->power.usage_count++;return 0;}
static int rpm_drop_usage_count(struct device *dev);
static int pm_runtime_put(struct device *dev) {int ret=rpm_drop_usage_count(dev);return ret<0?ret:0;}
static int __v4l2_ctrl_modify_range(struct v4l2_ctrl *ctrl,int minimum,int maximum,int step,int def)
{range_updates++;assert(minimum<=maximum && def>=minimum && def<=maximum);ctrl->minimum=minimum;ctrl->maximum=maximum;ctrl->step=step;if(ctrl->val>maximum)ctrl->val=maximum;return 0;}
static int __v4l2_ctrl_s_ctrl(struct v4l2_ctrl *ctrl,int value) {ctrl->val=value;return 0;}
static int __v4l2_ctrl_handler_setup(struct v4l2_ctrl_handler *hdl) {(void)hdl;return setup_error;}
static int regulator_bulk_enable(unsigned n,struct regulator_bulk_data *supplies)
{assert(n==3);assert(!strcmp(supplies[0].supply,"dovdd") && !strcmp(supplies[1].supply,"avdd") && !strcmp(supplies[2].supply,"dvdd"));bulk_calls++;if(bulk_error)return bulk_error;power_refs++;return 0;}
static int regulator_bulk_disable(unsigned n,struct regulator_bulk_data *supplies)
{(void)supplies;assert(n==3 && power_refs);power_refs--;return 0;}
static int clk_prepare_enable(struct clk *clk) {clock_calls++;if(clock_error)return clock_error;assert(!clk->enabled);clk->enabled=true;return 0;}
static void clk_disable_unprepare(struct clk *clk) {assert(clk->enabled);clk->enabled=false;}
static int gpiod_set_value_cansleep(struct gpio_desc *g,int value) {g->value=value;return 0;}
static void usleep_range(unsigned low,unsigned high) {assert(low<=high);}
'''

MAIN = r'''
static unsigned cases,broken,stop_broken,format_broken;
#define CHECK(c) do {cases++;if(!(c))broken++;} while(0)
static struct SENSOR s;
static struct device device;
static struct regmap map;
static struct clk clock;
static struct gpio_desc gpio;
static struct v4l2_subdev_state active;
static struct media_device mdev;
static struct v4l2_ctrl exposure,vblank;
static void setup(unsigned mode)
{
 memset(&s,0,sizeof(s));memset(&device,0,sizeof(device));memset(&map,0,sizeof(map));
 memset(&clock,0,sizeof(clock));memset(&gpio,0,sizeof(gpio));memset(&active,0,sizeof(active));
 s.dev=&device;s.regmap=&map;s.xclk=&clock;s.reset_gpio=&gpio;s.mode=&SENSOR_modes[mode];
 for(unsigned i=0;i<ARRAY_SIZE(SENSOR_supply_names);i++)s.supplies[i].supply=SENSOR_supply_names[i];
 map.dev=&device;device.driver_data=&s.sd;device.power.runtime_status=RPM_ACTIVE;
 static const struct v4l2_subdev_pad_ops pads={.enable_streams=SENSOR_enable_streams,.disable_streams=SENSOR_disable_streams};
 static const struct v4l2_subdev_ops ops={.pad=&pads};
 s.sd.dev=&device;s.sd.ops=&ops;s.sd.active=&active;s.pad.flags=MEDIA_PAD_FL_SOURCE;
 mdev.dev=&device;s.sd.entity.graph_obj.mdev=&mdev;s.sd.entity.num_pads=1;s.sd.entity.pads=&s.pad;s.sd.entity.name="synthetic-sensor";
 exposure=(struct v4l2_ctrl){.id=V4L2_CID_EXPOSURE,.val=UPPER_FRAME_LENGTH_DEF-10,.minimum=1,.maximum=0xffff,.step=1,.handler=&s.ctrl_handler};
 vblank=(struct v4l2_ctrl){.id=V4L2_CID_VBLANK,.val=UPPER_FRAME_LENGTH_DEF-s.mode->height,.handler=&s.ctrl_handler};
 s.exposure=&exposure;s.vblank=&vblank;s.ctrl_handler.exposure=&exposure;s.ctrl_handler.vblank=&vblank;
 SENSOR_fill_format(&active.format,s.mode);
 writes=fail_write_at=underflows=0;resume_error=setup_error=bulk_error=clock_error=0;
 power_refs=bulk_calls=clock_calls=range_updates=0;
}
static unsigned reg16(unsigned address) {return ((unsigned)map.bytes[address]<<8)|map.bytes[address+1];}
int main(void)
{
 for(unsigned m=0;m<ARRAY_SIZE(SENSOR_modes);m++) {
  setup(m);
  for(unsigned cycle=0;cycle<10;cycle++) {
   CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==0 && device.power.usage_count==1 && s.sd.enabled_pads==1);
   CHECK(reg16(0x034c)==s.mode->width && reg16(0x034e)==s.mode->height && map.bytes[0x0100]==1);
   CHECK(v4l2_subdev_disable_streams(&s.sd,0,1)==0 && !device.power.usage_count && !s.sd.enabled_pads && !underflows);
  }
  unsigned write_count=ARRAY_SIZE(SENSOR_common_regs)+s.mode->num_regs+1;
  for(unsigned fail=1;fail<=write_count;fail++) {
   setup(m);fail_write_at=fail;
   CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==-EIO && !device.power.usage_count && !s.sd.enabled_pads && !underflows && writes==fail);
  }
  setup(m);resume_error=-EIO;CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==-EIO && !device.power.usage_count && !writes && !s.sd.enabled_pads);
  setup(m);setup_error=-ERANGE;CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==-ERANGE && !device.power.usage_count && !s.sd.enabled_pads);
  for(unsigned repeat=1;repeat<=3;repeat+=2) {
   setup(m);assert(v4l2_subdev_enable_streams(&s.sd,0,1)==0);bool ok=true;
   for(unsigned attempt=0;attempt<repeat;attempt++) {
    fail_write_at=writes+1;
    int ret=v4l2_subdev_disable_streams(&s.sd,0,1);
    ok &= ret==-EIO && device.power.usage_count==1 && s.sd.enabled_pads==1 && !underflows;
   }
   fail_write_at=0;
   ok &= v4l2_subdev_disable_streams(&s.sd,0,1)==0 && !device.power.usage_count && !s.sd.enabled_pads && !underflows;
   cases++;if(!ok){broken++;stop_broken++;}
  }
  setup(m);assert(v4l2_subdev_enable_streams(&s.sd,0,1)==0);
  struct v4l2_subdev_state attempt={0};
  struct v4l2_subdev_format fmt={.which=V4L2_SUBDEV_FORMAT_TRY,.format={.width=SENSOR_modes[0].width,.height=SENSOR_modes[0].height}};
  const struct SENSOR_mode *saved=s.mode;unsigned before=writes;
  CHECK(SENSOR_set_format(&s.sd,&attempt,&fmt)==0 && s.mode==saved && writes==before && device.power.usage_count==1);
  assert(v4l2_subdev_disable_streams(&s.sd,0,1)==0);
  {
   setup(m);assert(v4l2_subdev_enable_streams(&s.sd,0,1)==0);
   unsigned next=(m+1)%ARRAY_SIZE(SENSOR_modes);struct v4l2_mbus_framefmt old=active.format;unsigned width=reg16(0x034c);
   fmt=(struct v4l2_subdev_format){.which=V4L2_SUBDEV_FORMAT_ACTIVE,.format={.width=SENSOR_modes[next].width,.height=SENSOR_modes[next].height}};
   before=writes;active.locked=true;
   int ret=SENSOR_set_format(&s.sd,&active,&fmt);active.locked=false;
   bool ok=ret==-EBUSY && s.mode==&SENSOR_modes[m] && !memcmp(&old,&active.format,sizeof(old)) && writes==before && reg16(0x034c)==width;
   cases++;if(!ok){broken++;format_broken++;}
   assert(v4l2_subdev_disable_streams(&s.sd,0,1)==0);
  }
  setup(m);struct v4l2_ctrl ctrl={.handler=&s.ctrl_handler};
  const unsigned ids[]={V4L2_CID_EXPOSURE,V4L2_CID_ANALOGUE_GAIN,V4L2_CID_VBLANK,V4L2_CID_TEST_PATTERN};
  const unsigned addresses[]={0x0202,0x0205,0x0340,0x0600};
  for(unsigned i=0;i<4;i++) {
   ctrl.id=ids[i];ctrl.val=i==2?100:17;int saved_count=device.power.usage_count;
   CHECK(SENSOR_set_ctrl(&ctrl)==0 && device.power.usage_count==saved_count);
   CHECK(!writes); /* Suspended/not-in-use controls only update the cache. */
   device.power.usage_count=1;
   CHECK(SENSOR_set_ctrl(&ctrl)==0 && device.power.usage_count==1 && !underflows);
   unsigned value=i==2?s.mode->height+100:17;
   CHECK((i==1?map.bytes[addresses[i]]:reg16(addresses[i]))==value);
   writes=0;device.power.usage_count=0;
  }
  setup(m);CHECK(SENSOR_power_on(&device)==0 && power_refs==1 && clock.enabled && gpio.value==0);
  CHECK(SENSOR_power_off(&device)==0 && !power_refs && !clock.enabled && gpio.value==1);
  setup(m);bulk_error=-EIO;CHECK(SENSOR_power_on(&device)==-EIO && !power_refs && !clock_calls);
  setup(m);clock_error=-EIO;CHECK(SENSOR_power_on(&device)==-EIO && !power_refs && !clock.enabled);
 }
 setup(0);CHECK(v4l2_subdev_enable_streams(&s.sd,1,1)==-EINVAL && !writes);
 CHECK(v4l2_subdev_enable_streams(&s.sd,0,2)==-EINVAL && !writes);
 CHECK(v4l2_subdev_enable_streams(&s.sd,0,0)==0 && !writes);
 CHECK(v4l2_subdev_disable_streams(&s.sd,0,1)==-EALREADY && !underflows);
 printf("cases=%u broken=%u stop=%u format=%u\n",cases,broken,stop_broken,format_broken);
 return broken?1:0;
}
'''


def build_fixture(driver, kernel, sensor):
    prefix = STUBS
    cci_header = (kernel / 'include/media/v4l2-cci.h').read_text()
    prefix += '\n' + cci_header[cci_header.index('struct cci_reg_sequence {'):cci_header.index('/**\n * cci_read()')]
    prefix += '\n' + driver[driver.index('#define ' + sensor.upper() + '_REG_CHIP_ID'):driver.index('static inline struct ' + sensor + ' *to_')]
    runtime = (kernel / 'drivers/base/power/runtime.c').read_text()
    for name in ['rpm_drop_usage_count', 'pm_runtime_get_conditional', 'pm_runtime_get_if_in_use']:
        prefix += '\n' + function(runtime, name)
    cci = (kernel / 'drivers/media/v4l2-core/v4l2-cci.c').read_text()
    for name in ['cci_write', 'cci_multi_reg_write']:
        prefix += '\n' + function(cci, name)
    common = (kernel / 'drivers/media/v4l2-core/v4l2-common.c').read_text()
    common_h = (kernel / 'include/media/v4l2-common.h').read_text()
    math = (kernel / 'include/linux/math.h').read_text()
    prefix += '\n#undef abs\n' + macro(math, '__abs_choose_expr') + '\n' + macro(math, 'abs')
    prefix += '\n' + function(common, '__v4l2_find_nearest_size_conditional')
    for name in ['v4l2_find_nearest_size_conditional', 'v4l2_find_nearest_size']:
        prefix += '\n' + macro(common_h, name)
    subdev = (kernel / 'drivers/media/v4l2-core/v4l2-subdev.c').read_text()
    prefix += '\n' + function(subdev, 'v4l2_subdev_is_streaming')
    for name in ['to_' + sensor, sensor + '_update_exposure_range', sensor + '_set_ctrl', sensor + '_fill_format',
                 sensor + '_set_format', sensor + '_enable_streams', sensor + '_disable_streams',
                 sensor + '_power_on', sensor + '_power_off']:
        prefix += '\n' + function(driver, name)
    for name in ['v4l2_subdev_collect_streams', 'v4l2_subdev_set_streams_enabled', 'v4l2_subdev_enable_streams', 'v4l2_subdev_disable_streams']:
        prefix += '\n' + function(subdev, name)
    prefix += '\n' + MAIN.replace('SENSOR', sensor).replace('UPPER', sensor.upper())
    return prefix


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['kernel', 'driver', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--sensor', choices=['imx132', 'imx179'], required=True)
    parser.add_argument('--expected-broken', type=int, required=True)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    text = build_fixture(args.driver.read_text(), args.kernel, args.sensor)
    fixture, binary = args.output / 'fixture.c', args.output / 'fixture'
    fixture.write_text(text)
    build = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', '-Wno-unused-const-variable',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            str(fixture), '-o', str(binary)], capture_output=True, timeout=60)
    (args.output / 'compile.stdout').write_bytes(build.stdout)
    (args.output / 'compile.stderr').write_bytes(build.stderr)
    assert build.returncode == 0 and not build.stderr
    (args.output / 'tmp').mkdir(mode=0o700)
    run = subprocess.run([str(binary)], capture_output=True, timeout=60,
                         env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1', 'TMPDIR':str(args.output / 'tmp')})
    (args.output / 'run.stdout').write_bytes(run.stdout)
    (args.output / 'run.stderr').write_bytes(run.stderr)
    assert not run.stderr
    match = re.fullmatch(rb'cases=(\d+) broken=(\d+) stop=(\d+) format=(\d+)\n', run.stdout)
    assert match and int(match[2]) == args.expected_broken and run.returncode == bool(args.expected_broken)
    paths = ['drivers/base/power/runtime.c', 'drivers/media/v4l2-core/v4l2-subdev.c',
             'drivers/media/v4l2-core/v4l2-cci.c', 'drivers/media/v4l2-core/v4l2-common.c',
             'include/media/v4l2-common.h', 'include/media/v4l2-cci.h', 'include/linux/math.h']
    record = dict(passed=True, sensor=args.sensor, cases=int(match[1]), broken=int(match[2]),
                  stop_failures=int(match[3]), format_failures=int(match[4]), expected_result_verified=True,
                  driver_SHA256=hashlib.sha256(args.driver.read_bytes()).hexdigest(),
                  source_SHA256={p: hashlib.sha256((args.kernel / p).read_bytes()).hexdigest() for p in paths},
                  fixture_SHA256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                  actual_sensor_stream_control_format_power_functions_executed=True,
                  actual_V4L2_stream_CCI_nearest_size_PM_count_helpers_executed=True,
                  transport_locks_control_cache_power_resources_and_full_PM_mocked=True,
                  regulator_disable_failure_GPIO_failure_ioctl_layer_and_hardware_qualified=False,
                  host_Linux_UAPI_headers_used_for_fixture_types=True, phone_access=False)
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
