#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute QFPROM probe/read and current NVMEM keepout/sysfs helpers.

All MMIO values and platform resources are synthetic. Device registration,
SRCU, runtime PM and resource acquisition are contract stubs. This does not
read the phone or exercise fuse programming or the real kernel driver core.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def function(text, name):
    match = re.search(r'^(?:static\s+)?(?:inline\s+)?(?:int|void|ssize_t|umode_t)\s+' + re.escape(name) + r'\([^;{}]*\)\n\{', text, re.M)
    assert match, name
    brace = text.index('{', match.start())
    depth, end = 1, brace + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[match.start():end]


STUBS = r'''
// SPDX-License-Identifier: GPL-2.0-only
/* Extracted portions retain the original QFPROM and NVMEM core copyrights:
 * Copyright (C) 2015 Srinivas Kandagatla <srinivas.kandagatla@linaro.org>
 * Copyright (C) 2013 Maxime Ripard <maxime.ripard@free-electrons.com>
 */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t u32;
typedef unsigned umode_t;
#define __iomem
#define GFP_KERNEL 0
#define IORESOURCE_MEM 0
#define NVMEM_DEVID_AUTO (-2)
#define BITS_PER_BYTE 8
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
#define IS_ALIGNED(a,b) (!((a)% (b)))
#define round_down(a,b) ((a)-((a)%(b)))
#define min(a,b) ((a)<(b)?(a):(b))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p)>(uintptr_t)-4096)
#define PTR_ERR_OR_ZERO(p) (IS_ERR(p)?PTR_ERR(p):0)
#define dev_err(...) ((void)0)
#define dev_err_probe(dev,err,...) ((void)(dev),(err))
#define guard(type) fake_guard

#define srcu_dereference(p,s) ((void)(s),(p))
#define rcu_dereference_raw(p) (p)
struct resource {size_t start,end;unsigned slot;};
struct device {const void *match;bool read_only;};
struct platform_device {struct device dev;struct resource regions[4];unsigned count;};
struct clk {int unused;};
struct regulator {int unused;};
struct file {int unused;};
struct kobject {struct device *dev;};
struct bin_attribute {void *private;};
struct nvmem_keepout {unsigned start,end;unsigned char value;};
struct nvmem_cell_info {unsigned offset,bit_offset,nbits,bytes;};
struct nvmem_device;
struct nvmem_config {
 const char *name;bool add_legacy_fixed_of_cells,read_only,root_only;
 unsigned stride,word_size;int id;size_t size;struct device *dev;void *priv;
 int (*reg_read)(void *,unsigned,void *,size_t);
 int (*reg_write)(void *,unsigned,void *,size_t);
 void (*fixup_dt_cell_info)(struct nvmem_device *,struct nvmem_cell_info *);
 const struct nvmem_keepout *keepout;unsigned nkeepout;
};
struct nvmem_operations {
 int (*reg_read)(void *,unsigned,void *,size_t);
 int (*reg_write)(void *,unsigned,void *,size_t);
};
struct nvmem_device {
 struct device dev;struct nvmem_operations *ops;unsigned srcu;
 unsigned stride,word_size;size_t size;bool root_only,read_only;
 int (*reg_read)(void *,unsigned,void *,size_t);
 int (*reg_write)(void *,unsigned,void *,size_t);
 void *priv,*wp_gpio;const struct nvmem_keepout *keepout;unsigned nkeepout;
};
static struct nvmem_device registered;

static struct nvmem_config captured;
static bool raw_view;
static unsigned maps,clock_gets,regulator_gets,mmio_reads,bad_raw_reads,program_calls;
static unsigned pm_enables,pm_disables,registrations;
static int mapping_error,action_error,registration_error;
static u32 memory[4][2048];
static _Alignas(max_align_t) unsigned char allocation[4096];
static bool read_raw_data;
static struct device *kobj_to_dev(struct kobject *k) {return k->dev;}
#define to_nvmem_device(d) ((struct nvmem_device *)((char *)(d)-offsetof(struct nvmem_device,dev)))
static const void *device_get_match_data(struct device *dev) {return dev->match;}
static bool device_property_present(struct device *dev,const char *name)
{assert(!strcmp(name,"read-only"));return dev->read_only;}
static struct resource *platform_get_resource(struct platform_device *p,int type,unsigned index)
{assert(type==IORESOURCE_MEM);return index<p->count?&p->regions[index]:NULL;}
static size_t resource_size(struct resource *r) {return r->end-r->start+1;}
static void *devm_kzalloc(struct device *dev,size_t size,int flags)
{(void)dev;(void)flags;assert(size<=sizeof(allocation));memset(allocation,0,sizeof(allocation));return allocation;}
static void *devm_platform_get_and_ioremap_resource(struct platform_device *p,unsigned index,struct resource **res)
{*res=platform_get_resource(p,0,index);if(!*res)return ERR_PTR(-ENOENT);if(mapping_error)return ERR_PTR(mapping_error);maps++;return memory[index];}
static void *devm_ioremap_resource(struct device *dev,struct resource *res)
{(void)dev;maps++;return memory[res->slot];}
static void *devm_platform_ioremap_resource(struct platform_device *p,unsigned index)
{struct resource *r=platform_get_resource(p,0,index);return r?devm_ioremap_resource(&p->dev,r):ERR_PTR(-ENOENT);}
static bool readable(unsigned offset)
{return (offset>=0xb0 && offset<0xb8)||(offset>=0x450 && offset<0x460);}
static u32 readl(const void *ptr)
{
 uintptr_t address=(uintptr_t)ptr,base=(uintptr_t)memory;
 assert(address>=base && address+4<=base+sizeof(memory) && !(address%4));
 unsigned slot=(address-base)/sizeof(memory[0]);unsigned offset=(address-base)%sizeof(memory[0]);
 mmio_reads++;if(raw_view && (slot!=0 || !readable(offset)))bad_raw_reads++;
 u32 value;memcpy(&value,ptr,sizeof(value));return value;
}
static struct regulator *devm_regulator_get(struct device *dev,const char *name)
{(void)dev;assert(!strcmp(name,"vcc"));regulator_gets++;static struct regulator r;return &r;}
static struct clk *devm_clk_get_optional(struct device *dev,const char *name)
{(void)dev;assert(!strcmp(name,"core"));clock_gets++;static struct clk c;return &c;}
static void pm_runtime_enable(void *dev) {(void)dev;pm_enables++;}
static void pm_runtime_disable(void *dev) {(void)dev;pm_disables++;}
static int devm_add_action_or_reset(struct device *dev,void (*action)(void *),void *data)
{(void)dev;if(action_error)action(data);return action_error;}
static int qfprom_reg_write(void *priv,unsigned offset,void *val,size_t bytes)
{(void)priv;(void)offset;(void)val;(void)bytes;program_calls++;return -EIO;}
static int gpiod_set_value_cansleep(void *gpio,int value)
{(void)gpio;(void)value;program_calls++;return 0;}
static struct nvmem_device *devm_nvmem_register(struct device *,const struct nvmem_config *);
'''

