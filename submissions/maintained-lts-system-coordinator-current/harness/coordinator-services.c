// SPDX-License-Identifier: GPL-2.0-only
#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdatomic.h>
#include <pthread.h>
#include <unistd.h>
#include <stdarg.h>
typedef uint32_t u32;
typedef int suspend_state_t;
#define __iomem
#define CONFIG_HOTPLUG_CPU 1
#define MSM8226_CPUS 4
#define MSM8226_SLEEP_STATUS 8
#define BIT(n) (1U<<(n))
#define MSM8226_CPU_COLLAPSED BIT(19)
#define GENMASK(h,l) ((~0U<<(l))&(~0U>>(31-(h))))
#define U32_MAX UINT32_MAX
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define smp_store_release(p,v) atomic_store_explicit((p),(v),memory_order_release)
#define smp_load_acquire(p) atomic_load_explicit((p),memory_order_acquire)
#define per_cpu(n,c) (n[c])
#define BUG_ON(x) CHECK(!(x))
#define pr_err(...) ((void)0)
#define TPS(x) (x)
#define trace_suspend_resume(...) ((void)0)
#define CONFIG_ARM_GIC_MAX_NR 1
#define GIC_DIST_ENABLE_SET 0x100
#define GIC_DIST_ENABLE_CLEAR 0x180
#define GIC_DIST_SGI_PENDING_CLEAR 0xf10
#define dsb(x) atomic_thread_fence(memory_order_seq_cst)
enum {PM_SUSPEND_TO_IDLE=1,PM_SUSPEND_MEM=3,PMSG_SUSPEND=0,PMSG_RESUME=1,TEST_PLATFORM=1,TEST_CPUS,TEST_CORE,SYSTEM_RUNNING=0,SYSTEM_SUSPEND=1};
enum {PM_SLEEP_MODE_STBY=0,PM_SLEEP_MODE_SPC=4,PM_SLEEP_MODE_PC=5,SPM_L2_MODE_DISABLED=0,SPM_L2_MODE_COLLAPSE_RPM=3,QCOM_SCM_CPU_PWR_DOWN_L2_ON=1,QCOM_SCM_CPU_PWR_DOWN_L2_OFF=2};
enum {DPM_LATE=1,DPM_NOIRQ,RPM_PREPARE,MPM_PREPARE,CPUS_OFF,SYSCORE_OFF,CPU_READY,CPU_ENTER,CLUSTER_ENTER,L2_ARM,CPU_ARM,SUSPEND_CALL,CPU_DISARM,L2_DISARM,CPR_PREPARE,SECONDARY_NOT_READY};
static atomic_int checks;
static int cases,fail_step,test_level,system_state,threaded_scenarios;
static bool gic_drop_clear,gic_boot_during_clear,lose_secondary_at_cluster,lose_secondary_at_cpu_arm;
static bool pending,firmware_wake;
static _Thread_local unsigned int current_cpu;
static _Thread_local bool irq_off;
static _Thread_local int pm_depth,cluster_depth;
static atomic_bool msm8226_boot_requested[4];
static atomic_uint acc[4][3];
static atomic_uint gic_regs[4][1024];
static atomic_int online_cpus;
static atomic_int arrived[4];
static pthread_t cpu_threads[4];
static bool started[4];
static pthread_mutex_t wake_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t wake_cond=PTHREAD_COND_INITIALIZER;
static atomic_int cpu_modes[4];
static int l2_mode,cache_clean,outer_clean,scm_calls,genpd_requests,enter_calls;
static bool cpr_quiesced,cpr_safe,rpm_frozen,rx_masked,mpm_armed,device_irqs,core_suspended,late_done;
#define CHECK(x) do {atomic_fetch_add(&checks,1);if(!(x)){fprintf(stderr,"%d cpu%u: %s\n",__LINE__,current_cpu,#x);exit(1);}}while(0)
static void panic(const char *fmt,...) {fprintf(stderr,"unexpected fatal: %s\n",fmt);exit(2);}
struct device {void *data;};
struct platform_device {struct device dev;};
struct device_link {int unused;};
struct work_struct {int unused;};
struct task_struct {int unused;};
struct qcom_smd_rpm {int unused;};
struct spm_driver_data {unsigned int cpu;};
struct platform_suspend_ops {int (*valid)(suspend_state_t);int (*prepare)(void),(*prepare_late)(void),(*enter)(suspend_state_t);void (*wake)(void),(*finish)(void);};
struct platform_s2idle_ops {int (*prepare)(void),(*prepare_late)(void);void (*restore_early)(void),(*restore)(void);};
static const struct platform_suspend_ops *suspend_ops;
static struct platform_s2idle_ops *s2idle_ops;
static suspend_state_t pm_suspend_target_state;
static struct {bool available;} gic_data[1];
static bool irqs_disabled(void) {return irq_off;}
static unsigned int raw_smp_processor_id(void) {return current_cpu;}
static unsigned int num_online_cpus(void) {return atomic_load(&online_cpus);}
static void *dev_get_drvdata(struct device *d) {return d->data;}
static void *gic_data_dist_base(void *d) {return gic_data[0].available?gic_regs[current_cpu]:NULL;}
static u32 readl_relaxed(const void *p) {return atomic_load((const atomic_uint *)p);}
static void writel_relaxed(u32 v,void *p) {
 uintptr_t a=(uintptr_t)p,b=(uintptr_t)&gic_regs[current_cpu][0];
 if(a>=b&&a<b+sizeof(gic_regs[0])) {
  unsigned int off=a-b;
  if(off==GIC_DIST_ENABLE_CLEAR){if(gic_drop_clear)return;atomic_fetch_and(&gic_regs[current_cpu][GIC_DIST_ENABLE_SET/4],~v);return;}
  if(off>=GIC_DIST_SGI_PENDING_CLEAR&&off<GIC_DIST_SGI_PENDING_CLEAR+16){if(gic_boot_during_clear&&off==GIC_DIST_SGI_PENDING_CLEAR+12)smp_store_release(&per_cpu(msm8226_boot_requested,current_cpu),true);atomic_fetch_and(&gic_regs[current_cpu][off/4],~v);return;}
 }
 atomic_store((atomic_uint *)p,v);
}
#define readl_poll_timeout_atomic(p,v,condition,delay,bound) ({int result=-ETIMEDOUT;for(int attempt=0;attempt<=(bound);attempt++){(v)=readl_relaxed(p);if(condition){result=0;break;}}result;})
static bool qcom_cpr_msm8926_suspend_ready(struct device *d,struct device *o) {CHECK(irq_off&&current_cpu==0);return cpr_safe&&cpr_quiesced;}
static bool qcom_rpm_smd_sleep_ready(struct qcom_smd_rpm *r,struct device *o) {CHECK(irq_off&&current_cpu==0);return rpm_frozen&&rx_masked;}
static bool qcom_mpm_sleep_ready(struct device *d,struct device *o) {CHECK(irq_off&&current_cpu==0);return mpm_armed;}
static int qcom_cpr_msm8926_suspend_prepare(struct device *d,struct device *o) {CHECK(cpr_quiesced&&!irq_off&&device_irqs&&!rpm_frozen);if(fail_step==CPR_PREPARE)return -EIO;cpr_safe=true;return 0;}
static int qcom_cpr_msm8926_suspend_restore(struct device *d,struct device *o) {CHECK(cpr_safe&&cpr_quiesced&&device_irqs&&!irq_off&&!rpm_frozen&&!rx_masked&&!mpm_armed);cpr_safe=false;return 0;}
static int qcom_rpm_smd_prepare_sleep(struct qcom_smd_rpm *r,struct device *o) {CHECK(!irq_off&&!device_irqs&&cpr_safe&&!rx_masked&&!rpm_frozen);if(fail_step==RPM_PREPARE)return -EIO;rpm_frozen=true;rx_masked=true;return 0;}
static int qcom_rpm_smd_finish_sleep(struct qcom_smd_rpm *r,struct device *o) {CHECK(!irq_off&&!device_irqs&&rpm_frozen&&rx_masked);rx_masked=false;rpm_frozen=false;return 0;}
static int qcom_mpm_prepare_sleep(struct device *d,struct device *o) {CHECK(!irq_off&&!device_irqs&&rpm_frozen&&rx_masked);if(fail_step==MPM_PREPARE)return -EIO;mpm_armed=true;return 0;}
static int qcom_mpm_finish_sleep(struct device *d,struct device *o) {CHECK(!irq_off&&!device_irqs&&mpm_armed&&rpm_frozen&&rx_masked&&!core_suspended&&num_online_cpus()==4);mpm_armed=false;return 0;}
static int spm_msm8226_cpu_ready(struct spm_driver_data *s) {CHECK(s&&s->cpu==current_cpu&&irq_off);return fail_step==(current_cpu?SECONDARY_NOT_READY:CPU_READY)?-EIO:0;}
static int cpu_pm_enter(void) {CHECK(irq_off&&!pm_depth);if(!current_cpu&&fail_step==CPU_ENTER)return -EIO;pm_depth++;return 0;}
static void cpu_pm_exit(void) {CHECK(irq_off&&pm_depth==1&&!cluster_depth&&cpu_modes[current_cpu]==PM_SLEEP_MODE_STBY);pm_depth--;}
static int cpu_cluster_pm_enter(void) {CHECK(!current_cpu&&pm_depth==1&&!cluster_depth);if(fail_step==CLUSTER_ENTER)return -EIO;cluster_depth++;if(lose_secondary_at_cluster)atomic_store(&acc[2][2],0);return 0;}
static void cpu_cluster_pm_exit(void) {CHECK(!current_cpu&&cluster_depth==1&&l2_mode==SPM_L2_MODE_DISABLED);cluster_depth--;}
static int spm_set_low_power_mode(struct spm_driver_data *s,int mode) {
 CHECK(s&&s->cpu==current_cpu&&irq_off&&pm_depth==1);
 if(!current_cpu&&mode==PM_SLEEP_MODE_PC&&fail_step==CPU_ARM){cpu_modes[0]=PM_SLEEP_MODE_STBY;return -EIO;}
 cpu_modes[current_cpu]=mode;if(!current_cpu&&mode==PM_SLEEP_MODE_PC&&lose_secondary_at_cpu_arm)atomic_store(&acc[3][2],0);
 return !current_cpu&&mode==PM_SLEEP_MODE_STBY&&fail_step==CPU_DISARM?-EIO:0;
}
static int spm_set_l2_low_power_mode(struct spm_driver_data *s,int mode) {
 CHECK(!current_cpu&&irq_off&&cluster_depth==1);
 if(mode==SPM_L2_MODE_COLLAPSE_RPM){CHECK(num_online_cpus()==1);if(fail_step==L2_ARM){l2_mode=SPM_L2_MODE_DISABLED;return -EIO;}}
 l2_mode=mode;return mode==SPM_L2_MODE_DISABLED&&fail_step==L2_DISARM?-EIO:0;
}
static void flush_cache_all(void) {CHECK(!current_cpu&&irq_off);cache_clean++;}
static void outer_flush_all(void) {CHECK(cache_clean>outer_clean);outer_clean++;}
static void qcom_scm_cpu_power_down(int mode) {
 if(current_cpu) {
  CHECK(mode==QCOM_SCM_CPU_PWR_DOWN_L2_ON&&pm_depth==1&&cpu_modes[current_cpu]==PM_SLEEP_MODE_SPC);
  CHECK(!(readl_relaxed(&gic_regs[current_cpu][GIC_DIST_ENABLE_SET/4])&GENMASK(31,16)));
  CHECK(!pthread_mutex_lock(&wake_lock));atomic_store(&acc[current_cpu][2],MSM8226_CPU_COLLAPSED);atomic_store(&arrived[current_cpu],1);CHECK(!pthread_cond_broadcast(&wake_cond));
  while(!smp_load_acquire(&per_cpu(msm8226_boot_requested,current_cpu)))CHECK(!pthread_cond_wait(&wake_cond,&wake_lock));
  atomic_store(&acc[current_cpu][2],0);CHECK(!pthread_mutex_unlock(&wake_lock));
 } else {
  CHECK(mode==QCOM_SCM_CPU_PWR_DOWN_L2_OFF&&irq_off&&cluster_depth==1&&cpu_modes[0]==PM_SLEEP_MODE_PC&&l2_mode==SPM_L2_MODE_COLLAPSE_RPM);
  CHECK(cache_clean==outer_clean&&cache_clean>0);for(int c=1;c<4;c++)CHECK(readl_relaxed(&acc[c][2])&MSM8226_CPU_COLLAPSED);scm_calls++;
 }
}
static int cpu_suspend(unsigned long arg,int (*fn)(unsigned long)) {if(!current_cpu&&fail_step==SUSPEND_CALL)return -EIO;int before=scm_calls;int ret=fn(arg);return current_cpu||(firmware_wake&&scm_calls>before)?0:ret;}
static void wfi(void) {
 CHECK(!current_cpu||cpu_modes[current_cpu]==PM_SLEEP_MODE_STBY);
 if(current_cpu){CHECK(!pthread_mutex_lock(&wake_lock));atomic_store(&arrived[current_cpu],1);CHECK(!pthread_cond_broadcast(&wake_cond));while(!smp_load_acquire(&per_cpu(msm8226_boot_requested,current_cpu)))CHECK(!pthread_cond_wait(&wake_cond,&wake_lock));CHECK(!pthread_mutex_unlock(&wake_lock));}
}
static int cortex_a7_boot_secondary(unsigned int cpu,struct task_struct *idle) {CHECK(smp_load_acquire(&per_cpu(msm8226_boot_requested,cpu)));CHECK(!pthread_mutex_lock(&wake_lock));CHECK(!pthread_cond_broadcast(&wake_cond));CHECK(!pthread_mutex_unlock(&wake_lock));return 0;}
static int suspend_valid_only_mem(suspend_state_t s) {return s==PM_SUSPEND_MEM;}
