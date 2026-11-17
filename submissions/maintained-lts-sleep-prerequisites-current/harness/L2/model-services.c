/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <errno.h>
typedef uint32_t u32;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define CHECK(x) do { if (!(x)) { fprintf(stderr,"model invariant at %d: %s\n",__LINE__,#x); exit(1); } } while (0)
static unsigned cases, checks, failures;
static bool reported[4096];
#define EXPECT(x) do { ++checks; if (!(x)) { ++failures; CHECK(__LINE__<ARRAY_SIZE(reported)); \
    if(!reported[__LINE__])fprintf(stderr,"check failed at %d: %s\n",__LINE__,#x); \
    reported[__LINE__]=true; } } while (0)
static jmp_buf fatal_target;
static bool expect_fatal;
static unsigned fatal_calls;
#define panic(...) do { CHECK(expect_fatal); ++fatal_calls; longjmp(fatal_target,1); } while (0)
/* ACTUAL_ENUM */
struct regmap { u32 registers[1024]; };
static struct regmap bank;
static int regmap_read(struct regmap *,unsigned int,unsigned int *);
static int regmap_write(struct regmap *,unsigned int,unsigned int);
/* ACTUAL_HEADER */
struct device_node { int unused; };
struct device { struct device_node *of_node; };
struct platform_device { struct device dev; };
struct resource { unsigned int size; };
struct spm_reg_data { bool pmic_arbiter_master; };
struct spm_driver_data { void *reg_base; struct regmap *l2_map; const struct spm_reg_data *reg_data; };
struct regmap_range { unsigned int range_min,range_max; };
struct regmap_access_table { const struct regmap_range *yes_ranges; unsigned int n_yes_ranges; };
struct regmap_config {
    const char *name;
    unsigned int reg_bits,val_bits,reg_stride,max_register;
    bool fast_io,use_raw_spinlock;
    const struct regmap_access_table *rd_table,*wr_table;
};
#define regmap_reg_range(lo,hi) {(lo),(hi)}
/* ACTUAL_ACCESS_TABLES */
static bool access_ok(unsigned int address,bool write)
{
    const struct regmap_access_table *table = write ? spm_8226_l2_regmap_config.wr_table : spm_8226_l2_regmap_config.rd_table;
    if (address > spm_8226_l2_regmap_config.max_register || address % spm_8226_l2_regmap_config.reg_stride) return false;
    for (unsigned i=0;i<table->n_yes_ranges;i++)
        if (address>=table->yes_ranges[i].range_min && address<=table->yes_ranges[i].range_max) return true;
    return false;
}
enum { GOOD, FAIL, DROP, CORRUPT };
static unsigned operations,writes,sequence_writes,control_writes;
static unsigned fault_at,fault_span,fault_kind;
static bool applied,mode_phase;
static bool fault_now(void)
{
    return fault_at && operations>=fault_at && operations<fault_at+(fault_span ? fault_span : 1);
}
static int regmap_read(struct regmap *map,unsigned int address,unsigned int *value)
{
    CHECK(map==&bank && address/4<1024 && access_ok(address,false));
    CHECK(++operations<4096);
    if (fault_now() && fault_kind==FAIL) return -EIO;
    *value=map->registers[address/4];
    if (fault_now() && (fault_kind==DROP || fault_kind==CORRUPT)) *value ^= 1;
    return 0;
}
static int regmap_write(struct regmap *map,unsigned int address,unsigned int value)
{
    CHECK(map==&bank && address/4<1024 && access_ok(address,true));
    CHECK(++operations<4096); ++writes;
    if (mode_phase) EXPECT(address==0x30);
    else EXPECT(address==8 || address==0x34 || address==0x40 || address==0x44 || (address>=0x80 && address<=0xd0));
    if (address>=0x80 && address<=0xd0) { ++sequence_writes; EXPECT(!map->registers[0x30/4]); }
    if (address==0x30) ++control_writes;
    if (fault_now() && fault_kind==FAIL && !applied) return -EIO;
    if (!(fault_now() && fault_kind==DROP)) map->registers[address/4] = fault_now() && fault_kind==CORRUPT ? value^1 : value;
    return fault_now() && fault_kind==FAIL ? -EIO : 0;
}
static const struct spm_reg_data master = {.pmic_arbiter_master=true}, ordinary = {0};
static struct device_node node;
static struct platform_device pdev = {.dev.of_node=&node};
static struct resource resource;
static struct spm_driver_data driver;
static unsigned cpu,online;
static bool irq_off;
#define raw_smp_processor_id() cpu
#define irqs_disabled() irq_off
#define num_online_cpus() online
/* ACTUAL_WRAPPER */
static bool master_flag,is_module,is_syscon,missing_resource,published;
static int map_error,lookup_error,registry_error;
static unsigned publication_calls,map_calls,lookups;
#define IS_MODULE(x) is_module
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define IORESOURCE_MEM 1
#define resource_size(r) ((r)->size)
#define dev_err_probe(dev,error,fmt,...) (error)
static bool of_property_read_bool(struct device_node *n,const char *name)
{ CHECK(n==&node&&!strcmp(name,"qcom,pmic-arbiter-master")); return master_flag; }
static bool of_device_is_compatible(struct device_node *n,const char *name)
{ CHECK(n==&node&&!strcmp(name,"syscon")); return is_syscon; }
static struct resource *platform_get_resource(struct platform_device *d,int type,int index)
{ CHECK(d==&pdev&&type==IORESOURCE_MEM&&!index); return missing_resource ? NULL : &resource; }
static struct regmap *syscon_node_to_regmap(struct device_node *n)
{ CHECK(n==&node); ++lookups; return published ? &bank : ERR_PTR(lookup_error ? lookup_error : -EINVAL); }
static struct regmap *devm_regmap_init_mmio(struct device *d,void *base,const struct regmap_config *config)
{ CHECK(d==&pdev.dev&&base==driver.reg_base&&config==&spm_8226_l2_regmap_config); ++map_calls; return map_error ? ERR_PTR(map_error) : &bank; }
static int of_syscon_register_regmap(struct device_node *n,struct regmap *map)
{
    CHECK(n==&node&&map==&bank&&!published); ++publication_calls;
    EXPECT(!bank.registers[0x30/4]&&!bank.registers[0x20/4]);
    for(unsigned i=0;i<ARRAY_SIZE(spm_8226_l2_sequence);i++)
        EXPECT(bank.registers[(0x80+4*i)/4]==spm_8226_l2_sequence[i]);
    if (registry_error) return registry_error;
    published=true; return 0;
}
/* ACTUAL_REGISTER */
static void clear_io(void)
{
    operations=writes=sequence_writes=control_writes=publication_calls=map_calls=lookups=0;
    fault_at=fault_span=fault_kind=0; applied=false;
}
static void reset(void)
{
    memset(&bank,0,sizeof(bank)); clear_io(); mode_phase=false;
    driver=(struct spm_driver_data){.reg_base=&bank,.reg_data=&master};
    resource.size=4096;
    master_flag=true; is_module=is_syscon=missing_resource=published=false;
    map_error=lookup_error=registry_error=0; cpu=0; online=1; irq_off=true;
    bank.registers[0xfd0/4]=0x20010000; bank.registers[4/4]=4;
    bank.registers[0x1c/4]=0x73; bank.registers[0x14/4]=0x73;
    expect_fatal=false; fatal_calls=0;
}
static void ready(void)
{
    reset(); CHECK(spm_8226_l2_register(&pdev,&driver)==0);
    clear_io(); mode_phase=true;
}
static void preserved(void)
{
    EXPECT(bank.registers[0x1c/4]==0x73 && bank.registers[0x14/4]==0x73);
    EXPECT(bank.registers[8/4]==0x14 && bank.registers[0x34/4]==0x3c102800);
    EXPECT(bank.registers[0x40/4]==0x02030080 && bank.registers[0x44/4]==0x00030000);
    EXPECT(!bank.registers[0x20/4]);
}
