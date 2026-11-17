/* SPDX-License-Identifier: GPL-2.0-only */
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <setjmp.h>
#include <errno.h>
#include <limits.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef void (*smp_call_func_t)(void *);
#define __iomem
#define __cpuidle
#define BIT(n) (1U<<(n))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define CHECK(x) do { if(!(x)) { fprintf(stderr,"model invariant at %d: %s\n",__LINE__,#x); exit(1); } } while(0)
static unsigned cases,checks,failures;
static bool reported[4096];
#define EXPECT(x) do { ++checks; if(!(x)) { ++failures; CHECK(__LINE__<ARRAY_SIZE(reported)); \
    if(!reported[__LINE__]) fprintf(stderr,"check failed at %d: %s\n",__LINE__,#x); reported[__LINE__]=true; } } while(0)
static jmp_buf fatal_target;
static bool expect_fatal;
static unsigned fatal_calls;
#define panic(...) do { CHECK(expect_fatal); ++fatal_calls; longjmp(fatal_target,1); } while(0)
struct device_node { const char *compatible; int refs; unsigned cpu; bool is_cpu,available; };
struct device { struct device_node *of_node; unsigned refs; };
struct regmap { int unused; };
struct linear_range { int min,min_sel,max_sel,step; };
#define REGULATOR_LINEAR_RANGE(v,lo,hi,s) {(v),(lo),(hi),(s)}
/* ACTUAL_DEFINES */
/* ACTUAL_TYPES */
static void smp_set_vdd_v1_1(void *data) { CHECK(!"voltage programming is not a model service"); }
/* ACTUAL_CATALOGUES */
static u32 bank[1024],snapshot[1024];
static struct spm_driver_data *active;
static unsigned ctl_writes,ctl_reads,delays,total_writes;
static unsigned seq_copies,publication_calls,regulator_calls;
static bool probe_phase,sequence_loaded;
static bool reset_disabled_index;
enum { GOOD,DROP,CORRUPT,STALE };
static unsigned fault_kind,fault_start,fault_count;
static unsigned suspend_calls,scm_calls,pm_enters,pm_exits,ct_enters,ct_exits,wfi_calls;
static int suspend_result,pm_error;
static bool in_pm;
static unsigned int control_offset(void)
{ CHECK(active&&active->reg_data&&active->reg_data->reg_offset); return active->reg_data->reg_offset[SPM_REG_SPM_CTL]; }
static bool fault_now(void)
{ return fault_start&&ctl_writes>=fault_start&&ctl_writes<fault_start+fault_count; }
static size_t offset_of(const volatile void *address)
{
    uintptr_t p=(uintptr_t)address,base=(uintptr_t)bank;
    CHECK(p>=base&&p<base+sizeof(bank)&&(p-base)%4==0);
    return p-base;
}
static void writel_relaxed(u32 value,volatile void *address)
{
    size_t offset=offset_of(address); ++total_writes;
    bool control=active->reg_data->reg_offset&&control_offset()&&offset==control_offset();
    if(!probe_phase) EXPECT(control);
    if(control) {
        ++ctl_writes;
        if(probe_phase&&active->reg_data->reg_offset[SPM_REG_SEQ_ENTRY]) EXPECT(sequence_loaded);
        if(fault_now()&&fault_kind==DROP) return;
        if(fault_now()&&fault_kind==CORRUPT) value^=1;
        if(reset_disabled_index&&!(value&SPM_CTL_EN)) value&=~(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT);
    }
    bank[offset/4]=value;
}
static u32 readl_relaxed(const volatile void *address)
{
    size_t offset=offset_of(address);
    u32 value=bank[offset/4];
    if(active->reg_data->reg_offset&&control_offset()&&offset==control_offset()) {
        ++ctl_reads;
        if(fault_now()&&fault_kind==STALE) value^=1;
    }
    return value;
}
static void udelay(unsigned int us) { EXPECT(us==1); ++delays; }
static bool model_irqs_off;
static unsigned int model_cpu;
static bool irqs_disabled(void) { return model_irqs_off; }
static unsigned int raw_smp_processor_id(void) { return model_cpu; }
/* ACTUAL_CPU_FUNCTIONS */
struct of_device_id { const char *compatible; const void *data; };
/* ACTUAL_MATCH_TABLE */
struct platform_device { struct device dev; void *data; };
static struct device_node node;
static struct platform_device pdev={.dev.of_node=&node};
static struct platform_device idle_pdev;
static void *idle_allocated[32];
static unsigned idle_allocation_count,idle_allocation_attempts,idle_fail_allocation;
static struct spm_driver_data *allocated;
static bool allocation_fail,regulator_enabled;
static int mapping_error,regulator_error,l2_error;
static unsigned l2_calls;
#define GFP_KERNEL 0
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define IS_ENABLED(x) regulator_enabled
#define dev_err_probe(dev,error,fmt,...) (error)
static void *devm_kzalloc(struct device *dev,size_t size,int flags)
{
    if(dev==&idle_pdev.dev) {
        if(++idle_allocation_attempts==idle_fail_allocation) return NULL;
        CHECK(idle_allocation_count<ARRAY_SIZE(idle_allocated));
        void *p=calloc(1,size); CHECK(p); idle_allocated[idle_allocation_count++]=p; return p;
    }
    CHECK(dev==&pdev.dev&&size==sizeof(struct spm_driver_data)&&!allocated);
    if(allocation_fail) return NULL;
    allocated=calloc(1,size); CHECK(allocated); return allocated;
}
static void *devm_platform_ioremap_resource(struct platform_device *dev,unsigned int index)
{ CHECK(dev==&pdev&&!index); return mapping_error ? ERR_PTR(mapping_error) : bank; }
static const struct of_device_id *of_match_node(const struct of_device_id *table,struct device_node *n)
{
    CHECK(table==spm_match_table&&n==&node);
    for(const struct of_device_id *p=table;p->compatible;p++)
        if(!strcmp(p->compatible,n->compatible)) { active=allocated; active->reg_data=p->data; return p; }
    return NULL;
}
static void __iowrite32_copy(void *destination,const void *source,size_t count)
{
    size_t offset=offset_of(destination);
    EXPECT(offset==active->reg_data->reg_offset[SPM_REG_SEQ_ENTRY]&&count==MAX_SEQ_DATA/4);
    EXPECT(!ctl_writes&&!publication_calls);
    CHECK(offset+count*4<=sizeof(bank)); memcpy(destination,source,count*4);
    sequence_loaded=true; ++seq_copies;
}
static int spm_register_regulator(struct device *dev,struct spm_driver_data *drv)
{ CHECK(dev==&pdev.dev&&drv==active); EXPECT(!publication_calls); ++regulator_calls; return regulator_error; }
static int spm_8226_l2_register(struct platform_device *dev,struct spm_driver_data *drv)
{ CHECK(dev==&pdev&&drv==active&&drv->reg_data->pmic_arbiter_master); EXPECT(!publication_calls); ++l2_calls; return l2_error; }
static void platform_set_drvdata(struct platform_device *dev,void *data)
{
    CHECK(dev==&pdev&&data==active); ++publication_calls;
    if(!active->reg_data->pmic_arbiter_master&&control_offset()) {
        u32 value=bank[control_offset()/4];
        EXPECT((value&(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT|SPM_CTL_EN))==SPM_CTL_EN);
    }
    if(!active->reg_data->pmic_arbiter_master&&regulator_enabled) EXPECT(regulator_calls==1&&!regulator_error);
    pdev.data=data;
}
static int spm_get_cpu(struct device *dev);
/* ACTUAL_PROBE */
struct cpuidle_device { int unused; };
struct cpuidle_driver;
struct cpumask { unsigned cpu; };
struct cpuidle_state {
    int (*enter)(struct cpuidle_device *,struct cpuidle_driver *,int);
    unsigned int exit_latency,target_residency,power_usage;
    const char *name,*desc;
};
struct cpuidle_driver { const char *name; void *owner; struct cpuidle_state states[8]; struct cpumask *cpumask; };
/* ACTUAL_IDLE_DATA */
#define container_of(p,type,member) ((type *)((char *)(p)-offsetof(type,member)))
static void cpu_do_idle(void)
{
    u32 ctl=bank[control_offset()/4]; ++wfi_calls;
    EXPECT(!(ctl&SPM_CTL_EN)||((ctl>>SPM_CTL_INDEX_SHIFT)&SPM_CTL_INDEX)==0);
}
static int cpu_pm_enter(void) { ++pm_enters; CHECK(!in_pm); if(!pm_error)in_pm=true; return pm_error; }
static void cpu_pm_exit(void) { ++pm_exits; CHECK(in_pm); in_pm=false; }
static void ct_cpuidle_enter(void) { ++ct_enters; }
static void ct_cpuidle_exit(void) { ++ct_exits; }
/* ACTUAL_SCM_FLAG */
static void qcom_scm_cpu_power_down(unsigned int flags)
{
    ++scm_calls; EXPECT(flags==QCOM_SCM_CPU_PWR_DOWN_L2_ON);
    u32 ctl=bank[control_offset()/4];
    EXPECT((ctl&SPM_CTL_EN)&&((ctl>>SPM_CTL_INDEX_SHIFT)&SPM_CTL_INDEX)==active->reg_data->start_index[PM_SLEEP_MODE_SPC]);
}
static int cpu_suspend(unsigned long argument,int (*finish)(unsigned long))
{
    ++suspend_calls;
    EXPECT((bank[control_offset()/4]&SPM_CTL_EN)!=0);
    EXPECT(finish(argument)==-1);
    /* A logical zero models the separate warm-resume return from cpu_suspend. */
    return suspend_result;
}
/* ACTUAL_IDLE_MACROS */
static int spm_enter_idle_state(struct cpuidle_device *,struct cpuidle_driver *,int);
#define THIS_MODULE NULL
/* ACTUAL_IDLE_SETUP */
static struct device_node cpu_nodes[4],saw_nodes[4];
static struct platform_device providers[4];
static struct spm_driver_data provider_data[4];
static struct cpumask masks[4];
static bool cpu_missing[4],saw_missing[4],provider_exists[4],registered[4];
static unsigned present_cpus,warm_calls,registration_calls,provider_gets;
static bool scm_available;
static int warm_error,DT_error,DT_error_cpu,registration_error,registration_error_cpu;
#define EPROBE_DEFER 517
#define for_each_possible_cpu(cpu) for((cpu)=0;(cpu)<4;(cpu)++)
#define for_each_present_cpu(cpu) for((cpu)=0;(unsigned)(cpu)<present_cpus;(cpu)++)
#define dev_err(...) ((void)0)
static struct device_node *of_cpu_device_node_get(unsigned cpu)
{ CHECK(cpu<4); if(cpu_missing[cpu])return NULL; ++cpu_nodes[cpu].refs; return &cpu_nodes[cpu]; }
static struct device_node *of_parse_phandle(struct device_node *n,const char *name,int index)
{
    CHECK(n->is_cpu&&!strcmp(name,"qcom,saw")&&!index);
    if(saw_missing[n->cpu]) return NULL;
    if(probe_phase&&n->cpu==0) { ++node.refs; return &node; }
    ++saw_nodes[n->cpu].refs; return &saw_nodes[n->cpu];
}
static void of_node_put(struct device_node *n) { if(n) { CHECK(n->refs>0); --n->refs; } }
static bool of_device_is_available(struct device_node *n) { return n&&n->available; }
static struct platform_device *of_find_device_by_node(struct device_node *n)
{ CHECK(!n->is_cpu&&n->cpu<4); if(!provider_exists[n->cpu])return NULL; ++providers[n->cpu].dev.refs; return &providers[n->cpu]; }
static void *dev_get_drvdata(struct device *d)
{
    for(unsigned i=0;i<4;i++) if(d==&providers[i].dev) { ++provider_gets; CHECK(d->refs); return providers[i].data; }
    CHECK(!"unexpected device"); return NULL;
}
static void put_device(struct device *d) { CHECK(d->refs); --d->refs; }
static const struct cpumask *cpumask_of(unsigned cpu) { CHECK(cpu<4); return &masks[cpu]; }
static int dt_init_idle_driver(struct cpuidle_driver *d,const struct of_device_id *match,unsigned first)
{
    CHECK(match==qcom_idle_state_match&&first==1&&d->cpumask&&d->cpumask->cpu<4);
    EXPECT(d->states[0].enter==spm_enter_idle_state);
    return (int)d->cpumask->cpu==DT_error_cpu ? DT_error : 1;
}
static int cpuidle_register(struct cpuidle_driver *d,const void *unused)
{
    unsigned cpu=d->cpumask->cpu; CHECK(cpu<4&&!unused); ++registration_calls;
    struct cpuidle_qcom_spm_data *data=container_of(d,struct cpuidle_qcom_spm_data,cpuidle_driver);
    EXPECT(data->spm==&provider_data[cpu]&&!registered[cpu]);
    if((int)cpu==registration_error_cpu) return registration_error;
    registered[cpu]=true; return 0;
}
static bool qcom_scm_is_available(void) { return scm_available; }
static void cpu_resume_arm(void) { CHECK(!"warm vector is never executed"); }
static int qcom_scm_set_warm_boot_addr(const void *entry)
{ EXPECT(entry==(const void *)cpu_resume_arm); ++warm_calls; return warm_error; }
/* ACTUAL_GET_CPU */
/* ACTUAL_IDLE_FUNCTIONS */
static struct spm_driver_data direct;
static void clear_io(void)
{
    ctl_writes=ctl_reads=delays=total_writes=0;
    suspend_calls=scm_calls=pm_enters=pm_exits=ct_enters=ct_exits=wfi_calls=0;
    fault_start=fault_count=fault_kind=0; suspend_result=pm_error=0; in_pm=false;
}
static void reset(const struct spm_reg_data *data)
{
    CHECK(!allocated);
    memset(bank,0xa5,sizeof(bank)); clear_io();
    direct=(struct spm_driver_data){.reg_base=bank,.reg_data=data,.dev=&pdev.dev}; active=&direct;
    if(data->reg_offset&&control_offset()) bank[control_offset()/4]=0x8029;
    memcpy(snapshot,bank,sizeof(bank));
    probe_phase=sequence_loaded=reset_disabled_index=false; seq_copies=publication_calls=regulator_calls=l2_calls=0;
    pdev.data=NULL; allocation_fail=false; mapping_error=regulator_error=l2_error=0; regulator_enabled=true;
    expect_fatal=false; fatal_calls=0; model_irqs_off=false; model_cpu=0;
    for(unsigned i=0;i<4;i++) {
        cpu_nodes[i]=(struct device_node){.cpu=i,.is_cpu=true,.available=true};
        saw_nodes[i]=(struct device_node){.cpu=i,.available=true};
        cpu_missing[i]=saw_missing[i]=false;
    }
}
static void preserved(u32 initial)
{
    unsigned offset=control_offset();
    for(unsigned i=0;i<ARRAY_SIZE(bank);i++) if(i!=offset/4) EXPECT(bank[i]==snapshot[i]);
    EXPECT((bank[offset/4]&~(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT|SPM_CTL_EN))==(initial&~(SPM_CTL_INDEX<<SPM_CTL_INDEX_SHIFT|SPM_CTL_EN)));
}
static void runtime_ready(void)
{
    reset(&spm_reg_8226_cpu); bank[control_offset()/4]=0x8009;
    memcpy(snapshot,bank,sizeof(bank));
}
static void release_probe(void)
{
    free(allocated); allocated=NULL; pdev.data=NULL; active=NULL;
}
static void reset_admission(void)
{
    probe_phase=false;
    CHECK(!idle_allocation_count); present_cpus=4; warm_calls=registration_calls=provider_gets=0;
    scm_available=true; warm_error=0; DT_error_cpu=registration_error_cpu=-1;
    DT_error=registration_error=0; idle_fail_allocation=idle_allocation_attempts=0;
    for(unsigned i=0;i<4;i++) {
        cpu_nodes[i]=(struct device_node){.cpu=i,.is_cpu=true,.available=true};
        saw_nodes[i]=(struct device_node){.cpu=i,.available=true};
        providers[i]=(struct platform_device){.dev.of_node=&saw_nodes[i],.data=&provider_data[i]};
        provider_data[i]=(struct spm_driver_data){.reg_base=bank,.reg_data=&spm_reg_8226_cpu};
        masks[i].cpu=i; cpu_missing[i]=saw_missing[i]=registered[i]=false; provider_exists[i]=true;
    }
}
static void admission_refs_balanced(void)
{
    for(unsigned i=0;i<4;i++) EXPECT(!cpu_nodes[i].refs&&!saw_nodes[i].refs&&!providers[i].dev.refs);
}
static void release_admission(void)
{
    admission_refs_balanced();
    for(unsigned i=0;i<idle_allocation_count;i++) free(idle_allocated[i]);
    idle_allocation_count=0;
}
