"""Run actual L2 initialization and publication code against faulted regmap I/O."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
KERNEL = Path(os.environ.get('FX0_KERNEL_SOURCE', ROOT/'worktrees/linux-fx0-cpr'))
HEADER = Path(os.environ.get('FX0_SPM_L2_HEADER', KERNEL/'drivers/soc/qcom/spm-msm8226-l2.h'))
HARNESS = r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "spm-msm8226-l2.h"
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static int access_ok(unsigned int address,bool write);
static unsigned int registers[1024];
static struct regmap controller;
struct operation {unsigned int address,value;bool write;};
static struct operation operations[100];
static int n,writes,fail_at,drop_at,side_effect,flip_control,flip_avs;
static unsigned int expected_registers[]={8,0x34,0x40,0x44};
static unsigned int expected_values[]={EXPECTED_CFG,EXPECTED_DLY,EXPECTED_DATA0,EXPECTED_DATA1};
int regmap_read(struct regmap *map,unsigned int address,unsigned int *value){
 CHECK(map==&controller&&n<100&&access_ok(address,false));operations[n++]=(struct operation){address,0,false};
 if(n==fail_at)return -EIO;
 *value=registers[address/4];
 if(registers[8/4]==EXPECTED_CFG){
  if(address==0x30&&flip_control)*value=1;
  if(address==0x20&&flip_avs)*value=1;
 }
 return 0;
}
int regmap_write(struct regmap *map,unsigned int address,unsigned int value){
 CHECK(map==&controller&&n<100&&access_ok(address,true));operations[n++]=(struct operation){address,value,true};
 /* Initialization must never issue voltage, reset, AVS or sequencer commands. */
 CHECK(address==8||address==0x34||address==0x40||address==0x44);
 if(address==8)CHECK(registers[0x34/4]==EXPECTED_DLY&&registers[0x40/4]==EXPECTED_DATA0&&registers[0x44/4]==EXPECTED_DATA1);
 if(n==fail_at&&!side_effect)return -EIO;
 if(n!=drop_at){registers[address/4]=value;writes++;}
 return n==fail_at?-EIO:0;
}

struct device_node {int placeholder;};
struct device {struct device_node *of_node;};
struct platform_device {struct device dev;};
struct resource {unsigned long size;};
struct spm_driver_data {void *reg_base;};
struct regmap_range {unsigned int range_min,range_max;};
struct regmap_access_table {const struct regmap_range *yes_ranges;unsigned int n_yes_ranges;};
struct regmap_config {const char *name;unsigned int reg_bits,val_bits,reg_stride,max_register;bool fast_io;const struct regmap_access_table *rd_table,*wr_table;};
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define regmap_reg_range(min,max) {(min),(max)}
/* ACTUAL_REGISTER_ACCESS_TABLES */
static int access_ok(unsigned int address,bool write){
 const struct regmap_access_table *table=write?spm_8226_l2_regmap_config.wr_table:spm_8226_l2_regmap_config.rd_table;
 if(address>spm_8226_l2_regmap_config.max_register||address%spm_8226_l2_regmap_config.reg_stride)return 0;
 for(unsigned int i=0;i<table->n_yes_ranges;i++)if(address>=table->yes_ranges[i].range_min&&address<=table->yes_ranges[i].range_max)return 1;
 return 0;
}
static struct device_node node;
static struct platform_device pdev={{&node}};
static struct resource resource={4096};
static struct spm_driver_data driver;
static int master_flag,is_module,is_syscon,missing_resource,map_error,lookup_error,registry_error;
static int lookups,map_calls,publication_calls,published;
#define IS_MODULE(x) is_module
#define IS_ERR(p) ((long)(p)<0)
#define PTR_ERR(p) ((int)(long)(p))
#define ERR_PTR(e) ((void *)(long)(e))
#define IORESOURCE_MEM 1
#define resource_size(r) ((r)->size)
#define dev_err_probe(dev,ret,fmt,args...) (ret)
static int of_property_read_bool(struct device_node *np,const char *property){CHECK(np==&node&&!strcmp(property,"qcom,pmic-arbiter-master"));return master_flag;}
static int of_device_is_compatible(struct device_node *np,const char *name){CHECK(np==&node&&!strcmp(name,"syscon"));return is_syscon;}
static struct resource *platform_get_resource(struct platform_device *dev,int type,int index){CHECK(dev==&pdev&&type==IORESOURCE_MEM&&!index);return missing_resource?NULL:&resource;}
static struct regmap *syscon_node_to_regmap(struct device_node *np){CHECK(np==&node);lookups++;return published?&controller:ERR_PTR(lookup_error?lookup_error:-EINVAL);}
static struct regmap *devm_regmap_init_mmio(struct device *dev,void *base,const struct regmap_config *config){CHECK(dev==&pdev.dev&&base==driver.reg_base&&config==&spm_8226_l2_regmap_config);map_calls++;return map_error?ERR_PTR(map_error):&controller;}
static int of_syscon_register_regmap(struct device_node *np,struct regmap *map){
 CHECK(np==&node&&map==&controller&&!published);publication_calls++;
 for(int i=0;i<4;i++)CHECK(registers[expected_registers[i]/4]==expected_values[i]);
 CHECK(!registers[0x30/4]&&!registers[0x20/4]);
 if(registry_error)return registry_error;
 published=1;return 0;
}

/* ACTUAL_REGISTRATION_FUNCTION */

static void clear_trace(void){n=writes=fail_at=drop_at=side_effect=flip_control=flip_avs=0;lookups=map_calls=publication_calls=0;}
static void reset(void){
 memset(registers,0,sizeof(registers));clear_trace();
 master_flag=1;is_module=is_syscon=missing_resource=map_error=lookup_error=registry_error=published=0;
 resource.size=4096;registers[0xfd0/4]=0x20010000;registers[4/4]=4;
 registers[0x1c/4]=0x73;registers[0x14/4]=0x73; /* preserved voltage state */
}
static void check_preserved(void){CHECK(registers[0x1c/4]==0x73&&registers[0x14/4]==0x73&&!registers[0x30/4]&&!registers[0x20/4]);}
int main(void){
 int total,write_positions[4],count=0;
 for(unsigned int address=0;address<4096;address++){
  bool read=address==4||address==8||address==0x14||address==0x1c||address==0x20||address==0x30||address==0x34||address==0x40||address==0x44||address==0xfd0;
  bool write=address==8||address==0x18||address==0x1c||address==0x34||address==0x40||address==0x44;
  CHECK(access_ok(address,false)==read&&access_ok(address,true)==write);
 }
 reset();CHECK(!spm_8226_l2_register(&pdev,&driver));CHECK(published&&publication_calls==1&&writes==4);total=n;
 for(int i=0;i<n;i++)if(operations[i].write)write_positions[count++]=i+1;
 CHECK(count==4&&operations[write_positions[3]-1].address==8);check_preserved();
 /* Existing complete setup is adopted without touching hardware. */
 published=0;clear_trace();CHECK(!spm_8226_l2_register(&pdev,&driver)&&published&&!writes);check_preserved();
 /* Every register I/O error prevents publication; all partial setups retry. */
 for(int fault=1;fault<=total;fault++){
  reset();fail_at=fault;CHECK(spm_8226_l2_register(&pdev,&driver)==-EIO&&!published&&!publication_calls);check_preserved();
  clear_trace();CHECK(!spm_8226_l2_register(&pdev,&driver)&&published);check_preserved();
 }
 for(int i=0;i<4;i++){
  reset();fail_at=write_positions[i];side_effect=1;
  CHECK(spm_8226_l2_register(&pdev,&driver)==-EIO&&!published);check_preserved();
  clear_trace();CHECK(!spm_8226_l2_register(&pdev,&driver)&&published);check_preserved();
  reset();drop_at=write_positions[i];CHECK(spm_8226_l2_register(&pdev,&driver)==-EIO&&!published);
  CHECK(!registers[8/4]);clear_trace();CHECK(!spm_8226_l2_register(&pdev,&driver)&&published);check_preserved();
 }
 /* All known disabled partial states are repairable; enabled partials are not. */
 for(unsigned int mask=0;mask<8;mask++){
  reset();int filled=0;
  for(int i=1;i<4;i++)if(mask&(1U<<(i-1))){registers[expected_registers[i]/4]=expected_values[i];filled++;}
  CHECK(!spm_8226_l2_register(&pdev,&driver)&&writes==4-filled);check_preserved();
 }
 reset();registers[8/4]=EXPECTED_CFG;CHECK(spm_8226_l2_register(&pdev,&driver)==-EOPNOTSUPP&&!writes&&!published);
 reset();registers[0x40/4]=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EOPNOTSUPP&&!writes&&!published);
 reset();registers[0xfd0/4]=0x30000000;CHECK(spm_8226_l2_register(&pdev,&driver)==-ENODEV&&!writes&&!published);
 reset();registers[4/4]=0;CHECK(spm_8226_l2_register(&pdev,&driver)==-ENODEV&&!writes&&!published);
 reset();registers[0x20/4]=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EBUSY&&!writes&&!published);
 reset();registers[0x30/4]=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EBUSY&&!writes&&!published);
 reset();flip_control=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EBUSY&&!published);
 reset();flip_avs=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EBUSY&&!published);
 /* Publication/resource/lifetime preconditions do not touch controller state. */
 reset();master_flag=0;CHECK(spm_8226_l2_register(&pdev,&driver)==-ENODEV&&!n);
 reset();is_module=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EOPNOTSUPP&&!n);
 reset();missing_resource=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EINVAL&&!n);
 reset();resource.size=0x100;CHECK(spm_8226_l2_register(&pdev,&driver)==-EINVAL&&!n);
 reset();is_syscon=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EINVAL&&!n&&!lookups);
 reset();published=1;CHECK(spm_8226_l2_register(&pdev,&driver)==-EEXIST&&!n&&!map_calls);
 reset();lookup_error=-EIO;CHECK(spm_8226_l2_register(&pdev,&driver)==-EIO&&!n&&!map_calls);
 reset();map_error=-ENOMEM;CHECK(spm_8226_l2_register(&pdev,&driver)==-ENOMEM&&!n);
 reset();registry_error=-ENOMEM;CHECK(spm_8226_l2_register(&pdev,&driver)==-ENOMEM&&!published);
 clear_trace();registry_error=0;CHECK(!spm_8226_l2_register(&pdev,&driver)&&published&&!writes);check_preserved();
 printf("%d I/O failure points, partial retries, publication and no-voltage-write contracts passed\n",total);
 return 0;
}
'''


@unittest.skipUnless(HEADER.exists(), 'Candidate L2 master helper required')
class SpmL2Tests(unittest.TestCase):
    def test_actual_owner_and_publication(self):
        source=(HEADER.parent/'spm.c').read_text()
        match=re.search(r'static int spm_8226_l2_register\s*\(',source)
        self.assertIsNotNone(match)
        start=source.index('{',match.start());depth=1;end=start+1
        while depth:
            depth+=(source[end]=='{')-(source[end]=='}');end+=1
        registration=source[match.start():end]
        tables=source[source.index('static const struct regmap_range spm_8226_l2_read_ranges'):match.start()]
        params=json.loads((ROOT/'manifests/msm8226-l2-master.json').read_text())['parameters']
        defines=''.join(f'#define EXPECTED_{name} {params[prop][0]}U\n' for name,prop in [('CFG','qcom,saw2-cfg'),('DLY','qcom,saw2-spm-dly'),('DATA0','qcom,saw2-pmic-data0'),('DATA1','qcom,saw2-pmic-data1')])
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary);(base/'linux').mkdir()
            (base/'linux/regmap.h').write_text('#pragma once\n#include <stdbool.h>\nstruct regmap {int placeholder;};\nint regmap_read(struct regmap*,unsigned int,unsigned int*);\nint regmap_write(struct regmap*,unsigned int,unsigned int);\n')
            (base/'linux/errno.h').write_text('#define EIO 5\n#define ENOMEM 12\n#define EBUSY 16\n#define EEXIST 17\n#define ENODEV 19\n#define EINVAL 22\n#define EOPNOTSUPP 95\n')
            (base/'spm-msm8226-l2.h').write_bytes(HEADER.read_bytes())
            (base/'test.c').write_text(defines+HARNESS.replace('/* ACTUAL_REGISTRATION_FUNCTION */',registration).replace('/* ACTUAL_REGISTER_ACCESS_TABLES */',tables))
            result=subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-I',str(base),str(base/'test.c'),'-o',str(base/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(base/'test')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn('18 I/O failure points',result.stdout)


if __name__ == '__main__':
    unittest.main()
