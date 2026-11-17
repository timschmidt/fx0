// SPDX-License-Identifier: GPL-2.0-only
#define _GNU_SOURCE
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define U64_MAX UINT64_MAX
#define READ_ONCE(x) (x)
#define EXPORT_SYMBOL_GPL(x)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
static atomic_int checks;
static int cases;
#define CHECK(x) do {atomic_fetch_add(&checks,1);if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct mutex {pthread_mutex_t native;};
struct completion {int unused;};
typedef int spinlock_t;
struct device {struct device *parent;};
struct work_struct {bool scheduled;};
struct notifier_block {int unused;};
enum {PM_SUSPEND_PREPARE=1,PM_HIBERNATION_PREPARE,PM_RESTORE_PREPARE,PM_POST_SUSPEND,PM_POST_HIBERNATION,PM_POST_RESTORE,NOTIFY_BAD=-1,NOTIFY_OK=1,NOTIFY_DONE=0,SMD_CHANNEL_CLOSED=0,SMD_CHANNEL_OPENED=2};
struct qcom_smd_edge {bool no_suspend,system_sleep;int irq;struct mutex sleep_lock;struct notifier_block sleep_nb;struct work_struct scan_work,state_work;};
struct rpmsg_endpoint_ops {int unused;};
static const struct rpmsg_endpoint_ops qcom_smd_endpoint_ops={0},other_ops={0};
struct rpmsg_endpoint {const struct rpmsg_endpoint_ops *ops;};
struct qcom_smd_endpoint;
struct qcom_smd_channel {struct qcom_smd_edge *edge;const char *name;struct qcom_smd_endpoint *qsept;int state,rx_state;};
struct qcom_smd_endpoint {struct rpmsg_endpoint ept;struct qcom_smd_channel *qsch;};
#define to_smd_endpoint(p) container_of(p,struct qcom_smd_endpoint,ept)
#define GET_RX_CHANNEL_INFO(c,m) ((c)->rx_state)
static bool irq_off;
static int irq_depth,disable_calls,enable_calls;
static void mutex_lock(struct mutex *m) {CHECK(!pthread_mutex_lock(&m->native));}
static void mutex_unlock(struct mutex *m) {CHECK(!pthread_mutex_unlock(&m->native));}
static bool mutex_trylock(struct mutex *m) {int ret=pthread_mutex_trylock(&m->native);CHECK(!ret||ret==EBUSY);return !ret;}
static bool irqs_disabled(void) {return irq_off;}
static void assert_transport_irq_order(bool enable);
static void disable_irq(int irq) {CHECK(!irq_off&&irq==91&&irq_depth==0);assert_transport_irq_order(false);disable_calls++;irq_depth++;}
static void enable_irq(int irq) {CHECK(!irq_off&&irq==91&&irq_depth==1);assert_transport_irq_order(true);enable_calls++;irq_depth--;}
static void schedule_work(struct work_struct *w) {w->scheduled=true;}
static atomic_int scan_runs,state_runs,removed;
static bool worker_block,channel_closed;
static pthread_mutex_t system_sleep_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t cond=PTHREAD_COND_INITIALIZER;
static bool worker_entered;
static void qcom_channel_scan_worker_run(struct work_struct *w) {atomic_fetch_add(&scan_runs,1);}
static void qcom_channel_state_worker_run(struct work_struct *w) {
 atomic_fetch_add(&state_runs,1);
 if(worker_block){CHECK(!pthread_mutex_lock(&gate));worker_entered=true;CHECK(!pthread_cond_broadcast(&cond));CHECK(!pthread_mutex_unlock(&gate));CHECK(!pthread_mutex_lock(&system_sleep_lock));CHECK(!pthread_mutex_unlock(&system_sleep_lock));}
 if(channel_closed)atomic_fetch_add(&removed,1);
}
