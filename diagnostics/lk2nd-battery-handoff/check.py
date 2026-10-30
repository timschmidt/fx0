#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Run the actual firmware battery selector and transactional real-libfdt hook."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("lk2nd", type=Path)
parser.add_argument("--vendor", type=Path)
parser.add_argument("--dtb-in", type=Path)
parser.add_argument("--dtb-out", type=Path)
parser.add_argument("--expect-unaligned-failure", action="store_true")
args = parser.parse_args()
assert bool(args.dtb_in) == bool(args.dtb_out)
if args.dtb_out:
    assert not args.dtb_out.exists(), "Keep generated DT artifacts immutable"
source = args.lk2nd.resolve() / "lk2nd/device/2nd/gpl/lg-madai-battery.c"
if args.vendor:
    vendor = (args.vendor / "arch/arm/mach-msm/lge/bms-batterydata-LGE_BL_59UH_2440mAh_TOCAD_MADAI_Final.c").read_text()
    vendor = vendor[vendor.index("static struct pc_temp_ocv_lut"):]
    data = source.with_name("lg-madai-battery-data.h").read_text()
    values = [int(x) for x in re.findall(r"\d+", re.search(r"madai_ocv_mv\[31\]\[5\] = \{(.*?)\n\};", data, re.S).group(1))]
    original = [int(x) for x in re.findall(r"\d+", re.search(r"\.ocv\s*=\s*\{(.*?)\n\s*\}\s*\n\};", vendor, re.S).group(1))]
    assert len(values) == 155 and values == original
    for old, new in (("temp", "madai_ocv_temperatures"), ("percent", "madai_ocv_percent")):
        original = [int(x) for x in re.findall(r"-?\d+", re.search(r"\." + old + r"\s*=\s*\{([^}]+)\}", vendor).group(1))]
        values = [int(x) for x in re.findall(r"-?\d+", re.search(new + r"\[\d+\] = \{(.*?)\};", data, re.S).group(1))]
        assert values == original
    print("PASS: all 155 vendor OCV values, five temperatures and 31 percentages match")

