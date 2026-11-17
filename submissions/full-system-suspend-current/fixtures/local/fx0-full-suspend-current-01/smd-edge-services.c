// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
#define SMD_ALLOC_TBL_COUNT 2
#define SMD_ALLOC_TBL_SIZE 64
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define QCOM_SMEM_HOST_ANY 255
#define IRQF_TRIGGER_RISING 1
#define IRQF_NO_SUSPEND 2
#define EXPORT_SYMBOL(x)
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define IS_ERR_OR_NULL(p) (!(p)||IS_ERR(p))
#define PTR_ERR(p) ((intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define DECLARE_BITMAP(n,bits) unsigned long n[1]
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
#define pr_err(...) ((void)0)
#define dev_err_probe(d,e,...) (e)
static int cases,checks,failures;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define EXPECT(x) do{checks++;if(!(x)){if(failures++<16)fprintf(stderr,"%d: %s\n",__LINE__,#x);}}while(0)
struct qcom_smd_edge;
struct device_node {const char *name,*compatible;int refs;};
struct device {struct device *parent;struct device_node *of_node;void (*release)(struct device *);void *groups;bool registered;};
struct mutex {bool initialized;};
struct notifier_block {int (*notifier_call)(struct notifier_block *,unsigned long,void *);};
struct regmap {int unused;};
struct mbox_client {struct device *dev;bool knows_txdone;};
struct mbox_chan {int unused;};
struct list_head {int unused;};
struct work_struct {void (*fn)(struct work_struct *);bool initialized,scheduled;};
struct qcom_smd_channel {struct list_head list;char *name;};
typedef int spinlock_t;
typedef int wait_queue_head_t;
static int fail_at,ops,live_allocations,mailboxes,notifiers,irq_requests,irq_disables,irq_flags,chrdevs,removed_children,cancel_calls;
static bool full_pm,smem_available,legacy_syscon;
static struct mbox_chan mailbox;
static struct regmap regmap;
static struct device_node edge_node,syscon_node,parent_node;
static struct device parent,child;
static void *edge_memory;
#define IS_ENABLED(x) full_pm
#define kzalloc_obj(x) model_alloc(sizeof(x))
static bool fault(void) {return ++ops==fail_at;}
static void *model_alloc(size_t size) {if(fault())return NULL;CHECK(!edge_memory);edge_memory=calloc(1,size);CHECK(edge_memory);live_allocations++;return edge_memory;}
static void kfree(void *p) {CHECK(p==edge_memory&&live_allocations==1);free(p);edge_memory=NULL;live_allocations--;}
static void mutex_init(struct mutex *m) {m->initialized=true;}
#define INIT_LIST_HEAD(l) do{(l)->unused=0;}while(0)
#define spin_lock_init(l) do{*(l)=0;}while(0)
#define init_waitqueue_head(l) do{*(l)=0;}while(0)
#define INIT_WORK(w,f) do{(w)->fn=(f);(w)->initialized=true;}while(0)
/* No channels are allocated in this device/edge ownership model. */
#define list_for_each_entry_safe(c,t,h,m) for((c)=NULL,(t)=NULL;(c)!=NULL;(c)=NULL)
static void list_del(struct list_head *l) {CHECK(false);}
static struct device_node *of_node_get(struct device_node *n) {CHECK(n);n->refs++;return n;}
static void of_node_put(struct device_node *n) {if(n){CHECK(n->refs>1);n->refs--;}}
static int of_property_read_u32(struct device_node *n,const char *key,unsigned int *out) {if(!strcmp(key,"qcom,remote-pid"))return -ENOENT;if(fault())return -EINVAL;*out=15;return 0;}
static struct mbox_chan *mbox_request_channel(struct mbox_client *c,int index) {CHECK(c->dev&&c->knows_txdone&&!index);if(fault())return ERR_PTR(-EPROBE_DEFER);if(legacy_syscon)return ERR_PTR(-ENOENT);mailboxes++;return &mailbox;}
static void mbox_free_channel(struct mbox_chan *c) {if(!c)return;CHECK(c==&mailbox&&mailboxes==1);mailboxes--;}
static struct device_node *of_parse_phandle(struct device_node *n,const char *key,int index) {CHECK(n==&edge_node&&!strcmp(key,"qcom,ipc")&&!index);return fault()?NULL:of_node_get(&syscon_node);}
static struct regmap *syscon_node_to_regmap(struct device_node *n) {CHECK(n==&syscon_node);return fault()?ERR_PTR(-EIO):&regmap;}
static int of_property_read_u32_index(struct device_node *n,const char *key,int index,int *out) {CHECK(n==&edge_node&&!strcmp(key,"qcom,ipc")&&(index==1||index==2));if(fault())return -EINVAL;*out=index;return 0;}
static int of_property_read_string(struct device_node *n,const char *key,const char **out) {CHECK(n==&edge_node&&!strcmp(key,"label"));*out="rpm-edge";return 0;}
static int irq_of_parse_and_map(struct device_node *n,int index) {CHECK(n==&edge_node&&!index);return fault()?0:91;}
static bool of_device_is_compatible(struct device_node *n,const char *value) {return !strcmp(n->compatible,value);}
static void qcom_channel_scan_worker(struct work_struct *w) {CHECK(false);}
static void qcom_channel_state_worker(struct work_struct *w) {CHECK(false);}
static int qcom_smd_sleep_notify(struct notifier_block *n,unsigned long event,void *unused) {CHECK(false);return 0;}
static bool qcom_smem_is_available(void) {return smem_available;}
static const char *dev_name(struct device *d) {CHECK(d==&parent);return "parent";}
static void dev_set_name(struct device *d,const char *fmt,const char *name,struct device_node *n) {CHECK(n==&edge_node);}
static void *qcom_smd_edge_groups;
static int device_register(struct device *d) {if(fault())return -ENOMEM;d->registered=true;return 0;}
static void put_device(struct device *d);
static void device_unregister(struct device *d);
static int devm_request_irq(struct device *d,int irq,int (*fn)(int,void *),unsigned long flags,const char *name,void *arg);
static int qcom_smd_edge_intr(int irq,void *data) {CHECK(false);return 0;}
static int register_pm_notifier(struct notifier_block *nb) {CHECK(irq_requests==1&&nb->notifier_call==qcom_smd_sleep_notify);if(fault())return -ENOMEM;notifiers++;return 0;}
static int unregister_pm_notifier(struct notifier_block *nb) {CHECK(notifiers==1);notifiers--;return 0;}
static int qcom_smd_create_chrdev(struct qcom_smd_edge *e) {if(fault())return -ENOMEM;chrdevs++;child.registered=true;return 0;}
static void schedule_work(struct work_struct *w) {CHECK(w->initialized);w->scheduled=true;}
static void cancel_work_sync(struct work_struct *w) {CHECK(w->initialized);w->scheduled=false;cancel_calls++;}
static void disable_irq(int irq) {CHECK(irq==91&&irq_requests==1);irq_disables++;}
static int device_for_each_child(struct device *d,void *data,int (*fn)(struct device *,void *)) {CHECK(irq_disables==1&&cancel_calls==2);if(child.registered){removed_children++;return fn(&child,data);}return 0;}
