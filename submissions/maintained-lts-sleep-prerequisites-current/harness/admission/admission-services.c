// SPDX-License-Identifier: GPL-2.0-only
#define _GNU_SOURCE
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
#include <limits.h>
#include <signal.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef unsigned char u8;
typedef uint32_t __le32;
#define U64_MAX UINT64_MAX
#define HZ 100
#define GFP_ATOMIC 0
#define WARN_ON(x) (x)
#define ALIGN(x,a) (((x)+(a)-1)&~((a)-1))
#define cpu_to_le32(x) (x)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
static atomic_int checks,allocations,sends,cases;
#define CHECK(x) do { atomic_fetch_add(&checks,1); if (!(x)) { fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1); } } while (0)
struct mutex { pthread_mutex_t native; };
typedef struct { pthread_mutex_t native; } spinlock_t;
struct completion { pthread_mutex_t native; int done; };
struct qcom_smd_rpm;
struct device { void *data; };
struct rpmsg_device { struct device dev; };
struct rpmsg_endpoint { struct qcom_smd_rpm *rpm; int mode; };
static _Thread_local bool irq_off,allocation_fail;
static bool irqs_disabled(void) { return irq_off; }
static void *dev_get_drvdata(struct device *d) { return d->data; }
static void mutex_lock(struct mutex *m) { CHECK(!pthread_mutex_lock(&m->native)); }
static void mutex_unlock(struct mutex *m) { CHECK(!pthread_mutex_unlock(&m->native)); }
#define spin_lock_irqsave(m,f) do { (f)=irq_off; CHECK(!pthread_mutex_lock(&(m)->native)); } while (0)
#define spin_unlock_irqrestore(m,f) do { (void)(f); CHECK(!pthread_mutex_unlock(&(m)->native)); } while (0)
static void *kmalloc(size_t n,int flags) { if (allocation_fail) return NULL; void *p=malloc(n); if (p) atomic_fetch_add(&allocations,1); return p; }
static void kfree(void *p) { CHECK(p); atomic_fetch_sub(&allocations,1);free(p); }
static void reinit_completion(struct completion *c) { CHECK(!pthread_mutex_lock(&c->native)); c->done=0;CHECK(!pthread_mutex_unlock(&c->native)); }
static void complete(struct completion *c) { CHECK(!pthread_mutex_lock(&c->native)); c->done++;CHECK(!pthread_mutex_unlock(&c->native)); }
static int wait_for_completion_timeout(struct completion *c,int timeout);
static int rpmsg_send(struct rpmsg_endpoint *,void *,size_t);
static int qcom_smd_rpm_callback(struct rpmsg_device *,void *,int,void *,u32);
static u32 get_unaligned_le32(const void *p) { const u8 *v=p;return v[0]|(u32)v[1]<<8|(u32)v[2]<<16|(u32)v[3]<<24; }