boot_header = (args.lk2nd / "app/aboot/boot.h").read_text()
boot_enum = re.search(r"enum boot_type \{.*?\n\};", boot_header, re.S).group()
stubs = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <libfdt.h>
#include <malloc.h>
#define BIT(n) (1U<<(n))
#define CRITICAL 0
#define INFO 1
#define dprintf(...) ((void)0)
#define DEV_TREE_UPDATE(handler)
#define WITH_LK2ND_DEVICE_2ND 1
#define WITH_LK2ND 1
#define IS_ENABLED(option) (option)
#include "SOURCE_DEVICE_HEADER"
#undef LK2ND_DEVICE_INIT
#define LK2ND_DEVICE_INIT(compatible,handler)
struct lk2nd_device lk2nd_dev;
static int operation,fail_at;
static bool allocation_failure;
static void *unaligned_base,*unaligned_pointer;
extern int __real_fdt_setprop(void *,int,const char *,const void *,int);
extern int __real_fdt_add_subnode(void *,int,const char *);
extern int __real_fdt_open_into(const void *,void *,int);
static bool inject(void) {return ++operation==fail_at;}
int __wrap_fdt_setprop(void *fdt,int node,const char *name,const void *value,int length) {
 if(inject())return -FDT_ERR_NOSPACE;return __real_fdt_setprop(fdt,node,name,value,length);
}
int __wrap_fdt_add_subnode(void *fdt,int parent,const char *name) {
 if(inject())return -FDT_ERR_NOSPACE;return __real_fdt_add_subnode(fdt,parent,name);
}
int __wrap_fdt_open_into(const void *fdt,void *copy,int size) {
 if(inject())return -FDT_ERR_NOSPACE;return __real_fdt_open_into(fdt,copy,size);
}
static __attribute__((unused)) void *test_malloc(size_t size) {
 if(allocation_failure)return NULL;
 assert(!unaligned_base);unaligned_base=malloc(size+16);assert(unaligned_base);
 unaligned_pointer=(void *)(((uintptr_t)unaligned_base+7U)&~(uintptr_t)7U);
 unaligned_pointer=(char *)unaligned_pointer+4;assert(((uintptr_t)unaligned_pointer&7)==4);
 return unaligned_pointer;
}
static __attribute__((unused)) void *test_memalign(size_t alignment,size_t size) {
 assert(alignment>=8);if(allocation_failure)return NULL;
 void *pointer=NULL;assert(posix_memalign(&pointer,alignment,size)==0);
 assert(((uintptr_t)pointer&7)==0);return pointer;
}
static void test_free(void *pointer) {
 if(pointer && pointer==unaligned_pointer) {
  free(unaligned_base);unaligned_base=NULL;unaligned_pointer=NULL;
 } else free(pointer);
}
#define malloc test_malloc
#define memalign test_memalign
#define free test_free
#include "SOURCE_IMPLEMENTATION"
#undef malloc
#undef memalign
#undef free
'''
main = r'''
enum {CAPACITY=16384};
static unsigned char original[CAPACITY],tree[CAPACITY];
static int node(const char *path) {int n=fdt_path_offset(tree,path);assert(n>=0);return n;}
static uint32_t property(int n,const char *name) {
 int length;const fdt32_t *p=fdt_getprop(tree,n,name,&length);assert(p && length==4);return fdt32_to_cpu(*p);
}
static void fixture(bool bms) {
 fail_at=0;allocation_failure=false;operation=0;memset(tree,0,sizeof(tree));
 assert(fdt_create_empty_tree(tree,sizeof(tree))==0);
 assert(fdt_setprop_string(tree,0,"compatible","lg,madai")==0);
 int pmic=fdt_add_subnode(tree,0,"pmic");assert(pmic>=0);
 int n=fdt_add_subnode(tree,pmic,"charger@1000");assert(n>=0);
 assert(fdt_setprop_string(tree,n,"compatible","qcom,pm8226-charger")==0);
 assert(fdt_setprop_u32(tree,n,"phandle",40)==0);
 if(bms) {
  n=fdt_add_subnode(tree,pmic,"battery@4000");assert(n>=0);
  assert(fdt_setprop_string(tree,n,"compatible","qcom,pm8226-bms")==0);
 }
 lk2nd_dev.cmdline="other=x lge.battid=ISL6296_L unrelated=y";
 assert(madai_battery_detect(NULL,0)==0 && madai_known_battery);
 memcpy(original,tree,sizeof(tree));operation=0;
}
static void unchanged(void) {assert(memcmp(tree,original,sizeof(tree))==0);}
static void verify(bool bms) {
 int battery=node("/battery"),length;uint32_t phandle=fdt_get_phandle(tree,battery);
 assert(phandle>40 && property(node("/pmic/charger@1000"),"monitored-battery")==phandle);
 if(bms)assert(property(node("/pmic/battery@4000"),"monitored-battery")==phandle);
 assert(property(battery,"charge-full-design-microamp-hours")==2370000);
 assert(property(battery,"constant-charge-voltage-max-microvolt")==4350000);
 assert(property(battery,"voltage-min-design-microvolt")==3400000);
 assert(fdt_node_check_compatible(tree,battery,"simple-battery")==0);
 assert(!strcmp(fdt_getprop(tree,battery,"device-chemistry",NULL),"lithium-ion"));
 const fdt32_t *temps=fdt_getprop(tree,battery,"ocv-capacity-celsius",&length);assert(temps && length==20);
 for(int column=0;column<5;column++) {
  assert((int32_t)fdt32_to_cpu(temps[column])==madai_ocv_temperatures[column]);
  char name[32];snprintf(name,sizeof(name),"ocv-capacity-table-%d",column);
  const fdt32_t *table=fdt_getprop(tree,battery,name,&length);assert(table && length==31*8);
  for(int row=0;row<31;row++) {
   assert(fdt32_to_cpu(table[2*row])==(uint32_t)madai_ocv_mv[row][column]*1000);
   assert(fdt32_to_cpu(table[2*row+1])==madai_ocv_percent[row]);
  }
 }
 assert(!fdt_getprop(tree,battery,"operating-range-celsius",NULL));
 assert(!fdt_getprop(tree,battery,"constant-charge-current-max-microamp",NULL));
}
int main(int argc,char **argv) {
 if(argc==3) {
  FILE *input=fopen(argv[1],"rb");assert(input);
  assert(fseek(input,0,SEEK_END)==0);long length=ftell(input);assert(length>0 && length<1024*1024);
  rewind(input);void *image=malloc(length+8192);assert(image);
  assert(fread(image,1,length,input)==(size_t)length);fclose(input);
  assert(fdt_open_into(image,image,length+8192)==0);
  lk2nd_dev.cmdline="lge.battid=ISL6296_L";assert(madai_battery_detect(NULL,0)==0);
  assert(madai_battery_update_dt(image,"ignored",0)==0);
  assert(fdt_path_offset(image,"/battery")>=0);assert(fdt_pack(image)==0);
  FILE *output=fopen(argv[2],"wb");assert(output);
  assert(fwrite(image,1,fdt_totalsize(image),output)==(size_t)fdt_totalsize(image));
  assert(fclose(output)==0);free(image);puts("Generated private DTB using actual firmware hook");return 0;
 }
 assert(argc==1);
 if(EXPECT_UNALIGNED_FAILURE) {
  fixture(true);int ret=madai_battery_update_dt(tree,"ignored",0);
  assert(ret==-FDT_ERR_ALIGNMENT);unchanged();assert(!unaligned_base);
  puts("REPRODUCED: actual original helper rejects valid DT with four-byte-aligned LK allocation");return 0;
 }
 unsigned count=0;
 const char *bad[]={NULL,"","lge.battid=","lge.battid","lge.battid=ISL6296",
 "lge.battid=ISL6296_L_extra","lge.battid=ISL6296_C","lge.battid=ISL6296_N",
 "lge.battid=DS2704_L","xlge.battid=ISL6296_L","lge.battid=ISL6296_Lx",
 "lge.battid=ISL6296_L lge.battid=ISL6296_L","lge.battid=unknown lge.battid=ISL6296_L",
 "lge.battid=ISL6296_L lge.battid=unknown","lge.battid=ISL6296_L\tother=x"};
 for(unsigned i=0;i<sizeof(bad)/sizeof(bad[0]);i++) {assert(!madai_stock_battery(bad[i]));count++;}
 const char *good[]={"lge.battid=ISL6296_L"," lge.battid=ISL6296_L ","x=1  lge.battid=ISL6296_L  y=2"};
 for(unsigned i=0;i<sizeof(good)/sizeof(good[0]);i++) {assert(madai_stock_battery(good[i]));count++;}
 fixture(true);lk2nd_dev.cmdline="lge.battid=unknown";
 assert(madai_battery_detect(NULL,0)==0 && !madai_known_battery && !lk2nd_dev.battery);count++;
 for(int bms=0;bms<2;bms++) {
  fixture(bms);assert(madai_battery_update_dt(tree,"ignored",0)==0);verify(bms);count++;
  int operations=operation;
  for(int fail=1;fail<=operations;fail++) {
   fixture(bms);fail_at=fail;assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
  }
  fixture(bms);allocation_failure=true;assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
  fixture(bms);assert(madai_battery_update_dt(tree,"ignored",BOOT_DOWNSTREAM)==0);unchanged();count++;
  fixture(bms);assert(madai_battery_update_dt(tree,"ignored",BOOT_LK2ND)==0);unchanged();count++;
  fixture(bms);madai_known_battery=false;assert(madai_battery_update_dt(tree,"ignored",0)==0);unchanged();count++;
  fixture(bms);assert(fdt_setprop_string(tree,0,"compatible","other,board")==0);
  memcpy(original,tree,sizeof(tree));assert(madai_battery_update_dt(tree,"ignored",0)==0);unchanged();count++;
  fixture(bms);assert(madai_battery_update_dt(tree,"ignored",0)==0);memcpy(original,tree,sizeof(tree));
  assert(madai_battery_update_dt(tree,"ignored",0)==-FDT_ERR_EXISTS);unchanged();count++;
  fixture(bms);assert(fdt_setprop_u32(tree,node("/pmic/charger@1000"),"monitored-battery",40)==0);
  memcpy(original,tree,sizeof(tree));assert(madai_battery_update_dt(tree,"ignored",0)==-FDT_ERR_EXISTS);unchanged();count++;
 }
 for(int capacity=512;capacity<=4096;capacity+=64) {
  fixture(true);assert(fdt_pack(tree)==0);int used=fdt_totalsize(tree);
  if(capacity<used)continue;
  assert(fdt_open_into(tree,tree,capacity)==0);memcpy(original,tree,sizeof(tree));
  int ret=madai_battery_update_dt(tree,"ignored",0);
  if(ret)unchanged();else verify(true);count++;
 }
 fixture(true);tree[0]^=0xff;memcpy(original,tree,sizeof(tree));
 assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
 fixture(true);assert(fdt_del_node(tree,node("/pmic/charger@1000"))==0);memcpy(original,tree,sizeof(tree));
 assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
 fixture(true);int n=fdt_add_subnode(tree,node("/pmic"),"charger@2000");assert(n>=0);
 assert(fdt_setprop_string(tree,n,"compatible","qcom,pm8226-charger")==0);memcpy(original,tree,sizeof(tree));
 assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
 fixture(true);assert(fdt_setprop_u32(tree,node("/pmic/battery@4000"),"monitored-battery",40)==0);
 memcpy(original,tree,sizeof(tree));assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
 fixture(true);assert(fdt_setprop_u32(tree,node("/pmic/charger@1000"),"phandle",0xfffffffeU)==0);
 memcpy(original,tree,sizeof(tree));assert(madai_battery_update_dt(tree,"ignored",0)<0);unchanged();count++;
 printf("PASS: %u actual selector/FDT/data/atomic-failure cases under ASan/UBSan\n",count);
 return 0;
}
'''
with tempfile.TemporaryDirectory(prefix="fx0-battery-handoff-") as temporary:
    root = Path(temporary)
    (root / "boot.h").write_text(boot_enum)
    (root / "debug.h").write_text("")
    stubs = stubs.replace("SOURCE_DEVICE_HEADER", str(args.lk2nd.resolve() / "lk2nd/device/device.h"))
    stubs = stubs.replace("SOURCE_IMPLEMENTATION", str(source))
    (root / "check.c").write_text(stubs + main)
    subprocess.run(["clang", "-std=gnu11", "-Wall", "-Wextra", "-Werror",
                    "-Wno-misleading-indentation", "-fsanitize=address,undefined",
                    "-fno-sanitize-recover=all",
                    f"-DEXPECT_UNALIGNED_FAILURE={int(args.expect_unaligned_failure)}",
                    "-I", str(root), str(root / "check.c"),
                    "-lfdt", "-Wl,--wrap=fdt_setprop", "-Wl,--wrap=fdt_add_subnode",
                    "-Wl,--wrap=fdt_open_into", "-o", str(root / "check")], check=True)
    if args.dtb_in:
        subprocess.run([str(root / "check"), str(args.dtb_in), str(args.dtb_out)], check=True)
    else:
        subprocess.run([str(root / "check")], check=True)
