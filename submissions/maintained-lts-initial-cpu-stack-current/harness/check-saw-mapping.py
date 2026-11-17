# SPDX-License-Identifier: GPL-2.0-only
"""Execute the real SAW map acquisition helper with synthetic OF/MMIO services."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('source', type=Path)
p.add_argument('output', type=Path)
p.add_argument('--mutation', choices=['all-shared', 'no-defer', 'drop-map-error', 'legacy-spinlock'])
a = p.parse_args()
assert not a.output.exists()
a.output.mkdir(mode=0o700)
text = a.source.read_text()
match = re.search(r'static struct regmap \*spmi_regulator_get_saw_regmap\([^;{}]*\)\s*\{', text)
assert match
start = text.index('{', match.start());end = start + 1;depth = 1
while depth:
    depth += (text[end] == '{') - (text[end] == '}');end += 1
helper = text[match.start():end];original = helper
cfg = re.search(r'static const struct regmap_config saw_regmap_config\s*=\s*\{.*?\n\};', text, re.S).group(0)
if a.mutation == 'all-shared':
    condition = 'if (of_device_is_compatible(saw, "qcom,msm8226-saw2-v2.1-l2") &&\n\t    of_property_read_bool(saw, "qcom,pmic-arbiter-master"))'
    assert condition in helper
    helper = helper.replace(condition, 'if (true)')
if a.mutation == 'no-defer':
    old = 'PTR_ERR_OR_ZERO(map) == -EINVAL ? ERR_PTR(-EPROBE_DEFER) : map'
    assert old in helper
    helper = helper.replace(old, 'map')
if a.mutation == 'drop-map-error':
    assert 'return ERR_CAST(base);' in helper
    helper = helper.replace('return ERR_CAST(base);', 'return NULL;')
if a.mutation == 'legacy-spinlock':
    assert '.use_raw_spinlock = true' in cfg
    cfg = cfg.replace('.use_raw_spinlock = true', '.use_raw_spinlock = false')
head = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#define __iomem
#define UNUSED __attribute__((unused))
#define EINVAL 22
#define EIO 5
#define ENOMEM 12
#define EBUSY 16
#define ENOSYS 38
#define ENOENT 2
#define EPROBE_DEFER 517
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define PTR_ERR_OR_ZERO(p) (IS_ERR(p)?PTR_ERR(p):0)
#define ERR_CAST(p) ((void *)(p))
static int checks,failures,cases;
#define CHECK(x) do{checks++;if(!(x)){failures++;if(failures<9)fprintf(stderr,"line%d: %s\n",__LINE__,#x);}}while(0)
struct regmap_config {const char *name;unsigned int reg_bits,val_bits,reg_stride;bool use_raw_spinlock;};
struct device_node {int references;};
struct device {struct device_node *of_node;int id;};
struct regmap {int id;};
static struct device_node parents[2],saw;
static struct device devices[2]={{&parents[0],0},{&parents[1],1}};
static struct regmap private_maps[2]={{1},{2}},published_map={3};
static int registers[2],present,compatible,master,lookup_error,iomap_error,regmap_error;
static int parses,node_puts,lookups,iomaps,regmaps,property_calls,compatible_calls;
static struct device *current;
'''
services = r'''
static struct device_node *of_parse_phandle(struct device_node *parent,const char *name,int index){CHECK(parent==current->of_node&&!strcmp(name,"qcom,saw-reg")&&!index);parses++;if(!present)return NULL;saw.references++;return &saw;}
static bool UNUSED of_device_is_compatible(struct device_node *node,const char *name){CHECK(node==&saw&&saw.references==1&&!strcmp(name,"qcom,msm8226-saw2-v2.1-l2"));compatible_calls++;return compatible;}
static bool UNUSED of_property_read_bool(struct device_node *node,const char *name){CHECK(node==&saw&&saw.references==1&&!strcmp(name,"qcom,pmic-arbiter-master"));property_calls++;return master;}
static void of_node_put(struct device_node *node){CHECK(node==&saw&&saw.references==1);node_puts++;saw.references--;}
static struct regmap *syscon_node_to_regmap(struct device_node *node){CHECK(node==&saw&&saw.references==1);lookups++;return lookup_error?ERR_PTR(lookup_error):&published_map;}
static void *devm_of_iomap(struct device *dev,struct device_node *node,int index,void *size){CHECK(dev==current&&node==&saw&&saw.references==1&&!index&&!size);iomaps++;return iomap_error?ERR_PTR(iomap_error):&registers[dev->id];}
static struct regmap *devm_regmap_init_mmio(struct device *dev,void *base,const struct regmap_config *cfg){CHECK(dev==current&&base==&registers[dev->id]&&saw.references==0&&cfg==&saw_regmap_config);CHECK(cfg->reg_bits==32&&cfg->val_bits==32&&cfg->reg_stride==4);CHECK(cfg->use_raw_spinlock);regmaps++;return regmap_error?ERR_PTR(regmap_error):&private_maps[dev->id];}
static void reset(int id){present=1;compatible=master=lookup_error=iomap_error=regmap_error=0;parses=node_puts=lookups=iomaps=regmaps=property_calls=compatible_calls=0;saw.references=0;current=&devices[id];}
static void balanced(int expected_puts){CHECK(parses==1&&node_puts==expected_puts&&saw.references==0);}
'''
main = r'''
int main(void){
 struct regmap *map,*first;int errors[]={-EINVAL,-EIO,-ENOMEM,-ENOSYS,-EPROBE_DEFER,-ENOENT};
 for(int id=0;id<2;id++){
  reset(id);present=0;CHECK(!spmi_regulator_get_saw_regmap(current));balanced(0);CHECK(!lookups&&!iomaps&&!regmaps);cases++;
  for(int flags=0;flags<3;flags++){
   reset(id);compatible=flags&1;master=(flags>>1)&1;
   map=spmi_regulator_get_saw_regmap(current);CHECK(map==&private_maps[id]);balanced(1);
   CHECK(iomaps==1&&regmaps==1&&!lookups);CHECK(compatible_calls==1&&property_calls==compatible);cases++;
  }
  for(int error=-1;error<6;error++){
   reset(id);compatible=master=1;lookup_error=error<0?0:errors[error];
   map=spmi_regulator_get_saw_regmap(current);
   if(lookup_error)CHECK(IS_ERR(map)&&PTR_ERR(map)==(lookup_error==-EINVAL?-EPROBE_DEFER:lookup_error));else CHECK(map==&published_map);
   balanced(1);CHECK(lookups==1&&!iomaps&&!regmaps);cases++;
  }
  for(int stage=0;stage<2;stage++)for(int error=0;error<6;error++){
   reset(id);if(stage)regmap_error=errors[error];else iomap_error=errors[error];
   map=spmi_regulator_get_saw_regmap(current);CHECK(IS_ERR(map)&&PTR_ERR(map)==errors[error]);
   balanced(1);CHECK(!lookups&&iomaps==1&&regmaps==stage);cases++;
  }
 }
 /* A second device cannot replace the first device's private mapping. */
 reset(0);first=spmi_regulator_get_saw_regmap(current);reset(1);map=spmi_regulator_get_saw_regmap(current);
 CHECK(first==&private_maps[0]&&map==&private_maps[1]&&first!=map);cases++;
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":%d}\n",cases,checks,failures);
 return failures?1:0;
}
'''
program = head + cfg + '\n' + services + '\n' + helper + '\n' + main
(a.output / 'model.c').write_text(program)
r = subprocess.run(['clang-21','-std=gnu11','-Wall','-Wextra','-Werror',
    '-fsanitize=address,undefined','-fno-omit-frame-pointer','-g',str(a.output/'model.c'),'-o',str(a.output/'model')],
    capture_output=True,text=True,timeout=120)
(a.output/'compile.log').write_text(r.stdout+r.stderr)
assert r.returncode==0,r.stderr[-3000:]
r=subprocess.run([str((a.output/'model').resolve())],capture_output=True,text=True,timeout=120)
(a.output/'stdout').write_text(r.stdout);(a.output/'stderr').write_text(r.stderr)
j=json.loads(r.stdout);diagnostics=any(s in r.stderr for s in ['AddressSanitizer','LeakSanitizer','runtime error:'])
report=dict(**j,returncode=r.returncode,mutation=a.mutation,sanitizer_diagnostics=diagnostics,
            actual_helper_SHA256=hashlib.sha256(original.encode()).hexdigest(),
            actual_raw_map_config_SHA256=hashlib.sha256(re.search(r'static const struct regmap_config saw_regmap_config\s*=\s*\{.*?\n\};',text,re.S).group(0).encode()).hexdigest(),
            program_SHA256=hashlib.sha256(program.encode()).hexdigest(),
            OF_mapping_services_synthetic=True,physical_provider_acceptance=False)
(a.output/'qualification.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
assert not diagnostics and r.returncode==(1 if j['failures'] else 0)
