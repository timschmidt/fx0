// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint32_t u32;
typedef unsigned long irq_hw_number_t;
typedef int raw_spinlock_t;
#define __iomem
#define GFP_KERNEL 0
#define EPROBE_DEFER 517
#define EINVAL 22
#define IRQF_NO_SUSPEND 1
#define IRQ_DOMAIN_FLAG_QCOM_MPM_WAKEUP 1
#define DOMAIN_BUS_WAKEUP 1
#define GENPD_FLAG_IRQ_SAFE 1
#define DIV_ROUND_UP(n,d) (((n)+(d)-1)/(d))
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((intptr_t)(p))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define MPM_REG_ENABLE 0
#define MPM_REG_FALLING_EDGE 1
#define MPM_REG_RISING_EDGE 2
#define MPM_REG_POLARITY 3
#define MPM_REG_STATUS 4
#define dev_err(...) ((void)0)
#define dev_warn(...) ((void)0)
static int cases,checks,failures,ops,fail_at,failure_error,pin_count;
static bool full_pm,genpd_live,provider_live,mailbox_live,domain_live,irq_live;
#define IS_ENABLED(x) full_pm
#define CHECK(x) do {checks++;if(!(x)){fprintf(stderr,"%d: %s\n",__LINE__,#x);exit(1);}}while(0)
#define EXPECT(x) do {checks++;if(!(x)){if(failures++<16)fprintf(stderr,"%d: %s\n",__LINE__,#x);}}while(0)
struct device_node {int id,refs;};
struct device {struct device_node *of_node;struct device *parent;void *data;};
struct platform_device {struct device dev;};
struct resource {uintptr_t start,end;};
struct irq_domain {int unused;};
struct generic_pm_domain {unsigned int flags;int (*power_off)(struct generic_pm_domain *);const char *name;};
struct mbox_client {struct device *dev;bool knows_txdone;};
struct mbox_chan {int unused;};
static struct device_node mpm_node,parent_node,sram_node;
static struct device parent;
static struct platform_device pdev;
static u32 mmio[12];
static struct irq_domain parent_domain,domain;
static struct mbox_chan mailbox;
static void *allocations[12];static int allocation_count;
static bool fault(void) {return ++ops==fail_at;}
static void *devm_kzalloc(struct device *d,size_t size,int flags) {if(fault())return NULL;CHECK(allocation_count<12);void *p=calloc(1,size);CHECK(p);allocations[allocation_count++]=p;return p;}
static void *devm_kcalloc(struct device *d,size_t count,size_t size,int flags) {return devm_kzalloc(d,count*size,flags);}
static int of_property_read_u32(struct device_node *n,const char *key,u32 *out) {CHECK(n==&mpm_node&&!strcmp(key,"qcom,mpm-pin-count"));if(fault())return failure_error;*out=pin_count;return 0;}
static bool of_device_is_compatible(struct device_node *n,const char *value) {CHECK(n==&parent_node&&!strcmp(value,"qcom,msm8226-rpm-proc"));return true;}
static int of_property_count_u32_elems(struct device_node *n,const char *key) {CHECK(n==&mpm_node&&!strcmp(key,"qcom,mpm-pin-map"));return fault()?failure_error:8;}
static int of_property_read_u32_index(struct device_node *n,const char *key,unsigned int index,u32 *out) {static const u32 map[]={2,184,47,140,53,72,62,190};CHECK(n==&mpm_node&&!strcmp(key,"qcom,mpm-pin-map")&&index<8);*out=map[index];return 0;}
static void raw_spin_lock_init(raw_spinlock_t *l) {*l=0;}
static struct device_node *of_parse_phandle(struct device_node *n,const char *key,int index) {CHECK(n==&mpm_node&&!strcmp(key,"qcom,rpm-msg-ram")&&!index);sram_node.refs++;return &sram_node;}
static void of_node_put(struct device_node *n) {CHECK(n==&sram_node&&n->refs==2);n->refs--;}
static int of_address_to_resource(struct device_node *n,int index,struct resource *r) {CHECK(n==&sram_node&&!index);if(fault())return failure_error;r->start=0xfc4281d0;r->end=r->start+sizeof(mmio)-1;return 0;}
static size_t resource_size(struct resource *r) {return r->end-r->start+1;}
static void *devm_ioremap(struct device *d,uintptr_t start,size_t size) {CHECK(start==0xfc4281d0&&size==sizeof(mmio));return fault()?NULL:mmio;}
static void *devm_platform_ioremap_resource(struct platform_device *p,int index) {CHECK(false);return NULL;}
static int platform_get_irq(struct platform_device *p,int index) {CHECK(p==&pdev&&!index);return fault()?failure_error:71;}
static const char *dev_name(struct device *d) {CHECK(d==&pdev.dev);return "mpm";}
static const char *devm_kasprintf(struct device *d,int flags,const char *fmt,const char *name) {CHECK(!strcmp(fmt,"%s")&&!strcmp(name,"mpm"));return fault()?NULL:"mpm";}
static int pm_genpd_init(struct generic_pm_domain *g,void *unused,bool off) {CHECK(!unused&&!off&&!genpd_live);if(fault())return failure_error;genpd_live=true;return 0;}
static int pm_genpd_remove(struct generic_pm_domain *g) {CHECK(genpd_live);EXPECT(!provider_live);genpd_live=false;return 0;}
static int of_genpd_add_provider_simple(struct device_node *n,struct generic_pm_domain *g) {CHECK(n==&mpm_node&&genpd_live&&!provider_live);if(fault())return failure_error;provider_live=true;return 0;}
static void of_genpd_del_provider(struct device_node *n) {CHECK(n==&mpm_node&&provider_live);provider_live=false;}
static struct mbox_chan *mbox_request_channel(struct mbox_client *c,int index) {CHECK(c->dev==&pdev.dev&&c->knows_txdone&&!index&&!mailbox_live);if(fault())return ERR_PTR(failure_error);mailbox_live=true;return &mailbox;}
static void mbox_free_channel(struct mbox_chan *c) {CHECK(c==&mailbox&&mailbox_live);mailbox_live=false;}
static struct irq_domain *irq_find_host(struct device_node *n) {CHECK(n==&parent_node);return fault()?NULL:&parent_domain;}
static void *of_fwnode_handle(struct device_node *n) {return n;}
static int qcom_mpm_ops;
static struct irq_domain *irq_domain_create_hierarchy(struct irq_domain *parent,int flags,unsigned int pins,void *node,void *ops,void *priv) {CHECK(parent==&parent_domain&&flags==IRQ_DOMAIN_FLAG_QCOM_MPM_WAKEUP&&pins==64&&node==&mpm_node&&ops==&qcom_mpm_ops&&!domain_live);if(fault())return NULL;domain_live=true;return &domain;}
static void irq_domain_remove(struct irq_domain *d) {CHECK(d==&domain&&domain_live);domain_live=false;}
static void irq_domain_update_bus_token(struct irq_domain *d,int token) {CHECK(d==&domain&&domain_live&&token==DOMAIN_BUS_WAKEUP);}
static int qcom_mpm_handler(int irq,void *priv) {CHECK(false);return 0;}
static int devm_request_irq(struct device *d,int irq,int (*fn)(int,void *),unsigned long flags,const char *name,void *priv) {CHECK(d==&pdev.dev&&irq==71&&fn==qcom_mpm_handler&&flags==IRQF_NO_SUSPEND&&!strcmp(name,"qcom_mpm")&&domain_live);if(fault())return failure_error;irq_live=true;return 0;}
static void dev_set_drvdata(struct device *d,void *data) {CHECK(d==&pdev.dev&&genpd_live&&provider_live&&mailbox_live&&domain_live&&irq_live);d->data=data;}
static int mpm_pd_power_off(struct generic_pm_domain *g) {CHECK(false);return 0;}
