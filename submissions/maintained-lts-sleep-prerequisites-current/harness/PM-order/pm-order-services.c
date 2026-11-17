// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef int suspend_state_t;
enum { PM_SUSPEND_TO_IDLE=1, PM_SUSPEND_MEM=3, PMSG_SUSPEND=0, PMSG_RESUME=1,
 TEST_PLATFORM=1,TEST_CPUS=2,TEST_CORE=3,SYSTEM_SUSPEND=1,SYSTEM_RUNNING=0 };
static int checks,cases;
#define CHECK(x) do { checks++;if (!(x)) { fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1); } } while (0)
#define BUG_ON(x) CHECK(!(x))
#define pr_err(...) ((void)0)
#define TPS(x) (x)
#define trace_suspend_resume(...) ((void)0)
struct platform_suspend_ops { int (*prepare)(void),(*prepare_late)(void),(*enter)(suspend_state_t); void (*wake)(void),(*finish)(void); };
struct platform_s2idle_ops { int (*prepare)(void),(*prepare_late)(void);void (*restore_early)(void),(*restore)(void); };
static struct platform_suspend_ops mem_ops;
static struct platform_s2idle_ops idle_ops;
static struct platform_suspend_ops *suspend_ops=&mem_ops;
static struct platform_s2idle_ops *s2idle_ops=&idle_ops;
static bool irq_disabled,device_irqs,late_done,admission_closed,cpus_disabled,core_suspended;
static int fail_step,test_level,system_state;
static bool pending;
static int events[64],num_events;
enum { PREPARE=1,DPM_LATE,IDLE_PREPARE,DPM_NOIRQ,MEM_LATE,IDLE_LATE,CPUS_OFF,IRQS_OFF,CORE_OFF,ENTER,CORE_ON,IRQS_ON,CPUS_ON,MEM_WAKE,IDLE_WAKE,DPM_RESUME_NOIRQ,IDLE_RESTORE,DPM_EARLY,FINISH,IDLE_LOOP };
static void event(int code) { CHECK(num_events<64);events[num_events++]=code; }
static int failure(int code) { return fail_step==code?-EIO:0; }
static bool irqs_disabled(void) { return irq_disabled; }
static int dpm_suspend_late(int msg) {
 event(DPM_LATE);CHECK(device_irqs&&!irq_disabled);late_done=true;admission_closed=true;
 if (failure(DPM_LATE)) { /* dpm_suspend_late internally resumes successful devices. */ late_done=false;admission_closed=false;return -EIO; }
 return 0;
}
static int dpm_suspend_noirq(int msg) {
 event(DPM_NOIRQ);CHECK(admission_closed&&device_irqs&&!irq_disabled);device_irqs=false;
 if (failure(DPM_NOIRQ)) { device_irqs=true;return -EIO; } /* internal noirq rollback */
 return 0;
}
static int pm_sleep_disable_secondary_cpus(void) { event(CPUS_OFF);CHECK(admission_closed&&!device_irqs);cpus_disabled=true;return failure(CPUS_OFF); }
static void pm_sleep_enable_secondary_cpus(void) { event(CPUS_ON);CHECK(!irq_disabled&&cpus_disabled);cpus_disabled=false; }
static void arch_suspend_disable_irqs(void) { event(IRQS_OFF);CHECK(cpus_disabled);irq_disabled=true; }
static void arch_suspend_enable_irqs(void) { event(IRQS_ON);CHECK(irq_disabled);irq_disabled=false; }
static int syscore_suspend(void) { event(CORE_OFF);CHECK(irq_disabled);if (failure(CORE_OFF))return -EIO;core_suspended=true;return 0; }
static void syscore_resume(void) { event(CORE_ON);CHECK(core_suspended&&irq_disabled);core_suspended=false; }
static bool pm_wakeup_pending(void) { return pending; }
static int suspend_test(int level) { return test_level==level; }
static void s2idle_loop(void) { event(IDLE_LOOP);CHECK(admission_closed&&!device_irqs&&!irq_disabled); }
static void dpm_resume_noirq(int msg) { event(DPM_RESUME_NOIRQ);CHECK(!device_irqs&&!irq_disabled);device_irqs=true; }
static void dpm_resume_early(int msg) { event(DPM_EARLY);CHECK(late_done&&device_irqs&&!irq_disabled);admission_closed=false;late_done=false; }
