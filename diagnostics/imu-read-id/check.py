#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Exercise real DT gating and fixed ID messages; not a PAS/lifecycle simulation."""
from pathlib import Path
import resource
import subprocess
import tempfile

resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
source = Path(__file__).with_name('fx0_imu_read_id.c').read_text()

def function(name):
    start = source.index('static int '+name+'(')
    brace = source.index('{', start)
    end, depth = brace+1, 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]

stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
typedef uint8_t u8;
struct resource {unsigned long start;};
struct device_node {bool enabled;unsigned long address;int error;};
static struct device_node adsp,buses[4];
static bool board,have_adsp;
static unsigned int bus_count;
static bool of_machine_is_compatible(const char *name)
{assert(!strcmp(name,"lg,madai"));return board;}
static struct device_node *of_find_compatible_node(void *a,void *b,const char *c)
{assert(!a && !b && !strcmp(c,"qcom,msm8226-adsp-pil"));return have_adsp?&adsp:NULL;}
static bool of_device_is_available(struct device_node *n) {return n->enabled;}
static void of_node_put(struct device_node *n) {assert(n);}
static int of_address_to_resource(struct device_node *n,int index,struct resource *r)
{assert(index==0);r->start=n->address;return n->error;}
static struct device_node *first_node(const char *c)
{assert(!strcmp(c,"qcom,i2c-qup-v2.1.1"));return bus_count?buses:NULL;}
static struct device_node *next_node(struct device_node *n)
{return (unsigned int)(n-buses)+1<bus_count?n+1:NULL;}
#define for_each_compatible_node(n,t,c) for(n=first_node(c);n;n=next_node(n))
struct i2c_adapter {int unused;};
struct i2c_msg {unsigned short addr,flags,len;u8 *buf;};
#define I2C_M_RD 1
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define pr_info(...) ((void)0)
static unsigned int calls,sleeps;
static int results[3];
static u8 ids[3];
static int i2c_transfer(struct i2c_adapter *a,struct i2c_msg *m,int count)
{
 assert(a && count==2 && calls<3);
 assert(m[0].addr==0x68 && !m[0].flags && m[0].len==1 && m[0].buf[0]==0x75);
 assert(m[1].addr==0x68 && m[1].flags==I2C_M_RD && m[1].len==1);
 *m[1].buf=ids[calls];return results[calls++];
}
static void usleep_range(unsigned int min,unsigned int max)
{assert(min==1000 && max==2000);sleeps++;}
static void reset(void)
{
 board=have_adsp=true;adsp=(struct device_node){0};bus_count=1;
 memset(buses,0,sizeof(buses));buses[0].address=0xf9924000;
 calls=sleeps=0;for(unsigned int i=0;i<3;i++){results[i]=2;ids[i]=0x74;}
}
'''
tests = r'''
int main(void)
{
 unsigned int cases=0;struct i2c_adapter adapter={0};
 reset();assert(!require_disabled_paths());cases++;
 reset();board=false;assert(require_disabled_paths()==-ENODEV);cases++;
 reset();have_adsp=false;assert(require_disabled_paths()==-ENODEV);cases++;
 reset();adsp.enabled=true;assert(require_disabled_paths()==-EBUSY);cases++;
 reset();bus_count=0;assert(require_disabled_paths()==-ENODEV);cases++;
 reset();buses[0].enabled=true;assert(require_disabled_paths()==-EBUSY);cases++;
 reset();buses[0].address=0xf9927000;assert(require_disabled_paths()==-ENODEV);cases++;
 reset();buses[0].error=-EINVAL;assert(require_disabled_paths()==-ENODEV);cases++;
 reset();bus_count=2;buses[1]=buses[0];assert(require_disabled_paths()==-ENODEV);cases++;
 reset();bus_count=2;buses[1]=(struct device_node){.enabled=true,.address=0xf9927000};
 assert(!require_disabled_paths());cases++;
 reset();assert(!read_identities(&adapter) && calls==3 && sleeps==3);cases++;
 const int errors[]={-ETIMEDOUT,-ENXIO,-EAGAIN,0,1,3,INT_MAX};
 for(unsigned int at=0;at<3;at++)for(unsigned int err=0;err<ARRAY_SIZE(errors);err++) {
  reset();results[at]=errors[err];
  assert(read_identities(&adapter)==(errors[err]<0?errors[err]:-EIO));
  assert(calls==at+1 && sleeps==at);cases++;
 }
 for(unsigned int at=0;at<3;at++)for(unsigned int id=0;id<256;id++) {
  reset();ids[at]=id;int ret=read_identities(&adapter);
  assert(ret==(id==0x74?0:-ENODEV));
  assert(calls==(id==0x74?3:at+1));cases++;
 }
 printf("PASS: %u real DT-gate/fixed-register/partial/error/identity cases ASan/UBSan\n",cases);
}
'''
with tempfile.TemporaryDirectory(prefix='fx0-imu-id-') as directory:
    path = Path(directory)
    code = stubs+'\n'.join(function(name) for name in ['require_disabled_paths', 'read_identity', 'read_identities'])+tests
    (path/'check.c').write_text(code)
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-sign-compare',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all',
                    str(path/'check.c'), '-o', str(path/'check')], check=True)
    subprocess.run([str(path/'check')], check=True, timeout=10)
