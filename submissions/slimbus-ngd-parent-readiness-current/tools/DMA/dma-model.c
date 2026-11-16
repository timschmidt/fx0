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
#define REQUIRE(x) do { if(!(x)){fprintf(stderr,"fixture invariant %d: %s\n",__LINE__,#x);exit(3);} } while(0)
typedef uint32_t u32;
typedef uint8_t u8;
typedef uintptr_t dma_addr_t;
typedef int dma_cookie_t;
struct completion { int done; };
struct device { int unused; };
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
 struct { struct completion qmi_comp; } qmi;
 struct completion reconf;
 void *rx_base,*tx_base;
 dma_addr_t rx_phys_base,tx_phys_base;
 int tx_buf_lock,tx_tail,tx_head;
 u32 ver;
 enum qcom_slim_ngd_state state;
};
static struct qcom_slim_ngd_ctrl ctrl;
static struct device parent;
static struct qcom_slim_ngd ngd;
static u32 parent_regs[128],child_regs[128];
static struct dma_chan channels[128];
static struct dma_async_tx_descriptor descriptors[1024];
struct buffer { void *ptr; bool live,managed; size_t size; };
static struct buffer buffers[128];
static unsigned channel_count,buffer_count,descriptor_count,allocations,live_channels,preps,submits;
static unsigned premature_frees,unquiesced_release,double_release,invalid_channel,early_RX,enable_writes;
static unsigned cases,checks,failures;
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
{REQUIRE(c==&ctrl && on);return power_request_error;}
/* ACTUAL_POWER */
/* ACTUAL_SETUP_ADAPTER */
static void fixture_reset(const char *label,int kind,unsigned at)
{
 for(unsigned i=0;i<buffer_count;i++)free(buffers[i].ptr);
 memset(&ctrl,0,sizeof(ctrl));memset(channels,0,sizeof(channels));memset(buffers,0,sizeof(buffers));memset(parent_regs,0,sizeof(parent_regs));memset(child_regs,0,sizeof(child_regs));
 channel_count=buffer_count=descriptor_count=allocations=live_channels=preps=submits=0;
 premature_frees=unquiesced_release=double_release=invalid_channel=early_RX=enable_writes=0;
 fault_kind=kind;fault_at=at;power_request_error=0;qmi_wait=reconf_wait=1;
 ctrl.dev=&parent;ctrl.base=parent_regs;ngd.base=child_regs;ctrl.ngd=&ngd;ctrl.state=QCOM_SLIM_NGD_CTRL_DOWN;name=label;cases++;
}
static void active_pair(void)
{
 check(live_channels==2 && ctrl.dma_rx_channel && ctrl.dma_tx_channel,"both DMA channels live");
 check(live_buffer(ctrl.rx_base)&&live_buffer(ctrl.tx_base),"both message buffers live");
 check(ctrl.dma_rx_channel && ctrl.dma_rx_channel->queued==QCOM_SLIM_NGD_DESC_NUM,"all RX descriptors submitted");
 check(!early_RX,"TX resources ready before RX can queue master work");
}
static void audit_error(void)
{
 check(!live_channels,"failed setup releases every acquired DMA channel");
 check(!ctrl.dma_rx_channel && !ctrl.dma_tx_channel,"failed setup clears channel pointers");
 check(!premature_frees && !unquiesced_release,"queued DMA quiesced before release");
 check(!invalid_channel && !double_release,"no stale channel or duplicate release");
}
static void finish(void)
{
 qcom_slim_ngd_exit_dma(&ctrl);
 check(!live_channels && !ctrl.dma_rx_channel && !ctrl.dma_tx_channel,"final DMA teardown releases channels");
 check(!premature_frees && !unquiesced_release && !invalid_channel && !double_release,"channel cleanup preserves resource ordering");
 unsigned outside_parent=0;
 for(unsigned i=0;i<buffer_count;i++)if(buffers[i].live){if(buffers[i].managed)buffers[i].live=false;else outside_parent++;}
 check(!outside_parent,"all message buffer allocations belong to parent devres");
 /* Recover baseline leaks after audit; no real DMA or stale-memory access. */
}
int main(void)
{
 fixture_reset("setup-success",NONE,0);check(!setup(&ctrl),"setup succeeds");active_pair();check(enable_writes==1,"hardware enabled only after successful DMA setup");finish();
 for(int kind=RX_REQUEST;kind<=TX_ALLOC;kind++){
  char label[64];snprintf(label,sizeof(label),"allocation-error-%d",kind);fixture_reset(label,kind,0);
  check(qcom_slim_ngd_init_dma(&ctrl)==(kind==RX_ALLOC||kind==TX_ALLOC?-ENOMEM:-EIO),"DMA allocation error propagated");audit_error();
  fault_kind=NONE;check(!qcom_slim_ngd_init_dma(&ctrl),"retry after allocation error succeeds");active_pair();finish();
 }
 for(int kind=RX_PREP;kind<=RX_SUBMIT;kind++)for(unsigned at=0;at<QCOM_SLIM_NGD_DESC_NUM;at++){
  char label[64];snprintf(label,sizeof(label),"RX-error-%d-%u",kind,at);fixture_reset(label,kind,at);
  check(qcom_slim_ngd_init_dma(&ctrl)==(kind==RX_PREP?-EINVAL:-EIO),"descriptor prepare/submit error preserved");audit_error();
  fault_kind=NONE;preps=submits=0;check(!qcom_slim_ngd_init_dma(&ctrl),"retry after partial descriptor setup succeeds");active_pair();finish();
 }
 for(int kind=RX_REQUEST;kind<=TX_ALLOC;kind++)for(int retained=0;retained<2;retained++){
  char label[64];snprintf(label,sizeof(label),"power-setup-error-%d-retained-%d",kind,retained);fixture_reset(label,kind,0);if(retained)child_regs[NGD_STATUS/4]=NGD_LADDR;
  check(qcom_slim_ngd_power_up(&ctrl)<0,"power-up propagates DMA setup failure");
  check(!enable_writes,"failed DMA setup never enables NGD queues");audit_error();finish();
 }
 for(unsigned retained=0;retained<2;retained++){
  char label[64];snprintf(label,sizeof(label),"asleep-power-success-retained-%u",retained);fixture_reset(label,NONE,0);ctrl.state=QCOM_SLIM_NGD_CTRL_ASLEEP;if(retained)child_regs[NGD_STATUS/4]=NGD_LADDR;
  check(!qcom_slim_ngd_power_up(&ctrl),"asleep wake succeeds");active_pair();finish();
 }
 fixture_reset("persistent-RX-allocation-failure",RX_ALLOC,0);
 for(unsigned n=0;n<16;n++){check(qcom_slim_ngd_init_dma(&ctrl)==-ENOMEM,"persistent allocation failure remains visible");audit_error();}
 check(allocations<=1,"persistent failure retains at most one parent TX buffer");finish();
 fixture_reset("repeated-setup",NONE,0);check(!setup(&ctrl),"initial setup succeeds");void *rx=ctrl.rx_base,*tx=ctrl.tx_base;unsigned allocated=allocations,requested=channel_count;
 check(!setup(&ctrl),"repeat setup succeeds");active_pair();check(allocations==allocated && channel_count==requested,"repeat setup reuses live channels and buffers");finish();
 fixture_reset("suspend-resume-buffer-reuse",NONE,0);check(!setup(&ctrl),"initial setup succeeds");rx=ctrl.rx_base;tx=ctrl.tx_base;allocated=allocations;
 for(unsigned n=0;n<10;n++){qcom_slim_ngd_exit_dma(&ctrl);check(!setup(&ctrl),"new channel session succeeds");active_pair();}
 check(ctrl.rx_base==rx && ctrl.tx_base==tx && allocations==allocated,"all sessions reuse parent-owned buffers");finish();
 fixture_reset("capability-timeout-retry",NONE,0);reconf_wait=0;check(qcom_slim_ngd_power_up(&ctrl)==-ETIMEDOUT,"capability timeout preserved");allocated=allocations;requested=channel_count;reconf_wait=1;
 check(!qcom_slim_ngd_power_up(&ctrl),"power-up retry succeeds");check(allocations==allocated && channel_count==requested,"retry after capability timeout reuses prepared resources");active_pair();finish();
 fixture_reset("QMI-timeout-no-DMA",NONE,0);qmi_wait=0;check(qcom_slim_ngd_power_up(&ctrl)==-EREMOTEIO,"QMI timeout propagated");check(!channel_count && !allocations,"QMI timeout acquires no DMA");finish();
 fixture_reset("power-request-error-no-DMA",NONE,0);power_request_error=-EBUSY;check(qcom_slim_ngd_power_up(&ctrl)==-EBUSY,"power request error propagated");check(!channel_count && !allocations,"power request error acquires no DMA");finish();
 for(unsigned i=0;i<buffer_count;i++)free(buffers[i].ptr);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
