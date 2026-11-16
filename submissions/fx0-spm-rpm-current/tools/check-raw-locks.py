# SPDX-License-Identifier: GPL-2.0-only
"""Execute actual regmap lock selection/callbacks with the two SAW configs."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('spm', type=Path)
p.add_argument('regulator', type=Path)
p.add_argument('core', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--pmic', type=Path)
p.add_argument('--mutation', choices=['ignore-raw', 'disable-owner-locking'])
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir(mode=0o700)
spm, regulator, core = (f.read_text() for f in [a.spm, a.regulator, a.core])
def config(text, name):
    match = re.search(r'static const struct regmap_config ' + name + r'\s*=\s*\{.*?\n\};', text, re.S)
    assert match, name
    return match.group(0)
owner = config(spm, 'spm_8226_l2_regmap_config')
legacy = config(regulator, 'saw_regmap_config')
pmic = config(a.pmic.read_text(), 'spmi_regmap_config') if a.pmic else ''
callbacks = core[core.index('static void regmap_lock_hwlock('):core.index('static void dev_get_regmap_release(')]
selection = core[core.index('\tif (config->disable_locking) {'):core.index('\n\t/*\n\t * When we write in fast-paths')]
original_selection = selection
if a.mutation == 'ignore-raw':
    assert selection.count('if (config->use_raw_spinlock)') == 1
    selection = selection.replace('if (config->use_raw_spinlock)', 'if (false)')
if a.mutation == 'disable-owner-locking':
    owner = owner.replace('.name =', '.disable_locking = true,\n\t.name =', 1)
prefix = r'''
#include <stdbool.h>
#include <stdint.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
static int checks, failures, cases;
#define CHECK(x) do { checks++; if (!(x)) { failures++; if(failures<9)fprintf(stderr,"line%d: %s\n",__LINE__,#x); } } while(0)
#define ENXIO 6
#define HWLOCK_IRQSTATE 2
#define HWLOCK_IRQ 1
#define __acquires(x)
#define __releases(x)
struct lock { int initialized; };
struct regmap {
 void (*lock)(void *), (*unlock)(void *); void *lock_arg, *lock_key;
 bool can_sleep; struct lock raw_spinlock,spinlock,mutex;
 unsigned long raw_spinlock_flags,spinlock_flags; void *hwlock;
};
struct regmap_config {
 const char *name; unsigned int reg_bits,val_bits,reg_stride,max_register;
 bool fast_io,use_raw_spinlock,disable_locking,can_sleep,use_hwlock;
 void (*lock)(void *),(*unlock)(void *); void *lock_arg;
 unsigned int hwlock_id,hwlock_mode; const void *rd_table,*wr_table;
};
struct regmap_bus { bool fast_io; };
static const int spm_8226_l2_read_table,spm_8226_l2_write_table;
static int rt,in_ipi,invalid_wait,raw_locks,raw_unlocks,spin_locks,spin_unlocks,mutex_locks,mutex_unlocks;
static int hw_locks,hw_unlocks,custom_locks,custom_unlocks,no_hw;
#define raw_spin_lock_init(p) ((p)->initialized=1)
#define spin_lock_init(p) ((p)->initialized=1)
#define mutex_init(p) ((p)->initialized=1)
#define lockdep_set_class_and_name(p,key,name) do{CHECK((p)->initialized);(void)(key);(void)(name);}while(0)
#define raw_spin_lock_irqsave(p,flags) do{CHECK((p)->initialized);raw_locks++;flags=0x34;}while(0)
#define raw_spin_unlock_irqrestore(p,flags) do{CHECK((p)->initialized);CHECK((flags)==0x34);raw_unlocks++;}while(0)
#define spin_lock_irqsave(p,flags) do{CHECK((p)->initialized);spin_locks++;invalid_wait+=rt&&in_ipi;flags=0x12;}while(0)
#define spin_unlock_irqrestore(p,flags) do{CHECK((p)->initialized);CHECK((flags)==0x12);spin_unlocks++;}while(0)
static void mutex_lock(struct lock *p){CHECK(p->initialized);mutex_locks++;invalid_wait+=in_ipi;}
static void mutex_unlock(struct lock *p){CHECK(p->initialized);mutex_unlocks++;}
static void regmap_debugfs_disable(struct regmap *p){CHECK(p!=NULL);}
static void *hwspin_lock_request_specific(unsigned int id){CHECK(id==3);return no_hw?NULL:(void *)(uintptr_t)3;}
#define hwspin_lock_timeout(p,t) do{CHECK((p)!=NULL&&(t)==UINT_MAX);hw_locks++;}while(0)
#define hwspin_lock_timeout_irq(p,t) hwspin_lock_timeout(p,t)
#define hwspin_lock_timeout_irqsave(p,t,flags) do{hwspin_lock_timeout(p,t);*(flags)=0x12;}while(0)
#define hwspin_unlock(p) do{CHECK((p)!=NULL);hw_unlocks++;}while(0)
#define hwspin_unlock_irq(p) hwspin_unlock(p)
#define hwspin_unlock_irqrestore(p,flags) do{CHECK(*(flags)==0x12);hwspin_unlock(p);}while(0)
'''
wrapper = '''\nstatic int select_lock(struct regmap *map, const struct regmap_config *config,
                       const struct regmap_bus *bus)
{
 int ret=0; void *lock_key=NULL; const char *lock_name="actual-regmap";
''' + selection + '''
 return 0;
err_name:
 return ret;
}
'''
main = r'''
static void clear_trace(void){invalid_wait=raw_locks=raw_unlocks=spin_locks=spin_unlocks=mutex_locks=mutex_unlocks=hw_locks=hw_unlocks=custom_locks=custom_unlocks=no_hw=0;}
static void custom_lock(void *p){CHECK(p==(void *)(uintptr_t)9);custom_locks++;}
static void custom_unlock(void *p){CHECK(p==(void *)(uintptr_t)9);custom_unlocks++;}
int main(void){
 struct regmap_bus mmio={true},slow={false};struct regmap map;
 const struct regmap_config *saw_configs[]={&spm_8226_l2_regmap_config,&saw_regmap_config /* PMIC_CONFIG_ENTRY */};
 for(unsigned int config_index=0;config_index<sizeof(saw_configs)/sizeof(saw_configs[0]);config_index++)for(rt=0;rt<2;rt++)for(in_ipi=0;in_ipi<2;in_ipi++){
  memset(&map,0,sizeof(map));clear_trace();
  CHECK(!select_lock(&map,saw_configs[config_index],config_index==2?&slow:&mmio));
  CHECK(!map.can_sleep&&map.lock_arg==&map);
  CHECK(map.lock==regmap_lock_raw_spinlock&&map.unlock==regmap_unlock_raw_spinlock);
  map.lock(map.lock_arg);map.unlock(map.lock_arg);
  CHECK(raw_locks==1&&raw_unlocks==1&&!spin_locks&&!mutex_locks);
  CHECK(!invalid_wait);cases++;
 }
 /* Independent controls exercise every generic decision route used above. */
 rt=1;in_ipi=0;struct regmap_config c={0};
 memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,NULL));CHECK(map.can_sleep&&map.lock==regmap_lock_mutex);
 map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(mutex_locks==1&&mutex_unlocks==1);cases++;
 c.fast_io=true;memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&slow));CHECK(!map.can_sleep&&map.lock==regmap_lock_spinlock);
 in_ipi=1;map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(invalid_wait==1&&spin_locks==1&&spin_unlocks==1);cases++;
 c.disable_locking=true;memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&mmio));CHECK(map.lock==regmap_lock_unlock_none);map.lock(&map);map.unlock(&map);CHECK(!raw_locks&&!spin_locks&&!mutex_locks);cases++;
 c=(struct regmap_config){.lock=custom_lock,.unlock=custom_unlock,.lock_arg=(void *)(uintptr_t)9};
 memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&mmio));CHECK(map.lock==custom_lock&&map.lock_arg==c.lock_arg);map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(custom_locks==1&&custom_unlocks==1);cases++;
 for(unsigned int mode=0;mode<3;mode++){
  c=(struct regmap_config){.use_hwlock=true,.hwlock_id=3,.hwlock_mode=mode};
  memset(&map,0,sizeof(map));clear_trace();CHECK(!select_lock(&map,&c,&mmio));map.lock(map.lock_arg);map.unlock(map.lock_arg);CHECK(hw_locks==1&&hw_unlocks==1);cases++;
 }
 memset(&map,0,sizeof(map));clear_trace();no_hw=1;CHECK(select_lock(&map,&c,&mmio)==-ENXIO);CHECK(!map.lock&&!map.unlock);cases++;
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);
 return failures?1:0;
}
'''
main = main.replace('/* PMIC_CONFIG_ENTRY */', ',&spmi_regmap_config' if a.pmic else '')
program = prefix + owner + '\n' + legacy + '\n' + pmic + '\n' + callbacks + wrapper + main
(a.output / 'model.c').write_text(program)
command = ['clang-21', '-std=gnu11', '-Wall', '-Werror', '-fsanitize=address,undefined',
           '-fno-omit-frame-pointer', '-g', str(a.output / 'model.c'), '-o', str(a.output / 'model')]
r = subprocess.run(command, capture_output=True, text=True, timeout=120)
(a.output / 'compile.log').write_text(r.stdout + r.stderr)
assert r.returncode == 0, r.stderr[-3000:]
r = subprocess.run([str((a.output / 'model').resolve())], capture_output=True, text=True, timeout=120)
(a.output / 'stdout').write_text(r.stdout)
(a.output / 'stderr').write_text(r.stderr)
result = json.loads(r.stdout)
diagnostics = any(s in r.stderr for s in ['AddressSanitizer', 'LeakSanitizer', 'runtime error:'])
report = dict(**result, returncode=r.returncode, sanitizer_diagnostics=diagnostics,
              mutation=a.mutation, actual_core_callbacks=True, actual_lock_selection=True,
              lock_services_and_RT_context_synthetic=True, physical_RT_acceptance=False,
              program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
              actual_core_callbacks_SHA256=hashlib.sha256(callbacks.encode()).hexdigest(),
              actual_core_selection_SHA256=hashlib.sha256(original_selection.encode()).hexdigest(),
              actual_SPM_config_SHA256=hashlib.sha256(config(spm, 'spm_8226_l2_regmap_config').encode()).hexdigest(),
              actual_regulator_config_SHA256=hashlib.sha256(config(regulator, 'saw_regmap_config').encode()).hexdigest())
if a.pmic:
    report['actual_PMIC_config_SHA256'] = hashlib.sha256(pmic.encode()).hexdigest()
(a.output / 'qualification.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
assert not diagnostics and r.returncode == (1 if result['failures'] else 0)
