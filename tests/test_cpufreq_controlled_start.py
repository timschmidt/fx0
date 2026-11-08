"""Execute default-governor selection and actual userspace target suppression."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
KERNEL=Path(os.environ.get('FX0_KERNEL_SOURCE',ROOT/'worktrees/linux-fx0-cpr-observe'))
spec=importlib.util.spec_from_file_location('extract',ROOT/'tests/test_cpr_runtime_clock.py')
EXTRACT=importlib.util.module_from_spec(spec);spec.loader.exec_module(EXTRACT)
HARNESS=r'''
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define CPUFREQ_NEED_UPDATE_LIMITS 1
#define CPUFREQ_NEED_INITIAL_FREQ_CHECK 2
#define CPUFREQ_IS_COOLING_DEV 4
#define CPUFREQ_RELATION_L 0
#define CPUFREQ_RELATION_H 1
#define CPUFREQ_RELATION_E 2
#define CPUFREQ_POLICY_UNKNOWN 0
#define CPUFREQ_POLICY_PERFORMANCE 1
#define CPUFREQ_POLICY_POWERSAVE 2
#define ENODEV 19
#define EINVAL 22
#define ENOMEM 12
#define ENODATA 61
#define GFP_KERNEL 0
#define BUG_ON(x) CHECK(!(x))
#define pr_debug(...) debug(__VA_ARGS__)
struct userspace_policy {unsigned int is_managed,setspeed;int mutex;};
struct cpufreq_governor {void *owner;int id;const char *name;};
struct cpufreq_policy {
 unsigned int cur,min,max,cpu,cached_resolved_idx;bool efficiencies_available;
 char last_governor[16];unsigned int last_policy,policy;
 void *governor_data;struct cpufreq_governor *governor;
};
struct cpufreq_driver {
 unsigned int flags;
 int (*target)(struct cpufreq_policy *,unsigned int,unsigned int);
 int (*target_index)(struct cpufreq_policy *,unsigned int);
};
static struct cpufreq_driver driver,*cpufreq_driver=&driver;
static struct cpufreq_governor userspace_gov={.id=1,.name="userspace"},schedutil_gov={.id=2,.name="schedutil"};
static bool userspace_registered;static char default_governor[16];
static int target_calls,governor_refs;static unsigned int last_target;
static void debug(const char *fmt,...){(void)fmt;}
static void mutex_lock(int *lock){CHECK(lock);}
static void mutex_unlock(int *lock){CHECK(lock);}
static void mutex_init(int *lock){*lock=0;}
static void *kzalloc(size_t size,int flags){CHECK(flags==0);return calloc(1,size);}
static void kfree(void *p){free(p);}
static int cpufreq_disabled(void){return 0;}
static unsigned int __resolve_freq(struct cpufreq_policy *p,unsigned int f,unsigned int min,unsigned int max,unsigned int relation){
 (void)relation;f=f<min?min:f>max?max:f;
 CHECK(f==300000 || f==384000 || f==1190400);p->cached_resolved_idx=f==300000?0:f==384000?1:6;return f;
}
static int __target_index(struct cpufreq_policy *p,unsigned int index){
 target_calls++;last_target=index==0?300000:index==1?384000:1190400;p->cur=last_target;return 0;
}
static int has_target(void){return 1;}
static struct cpufreq_governor *get_governor(const char *name){
 if(!strcmp(name,"userspace") && userspace_registered){governor_refs++;return &userspace_gov;}
 if(!strcmp(name,"schedutil")){governor_refs++;return &schedutil_gov;}
 return NULL;
}
static struct cpufreq_governor *cpufreq_default_governor(void){return &schedutil_gov;}
static void __module_get(void *owner){(void)owner;governor_refs++;}
static void module_put(void *owner){(void)owner;governor_refs--;}
static unsigned int cpufreq_parse_policy(const char *name){(void)name;return CPUFREQ_POLICY_UNKNOWN;}
static int cpufreq_set_policy(struct cpufreq_policy *,struct cpufreq_governor *,unsigned int);
'''
MAIN=r'''
static int cpufreq_set_policy(struct cpufreq_policy *p,struct cpufreq_governor *gov,unsigned int pol){
 (void)pol;p->governor=gov;
 if(gov==&userspace_gov){
  int ret=cpufreq_userspace_policy_init(p);if(ret)return ret;
  ret=cpufreq_userspace_policy_start(p);if(ret)return ret;
  cpufreq_userspace_policy_limits(p);return 0;
 }
 CHECK(gov==&schedutil_gov);
 /* Model an immediate schedutil demand after falling back to that governor. */
 return __cpufreq_driver_target(p,p->max,CPUFREQ_RELATION_L);
}
int main(void){
 struct cpufreq_policy p={.cur=300000,.min=300000,.max=1190400};
 driver.flags=ACTUAL_DT_FLAGS;driver.target_index=__target_index;
 CHECK(!(driver.flags&CPUFREQ_NEED_UPDATE_LIMITS));
 strcpy(default_governor,"userspace");userspace_registered=true;
 CHECK(!cpufreq_init_policy(&p) && !governor_refs && p.governor==&userspace_gov);
 CHECK(!target_calls && p.cur==300000);
 p.max=384000;cpufreq_userspace_policy_limits(&p);CHECK(!target_calls && p.cur==300000);
 CHECK(!cpufreq_set(&p,384000) && target_calls==1 && last_target==384000);
 CHECK(!cpufreq_set(&p,300000) && target_calls==2 && last_target==300000);
 /* If the driver flags change, identical-frequency targets are no longer skipped. */
 driver.flags|=CPUFREQ_NEED_UPDATE_LIMITS;target_calls=0;
 cpufreq_userspace_policy_limits(&p);CHECK(target_calls==1 && last_target==300000);
 driver.flags=ACTUAL_DT_FLAGS;cpufreq_userspace_policy_exit(&p);
 /* The configured boot name alone is insufficient when the module is absent. */
 p=(struct cpufreq_policy){.cur=300000,.min=300000,.max=1190400};target_calls=0;userspace_registered=false;
 CHECK(!cpufreq_init_policy(&p) && p.governor==&schedutil_gov && target_calls==1 && last_target==1190400);
 /* A loaded userspace module cannot protect a boot that still asks for schedutil. */
 p=(struct cpufreq_policy){.cur=300000,.min=300000,.max=1190400};target_calls=0;userspace_registered=true;strcpy(default_governor,"schedutil");
 CHECK(!cpufreq_init_policy(&p) && p.governor==&schedutil_gov && target_calls==1 && last_target==1190400);
 puts("actual default selection, userspace start/limits and same-rate skip passed; missing module/default/flag controls expose the unsafe path; explicit 300-384 targets passed");
 return 0;
}
'''
class ControlledStartTests(unittest.TestCase):
 def test_actual_governor_and_target_functions(self):
  core=(KERNEL/'drivers/cpufreq/cpufreq.c').read_text();user=(KERNEL/'drivers/cpufreq/cpufreq_userspace.c').read_text();dt=(KERNEL/'drivers/cpufreq/cpufreq-dt.c').read_text()
  flags=' '.join(re.search(r'static struct cpufreq_driver dt_cpufreq_driver = \{\s*\.flags = (.*?),',dt,re.S)[1].split())
  target=EXTRACT.function(core[core.index('\nint __cpufreq_driver_target('):],'__cpufreq_driver_target(')
  policy=EXTRACT.function(core[core.index('static int cpufreq_init_policy('):],'cpufreq_init_policy(')
  functions=target+''.join(EXTRACT.function(user,name) for name in ['cpufreq_set(', 'cpufreq_userspace_policy_init(', 'cpufreq_userspace_policy_exit(', 'cpufreq_userspace_policy_start(', 'cpufreq_userspace_policy_limits('])+policy
  with tempfile.TemporaryDirectory() as directory:
   base=Path(directory);source=base/'test.c';binary=base/'test'
   source.write_text(HARNESS+'\n#define ACTUAL_DT_FLAGS ('+flags+')\n'+functions+MAIN)
   result=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror',str(source),'-o',str(binary)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
   result=subprocess.run([str(binary)],capture_output=True,text=True);self.assertEqual(result.returncode,0,result.stderr)
   self.assertIn('explicit 300-384 targets passed',result.stdout)
if __name__=='__main__':unittest.main()