MAIN = r'''
static unsigned cases,broken;
#define CHECK(c) do {cases++;if(!(c))broken++;} while(0)
static void setup(struct platform_device *p,bool raw,unsigned regions,size_t size)
{
 memset(p,0,sizeof(*p));memset(&registered,0,sizeof(registered));memset(&captured,0,sizeof(captured));
 raw_view=raw;p->count=regions;
 p->dev.match=raw?&msm8926_raw_qfprom:&sc7180_qfprom;
 for(unsigned i=0;i<4;i++)p->regions[i]=(struct resource){.start=0,.end=size-1,.slot=i};
 for(unsigned i=0;i<4;i++)for(unsigned j=0;j<2048;j++)memory[i][j]=0xa5b70000U+i*0x10000U+j;
 memory[3][0]=0x70080000;
 maps=clock_gets=regulator_gets=mmio_reads=bad_raw_reads=program_calls=0;
 pm_enables=pm_disables=registrations=0;mapping_error=action_error=registration_error=0;read_raw_data=false;
}
static void check_bytes(const unsigned char *buf,unsigned offset,unsigned count)
{
 bool same=true;
 for(unsigned i=0;i<count;i++) {
  const unsigned char *raw=(const unsigned char *)memory[0];
  unsigned char expected=readable(offset+i)?raw[offset+i]:0;
  if(buf[i]!=expected)same=false;
 }
 CHECK(same && !bad_raw_reads && !program_calls);
}
int main(void)
{
 struct platform_device p;unsigned char buf[0x2000];struct bin_attribute attr={0};
 for(unsigned raw_parameter=0;raw_parameter<2;raw_parameter++) {
  setup(&p,true,1,0x1000);p.dev.read_only=raw_parameter;
  CHECK(qfprom_probe(&p)==0 && registrations==1 && maps==1 && !clock_gets && !regulator_gets && !mmio_reads);
  CHECK(captured.read_only && captured.root_only && !captured.reg_write && !strcmp(captured.name,"qfprom-raw"));
  CHECK(registered.read_only && registered.root_only && nvmem_bin_attr_get_umode(&registered)==0400);
  read_raw_data=raw_parameter;struct kobject kobj={.dev=&registered.dev};
  const unsigned sizes[]={4,8,16,64};
  for(unsigned offset=0;offset<0x1000;offset+=4)for(unsigned s=0;s<4;s++) {
   unsigned count=sizes[s];if(offset+count>0x1000)continue;
   memset(buf,0xcc,sizeof(buf));
   ssize_t rc=bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,offset,count);
   CHECK(rc==count);check_bytes(buf,offset,count);
  }
  mmio_reads=bad_raw_reads=0;memset(buf,0xcc,sizeof(buf));
  CHECK(nvmem_device_read(&registered,0,0x1000,buf)==0x1000);
  check_bytes(buf,0,0x1000);CHECK(mmio_reads==6);
  for(unsigned offset=0;offset<0x1000;offset+=4)
   CHECK(bin_attr_nvmem_write(NULL,&kobj,&attr,(char *)buf,offset,4)==-EPERM && !program_calls);
  CHECK(bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,1,4)==-EINVAL);
  CHECK(bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,0xb0,3)==-EINVAL);
  CHECK(bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,0xb0,7)==4);
  CHECK(nvmem_device_write(&registered,0xb0,4,buf)==-EINVAL && !program_calls);
  registered.reg_read=NULL;CHECK(nvmem_device_read(&registered,0xb0,4,buf)==-EINVAL);
 }
 for(unsigned regions=2;regions<=4;regions+=2) {
  setup(&p,true,regions,0x1000);
  CHECK(qfprom_probe(&p)==-EINVAL && !maps && !registrations && !clock_gets && !regulator_gets);
 }
 setup(&p,true,0,0x1000);CHECK(qfprom_probe(&p)==-ENOENT && !registrations);
 setup(&p,true,1,0x2000);
 int ret=qfprom_probe(&p);
 /* Keepouts end at 0x1000; a wider registered view must be rejected. */
 CHECK(ret==-EINVAL && !registrations && !clock_gets && !regulator_gets);
 if(!ret) {
  unsigned before=bad_raw_reads;ret=nvmem_device_read(&registered,0x1000,4,buf);
  assert(ret==4 && bad_raw_reads==before+1); /* Demonstrates the earlier over-wide view. */
 }
 for(unsigned profile=0;profile<2;profile++) {
  setup(&p,false,profile?4:1,0x1000);CHECK(qfprom_probe(&p)==0 && registrations==1);
  CHECK(captured.reg_write==(profile?qfprom_reg_write:NULL));
  CHECK(clock_gets==profile && regulator_gets==profile && mmio_reads==profile && !program_calls);
  CHECK(!captured.root_only && !captured.read_only && registered.read_only==!profile);
 }
 setup(&p,true,1,0x1000);mapping_error=-EIO;CHECK(qfprom_probe(&p)==-EIO && !registrations);
 setup(&p,true,1,0x1000);action_error=-ENOMEM;CHECK(qfprom_probe(&p)==-ENOMEM && !registrations && pm_disables==1);
 setup(&p,true,1,0x1000);registration_error=-EIO;CHECK(qfprom_probe(&p)==-EIO);
 printf("cases=%u broken=%u\n",cases,broken);return broken?1:0;
}
'''


