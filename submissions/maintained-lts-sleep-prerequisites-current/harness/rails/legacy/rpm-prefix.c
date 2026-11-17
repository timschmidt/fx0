
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <limits.h>
#include <sys/mman.h>
#include <unistd.h>
typedef uint64_t u64;
typedef uint32_t u32;
typedef unsigned char u8;
typedef uint32_t __le32;
#define EBUSY 16
#define EINVAL 22
#define ENOMEM 12
#define ENXIO 6
#define ETIMEDOUT 110
#define EIO 5
#define HZ 100
#define GFP_ATOMIC 0
#define WARN_ON(x) (x)
#define ALIGN(x,a) (((x)+(a)-1)&~((a)-1))
#define cpu_to_le32(x) (x)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define CHECK(x) do{if(!(x)){fprintf(stderr,"line %d: %s\n",__LINE__,#x);exit(1);}}while(0)
struct qcom_smd_rpm;
struct completion {int done;};
struct mutex {int held;};
typedef struct {int held;} spinlock_t;
struct device {void *data;};
struct rpmsg_device {struct device dev;};
struct rpmsg_endpoint {struct qcom_smd_rpm *rpm;};
static void *dev_get_drvdata(struct device *dev) {return dev->data;}
static void mutex_lock(struct mutex *lock) {CHECK(!lock->held);lock->held=1;}
static void mutex_unlock(struct mutex *lock) {CHECK(lock->held);lock->held=0;}
#define spin_lock_irqsave(lock,flags) do{flags=0;CHECK(!(lock)->held);(lock)->held=1;}while(0)
#define spin_unlock_irqrestore(lock,flags) do{(void)flags;CHECK((lock)->held);(lock)->held=0;}while(0)
static u32 get_unaligned_le32(const void *p) {
 const u8 *v=p;return v[0]|(u32)v[1]<<8|(u32)v[2]<<16|(u32)v[3]<<24;
}
static int allocated;
static void *kmalloc(size_t size,int flags);
static void kfree(void *p) {CHECK(allocated>0);allocated--;free(p);}
static void reinit_completion(struct completion *c) {c->done=0;}
static void complete(struct completion *c);
static int wait_for_completion_timeout(struct completion *c,int timeout);
static int rpmsg_send(struct rpmsg_endpoint *,void *,size_t);
static int qcom_smd_rpm_callback(struct rpmsg_device *,void *,int,void *,u32);

#define DECLARE_FLEX_ARRAY(type,name) struct { struct { } __empty_ ## name; type name[]; }
#define le32_to_cpu(x) (x)
#define min_t(type,a,b) ((type)(a)<(type)(b)?(type)(a):(type)(b))
#define PTR_ALIGN(p,a) ((void *)(((uintptr_t)(p)+(a)-1)&~((uintptr_t)(a)-1)))
#define memcpy_fromio memcpy
#define dev_err(dev,fmt,...) ((void)(dev))

#ifndef EOPNOTSUPP
#define EOPNOTSUPP 95
#endif
