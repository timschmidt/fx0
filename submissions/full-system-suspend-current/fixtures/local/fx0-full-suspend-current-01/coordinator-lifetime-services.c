// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <stdarg.h>
typedef uint32_t u32;
#define __iomem
#define MSM8226_CPUS 4
#define MSM8226_SLEEP_STATUS 8
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define DL_FLAG_STATELESS 1
#define DL_FLAG_AUTOREMOVE_CONSUMER 2
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
static int checks,cases;
#define CHECK(x) do{checks++;if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
static void panic(const char *fmt,...) {fprintf(stderr,"unexpected fatal: %s\n",fmt);exit(2);}
struct device_node {int id,refs;bool available;const char *compatible;};
struct device {struct device *parent;struct device_node *of_node;void *data;int refs;bool bound;};
struct platform_device {struct device dev;};
struct device_link {struct device *consumer,*supplier;int flags;bool live;};
struct work_struct {void (*fn)(struct work_struct *);bool scheduled;};
struct resource {uint64_t start,end;};
struct spm_driver_data {int cpu;};
struct qcom_smd_rpm {int unused;};
static struct device_node nodes[18];
static struct platform_device pdev,providers[7];
static struct device rpm_dev;
static struct spm_driver_data spms[4],l2;
static struct qcom_smd_rpm rpm;
static struct device_link links[3];
static void *allocation;
static int fail_at,ops,link_count,mpm_owner,rpm_owner,cpr_owner,warm_calls,install_calls,uninstall_calls,cancel_calls;
static const void *installed_ops;
static bool in_probe,hotplug_writer,scm_available,offline_at_publish,system_sleep_mutex;
static unsigned int online_mask,present_mask,present_count;
#define cpu_online_mask (&online_mask)
#define cpu_present_mask (&present_mask)
static unsigned long acc_words[4][4];
static bool fault(void) {return ++ops==fail_at;}
static void *dev_get_drvdata(struct device *d) {return d->data;}
static void *platform_get_drvdata(struct platform_device *p) {return p->dev.data;}
static void platform_set_drvdata(struct platform_device *p,void *v) {CHECK(hotplug_writer);p->dev.data=v;}
static bool device_is_bound(struct device *d) {return d->bound;}
static void *devm_kzalloc(struct device *d,size_t size,int flags) {if(fault())return NULL;CHECK(!allocation);allocation=calloc(1,size);CHECK(allocation);return allocation;}
static void of_node_put(struct device_node *n) {if(n){CHECK(n->refs>1);n->refs--;}}
static struct device_node *get_node(unsigned int id) {CHECK(id<18);nodes[id].refs++;return &nodes[id];}
static struct device_node *of_parse_phandle(struct device_node *n,const char *name,int index) {
 CHECK(!index);if(fault())return NULL;
 if(n==pdev.dev.of_node){if(!strcmp(name,"qcom,cpr"))return get_node(1);if(!strcmp(name,"qcom,mpm"))return get_node(2);if(!strcmp(name,"qcom,l2-spm"))return get_node(3);}
 if(n->id>=10&&n->id<14){if(!strcmp(name,"qcom,saw"))return get_node(4+n->id-10);if(!strcmp(name,"qcom,acc"))return get_node(14+n->id-10);}
 CHECK(false);return NULL;
}
static bool of_device_is_available(struct device_node *n) {return n->available;}
static bool of_device_is_compatible(struct device_node *n,const char *name) {return n&&n->compatible&&!strcmp(n->compatible,name);}
static struct platform_device *of_find_device_by_node(struct device_node *n) {if(fault())return NULL;CHECK(n->id>=1&&n->id<=7);struct platform_device *p=&providers[n->id-1];p->dev.refs++;return p;}
static void put_device(struct device *d) {CHECK(d->refs>1);d->refs--;}
static unsigned int num_present_cpus(void) {return present_count;}
static bool cpu_present(int cpu) {return present_mask&(1U<<cpu);}
static unsigned int cpu_logical_map(int cpu) {return cpu;}
static struct device_node *of_cpu_device_node_get(unsigned int cpu) {CHECK(cpu<4);if(fault())return NULL;return get_node(cpu+10);}
static int of_property_read_string(struct device_node *n,const char *key,const char **value) {CHECK(!strcmp(key,"enable-method")&&n->id>=10&&n->id<14);if(fault())return -EINVAL;*value="qcom,msm8226-smp";return 0;}
static int of_address_to_resource(struct device_node *n,int index,struct resource *r) {CHECK(!index&&n->id>=14&&n->id<18);if(fault())return -EINVAL;r->start=0xf9088000ULL+(n->id-14)*0x10000;r->end=r->start+0xfff;return 0;}
static uint64_t resource_size(struct resource *r) {return r->end-r->start+1;}
static void *devm_ioremap(struct device *d,uint64_t start,uint64_t size) {CHECK(start>=0xf9088000&&start<=0xf90b8000&&size==0x1000);if(fault())return NULL;return acc_words[(start-0xf9088000)/0x10000];}
static struct device_link *device_link_add(struct device *consumer,struct device *supplier,int flags) {
 if(fault())return NULL;CHECK(link_count<3);struct device_link *link=&links[link_count++];*link=(struct device_link){consumer,supplier,flags,true};
 if(flags==DL_FLAG_STATELESS)CHECK(consumer==&providers[0].dev&&supplier==&pdev.dev);
 else CHECK(consumer==&pdev.dev&&(supplier==&providers[1].dev||supplier==&rpm_dev));
 return link;
}
static void device_link_del(struct device_link *link) {CHECK(link&&link->live&&link->flags==DL_FLAG_STATELESS);link->live=false;}
static int qcom_mpm_register_sleep(struct device *d,struct device *o) {CHECK(d==&providers[1].dev&&o==&pdev.dev&&!mpm_owner);if(fault())return -EBUSY;mpm_owner=1;return 0;}
static int qcom_mpm_unregister_sleep(struct device *d,struct device *o) {CHECK(d==&providers[1].dev&&o==&pdev.dev&&mpm_owner);mpm_owner=0;return 0;}
static int qcom_rpm_smd_register_sleep(struct qcom_smd_rpm *r,struct device *o) {CHECK(r==&rpm&&o==&pdev.dev&&!rpm_owner&&mpm_owner);if(fault())return -EBUSY;rpm_owner=1;return 0;}
static int qcom_rpm_smd_unregister_sleep(struct qcom_smd_rpm *r,struct device *o) {CHECK(r==&rpm&&o==&pdev.dev&&rpm_owner);rpm_owner=0;return 0;}
static int qcom_cpr_msm8926_suspend_attach(struct device *d,struct device *o) {CHECK(d==&providers[0].dev&&o==&pdev.dev&&rpm_owner&&mpm_owner&&!cpr_owner);if(fault())return -EBUSY;cpr_owner=1;return 0;}
static int qcom_cpr_msm8926_suspend_detach(struct device *d,struct device *o) {CHECK(d==&providers[0].dev&&o==&pdev.dev&&cpr_owner);cpr_owner=0;return 0;}
static bool qcom_scm_is_available(void) {return scm_available;}
static void cpu_resume_arm(void) {CHECK(false);}
static int qcom_scm_set_warm_boot_addr(void (*fn)(void)) {CHECK(fn==cpu_resume_arm&&cpr_owner&&rpm_owner&&mpm_owner);warm_calls++;return fault()?-EIO:0;}
static void cpus_write_lock(void) {CHECK(!hotplug_writer);hotplug_writer=true;if(offline_at_publish)online_mask=7;}
static void cpus_write_unlock(void) {CHECK(hotplug_writer);hotplug_writer=false;}
static bool cpumask_equal(const unsigned int *a,const unsigned int *b) {CHECK(hotplug_writer);return *a==*b;}
#define INIT_WORK(w,f) do {(w)->fn=(f);(w)->scheduled=false;}while(0)
static void schedule_work(struct work_struct *w) {CHECK(in_probe&&system_sleep_mutex);w->scheduled=true;}
static void cancel_work_sync(struct work_struct *w) {CHECK(!in_probe&&!system_sleep_mutex);w->scheduled=false;cancel_calls++;}
static int msm8226_suspend_ops;
static void suspend_set_ops(const void *ops) {CHECK(!in_probe&&!system_sleep_mutex);if(ops){CHECK(ops==&msm8226_suspend_ops);install_calls++;installed_ops=ops;}else {CHECK(cpr_owner&&rpm_owner&&mpm_owner);uninstall_calls++;installed_ops=NULL;}}
