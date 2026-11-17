# SPDX-License-Identifier: GPL-2.0-only
"""Exercise the production first-generation torch sequences with host regmap faults."""
from pathlib import Path
import argparse, hashlib, json, re, subprocess, sys
if sys.flags.optimize:
    raise RuntimeError('Assertions must remain enabled')
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--source',required=True,type=Path)
p.add_argument('--output',required=True,type=Path)
p.add_argument('--expect',required=True,choices=['broken','fixed'])
a=p.parse_args();a.output.mkdir(mode=0o700)
source=(a.source/'drivers/leds/flash/leds-qcom-flash-v1.c').read_text()
definitions='\n'.join(re.findall(r'^#define[^\n]+',source,re.M))
struct=re.search(r'struct qcom_flash_v1 \{.*?\n\};',source,re.S)[0]
functions=[]
for name in ['torch_mode','off','on','brightness_set']:
    match=re.search(r'static int qcom_flash_v1_'+name+r'\(.*?\n\}',source,re.S)
    assert match,name
    functions.append(match[0])
prefix=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
typedef uint32_t u32;
#define BIT(n) (1u << (n))
#define GENMASK(h,l) (((~0u) << (l)) & ((~0u) >> (31-(h))))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
enum led_brightness { LED_OFF=0, LED_FULL=255 };
struct led_classdev { unsigned max_brightness; };
struct regmap { int unused; };
struct regulator { unsigned enabled; };
struct mutex { pthread_mutex_t actual; };
static unsigned regs[256], operation, failures[2], disable_calls;
static bool initialized;
static void mutex_lock(struct mutex *m) { assert(!pthread_mutex_lock(&m->actual)); }
static void mutex_unlock(struct mutex *m) { assert(!pthread_mutex_unlock(&m->actual)); }
static bool fail(void) { operation++; return operation==failures[0] || operation==failures[1]; }
static int regmap_write(struct regmap *m,unsigned addr,unsigned val)
{
    (void)m; assert(addr>=0x100 && addr<0x200); assert(val<=255);
    if (fail()) return -EIO;
    regs[addr-0x100]=val; return 0;
}
static int regmap_update_bits(struct regmap *m,unsigned addr,unsigned mask,unsigned val)
{
    (void)m; assert(addr>=0x100 && addr<0x200); assert(!(val & ~mask));
    if (fail()) return -EIO;
    regs[addr-0x100]=(regs[addr-0x100]&~mask)|val; return 0;
}
static int regulator_enable(struct regulator *r)
{
    if (fail()) return -EIO;
    assert(!r->enabled); r->enabled++; return 0;
}
static int regulator_disable(struct regulator *r)
{
    disable_calls++;
    if (fail()) return -EIO;
    assert(r->enabled==1); r->enabled--; return 0;
}
static void usleep_range(unsigned lo,unsigned hi) { assert(lo==2200 && hi==2500); }
'''
suffix=r'''
static struct regmap map;
static struct regulator supply;
static struct qcom_flash_v1 flash;
static void reset(bool on,bool with_vin,unsigned f1,unsigned f2)
{
    if (initialized) assert(!pthread_mutex_destroy(&flash.lock.actual));
    memset(&flash,0,sizeof(flash)); memset(regs,0,sizeof(regs));
    assert(!pthread_mutex_init(&flash.lock.actual,NULL)); initialized=true;
    flash.regmap=&map; flash.vin=with_vin?&supply:NULL; flash.base=0x100;
    flash.vin_on=on&&with_vin; supply.enabled=flash.vin_on;
    regs[FLASH_ENABLE_CTRL]=on?FLASH_ENABLE_ALL:0;
    regs[FLASH_STROBE_CTRL]=on?FLASH_STROBE_TORCH:0;
    regs[FLASH_TORCH]=on?FLASH_TORCH_ENABLE:FLASH_TORCH_DISABLE;
    failures[0]=f1;failures[1]=f2;operation=disable_calls=0;
}
static void *toggle(void *arg)
{
    (void)arg;
    for (unsigned i=0;i<100;i++) {
        assert(!qcom_flash_v1_brightness_set(&flash.cdev,16));
        assert(!qcom_flash_v1_brightness_set(&flash.cdev,0));
    }
    return NULL;
}
int main(void)
{
    unsigned off_correct=0,off_wrong=0,on_controls=0,levels=0;
    for (unsigned failed=1;failed<=5;failed++) {
        reset(true,true,failed,0);
        int ret=qcom_flash_v1_brightness_set(&flash.cdev,0);
        bool okay=ret==-EIO && disable_calls==1;
        if (failed!=4) okay &= regs[FLASH_ENABLE_CTRL]==0;
        if (failed==5) okay &= flash.vin_on && supply.enabled==1;
        else okay &= !flash.vin_on && supply.enabled==0;
        if (okay) off_correct++; else off_wrong++;
        if (!EXPECT_BROKEN) {
            assert(okay);
            failures[0]=failures[1]=0;
            assert(!qcom_flash_v1_brightness_set(&flash.cdev,0));
            assert(!flash.vin_on && !supply.enabled && !regs[FLASH_ENABLE_CTRL]);
        }
    }
    for (unsigned failed=1;failed<=8;failed++) {
        reset(false,true,failed,0);
        assert(qcom_flash_v1_brightness_set(&flash.cdev,16)==-EIO);
        assert(!regs[FLASH_ENABLE_CTRL] && !regs[FLASH_STROBE_CTRL] && !flash.vin_on && !supply.enabled);
        on_controls++;
    }
    reset(false,true,8,9);
    assert(qcom_flash_v1_brightness_set(&flash.cdev,16)==-EIO);
    bool double_okay=!regs[FLASH_ENABLE_CTRL] && !flash.vin_on && !supply.enabled;
    if (!EXPECT_BROKEN) assert(double_okay);
    for (unsigned vin=0;vin<=1;vin++) for (unsigned level=1;level<=16;level++) {
        reset(false,vin,0,0);
        assert(!qcom_flash_v1_brightness_set(&flash.cdev,level));
        assert(regs[FLASH_LED0_CURR]==level-1 && regs[FLASH_LED1_CURR]==level-1);
        assert(regs[FLASH_ENABLE_CTRL]==FLASH_ENABLE_ALL && regs[FLASH_STROBE_CTRL]==FLASH_STROBE_TORCH);
        assert(!qcom_flash_v1_brightness_set(&flash.cdev,0));
        assert(!regs[FLASH_ENABLE_CTRL] && !regs[FLASH_STROBE_CTRL] && regs[FLASH_TORCH]==FLASH_TORCH_DISABLE);
        assert(!flash.vin_on && !supply.enabled); levels++;
    }
    reset(false,true,0,0);pthread_t one,two;
    assert(!pthread_create(&one,NULL,toggle,NULL));assert(!pthread_create(&two,NULL,toggle,NULL));
    assert(!pthread_join(one,NULL));assert(!pthread_join(two,NULL));
    assert(!regs[FLASH_ENABLE_CTRL] && !regs[FLASH_STROBE_CTRL] && !supply.enabled && !flash.vin_on);
    assert(!pthread_mutex_destroy(&flash.lock.actual));initialized=false;
    if (EXPECT_BROKEN) assert(off_wrong==5 && !double_okay);
    else assert(off_correct==5 && !off_wrong && double_okay);
    printf("{\"off_error_cases\":5,\"off_correct\":%u,\"off_wrong\":%u,\"on_error_controls\":%u,\"combined_on_cleanup_fault_correct\":%s,\"healthy_level_cases\":%u,\"concurrent_callback_transactions\":400}\n",off_correct,off_wrong,on_controls,double_okay?"true":"false",levels);
    return 0;
}
'''
body=prefix+definitions+'\n'+struct+'\n'+'\n'.join(functions)+suffix
c=a.output/'torch-errors.c';c.write_text(body)
command=['clang-21','-std=gnu11','-Wall','-Wextra','-Werror','-g','-O1','-fsanitize=address,undefined','-fno-omit-frame-pointer','-pthread','-DEXPECT_BROKEN='+str(int(a.expect=='broken')),str(c),'-o',str(a.output/'torch-errors')]
record=dict(source_SHA256=hashlib.sha256(source.encode()).hexdigest(),fixture_SHA256=hashlib.sha256(body.encode()).hexdigest(),extracted_function_SHA256={name:hashlib.sha256(code.encode()).hexdigest() for name,code in zip(['torch_mode','off','on','brightness_set'],functions)},expect=a.expect,host_interfaces_emulated=True,hardware_qualified=False)
for name,cmd in [('compile',command),('execute',[str(a.output/'torch-errors')])]:
    result=subprocess.run(cmd,capture_output=True,timeout=60)
    (a.output/(name+'.stdout')).write_bytes(result.stdout);(a.output/(name+'.stderr')).write_bytes(result.stderr)
    record[name+'_returncode']=result.returncode;(a.output/'controller.json').write_text(json.dumps(record,indent=2)+'\n')
    assert result.returncode==0 and not result.stderr,(name,result.returncode)
record.update(passed=True,result=json.loads(result.stdout));(a.output/'controller.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(record['result']))