def build_fixture(driver, core):
    text = STUBS
    for name in ['QFPROM_VERSION_OFFSET', 'QFPROM_MAJOR_VERSION_SHIFT', 'QFPROM_MAJOR_VERSION_MASK',
                 'QFPROM_MINOR_VERSION_SHIFT', 'QFPROM_MINOR_VERSION_MASK']:
        line = re.search(r'^#define ' + name + r'\s+([^\n]+)', driver, re.M)
        assert line
        text += '\n#define ' + name + ' ' + line[1]
    text += '\n#define GENMASK(h,l) ((~0U << (l)) & (~0U >> (31-(h))))\n'
    start = driver.index('struct qfprom_soc_data {')
    end = driver.index('/**\n * qfprom_disable_fuse_blowing', start)
    text += driver[start:end]
    for name in ['qfprom_reg_read', 'qfprom_fixup_dt_cell_info', 'qfprom_runtime_disable']:
        text += '\n' + function(driver, name)
    start = driver.index('static const struct qfprom_soc_data qfprom_7_8_data')
    text += '\n' + driver[start:driver.index('static int qfprom_probe', start)]
    for name in ['__nvmem_reg_read', '__nvmem_reg_write', 'nvmem_access_with_keepouts', 'nvmem_reg_read',
                 'nvmem_reg_write', 'bin_attr_nvmem_read', 'bin_attr_nvmem_write',
                 'nvmem_bin_attr_get_umode', 'nvmem_validate_keepouts', 'nvmem_device_read', 'nvmem_device_write']:
        text += '\n' + function(core, name)
    text += '\nstatic struct nvmem_device *devm_nvmem_register(struct device *dev,const struct nvmem_config *config) {\n'
    text += ' (void)dev;captured=*config;if(registration_error)return ERR_PTR(registration_error);\n'
    text += ' struct nvmem_device *nvmem=&registered;\n'
    # These assignments execute verbatim, but the enclosing registration
    # machinery is mocked and must not be described as full core execution.
    for field in ['reg_read', 'reg_write']:
        statement = re.search(r'\tnvmem->' + field + r' = config->' + field + ';', core)
        assert statement
        text += statement[0] + '\n'
    for field in ['stride', 'word_size', 'size', 'root_only', 'priv', 'keepout', 'nkeepout']:
        statement = re.search(r'\tnvmem->' + field + r' = [^;]+;', core)
        assert statement
        text += statement[0] + '\n'
    statement = re.search(r'\tnvmem->read_only = device_property_present\([^;]+;', core)
    assert statement
    text += statement[0] + '\n'
    text += ' int ret=nvmem_validate_keepouts(nvmem);if(ret)return ERR_PTR(ret);registrations++;return nvmem;\n}\n'
    text += function(driver, 'qfprom_probe') + '\n' + MAIN
    return text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ['kernel', 'driver', 'output']:
        parser.add_argument('--' + name, required=True, type=Path)
    parser.add_argument('--expected-broken', required=True, type=int)
    args = parser.parse_args()
    args.output.mkdir(mode=0o700)
    core_path = args.kernel / 'drivers/nvmem/core.c'
    text = build_fixture(args.driver.read_text(), core_path.read_text())
    fixture, binary = args.output / 'fixture.c', args.output / 'fixture'
    fixture.write_text(text)
    build = subprocess.run(['clang-21', '-std=gnu11', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-const-variable', '-Wno-unused-parameter',
                            '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                            str(fixture), '-o', str(binary)], capture_output=True, timeout=60)
    (args.output / 'compile.stdout').write_bytes(build.stdout)
    (args.output / 'compile.stderr').write_bytes(build.stderr)
    assert build.returncode == 0 and not build.stderr
    run = subprocess.run([str(binary)], capture_output=True, timeout=60,
                         env=os.environ | {'ASAN_OPTIONS': 'detect_leaks=1:halt_on_error=1', 'UBSAN_OPTIONS': 'halt_on_error=1'})
    (args.output / 'run.stdout').write_bytes(run.stdout)
    (args.output / 'run.stderr').write_bytes(run.stderr)
    assert not run.stderr
    match = re.fullmatch(rb'cases=(\d+) broken=(\d+)\n', run.stdout)
    assert match and int(match[2]) == args.expected_broken and run.returncode == bool(args.expected_broken)
    record = dict(passed=True, cases=int(match[1]), broken=int(match[2]), expected_result_verified=True,
                  driver_SHA256=hashlib.sha256(args.driver.read_bytes()).hexdigest(),
                  NVMEM_core_SHA256=hashlib.sha256(core_path.read_bytes()).hexdigest(),
                  fixture_SHA256=hashlib.sha256(fixture.read_bytes()).hexdigest(),
                  actual_probe_read_keepout_sysfs_functions_and_registration_assignments_executed=True,
                  platform_resources_MMIO_SRCU_PM_and_full_registration_mocked=True,
                  physical_fuses_read_or_written=False, real_kernel_or_hardware_qualified=False)
    (args.output / 'qualification.json').write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record))


if __name__ == '__main__':
    main()
