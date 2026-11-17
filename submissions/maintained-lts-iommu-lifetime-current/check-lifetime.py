# SPDX-License-Identifier: GPL-2.0-only
"""Extract actual probe-tail/remove and LTS cleanup helpers into owned models.

The pre-tail allocations/getters, devres list container, device creation,
client release, PM transitions and hardware are explicit service models.
An unavailable parent access is intercepted as a contract failure before a
real NULL dereference. Linux driver-core registration/concurrency is not run.
"""
from pathlib import Path
import argparse,hashlib,json,os,re,resource,subprocess
P=Path(__file__).resolve().parent;ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--kernel',required=True,type=Path);ap.add_argument('--driver',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--expected-wrong',required=True,type=int);a=ap.parse_args();a.output.mkdir(mode=0o700);resource.setrlimit(resource.RLIMIT_CORE,(0,0));texts={f:(a.kernel/f).read_text() for f in ['drivers/base/power/runtime.c','drivers/of/platform.c','drivers/base/dd.c','drivers/base/devres.c','drivers/iommu/iommu.c']};source=a.driver.read_text();bindings={}
def function(text,name):
 m=re.search(r'^(?:static )?(?:int|void) '+name+r'\([^;{}]*\)\n\{',text,re.M);assert m,name;end=text.index('{',m.start())+1;depth=1
 while depth:depth+=(text[end]=='{')-(text[end]=='}');end+=1
 body=text[m.start():end];bindings[name]=hashlib.sha256(body.encode()).hexdigest();return body
