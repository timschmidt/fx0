/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical DMA/devres services; no kernel DMA, firmware, audio or device access. */
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define GFP_KERNEL 0
#define HZ 1000
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define BIT(n) (1U << (n))
#define DMA_PREP_INTERRUPT 1
#define DMA_DEV_TO_MEM 1
#define DMA_MEM_TO_DEV 2
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define EXPORT_SYMBOL_GPL(x)
#define SLIM_MIN_CLK_GEAR 1
#define SLIM_MAX_CLK_GEAR 10
#define REQUIRE(x) do { if(!(x)){fprintf(stderr,"fixture invariant %d: %s\n",__LINE__,#x);exit(3);} } while(0)
typedef uint32_t u32;
typedef uint8_t u8;
typedef uintptr_t dma_addr_t;
typedef int dma_cookie_t;
struct completion { int done; };
struct mutex { bool held; };
struct device { void *data; struct device *parent; bool pm_enabled,suspended; int usage; struct { bool memalloc_noio; int runtime_error; } power; };
struct platform_device { struct device dev; };
struct slim_device { struct device dev; };
struct slim_controller { struct device *dev; int id,min_cg,max_cg,laddr_ida,tid_idr,txn_lock; struct mutex lock; struct { struct mutex m_reconf; struct completion pause_comp; } sched; const char *name; };
struct dma_async_tx_descriptor { void (*callback)(void *); void *callback_param; int cookie; };
struct dma_chan { bool live, active; unsigned queued, direction; };
struct qcom_slim_ngd_ctrl;
/* ACTUAL_DEFINES */
/* ACTUAL_DMA_TYPE */
/* ACTUAL_STATE_TYPE */
struct qcom_slim_ngd { void *base; };
struct qcom_slim_ngd_ctrl {
 struct device *dev;
 struct qcom_slim_ngd *ngd;
 void *base;
 struct dma_chan *dma_rx_channel,*dma_tx_channel;
 struct qcom_slim_ngd_dma_desc rx_desc[QCOM_SLIM_NGD_DESC_NUM];
 struct qcom_slim_ngd_dma_desc txdesc[QCOM_SLIM_NGD_DESC_NUM];
 struct { struct completion qmi_comp; void *handle; } qmi;
 struct slim_controller ctrl;
 struct mutex ssr_lock;
 bool registered,child_ready,up_requested,pm_ref_held;
 int ngd_up_work;
 struct completion reconf;
 void *rx_base,*tx_base;
 dma_addr_t rx_phys_base,tx_phys_base;
 int tx_buf_lock,tx_tail,tx_head;
 u32 ver;
 enum qcom_slim_ngd_state state;
};
static struct qcom_slim_ngd_ctrl ctrl;
static struct device parent;
static struct platform_device child;
static struct qcom_slim_ngd ngd;
static u32 parent_regs[128],child_regs[128];
static struct dma_chan channels[128];
static struct dma_async_tx_descriptor descriptors[1024];
struct buffer { void *ptr; bool live,managed; size_t size; };
static struct buffer buffers[128];
static unsigned channel_count,buffer_count,descriptor_count,allocations,live_channels,preps,submits;
static unsigned premature_frees,unquiesced_release,double_release,invalid_channel,early_RX,enable_writes;
static unsigned cases,checks,failures;
static int ctrl_ida,client_error,registration_error,framework_result;
static bool allocated_ids[64];
static struct slim_device children[64];
static void *clients[64];
static unsigned child_count,ida_live,qmi_live,qmi_inits,qmi_exits,registrations,unregistrations,unowned_frees,resumes;
static unsigned busy_marks,pm_puts,powerups;
static unsigned fault_at;
static int fault_kind,power_request_error;
static long qmi_wait,reconf_wait;
static const char *name;
enum { NONE,RX_REQUEST,TX_REQUEST,RX_ALLOC,TX_ALLOC,RX_PREP,RX_SUBMIT };
static void check(bool ok,const char *what)
{checks++;if(!ok){failures++;fprintf(stderr,"%s: %s\n",name,what);}}
static bool fail(int kind,unsigned at) {return fault_kind==kind && fault_at==at;}
static unsigned direction_size(size_t size)
{ REQUIRE(size==QCOM_SLIM_NGD_DESC_NUM*SLIM_MSGQ_BUF_LEN || size==(QCOM_SLIM_NGD_DESC_NUM+1)*SLIM_MSGQ_BUF_LEN);return size==QCOM_SLIM_NGD_DESC_NUM*SLIM_MSGQ_BUF_LEN?DMA_DEV_TO_MEM:DMA_MEM_TO_DEV; }
static struct dma_chan *dma_request_chan(struct device *d,const char *which)
{
 REQUIRE(d==&parent);bool rx=!strcmp(which,"rx");REQUIRE(rx||!strcmp(which,"tx"));
 if(fail(rx?RX_REQUEST:TX_REQUEST,0))return (void *)(intptr_t)-EIO;
 REQUIRE(channel_count<128);struct dma_chan *c=&channels[channel_count++];c->live=true;c->direction=rx?DMA_DEV_TO_MEM:DMA_MEM_TO_DEV;live_channels++;return c;
}
static void dma_release_channel(struct dma_chan *c)
{
 REQUIRE(c>=channels && c<channels+128);
 if(!c->live){double_release++;return;}
 if(c->active||c->queued)unquiesced_release++;
 c->live=false;live_channels--;
}
static int dmaengine_terminate_sync(struct dma_chan *c)
{ REQUIRE(c>=channels && c<channels+128);if(!c->live)invalid_channel++;c->active=false;c->queued=0;return 0; }
static void *allocate(struct device *d,size_t size,dma_addr_t *physical,bool managed)
{
 REQUIRE(d==&parent);unsigned dir=direction_size(size);
 if(fail(dir==DMA_DEV_TO_MEM?RX_ALLOC:TX_ALLOC,0))return NULL;
 REQUIRE(buffer_count<128);void *p=calloc(1,size);REQUIRE(p);buffers[buffer_count++]=(struct buffer){p,true,managed,size};*physical=(uintptr_t)p;allocations++;return p;
}
static void *dma_alloc_coherent(struct device *d,size_t size,dma_addr_t *physical,int flags)
{return allocate(d,size,physical,false);}
static void *dmam_alloc_coherent(struct device *d,size_t size,dma_addr_t *physical,int flags)
{return allocate(d,size,physical,true);}
static bool live_buffer(void *p)
{for(unsigned i=0;i<buffer_count;i++)if(buffers[i].ptr==p)return buffers[i].live;return false;}
static void dma_free_coherent(struct device *d,size_t size,void *p,dma_addr_t phys)
{
 REQUIRE(d==&parent && (uintptr_t)p==phys);
 for(unsigned i=0;i<buffer_count;i++)if(buffers[i].ptr==p){
  REQUIRE(buffers[i].size==size);if(!buffers[i].live)double_release++;
  for(unsigned j=0;j<channel_count;j++)if(channels[j].live && channels[j].direction==direction_size(size) && (channels[j].queued||channels[j].active))premature_frees++;
  buffers[i].live=false;return;
 }REQUIRE(0);
}
static struct dma_async_tx_descriptor *dmaengine_prep_slave_single(struct dma_chan *c,dma_addr_t physical,size_t size,int direction,int flags)
{
 REQUIRE(c && c>=channels && c<channels+128 && direction==DMA_DEV_TO_MEM && flags==DMA_PREP_INTERRUPT);
 if(!c->live)invalid_channel++;
 unsigned at=preps++%QCOM_SLIM_NGD_DESC_NUM;if(fail(RX_PREP,at))return NULL;
 REQUIRE(descriptor_count<1024);return &descriptors[descriptor_count++];
}
static dma_cookie_t dmaengine_submit(struct dma_async_tx_descriptor *d)
{
 unsigned at=submits++%QCOM_SLIM_NGD_DESC_NUM;if(fail(RX_SUBMIT,at))return -EIO;
 REQUIRE(ctrl.dma_rx_channel);ctrl.dma_rx_channel->queued++;return 1;
}
static bool dma_submit_error(dma_cookie_t cookie) {return cookie<0;}
static void dma_async_issue_pending(struct dma_chan *c)
{
 REQUIRE(c && c>=channels && c<channels+128);if(!c->live)invalid_channel++;c->active=true;
 if(c->direction==DMA_DEV_TO_MEM && (!ctrl.dma_tx_channel || !ctrl.dma_tx_channel->live || !live_buffer(ctrl.tx_base)))early_RX++;
}
#define spin_lock_irqsave(lock,flags) do { (flags)=0; REQUIRE(!*(lock));*(lock)=1; } while(0)
#define spin_unlock_irqrestore(lock,flags) do { REQUIRE(*(lock) && (flags)==0);*(lock)=0; } while(0)
static void qcom_slim_ngd_rx_msgq_cb(void *data) {(void)data;}
static int qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *c);
/* ACTUAL_DMA */
static u32 readl_relaxed(void *p) {return *(u32 *)p;}
static void writel_relaxed(u32 value,void *p)
{ if(p==ngd.base && (value&NGD_CFG_ENABLE))enable_writes++;*(u32 *)p=value; }
static long wait_for_completion_timeout(struct completion *c,unsigned long timeout)
{REQUIRE(timeout==HZ);return c==&ctrl.qmi.qmi_comp?qmi_wait:reconf_wait;}
static void reinit_completion(struct completion *c) {c->done=0;}
static int qcom_slim_qmi_power_request(struct qcom_slim_ngd_ctrl *c,bool on)
{REQUIRE(c==&ctrl && on);powerups++;return power_request_error;}
/* ACTUAL_POWER */


