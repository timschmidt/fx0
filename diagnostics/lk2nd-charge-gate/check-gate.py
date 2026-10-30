#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Execute the actual Fx0 gate hook with real libfdt and faulted SPMI."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('source', type=Path)
parser.add_argument('--dtb-in', type=Path)
parser.add_argument('--dtb-out', type=Path)
parser.add_argument('--apply', action='store_true', help='apply the real gate with fault-free fake PMIC instead of preparing a disabled-driver DTB')
args = parser.parse_args()
assert bool(args.dtb_in) == bool(args.dtb_out)
assert not args.dtb_out or not args.dtb_out.exists()
assert not args.apply or args.dtb_in
source = args.source.resolve()
boot_enum = re.search(r'enum boot_type \{.*?\n\};', (source/'app/aboot/boot.h').read_text(), re.S)[0]
stubs = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <libfdt.h>
#define BIT(n) (1U<<(n))
#define IS_ENABLED(x) 1
#define DEV_TREE_UPDATE(x)
static unsigned int operations,writes,fail_at;
static unsigned int fdt_operation,fdt_fail_at;
static bool after,persistent,allocation_failure;
static unsigned int drop_at,corrupt_at;
static uint8_t control,btc,pmic_type,pmic_subtype;
static uint32_t spmi_reg_read(uint32_t sid,uint16_t reg,uint8_t *value,uint8_t priority)
{
 assert(!sid && !priority);operations++;
 if(fail_at && (persistent?operations>=fail_at:operations==fail_at))return 2;
 assert(reg==0x104 || reg==0x105 || reg==0x1049 || reg==0x1249);
 *value=reg==0x104?pmic_type:reg==0x105?pmic_subtype:reg==0x1049?control:btc;
 if(operations==corrupt_at)*value^=0x80;
 return 0;
}
static uint32_t spmi_reg_write(uint32_t sid,uint16_t reg,uint8_t *value,uint8_t priority)
{
 assert(!sid && !priority && (reg==0x1049 || reg==0x1249));operations++;writes++;
 if(reg==0x1249)assert(!(control & 0x80));
 bool failed=fail_at && (persistent?operations>=fail_at:operations==fail_at);
 if((!failed || after) && operations!=drop_at) {
  if(reg==0x1049)control=*value;else btc=*value;
 }
 return failed?2:0;
}
extern int __real_fdt_setprop(void *,int,const char *,const void *,int);
extern int __real_fdt_open_into(const void *,void *,int);
int __wrap_fdt_setprop(void *dtb,int node,const char *name,const void *value,int length)
{if(++fdt_operation==fdt_fail_at)return -FDT_ERR_NOSPACE;return __real_fdt_setprop(dtb,node,name,value,length);}
int __wrap_fdt_open_into(const void *dtb,void *out,int size)
{if(++fdt_operation==fdt_fail_at)return -FDT_ERR_NOSPACE;return __real_fdt_open_into(dtb,out,size);}
static void *test_memalign(size_t alignment,size_t size)
{assert(alignment>=8);if(allocation_failure)return NULL;void *p=NULL;assert(!posix_memalign(&p,alignment,size));return p;}
#define memalign test_memalign
#include "IMPLEMENTATION"
#undef memalign
'''
tests = r'''
enum {SPACE=16384};
static unsigned char tree[SPACE],original[SPACE];
static unsigned int count;
static int node(const char *path) {int n=fdt_path_offset(tree,path);assert(n>=0);return n;}
static void checkpoint(void) {memcpy(original,tree,SPACE);fdt_operation=0;}
static void unchanged(void) {assert(!memcmp(original,tree,SPACE));}
static void fixture(bool enabled)
{
 operations=writes=fail_at=fdt_operation=fdt_fail_at=drop_at=corrupt_at=0;after=persistent=allocation_failure=false;
 control=0xd5;btc=0x82;pmic_type=0x51;pmic_subtype=4;
 assert(!fdt_create_empty_tree(tree,SPACE));assert(!fdt_setprop_string(tree,0,"compatible","lg,madai"));
 int p=fdt_add_subnode(tree,0,"pmic@0");assert(p>=0);
 assert(!fdt_setprop_string(tree,p,"compatible","qcom,pm8226"));
 fdt32_t reg[]={cpu_to_fdt32(0),cpu_to_fdt32(0)};assert(!fdt_setprop(tree,p,"reg",reg,sizeof(reg)));
 int c=fdt_add_subnode(tree,p,"charger@1000");assert(c>=0);
 assert(!fdt_setprop_string(tree,c,"compatible","qcom,pm8226-charger"));
 assert(!fdt_setprop_u32(tree,c,"reg",0x1000));
 if(enabled)assert(!fdt_setprop(tree,c,MADAI_CHARGE_CONTROL,NULL,0));
 checkpoint();
}
static bool marker(const void *dtb)
{int n=fdt_node_offset_by_compatible(dtb,-1,"qcom,pm8226-charger");assert(n>=0);int size;const void *p=fdt_getprop(dtb,n,MADAI_CHARGE_HANDOFF,&size);return p && !size;}
int main(int argc,char **argv)
{
 if(argc==3 || argc==4) {
  FILE *input=fopen(argv[1],"rb");assert(input);assert(!fseek(input,0,SEEK_END));long size=ftell(input);assert(size>0 && size<1024*1024);rewind(input);
  void *data=malloc(size+8192);assert(data);assert(fread(data,1,size,input)==(size_t)size);fclose(input);
  assert(!fdt_open_into(data,data,size+8192));int n=fdt_node_offset_by_compatible(data,-1,"qcom,pm8226-charger");assert(n>=0);
  if(argc==4) {
   assert(!strcmp(argv[3],"apply"));pmic_type=0x51;pmic_subtype=4;control=0x80;btc=0x82;
   assert(!madai_charge_gate_update_dt(data,"ignored",0));assert(marker(data) && control==0 && btc==0x81);
  } else {
   assert(!fdt_setprop(data,n,MADAI_CHARGE_CONTROL,NULL,0));
   /* Deliberately no native charger probe: qualify firmware's early interval. */
   assert(!fdt_setprop_string(data,n,"status","disabled"));assert(!marker(data));
  }
  assert(!fdt_pack(data));FILE *output=fopen(argv[2],"wb");assert(output);
  assert(fwrite(data,1,fdt_totalsize(data),output)==(size_t)fdt_totalsize(data));assert(!fclose(output));free(data);
  puts(argc==4?"Applied actual firmware gate with fake PMIC for schema fixture":"Prepared private opt-in/no-probe diagnostic DTB; no handoff marker forged");return 0;
 }
 assert(argc==1);
 for(unsigned int byte=0;byte<256;byte++) {
  fixture(true);control=btc=byte;assert(!madai_charge_gate_update_dt(tree,"ignored",0));
  assert(control==(byte & 0x7f) && operations==8 && writes==2 && marker(tree));
  assert(btc==((byte & ~0x83U) | 0x81));count++;
 }
 for(unsigned int at=1;at<=8;at++)for(int effect=0;effect<2;effect++) {
  fixture(true);fail_at=at;after=effect;
  assert(madai_charge_gate_update_dt(tree,"ignored",0)==-FDT_ERR_INTERNAL);unchanged();assert(!marker(tree));
  assert((control & 0x7f)==0x55);
  if(at>=3)assert(control==0x55);else assert(control==0xd5 && !writes);
  count++;
 }
 for(unsigned int at=1;at<=8;at++) {
  fixture(true);fail_at=at;persistent=true;
  assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);unchanged();assert(!marker(tree));
  assert(operations<=11);count++;
 }
 for(int target=0;target<2;target++)for(int mismatch=0;mismatch<2;mismatch++) {
  fixture(true);if(mismatch)corrupt_at=target?8:5;else drop_at=target?7:4;
  assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);unchanged();assert(control==0x55 && !marker(tree));count++;
 }
 for(unsigned int step=1;step<=2;step++) {
  fixture(true);fdt_fail_at=step;assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);
  unchanged();assert(!operations && control==0xd5);count++;
 }
 fixture(true);allocation_failure=true;assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);unchanged();assert(!operations);count++;
 for(int path=0;path<6;path++) {
  fixture(path!=0);unsigned int boot=0;
  if(path==1)boot=BOOT_DOWNSTREAM;
  if(path==2)boot=BOOT_LK2ND;
  if(path==3)assert(!fdt_setprop_string(tree,0,"compatible","other,board"));
  if(path==4)assert(!fdt_del_node(tree,node("/pmic@0/charger@1000")));
  if(path==5)assert(!fdt_delprop(tree,node("/pmic@0/charger@1000"),MADAI_CHARGE_CONTROL));
  checkpoint();assert(!madai_charge_gate_update_dt(tree,"ignored",boot));unchanged();assert(!operations);count++;
 }
 for(unsigned int bad=0;bad<10;bad++) {
  fixture(true);int c=node("/pmic@0/charger@1000"),p=node("/pmic@0");
  if(bad==0)assert(!fdt_setprop_u32(tree,c,MADAI_CHARGE_CONTROL,1));
  if(bad==1)assert(!fdt_setprop(tree,c,MADAI_CHARGE_HANDOFF,NULL,0));
  if(bad==2)assert(!fdt_setprop_u32(tree,c,"reg",0x2000));
  if(bad==3)assert(!fdt_delprop(tree,c,"reg"));
  if(bad==4)assert(!fdt_setprop_string(tree,p,"compatible","other,pmic"));
  if(bad==5)assert(!fdt_setprop_u32(tree,p,"reg",0));
  if(bad==6 || bad==7) {fdt32_t reg[]={cpu_to_fdt32(bad==6?1:0),cpu_to_fdt32(bad==7?1:0)};assert(!fdt_setprop(tree,p,"reg",reg,sizeof(reg)));}
  if(bad==8 || bad==9) {
   int second=fdt_add_subnode(tree,p,"charger@2000");assert(second>=0);
   assert(!fdt_setprop_string(tree,second,"compatible","qcom,pm8226-charger"));
   if(bad==9)assert(!fdt_setprop(tree,second,MADAI_CHARGE_CONTROL,NULL,0));
  }
  checkpoint();assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);unchanged();assert(!operations);count++;
 }
 for(int identity=0;identity<2;identity++) {
  fixture(true);if(identity)pmic_type=0;else pmic_subtype=1;
  assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);unchanged();assert(!writes);count++;
 }
 fixture(true);assert(!fdt_setprop_string(tree,node("/pmic@0/charger@1000"),"status","disabled"));
 assert(!madai_charge_gate_update_dt(tree,"ignored",0));assert(marker(tree) && control==0x55);count++;
 fixture(true);tree[0]^=0xff;checkpoint();assert(madai_charge_gate_update_dt(tree,"ignored",0)<0);unchanged();assert(!operations);count++;
 printf("PASS: %u actual gate/FDT/SPMI/rollback cases under ASan/UBSan\n",count);
}
'''
with tempfile.TemporaryDirectory(prefix='fx0-charge-gate-') as directory:
    root = Path(directory)
    (root/'boot.h').write_text(boot_enum)
    (root/'debug.h').write_text('#define dprintf(...) ((void)0)\n')
    (root/'pm8x41.h').write_text('')
    path = root/'check.c'
    path.write_text(stubs.replace('IMPLEMENTATION', str(source/'lk2nd/device/2nd/gpl/lg-madai-charge-gate.c'))+tests)
    binary = root/'check'
    subprocess.run(['clang', '-std=gnu11', '-Wall', '-Wextra', '-Werror', '-Wno-unused-but-set-variable',
                    '-fsanitize=address,undefined', '-fno-sanitize-recover=all', '-I', str(root),
                    str(path), '-lfdt', '-Wl,--wrap=fdt_setprop', '-Wl,--wrap=fdt_open_into',
                    '-o', str(binary)], check=True)
    subprocess.run([str(binary), *([str(args.dtb_in), str(args.dtb_out), *(['apply'] if args.apply else [])] if args.dtb_in else [])], check=True)
