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
typedef int irqreturn_t;
#define __iomem
#define BIT(n) (1UL << (n))
#define U32_MAX UINT32_MAX
#define IRQ_NONE 0
#define IRQ_HANDLED 1
#define IRQF_NO_SUSPEND BIT(0)
#define IRQCHIP_STATE_PENDING 0
#define EPROBE_DEFER 517
#define GFP_KERNEL 0
#define EXPORT_SYMBOL_GPL(x)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,y) ((x)=(y))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define MPM_REG_ENABLE 0
#define MPM_REG_FALLING_EDGE 1
#define MPM_REG_RISING_EDGE 2
#define MPM_REG_POLARITY 3
#define MPM_REG_STATUS 4
static int checks,cases,failures,lock_depth,rcu_depth,mbox_error,mbox_calls,txdone,replays;
static bool local_irqs_off;
static unsigned int current_cpu,online_cpus;
#define CHECK(x) do {checks++;if(!(x)){if(failures++<24)fprintf(stderr,"%d: %s\n",__LINE__,#x);}}while(0)
typedef int raw_spinlock_t;
#define raw_spin_lock_irqsave(l,f) do {(f)=local_irqs_off;CHECK(!*(l));(*(l))++;lock_depth++;local_irqs_off=true;}while(0)
#define raw_spin_unlock_irqrestore(l,f) do {CHECK(*(l)==1);(*(l))--;lock_depth--;local_irqs_off=(f);}while(0)
#define for_each_set_bit(j,p,n) for((j)=0;(j)<(n);(j)++) if(*(p)&BIT(j))
struct device_node {int id,refs,irq_count,args_count,pin;bool available,parse_fail,controller;struct device_node *parent;};
struct device {void *data;struct device_node *of_node;};
struct of_phandle_args {struct device_node *np;int args_count;u32 args[2];};
struct irq_domain {void *fwnode;struct irq_domain *parent;};
struct irq_data {struct irq_domain *domain;struct irq_data *parent_data;irq_hw_number_t hwirq;unsigned int irq;bool armed,disabled,level;};
struct irqaction {unsigned long flags;struct irqaction *next;};
struct irq_desc {struct irq_data irq_data;struct irqaction *action;};
struct mbox_client {int unused;};
struct mbox_chan {int unused;};
struct generic_pm_domain {int unused;};
static struct irq_desc *descriptors[128],*pin_desc[1024];
static unsigned int replay_count[128];
static struct device_node nodes[12],root;
static int node_count,pass_number;
static bool add_second_pass,alloc_fail;
static int action_fail,action_attempt;
static void *allocations[12];static int allocation_count;
static struct {void (*f)(void *);void *p;} actions[12];static int action_count;
static void *dev_get_drvdata(struct device *d) {return d->data;}
static bool irqs_disabled(void) {return local_irqs_off;}
static unsigned int raw_smp_processor_id(void) {return current_cpu;}
static unsigned int num_online_cpus(void) {return online_cpus;}
static void *model_cmpxchg(struct device **p,struct device *old,struct device *new) {struct device *v=*p;if(v==old)*p=new;return v;}
#define cmpxchg(p,o,n) model_cmpxchg((p),(o),(n))
static void wmb(void) {}
static u32 readl_relaxed(const void *p) {return *(const u32 *)p;}
static void writel_relaxed(u32 v,void *p) {*(u32 *)p=v;}
static int mbox_send_message(struct mbox_chan *c,void *p) {CHECK(!local_irqs_off&&!lock_depth);mbox_calls++;return mbox_error?mbox_error:7;}
static void mbox_client_txdone(struct mbox_chan *c,int e) {CHECK(!local_irqs_off&&!lock_depth&&!e);txdone++;}
static struct irq_desc *irq_resolve_mapping(struct irq_domain *d,unsigned int pin) {return pin<1024?pin_desc[pin]:NULL;}
static bool irqd_is_level_type(struct irq_data *d) {return d->level;}
static void irq_set_irqchip_state(unsigned int irq,int state,bool value) {CHECK(irq<128&&state==IRQCHIP_STATE_PENDING&&value);replay_count[irq]++;replays++;}
static struct irq_data *irq_desc_get_irq_data(struct irq_desc *d) {return &d->irq_data;}
static bool irqd_is_wakeup_armed(struct irq_data *d) {return d->armed;}
static bool irqd_irq_disabled(struct irq_data *d) {return d->disabled;}
static void rcu_read_lock(void) {rcu_depth++;}
static void rcu_read_unlock(void) {CHECK(rcu_depth==1);rcu_depth--;}
#define for_each_irq_desc(irq,desc) for((irq)=0;(irq)<128;(irq)++) if(((desc)=descriptors[irq]))
static void of_node_put(struct device_node *n) {if(n){CHECK(n->refs>1);n->refs--;}}
static void of_node_get(struct device_node *n) {CHECK(n&&n->refs>0);n->refs++;}
static struct device_node *next_node(struct device_node *old) {
 int i=old?old->id+1:0;
 if(old)of_node_put(old);else {pass_number++;if(add_second_pass&&pass_number==2){nodes[node_count].available=true;node_count++;}}
 for(;i<node_count;i++)if(nodes[i].controller){of_node_get(&nodes[i]);return &nodes[i];}
 return NULL;
}
#define for_each_node_with_property(n,p) for((n)=next_node(NULL);(n);(n)=next_node(n))
static bool of_device_is_available(struct device_node *n) {return n->available;}
static int of_irq_count(struct device_node *n) {return n->irq_count;}
static int of_irq_parse_one(struct device_node *n,int index,struct of_phandle_args *p) {if(n->parse_fail)return -EINVAL;p->np=n->parent;of_node_get(p->np);p->args_count=n->args_count;p->args[0]=n->pin;return 0;}
static void *of_fwnode_handle(struct device_node *n) {return n;}
static void *devm_kcalloc(struct device *d,unsigned int count,size_t size,int flags) {if(alloc_fail)return NULL;void *p=calloc(count,size);CHECK(p&&allocation_count<12);allocations[allocation_count++]=p;return p;}
static int devm_add_action_or_reset(struct device *d,void (*fn)(void *),void *p) {if(++action_attempt==action_fail){fn(p);return -ENOMEM;}CHECK(action_count<12);actions[action_count].f=fn;actions[action_count++].p=p;return 0;}