static void mutex_init(struct mutex *m) {m->held=false;}
static void mutex_lock(struct mutex *m) {REQUIRE(!m->held);m->held=true;}
static void mutex_unlock(struct mutex *m) {REQUIRE(m->held);m->held=false;}
static void init_completion(struct completion *c) {c->done=0;}
static void complete(struct completion *c) {c->done++;}
static void ida_init(int *p) {*p=0;}
static void idr_init(int *p) {*p=0;}
static void spin_lock_init(int *p) {*p=0;}
static int ida_alloc(int *id,int flags)
{
 REQUIRE(id==&ctrl_ida);registrations++;if(registration_error)return registration_error;
 for(unsigned i=0;i<64;i++)if(!allocated_ids[i]){allocated_ids[i]=true;ida_live++;return i;}REQUIRE(0);return -ENOSPC;
}
static void ida_free(int *id,int n)
{REQUIRE(id==&ctrl_ida && n>=0 && n<64);unregistrations++;if(!allocated_ids[n])unowned_frees++;else{allocated_ids[n]=false;ida_live--;}}
static void of_register_slim_devices(struct slim_controller *c) {REQUIRE(c==&ctrl.ctrl);child_count+=2;REQUIRE(child_count<=64);}
static struct slim_device *to_slim_device(struct device *d) {return (void *)d;}
static void device_unregister(struct device *d) {REQUIRE(child_count);child_count--;}
static int device_for_each_child(struct device *d,void *data,int (*fn)(struct device *,void *))
{REQUIRE(d==&child.dev);unsigned n=child_count;for(unsigned i=n;i>0;i--)fn(&children[i-1].dev,data);return 0;}
/* ACTUAL_CORE */
static void *dev_get_drvdata(struct device *d) {return d->data;}
static void *platform_get_drvdata(struct platform_device *p) {return p->dev.data;}
static bool pm_runtime_enabled(struct device *d) {return d->pm_enabled;}
static bool pm_runtime_suspended(struct device *d) {return d->suspended;}
static void pm_runtime_mark_last_busy(struct device *d) {REQUIRE(d==&child.dev);busy_marks++;}
static void pm_runtime_put(struct device *d) {REQUIRE(d==&child.dev);d->usage--;pm_puts++;}
static void pm_runtime_put_noidle(struct device *d) {REQUIRE(d==&child.dev);d->usage--;}
/* ACTUAL_RESUME */
static unsigned memalloc_noio_save(void) {return 1;}
static void memalloc_noio_restore(unsigned flag) {REQUIRE(flag==1);}
static int __rpm_callback(int (*fn)(struct device *),struct device *d) {return fn(d);}
/* ACTUAL_PM_CALLBACK */
static int pm_runtime_resume(struct device *d)
{
 resumes++;if(d->power.runtime_error)return -EINVAL;
 if(framework_result<0)return framework_result;
 int ret=rpm_callback(qcom_slim_ngd_runtime_resume,d);
 if(!ret)d->suspended=false;
 return !ret && framework_result>0?framework_result:ret;
}
static int qcom_slim_qmi_init(struct qcom_slim_ngd_ctrl *c,bool master)
{
 REQUIRE(c==&ctrl && !master);qmi_inits++;if(client_error)return client_error;
 for(unsigned i=0;i<64;i++)if(!clients[i]){clients[i]=calloc(1,1);REQUIRE(clients[i]);c->qmi.handle=clients[i];qmi_live++;return 0;}REQUIRE(0);return -ENOMEM;
}
static void qcom_slim_qmi_exit(struct qcom_slim_ngd_ctrl *c)
{
 REQUIRE(c==&ctrl);if(!c->qmi.handle)return;
 for(unsigned i=0;i<64;i++)if(clients[i]==c->qmi.handle){free(clients[i]);clients[i]=NULL;c->qmi.handle=NULL;qmi_live--;qmi_exits++;return;}REQUIRE(0);
}
/* ACTUAL_ENABLE */
static void cancel_work_sync(void *work) {REQUIRE(work==&ctrl.ngd_up_work && !ctrl.ssr_lock.held);}
static void pm_runtime_dont_use_autosuspend(struct device *d) {REQUIRE(d==&child.dev);}
static void pm_runtime_disable(struct device *d) {d->pm_enabled=false;}
static void qcom_slim_ngd_qmi_svc_event_deinit(void *q) {REQUIRE(q==&ctrl.qmi);}
/* ACTUAL_REMOVE */
static void fixture_reset(const char *label,unsigned mode)
{
 for(unsigned i=0;i<buffer_count;i++)free(buffers[i].ptr);
 for(unsigned i=0;i<64;i++){free(clients[i]);clients[i]=NULL;}
 memset(&ctrl,0,sizeof(ctrl));memset(&child,0,sizeof(child));memset(channels,0,sizeof(channels));memset(buffers,0,sizeof(buffers));memset(parent_regs,0,sizeof(parent_regs));memset(child_regs,0,sizeof(child_regs));memset(allocated_ids,0,sizeof(allocated_ids));
 channel_count=buffer_count=descriptor_count=allocations=live_channels=preps=submits=0;
 premature_frees=unquiesced_release=double_release=invalid_channel=early_RX=enable_writes=0;
 child_count=ida_live=qmi_live=qmi_inits=qmi_exits=registrations=unregistrations=unowned_frees=resumes=busy_marks=pm_puts=powerups=0;
 client_error=registration_error=framework_result=fault_kind=power_request_error=0;fault_at=0;qmi_wait=reconf_wait=1;
 ctrl.dev=&parent;ctrl.base=parent_regs;ngd.base=child_regs;ctrl.ngd=&ngd;ctrl.state=QCOM_SLIM_NGD_CTRL_DOWN;
 child.dev.data=&ctrl;child.dev.parent=&parent;child.dev.pm_enabled=mode&1;child.dev.suspended=mode&2;child.dev.usage=1;
 ctrl.ctrl.dev=&child.dev;ctrl.child_ready=ctrl.up_requested=ctrl.pm_ref_held=true;name=label;cases++;
}
static int enable(bool on)
{mutex_lock(&ctrl.ssr_lock);int ret=qcom_slim_ngd_enable(&ctrl,on);mutex_unlock(&ctrl.ssr_lock);return ret;}
static void finish(void)
{
 qcom_slim_ngd_remove(&child);
 check(!qmi_live && !ctrl.qmi.handle,"all QMI client ownership released at removal");
 check(!ida_live && !child_count && !ctrl.registered,"controller and children removed exactly once");
 check(!child.dev.usage && !ctrl.pm_ref_held,"driver bootstrap PM reference balanced at removal");
 check(!live_channels && !ctrl.dma_rx_channel && !ctrl.dma_tx_channel,"all channel sessions closed at removal");
 check(!premature_frees && !unquiesced_release && !invalid_channel && !double_release,"DMA setup and close preserve ordering");
 check(!unowned_frees && !ctrl.ssr_lock.held,"no unowned controller release or held SSR lock");
 unsigned unmanaged=0;for(unsigned i=0;i<buffer_count;i++)if(buffers[i].live){if(buffers[i].managed)buffers[i].live=false;else unmanaged++;}
 check(!unmanaged,"remaining buffers released by parent devres service");
}
static void live(void)
{
 check(ctrl.registered && ida_live==1 && child_count==2,"one successful controller enumeration");
 check(qmi_live==1 && ctrl.qmi.handle,"one owned QMI client");
 check(child.dev.usage==0 && !ctrl.pm_ref_held && pm_puts==1,"registration consumes exactly one bootstrap reference");
 check(ctrl.state==QCOM_SLIM_NGD_CTRL_AWAKE,"successful wake state is AWAKE");
 check(live_channels==2 && !early_RX,"complete TX-ready DMA pair");
}
enum { REQUEST_ERROR=7,QMI_TIMEOUT,CAP_TIMEOUT,FRAMEWORK_ERROR };
static int apply_fault(int kind,unsigned at,int error)
{
 fault_kind=kind<=RX_SUBMIT?kind:NONE;fault_at=at;
 if(kind==REQUEST_ERROR){power_request_error=error;return error;}
 if(kind==QMI_TIMEOUT){qmi_wait=0;return -EREMOTEIO;}
 if(kind==CAP_TIMEOUT){reconf_wait=0;return -ETIMEDOUT;}
 if(kind==FRAMEWORK_ERROR){framework_result=error;return error;}
 return kind==RX_ALLOC||kind==TX_ALLOC?-ENOMEM:kind==RX_PREP?-EINVAL:-EIO;
}
static void clear_fault(void)
{fault_kind=NONE;power_request_error=framework_result=0;qmi_wait=reconf_wait=1;preps=submits=0;}
static void failure_case(unsigned mode,int kind,unsigned at,int error,bool registered)
{
 char label[96];snprintf(label,sizeof(label),"%s-mode%u-fault%d-at%u-error%d",registered?"registered":"initial",mode,kind,at,error);fixture_reset(label,mode);
 if(registered){check(!enable(true),"initial registration succeeds");qcom_slim_ngd_exit_dma(&ctrl);ctrl.state=kind==QMI_TIMEOUT?QCOM_SLIM_NGD_CTRL_DOWN:QCOM_SLIM_NGD_CTRL_ASLEEP;child.dev.suspended=mode&2;}
 void *owned=ctrl.qmi.handle;unsigned prior_puts=pm_puts,prior_busy=busy_marks,prior_reg=registrations,prior_inits=qmi_inits;
 unsigned prior_allocations=allocations;
 int expected=apply_fault(kind,at,error);bool framework=mode==3;
 if(registered && (kind==RX_ALLOC || kind==TX_ALLOC)){
  check(!enable(true),"registered wake reuses existing buffers despite allocation fault injection");live();
  check(allocations==prior_allocations && ctrl.qmi.handle==owned,"registered wake needs no new buffer or client allocation");
  check(pm_puts==prior_puts && registrations==prior_reg,"registered wake preserves registration and PM accounting");finish();return;
 }
 if(framework && kind!=FRAMEWORK_ERROR && expected==-EACCES)expected=-EAGAIN;
 check(enable(true)==expected,"resume error reaches enable caller");
 check(pm_puts==prior_puts && busy_marks==prior_busy,"failed wake does not mark successful registration or drop PM reference");
 check(registrations==prior_reg,"failed wake never attempts controller registration");
 if(registered){
  check(ctrl.registered && ida_live==1 && child_count==2,"failed registered wake retains existing controller/children");
  check(ctrl.qmi.handle==owned && qmi_live==1 && qmi_inits==prior_inits,"failed registered wake retains its existing QMI client");
  check(child.dev.usage==0 && !ctrl.pm_ref_held,"registered wake failure takes no bootstrap reference");
 }else{
  check(!ctrl.registered && !ida_live && !child_count,"failed initial wake exposes no controller/children");
  check(!ctrl.qmi.handle && !qmi_live,"failed initial wake releases the newly initialized QMI client");
  check(child.dev.usage==1 && ctrl.pm_ref_held,"failed initial wake retains bootstrap ownership for retry/removal");
 }
 if(kind!=FRAMEWORK_ERROR)check(ctrl.state!=QCOM_SLIM_NGD_CTRL_AWAKE,"failed power-up never reports AWAKE");
 bool latched=PM_CALLBACK_LATCHES_ERRORS && framework && kind!=FRAMEWORK_ERROR && expected!=-EAGAIN && expected!=-EBUSY;
 clear_fault();int retry=enable(true);
 if(latched){
  check(retry==-EINVAL,"cached LTS PM latch requires separate recovery before retry");
  check(registered?ctrl.qmi.handle==owned:!ctrl.qmi.handle,"blocked retry preserves correct QMI ownership");
  check(pm_puts==prior_puts && registrations==prior_reg,"latched retry cannot register or consume bootstrap");
 }else{
  check(!retry,"retry succeeds after recoverable error");live();
  check(qmi_inits==(registered?1U:2U),"retry reuses registered client or reacquires released initial client");
 }
 finish();
}
int main(void)
{
 for(unsigned mode=0;mode<4;mode++)for(unsigned registered=0;registered<2;registered++){
  for(int kind=RX_REQUEST;kind<=TX_ALLOC;kind++)failure_case(mode,kind,0,-EIO,registered);
  for(int kind=RX_PREP;kind<=RX_SUBMIT;kind++)for(unsigned at=0;at<QCOM_SLIM_NGD_DESC_NUM;at++)failure_case(mode,kind,at,-EIO,registered);
  const int errors[]={-EIO,-ENOMEM,-EBUSY,-EAGAIN,-EACCES,-517};
  for(unsigned n=0;n<sizeof(errors)/sizeof(errors[0]);n++)failure_case(mode,REQUEST_ERROR,0,errors[n],registered);
  failure_case(mode,QMI_TIMEOUT,0,-EREMOTEIO,registered);failure_case(mode,CAP_TIMEOUT,0,-ETIMEDOUT,registered);
  if(mode==3)failure_case(mode,FRAMEWORK_ERROR,0,-EINPROGRESS,registered);
 }
 for(unsigned mode=0;mode<4;mode++){
  char label[80];snprintf(label,sizeof(label),"duplicate-UP-and-asleep-wake-mode%u",mode);fixture_reset(label,mode);
  check(!enable(true)&&!enable(true)&&!enable(true),"repeated successful UP accepted");live();check(qmi_inits==1 && registrations==1,"duplicates reuse one client/controller");
  qcom_slim_ngd_exit_dma(&ctrl);ctrl.state=QCOM_SLIM_NGD_CTRL_ASLEEP;child.dev.suspended=mode&2;
  check(!enable(true),"registered asleep wake succeeds");live();check(qmi_inits==1 && registrations==1,"registered wake reuses ownership");finish();
 }
 for(unsigned noio=0;noio<2;noio++){
  char label[80];snprintf(label,sizeof(label),"positive-framework-success-noio%u",noio);fixture_reset(label,3);child.dev.power.memalloc_noio=noio;framework_result=1;
  check(!enable(true),"positive framework resume result is success");live();finish();
 }
 const int errors[]={-EIO,-ENOMEM,-517};
 for(unsigned n=0;n<sizeof(errors)/sizeof(errors[0]);n++){
  char label[80];snprintf(label,sizeof(label),"client-initialization-error%d",errors[n]);fixture_reset(label,3);client_error=errors[n];
  check(enable(true)==errors[n],"QMI initialization errno preserved");check(!resumes && !registrations && child.dev.usage==1,"QMI failure precedes wake/registration");finish();
 }
 for(unsigned n=0;n<sizeof(errors)/sizeof(errors[0]);n++){
  char label[80];snprintf(label,sizeof(label),"controller-registration-error%d",errors[n]);fixture_reset(label,3);registration_error=errors[n];
  check(enable(true)==errors[n],"registration errno preserved");check(!qmi_live && !ida_live && child.dev.usage==1 && ctrl.pm_ref_held,"registration failure releases only new client and retains bootstrap");
  registration_error=0;check(!enable(true),"registration retry succeeds");live();finish();
 }
 for(int state=QCOM_SLIM_NGD_CTRL_ASLEEP;state<=QCOM_SLIM_NGD_CTRL_DOWN;state++){
  char label[80];snprintf(label,sizeof(label),"direct-runtime-callback-state%d",state);fixture_reset(label,3);check(!qcom_slim_qmi_init(&ctrl,false),"fixture supplies one client");ctrl.state=state;power_request_error=-EIO;
  check(qcom_slim_ngd_runtime_resume(&child.dev)==-EIO,"runtime callback returns actual power-up error");check(ctrl.state==(enum qcom_slim_ngd_state)state,"failed DOWN/ASLEEP callback retains restart state");finish();
 }
 fixture_reset("runtime-without-QMI",3);check(!qcom_slim_ngd_runtime_resume(&child.dev),"pre-discovery runtime callback remains a no-op");check(!allocations && !channel_count,"no-QMI callback acquires no DMA");finish();
 fixture_reset("remove-after-first-power-failure",3);power_request_error=-EIO;check(enable(true)==-EIO,"first failure visible before removal");finish();
 for(unsigned i=0;i<buffer_count;i++)free(buffers[i].ptr);
 for(unsigned i=0;i<64;i++)free(clients[i]);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u,\"PM_callback_latches_errors\":%s}\n",cases,checks,failures,PM_CALLBACK_LATCHES_ERRORS?"true":"false");return 0;
}
