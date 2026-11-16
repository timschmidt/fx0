/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical devres/refcount services. Fixture memory stays allocated until audit ends. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define __iomem
#define GFP_KERNEL 0
#define QCOM_SLIM_NGD_DRV_NAME "qcom,slim-ngd"
#define IS_ERR_OR_NULL(p) (!(p) || (uintptr_t)(p) >= (uintptr_t)-4095)
#define dev_err(...) ((void)0)
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr,"fixture invariant %d: %s\n",__LINE__,#x); exit(3); } } while (0)
typedef uint32_t u32;
struct device { struct device *parent; void *data, *of_node; unsigned refs; bool registered, bound; };
struct platform_device { struct device dev; };
struct device_node { int id; };
struct of_device_id { const void *data; };
struct ngd_reg_offset_data { u32 offset, size; };
/* ACTUAL_NGD_TYPE */
struct mutex { bool held; };
struct completion { int done; };
#define QCOM_SLIM_NGD_CTRL_DOWN 3
struct qcom_slim_ngd_ctrl {
 struct device *dev; void *base; struct qcom_slim_ngd *ngd;
 struct { struct device *dev; } ctrl;
 struct { struct completion qmi_comp; struct { unsigned sq_node,sq_port; } svc_info; } qmi;
 struct completion qmi_up;
 struct mutex ssr_lock;
 bool child_ready, up_requested, pm_ref_held, qmi_ready;
 int qmi_wait;
 int state;
 int irq, nb, ngd_up_work; void *pdr, *notifier, *mwq;
};
static struct platform_device parent;
static struct qcom_slim_ngd_ctrl ctrl;
static struct qcom_slim_ngd *descriptor;
static struct platform_device *pdev_allocation;
static unsigned char registers[65536];
static struct device_node test_node = {.id=2};
static const struct ngd_reg_offset_data offsets = {.offset=0x1000,.size=0x1000};
static const struct of_device_id match = {.data=&offsets};
static const struct of_device_id qcom_slim_ngd_dt_match[1];
static bool desc_live, device_live, desc_managed, irq_enabled, queue_live, exposed;
static bool bind_on_add, probe_failure, fault_hit;
static bool parent_cleanup_possible;
static unsigned double_releases, bad_owner_releases, IRQ_at_descriptor_release;
static unsigned descriptor_missing_at_queue_drain, device_missing_at_queue_drain;
static unsigned descriptor_releases, device_releases;
static int fault;
static unsigned cases, checks, failures;
static const char *case_name;
enum { NONE, DESC_ALLOC, DEVICE_ALLOC, ACTION_ALLOC, OVERRIDE, DEVICE_ADD };
struct resource { void (*release)(void *); void *data; };
static struct resource resources[8];
static unsigned resource_count;
static void check(bool ok,const char *message)
{ checks++; if(!ok){failures++;fprintf(stderr,"%s: %s\n",case_name,message);} }
static bool fail(int kind) {if(fault==kind){fault_hit=true;return true;}return false;}
static void release_descriptor(void *data)
{
 REQUIRE(data==descriptor);
 if(!desc_live){double_releases++;return;}
 if(irq_enabled)IRQ_at_descriptor_release++;
 desc_live=false;descriptor_releases++;
}
static void *allocate_descriptor(size_t bytes,bool managed)
{
 REQUIRE(bytes==sizeof(*descriptor));if(fail(DESC_ALLOC))return NULL;
 descriptor=calloc(1,bytes);REQUIRE(descriptor);desc_live=true;desc_managed=managed;
 if(managed){REQUIRE(resource_count<8);resources[resource_count++]=(struct resource){release_descriptor,descriptor};}
 return descriptor;
}
#define kzalloc_obj(p) allocate_descriptor(sizeof(p),false)
static void *devm_kzalloc(struct device *dev,size_t bytes,int flags)
{ REQUIRE(dev==&parent.dev && flags==GFP_KERNEL);return allocate_descriptor(bytes,true); }
#define devm_kzalloc_obj(dev,p) devm_kzalloc(dev,sizeof(p),GFP_KERNEL)
static void kfree(void *p)
{
 REQUIRE(p==descriptor);
 if(desc_managed)bad_owner_releases++;
 release_descriptor(p);
}
static struct platform_device *platform_device_alloc(const char *name,int id)
{
 REQUIRE(!strcmp(name,QCOM_SLIM_NGD_DRV_NAME));if(fail(DEVICE_ALLOC))return NULL;
 pdev_allocation=calloc(1,sizeof(*pdev_allocation));REQUIRE(pdev_allocation);
 pdev_allocation->dev.refs=1;device_live=true;return pdev_allocation;
}
static struct device *get_device(struct device *dev)
{ REQUIRE(dev==&pdev_allocation->dev && device_live && dev->refs);dev->refs++;return dev; }
static void put_device(struct device *dev)
{
 REQUIRE(dev==&pdev_allocation->dev);
 if(!device_live || !dev->refs){double_releases++;return;}
 dev->refs--;
 if(!dev->refs){device_live=false;device_releases++;}
}
static int __devm_add_action(struct device *dev,void (*action)(void *),void *data,const char *name)
{
 REQUIRE(dev==&parent.dev && action && data);if(fail(ACTION_ALLOC))return -ENOMEM;
 REQUIRE(resource_count<8);resources[resource_count++]=(struct resource){action,data};return 0;
}
/* ACTUAL_ACTION_OR_RESET */
#define devm_add_action_or_reset(dev,action,data) __devm_add_action_or_reset(dev,action,data,#action)
static int qcom_slim_ngd_probe(struct platform_device *pdev);
static void qcom_slim_ngd_remove(struct platform_device *pdev);
static int platform_device_add(struct platform_device *pdev)
{
 REQUIRE(pdev==pdev_allocation && device_live);
 if(fail(DEVICE_ADD))return -EIO;
 pdev->dev.registered=true;exposed=true;
 if(bind_on_add)pdev->dev.bound=qcom_slim_ngd_probe(pdev)==0;
 return 0;
}
static void platform_device_del(struct platform_device *pdev)
{
 REQUIRE(pdev==pdev_allocation && device_live && pdev->dev.registered);
 if(pdev->dev.bound){qcom_slim_ngd_remove(pdev);pdev->dev.bound=false;}
 pdev->dev.registered=false;
}
/* ACTUAL_PLATFORM_WRAPPERS */
static int device_set_driver_override(struct device *dev,const char *name)
{ REQUIRE(dev==&pdev_allocation->dev);return fail(OVERRIDE)?-ENOMEM:0; }
static const struct of_device_id *of_match_node(const struct of_device_id *table,void *node) {return &match;}
#define for_each_available_child_of_node_scoped(parent,node) for(struct device_node *node=&test_node;node;node=NULL)
static int of_property_read_u32(struct device_node *node,const char *name,u32 *id)
{ REQUIRE(node==&test_node && !strcmp(name,"reg"));*id=node->id;return 0; }
static void *of_fwnode_handle(struct device_node *node) {return node;}
static void platform_device_set_fwnode(struct platform_device *pdev,void *node) {pdev->dev.of_node=node;}
static void *dev_get_drvdata(struct device *dev) {return dev->data;}
static void platform_set_drvdata(struct platform_device *pdev,void *data) {pdev->dev.data=data;}
static void *platform_get_drvdata(struct platform_device *pdev) {return pdev->dev.data;}
static void mutex_lock(struct mutex *m) { REQUIRE(!m->held); m->held=true; }
static void mutex_unlock(struct mutex *m) { REQUIRE(m->held); m->held=false; }
static void reinit_completion(struct completion *c) { c->done=0; }
static void wake_up_all(void *q) { REQUIRE(q==&ctrl.qmi_wait); }
static void schedule_work(void *w) { REQUIRE(w==&ctrl.ngd_up_work); }
static void pm_runtime_put_noidle(struct device *dev) {}
static void pm_runtime_use_autosuspend(struct device *dev) {}
static void pm_runtime_set_autosuspend_delay(struct device *dev,int n) {REQUIRE(n==100);}
static void pm_runtime_set_suspended(struct device *dev) {}
static void pm_runtime_enable(struct device *dev) {}
static void pm_runtime_get_noresume(struct device *dev) {}
static void pm_runtime_dont_use_autosuspend(struct device *dev) {}
static void pm_runtime_disable(struct device *dev) {}
static int qcom_slim_ngd_qmi_svc_event_init(struct qcom_slim_ngd_ctrl *c)
{ REQUIRE(c==&ctrl);return probe_failure?-EAGAIN:0; }
static int qcom_slim_ngd_enable(struct qcom_slim_ngd_ctrl *c,bool on) {REQUIRE(c==&ctrl && !on);return 0;}
static void qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *c) {REQUIRE(c==&ctrl);}
static void qcom_slim_ngd_qmi_svc_event_deinit(void *q) {REQUIRE(q==&ctrl.qmi);}
static void pdr_handle_release(void *p) {REQUIRE(p==ctrl.pdr);}
static int qcom_unregister_ssr_notifier(void *n,void *nb) {REQUIRE(n==ctrl.notifier && nb==&ctrl.nb);return 0;}
static void cancel_work_sync(void *w) {REQUIRE(w==&ctrl.ngd_up_work);}
static void disable_irq(int irq) {REQUIRE(irq==42 && irq_enabled);irq_enabled=false;}
static void destroy_workqueue(void *q)
{
 REQUIRE(q==ctrl.mwq && queue_live);
 if(exposed){descriptor_missing_at_queue_drain+=!desc_live;device_missing_at_queue_drain+=!device_live;}
 queue_live=false;
}
/* ACTUAL_DRIVER */
static void reset_case(const char *name,int injected,bool bind,bool probe_fail)
{
 memset(&parent,0,sizeof(parent));memset(&ctrl,0,sizeof(ctrl));
 parent.dev.data=&ctrl;parent.dev.of_node=&test_node;ctrl.dev=&parent.dev;ctrl.base=registers;
 ctrl.irq=42;ctrl.pdr=&ctrl.pdr;ctrl.notifier=&ctrl.notifier;ctrl.mwq=&queue_live;
 descriptor=NULL;pdev_allocation=NULL;
 desc_live=device_live=desc_managed=irq_enabled=exposed=false;queue_live=true;
 resource_count=double_releases=bad_owner_releases=IRQ_at_descriptor_release=0;
 descriptor_missing_at_queue_drain=device_missing_at_queue_drain=0;
 descriptor_releases=device_releases=0;fault=injected;fault_hit=false;
 bind_on_add=bind;probe_failure=probe_fail;case_name=name;cases++;
 parent_cleanup_possible=true;
}
static void release_parent_resources(void)
{
 while(resource_count){struct resource r=resources[--resource_count];r.release(r.data);}
}
static void audit(bool external_ref)
{
 check(parent_cleanup_possible,"parent can unregister after child-only unbind");
 check(!double_releases && !bad_owner_releases,"each resource released by its owner once");
 check(!desc_live,"parent descriptor released at parent end");
 check(!IRQ_at_descriptor_release,"parent IRQ quiesced before descriptor release");
 check(!descriptor_missing_at_queue_drain && !device_missing_at_queue_drain,"descriptor and device survive parent queue drain");
 check(!queue_live,"parent queue drain completed");
 check(pdev_allocation ? pdev_allocation->dev.refs==(external_ref?1U:0U) : true,"only an external device reference remains");
 if(external_ref)put_device(&pdev_allocation->dev);
 check(!device_live,"all owned device references released");
 check(!pdev_allocation || device_releases==1,"platform device reaches final release exactly once");
 check(!descriptor || descriptor_releases==1,"descriptor reaches final release exactly once");
 /* Recover simulated baseline leaks without claiming that the driver released them. */
 free(pdev_allocation);free(descriptor);
}
static void execute(const char *name,int injected,bool bind,bool probe_fail,bool rebind,bool external_ref)
{
 reset_case(name,injected,bind,probe_fail);
 int ret=of_qcom_slim_ngd_register(&parent.dev,&ctrl);
 check(fault_hit ? ret<0 : ret==0,"registration returns the reached allocation error");
 if(ret){destroy_workqueue(ctrl.mwq);release_parent_resources();audit(false);return;}
 irq_enabled=true;
 if(external_ref)get_device(&pdev_allocation->dev);
 if(rebind){
  REQUIRE(pdev_allocation->dev.bound);struct qcom_slim_ngd *saved=ctrl.ngd;void *base=saved->base;int id=saved->id;
  qcom_slim_ngd_remove(pdev_allocation);pdev_allocation->dev.bound=false;
  check(desc_live && ctrl.ngd==saved,"child unbind retains its parent's descriptor");
  check(device_live && pdev_allocation->dev.registered,"child device remains registered across driver unbind");
  bool rebound=false;
  if(desc_live && ctrl.ngd==saved){probe_failure=false;rebound=qcom_slim_ngd_probe(pdev_allocation)==0;pdev_allocation->dev.bound=rebound;}
  check(rebound,"child driver can rebind using retained descriptor");
  check(desc_live && ctrl.ngd==saved && saved->base==base && saved->id==id,"rebind preserves address and instance identity");
 }
 if(ctrl.ngd && desc_live)qcom_slim_ngd_ctrl_remove(&parent);
 else{
  parent_cleanup_possible=false;
  /* Do not execute a NULL dereference in the unchanged baseline. */
  if(pdev_allocation->dev.registered)platform_device_del(pdev_allocation);
  destroy_workqueue(ctrl.mwq);
 }
 release_parent_resources();audit(external_ref);
}
int main(void)
{
 execute("parent-detach-bound",NONE,true,false,false,false);
 execute("parent-detach-unbound",NONE,false,false,false,false);
 execute("parent-detach-child-probe-failed",NONE,true,true,false,false);
 execute("child-unbind-rebind",NONE,true,false,true,false);
 execute("external-device-reference",NONE,true,false,false,true);
 execute("descriptor-allocation-error",DESC_ALLOC,true,false,false,false);
 execute("platform-allocation-error",DEVICE_ALLOC,true,false,false,false);
 execute("managed-action-allocation-error",ACTION_ALLOC,true,false,false,false);
 execute("override-error",OVERRIDE,true,false,false,false);
 execute("platform-add-error",DEVICE_ADD,true,false,false,false);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