probe=function(source,'qcom_iommu_device_probe');tail=probe[probe.index('\tplatform_set_drvdata(pdev, qcom_iommu);'):];bindings['probe_tail']=hashlib.sha256(tail.encode()).hexdigest()
parts=[function(texts['drivers/base/power/runtime.c'],x) for x in ['pm_runtime_disable_action','devm_pm_runtime_enable']]
parts += [function(texts['drivers/of/platform.c'],x) for x in ['devm_of_platform_populate_release','devm_of_platform_populate','devm_of_platform_depopulate']]
parts += [function(texts['drivers/base/dd.c'],'device_unbind_cleanup'),function(source,'qcom_iommu_ctx_remove')]
assert 'list_for_each_entry_safe_reverse' in function(texts['drivers/base/devres.c'],'release_nodes')
# Exact public devres_release dispatch; the container removal remains modeled.
parts.insert(0,function(texts['drivers/base/devres.c'],'devres_release'))
shim=r'''
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <setjmp.h>
#define GFP_KERNEL 0
#define SMMU_INTR_SEL_NS 0x2000
#define unlikely(x) (x)
#define dev_err(...) ((void)0)
#define WARN_ON(x) assert(!(x))
struct device;
typedef void (*dr_release_t)(struct device *,void *);
typedef int (*dr_match_t)(struct device *,void *,void *);
struct resource {dr_release_t release;_Alignas(max_align_t) unsigned char data[];};
struct pm_domain {void (*dismiss)(struct device *);};
struct device {struct device *parent;void *data;struct resource *resources[8];unsigned count;void *dma_range_map;struct {bool detach_power_off;} power;struct pm_domain *pm_domain;bool enabled;};
struct platform_device {struct device dev;};
struct qcom_iommu_ctx {unsigned asid;};
struct iommu_device {int unused;};
struct qcom_iommu_dev {struct iommu_device iommu;void *local_base;struct qcom_iommu_ctx *ctxs[3];};
static struct platform_device children[3];
static struct qcom_iommu_dev *owner;
static unsigned child_count,live_children,clients,violations,removed_children,pm_disables,forced,unregisters,sysfs_removes;
static bool alive,registered,sysfs_added,jump_active;
static int fault;
static jmp_buf invalid_parent;
static void qcom_iommu_ctx_remove(struct platform_device *);
static void device_unbind_cleanup(struct device *);
static struct resource *res_header(void *p) {return (void*)((char*)p - offsetof(struct resource,data));}
static void *devres_alloc(dr_release_t release,size_t size,int flags) {
 (void)flags;if(fault==2)return NULL;struct resource *r=calloc(1,sizeof(*r)+size);assert(r);r->release=release;return r->data;
}
static void devres_add(struct device *d,void *p) {assert(d->count<8);d->resources[d->count++]=res_header(p);}
static void devres_free(void *p) {free(res_header(p));}
static void *devres_remove(struct device *d,dr_release_t release,dr_match_t match,void *data) {
 for(unsigned i=d->count;i>0;i--){struct resource *r=d->resources[i-1];if(r->release==release&&match(d,r->data,data)){memmove(&d->resources[i-1],&d->resources[i],(d->count-i)*sizeof(r));d->count--;return r->data;}}return NULL;
}
static void devres_release_all(struct device *d) {while(d->count){struct resource *r=d->resources[--d->count];r->release(d,r->data);free(r);}}
struct action {void (*function)(void *);void *data;};
static void action_release(struct device *d,void *p) {(void)d;struct action *a=p;a->function(a->data);}
static int devm_add_action_or_reset(struct device *d,void (*f)(void *),void *p) {
 if(fault==1){f(p);return -ENOMEM;}struct resource *r=calloc(1,sizeof(*r)+sizeof(struct action));assert(r);r->release=action_release;*(struct action*)r->data=(struct action){f,p};devres_add(d,r->data);return 0;
}
static void pm_runtime_enable(struct device *d) {d->enabled=true;}
static void pm_runtime_disable(struct device *d) {if(live_children||clients)violations++;d->enabled=false;pm_disables++;}
static void pm_runtime_dont_use_autosuspend(void *d) {(void)d;}
static void *dev_get_drvdata(struct device *d) {
 if(d->parent==NULL&&(!d->data||!alive)&&jump_active){violations++;longjmp(invalid_parent,1);}return d->data;
}
static void platform_set_drvdata(struct platform_device *p,void *data) {p->dev.data=data;}
static void *platform_get_drvdata(struct platform_device *p) {return p->dev.data;}
static void dev_set_drvdata(struct device *d,void *data) {d->data=data;}
static int of_platform_populate(void *node,void *matches,void *lookup,struct device *d) {
 (void)node;(void)matches;(void)lookup;assert(d->enabled&&d->data==owner&&alive);
 for(unsigned i=0;i<child_count;i++){children[i]=(struct platform_device){.dev.parent=d};struct qcom_iommu_ctx *ctx=calloc(1,sizeof(*ctx));assert(ctx);ctx->asid=i;children[i].dev.data=ctx;owner->ctxs[i]=ctx;live_children++;}return 0;
}
static void of_platform_depopulate(struct device *d) {
 for(unsigned i=child_count;i>0;i--){struct platform_device *child=&children[i-1];if(!child->dev.data)continue;if(!d->enabled||!alive)violations++;struct qcom_iommu_ctx *ctx=child->dev.data;
  jump_active=true;if(!setjmp(invalid_parent))qcom_iommu_ctx_remove(child);jump_active=false;
  child->dev.data=NULL;free(ctx);live_children--;removed_children++;
 }
}
static int devm_of_platform_match(struct device *d,void *res,void *data) {(void)d;return res&&*(struct device**)res==data;}
static int pm_runtime_resume_and_get(struct device *d) {assert(d->enabled);return fault==5?-EIO:0;}
static void pm_runtime_put_sync(struct device *d) {assert(d->enabled);}
static void writel_relaxed(unsigned value,void *p) {assert(value==0xffffffff&&p==(char*)owner->local_base+SMMU_INTR_SEL_NS);}
static int iommu_device_sysfs_add(struct iommu_device *i,struct device *d,void *group,const char *name) {(void)i;(void)d;(void)group;(void)name;if(fault==3)return -ENOMEM;sysfs_added=true;return 0;}
static void iommu_device_sysfs_remove(struct iommu_device *i) {(void)i;assert(sysfs_added);sysfs_added=false;sysfs_removes++;}
static int qcom_iommu_ops;
static int iommu_device_register(struct iommu_device *i,int *ops,struct device *d) {(void)i;(void)ops;(void)d;if(fault==4)return -EIO;registered=true;clients=1;return 0;}
static void iommu_device_unregister(struct iommu_device *i) {
 (void)i;assert(registered);if(!alive||!children[0].dev.parent->data||!children[0].dev.parent->enabled||!owner->ctxs[0])violations++;clients=0;registered=false;unregisters++;
}
static int pm_runtime_force_suspend(struct device *d) {forced++;pm_runtime_disable(d);return 0;}
static const char *dev_name(struct device *d) {(void)d;return "owned-model";}
static void arch_teardown_dma_ops(struct device *d) {(void)d;}
#define kfree(p) free(p)
static void device_set_driver(struct device *d,void *driver) {(void)d;(void)driver;}
static void dev_pm_domain_detach(struct device *d,bool off) {(void)d;(void)off;}
static void pm_runtime_reinit(struct device *d) {d->enabled=false;}
static void dev_pm_set_driver_flags(struct device *d,unsigned flags) {(void)d;(void)flags;}
static void free_owner(struct device *d,void *data) {(void)d;assert(*(void**)data==owner);if(live_children||registered)violations++;alive=false;free(owner);owner=NULL;}
'''
# devm_of_platform_populate accesses dev->of_node. It is a modeled DT root.
shim=shim.replace('struct device *parent;void *data;','struct device *parent;void *of_node;void *data;')
code=shim+'\n'+'\n'.join(parts)+'\nstatic int probe_tail(struct platform_device *pdev,struct qcom_iommu_dev *qcom_iommu) {struct device *dev=&pdev->dev;int ret;\n'+tail+'\n'+function(source,'qcom_iommu_device_remove')
main=r'''
int main(void) {
 unsigned cases=0,wrong=0;
 bool managed=MANAGED;
 for(unsigned n=1;n<=3;n++)for(unsigned local=0;local<2;local++)for(int f=0;f<6;f++) {
  if(f==1&&!managed)continue;
  child_count=n;live_children=clients=violations=removed_children=pm_disables=forced=unregisters=sysfs_removes=0;alive=true;registered=sysfs_added=jump_active=false;fault=f;memset(children,0,sizeof(children));
  owner=calloc(1,sizeof(*owner));assert(owner);static unsigned char mmio[0x3000];owner->local_base=local?mmio:NULL;struct platform_device p={0};
  // Model a successful pre-tail managed allocation, before PM/child resources.
  struct resource *allocation=calloc(1,sizeof(*allocation)+sizeof(void*));assert(allocation);allocation->release=free_owner;*(void**)allocation->data=owner;devres_add(&p.dev,allocation->data);
  int ret=probe_tail(&p,owner);int expected=(f==1||f==2||f==3)?-ENOMEM:(f==4||(f==5&&local))?-EIO:0;assert(ret==expected);
  if(!ret)qcom_iommu_device_remove(&p);
  device_unbind_cleanup(&p.dev);
  bool bad=violations||owner||alive||registered||sysfs_added||live_children||clients||p.dev.data||p.dev.count||p.dev.enabled;
  if(f!=1&&f!=2)bad|=removed_children!=n;
  wrong+=bad;cases++;
 }
 printf("{\"cases\":%u,\"wrong\":%u}\n",cases,wrong);return 0;
}
'''.replace('MANAGED','true' if 'devm_pm_runtime_enable(dev)' in tail else 'false')
model=a.output/'model.c';model.write_text(code+'\n'+main);binary=a.output/'model';env=os.environ|{'TMPDIR':str(a.output),'ASAN_OPTIONS':'detect_leaks=1:halt_on_error=1','UBSAN_OPTIONS':'halt_on_error=1'}
r=subprocess.run(['clang-21','-std=gnu11','-O1','-g','-Wall','-Wextra','-Werror','-Wno-unused-function','-Wno-unused-parameter','-fsanitize=address,undefined','-fno-sanitize-recover=all',str(model),'-o',str(binary)],env=env,capture_output=True,text=True);(a.output/'compile.stdout').write_text(r.stdout);(a.output/'compile.stderr').write_text(r.stderr);assert r.returncode==0 and not r.stderr,r.stderr
r=subprocess.run([str(binary)],env=env,capture_output=True,text=True,timeout=30);(a.output/'run.stdout').write_text(r.stdout);(a.output/'run.stderr').write_text(r.stderr);assert r.returncode==0 and not r.stderr,(r.returncode,r.stderr);result=json.loads(r.stdout);assert result['wrong']==a.expected_wrong,result
j=dict(passed=True,**result,source_SHA256=hashlib.sha256(source.encode()).hexdigest(),bindings=bindings,core_files_SHA256={f:hashlib.sha256(t.encode()).hexdigest() for f,t in texts.items()},model_SHA256=hashlib.sha256(model.read_bytes()).hexdigest(),normal_LSan_and_failfast_ASan_UBSan=True,pre_tail_allocation_and_list_container_PM_client_services_modeled=True,unavailable_parent_access_intercepted_before_NULL_dereference=True,full_kernel_driver_core_or_hardware_execution=False,phone_access=False);(a.output/'qualification.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(dict(passed=True,**result)))
