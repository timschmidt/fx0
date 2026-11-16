/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical DMA and completion tokens; completion addresses are never dereferenced. */
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define REQUIRE(x) do{if(!(x)){fprintf(stderr,"fixture invariant %d: %s\n",__LINE__,#x);exit(3);}}while(0)
typedef uint8_t u8;typedef uint16_t u16;typedef uint32_t u32;typedef uintptr_t dma_addr_t;typedef int dma_cookie_t;
#define HZ 100
#define DMA_MEM_TO_DEV 1
#define DMA_PREP_INTERRUPT 1
#define dev_err(...) ((void)0)
#define GENMASK(h,l) (((~0u)>>(31-(h)))&((~0u)<<(l)))
/* ACTUAL_DEFINES */
struct completion {unsigned unused;};
struct device {void *data;};
struct slim_controller {struct device *dev;};
struct dma_async_tx_descriptor {void (*callback)(void *);void *callback_param;dma_cookie_t cookie;unsigned index,len;};
struct qcom_slim_ngd_ctrl;
/* ACTUAL_TYPES */
struct mutex {pthread_mutex_t lock;};
struct qcom_slim_ngd_ctrl {struct device *dev;struct slim_controller ctrl;struct mutex tx_lock;pthread_mutex_t tx_buf_lock;struct qcom_slim_ngd_dma_desc txdesc[QCOM_SLIM_NGD_DESC_NUM];void *tx_base;dma_addr_t tx_phys_base;void *dma_tx_channel;int tx_head,tx_tail;};
static struct qcom_slim_ngd_ctrl ctrl;static struct device dev;
static u32 coherent[(QCOM_SLIM_NGD_DESC_NUM+1)*SLIM_MSGQ_BUF_LEN/4];
static struct dma_async_tx_descriptor transfers[QCOM_SLIM_NGD_DESC_NUM];
static bool busy[QCOM_SLIM_NGD_DESC_NUM];
static pthread_mutex_t coordination=PTHREAD_MUTEX_INITIALIZER;static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static _Thread_local unsigned caller;static _Thread_local bool tx_held,buf_held;
struct token {struct completion *address;bool done;};
struct call_state {bool live;struct token tokens[2];bool prep_fail,tid_fail,tx_timeout,ack_timeout;int slot,result;unsigned type;};
static struct call_state calls[2];
static bool locks_live,hold_wait,wait_entered,release_wait,second_attempt,hold_complete,complete_entered,release_complete,helper_waiting,call_done;
static unsigned prep_calls,submit_calls,issue_calls,stale_attempts,alias_attempts,lock_errors,tid_allocs,callback_calls,engine_cookie_clobbers,invalid_callback_attempts;
static u8 wire_trace[131072];static unsigned wire_length;
static uint64_t wire_hash=UINT64_C(14695981039346656037);
static unsigned cases,checks,failures;static const char *case_name;
static void check(bool ok,const char *message){checks++;if(!ok){failures++;fprintf(stderr,"%s: %s\n",case_name,message);}}
static void mutex_lock(struct mutex *m){REQUIRE(m==&ctrl.tx_lock);pthread_mutex_lock(&coordination);if(caller==1){second_attempt=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);REQUIRE(!pthread_mutex_lock(&m->lock));tx_held=true;}
static void mutex_unlock(struct mutex *m){REQUIRE(tx_held);tx_held=false;REQUIRE(!pthread_mutex_unlock(&m->lock));}
static void spin_take(pthread_mutex_t *m){REQUIRE(m==&ctrl.tx_buf_lock);int ret=pthread_mutex_trylock(m);if(ret==EBUSY){pthread_mutex_lock(&coordination);if(caller==0&&complete_entered){helper_waiting=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);REQUIRE(!pthread_mutex_lock(m));}else REQUIRE(!ret);buf_held=true;}
static void spin_drop(pthread_mutex_t *m){REQUIRE(buf_held);buf_held=false;REQUIRE(!pthread_mutex_unlock(m));}
#define spin_lock_irqsave(m,f) do{(f)=0;(void)(f);spin_take(m);}while(0)
#define spin_unlock_irqrestore(m,f) do{(void)(f);spin_drop(m);}while(0)
static void fixture_assert_lock(struct mutex *m){REQUIRE(m==&ctrl.tx_lock);if(!tx_held)lock_errors++;}
#define lockdep_assert_held(m) fixture_assert_lock(m)
static void register_completion(struct completion *p,unsigned which){REQUIRE(caller<2);calls[caller].tokens[which]=(struct token){p,false};}
#define DECLARE_COMPLETION_ONSTACK(n) struct completion n;register_completion(&n,!strcmp(#n,"done"))
static void complete(struct completion *p){
 REQUIRE(buf_held);pthread_mutex_lock(&coordination);complete_entered=true;pthread_cond_broadcast(&changed);
 while(hold_complete&&!release_complete)pthread_cond_wait(&changed,&coordination);
 bool found=false;for(unsigned i=0;i<2;i++)for(unsigned n=0;n<2;n++)if(calls[i].tokens[n].address==p){found=true;if(!calls[i].live)stale_attempts++;else calls[i].tokens[n].done=true;}
 if(!found)stale_attempts++;pthread_mutex_unlock(&coordination);
}
static void *dev_get_drvdata(struct device *d){return d->data;}
static int slim_alloc_txn_tid(struct slim_controller *s,struct slim_msg_txn *txn){REQUIRE(s==&ctrl.ctrl&&caller<2);tid_allocs++;if(calls[caller].tid_fail)return -ENOSPC;txn->tid=7;return 0;}
static struct dma_async_tx_descriptor *dmaengine_prep_slave_single(void *channel,dma_addr_t phys,int len,int direction,int flags){
 REQUIRE(caller<2&&channel==ctrl.dma_tx_channel&&direction==DMA_MEM_TO_DEV&&flags==DMA_PREP_INTERRUPT&&buf_held);prep_calls++;unsigned index=(phys-ctrl.tx_phys_base)/SLIM_MSGQ_BUF_LEN;REQUIRE(index<QCOM_SLIM_NGD_DESC_NUM&&len<=SLIM_MSGQ_BUF_LEN);calls[caller].slot=index;
 if(calls[caller].prep_fail)return NULL;if(busy[index])alias_attempts++;transfers[index]=(struct dma_async_tx_descriptor){.index=index,.len=len};return &transfers[index];
}
static dma_cookie_t dmaengine_submit(struct dma_async_tx_descriptor *d){REQUIRE(buf_held);submit_calls++;busy[d->index]=true;d->cookie=-999;const u8 *bytes=(const u8 *)ctrl.tx_base+d->index*SLIM_MSGQ_BUF_LEN;REQUIRE(wire_length+1+d->len<=sizeof(wire_trace));wire_trace[wire_length++]=d->len;memcpy(wire_trace+wire_length,bytes,d->len);wire_length+=d->len;for(unsigned n=0;n<d->len;n++){wire_hash^=bytes[n];wire_hash*=UINT64_C(1099511628211);}return 17;}
static void dma_async_issue_pending(void *channel){REQUIRE(channel==ctrl.dma_tx_channel&&buf_held);issue_calls++;if(transfers[calls[caller].slot].cookie!=-999)engine_cookie_clobbers++;}
/* ACTUAL_LOW */
static void invoke_callback(unsigned index){REQUIRE(index<QCOM_SLIM_NGD_DESC_NUM);if(!busy[index]){invalid_callback_attempts++;return;}callback_calls++;transfers[index].callback(transfers[index].callback_param);busy[index]=false;}
static unsigned long wait_for_completion_timeout(struct completion *p,unsigned long timeout){
 REQUIRE(caller<2&&timeout==HZ&&tx_held);struct call_state *c=&calls[caller];unsigned which=c->tokens[1].address==p;
 if(which){if(c->ack_timeout)return 0;c->tokens[1].done=true;return 1;}
 pthread_mutex_lock(&coordination);if(hold_wait&&caller==0){wait_entered=true;pthread_cond_broadcast(&changed);while(!release_wait)pthread_cond_wait(&changed,&coordination);}pthread_mutex_unlock(&coordination);
 if(c->tx_timeout)return 0;invoke_callback(c->slot);return c->tokens[0].done;
}
/* ACTUAL_MESSAGE_HELPERS */
/* ACTUAL_TX */
static void reset(const char *name,unsigned position){
 if(locks_live){REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));}
 memset(&ctrl,0,sizeof(ctrl));memset(coherent,0,sizeof(coherent));memset(transfers,0,sizeof(transfers));memset(busy,0,sizeof(busy));memset(calls,0,sizeof(calls));
 dev.data=&ctrl;ctrl.dev=ctrl.ctrl.dev=&dev;ctrl.tx_base=coherent;ctrl.tx_phys_base=0x1000;ctrl.dma_tx_channel=&ctrl;ctrl.tx_head=ctrl.tx_tail=position;
 REQUIRE(!pthread_mutex_init(&ctrl.tx_lock.lock,NULL));REQUIRE(!pthread_mutex_init(&ctrl.tx_buf_lock,NULL));locks_live=true;
 hold_wait=wait_entered=release_wait=second_attempt=hold_complete=complete_entered=release_complete=helper_waiting=call_done=false;
 prep_calls=submit_calls=issue_calls=stale_attempts=alias_attempts=lock_errors=tid_allocs=callback_calls=engine_cookie_clobbers=0;case_name=name;cases++;
}
static int transfer(unsigned id,unsigned type){
 caller=id;struct call_state *c=&calls[id];u8 data[16];for(unsigned n=0;n<16;n++)data[n]=0x10+n;
 struct slim_val_inf msg={.num_bytes=4,.wbuf=data};struct slim_msg_txn txn={.rl=8,.mt=SLIM_MSG_MT_SRC_REFERRED_USER,.mc=SLIM_USR_MC_REPORT_SATELLITE,.la=SLIM_LA_MGR,.dt=SLIM_MSG_DEST_LOGICALADDR,.msg=&msg,.tid=5,.ec=0x1234};
 if(type>=1&&type<=3){txn.mt=SLIM_MSG_MT_CORE;txn.mc=type==1?SLIM_MSG_MC_CONNECT_SOURCE:type==2?SLIM_MSG_MC_CONNECT_SINK:SLIM_MSG_MC_DISCONNECT_PORT;msg.num_bytes=2;txn.rl=6;}
 if(type==4){txn.mt=SLIM_MSG_MT_CORE;txn.mc=SLIM_MSG_MC_REQUEST_VALUE;txn.rl=11;}
 if(type==5){txn.mt=SLIM_MSG_MT_CORE;txn.mc=SLIM_MSG_MC_CHANGE_VALUE;txn.rl=10;}
 if(type==6){txn.dt=SLIM_MSG_DEST_BROADCAST;txn.rl=7;}
 if(type==7)txn.dt=SLIM_MSG_DEST_ENUMADDR;
 if(type==8){txn.mt=SLIM_MSG_MT_CORE;txn.mc=SLIM_MSG_MC_BEGIN_RECONFIGURATION;}
 if(type==9){msg.num_bytes=SLIM_MSGQ_BUF_LEN+1;txn.rl=SLIM_MSGQ_BUF_LEN+1;}
 pthread_mutex_lock(&coordination);c->live=true;pthread_mutex_unlock(&coordination);int ret=qcom_slim_ngd_xfer_msg(&ctrl.ctrl,&txn);
 pthread_mutex_lock(&coordination);c->live=false;c->result=ret;if(!id){call_done=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);return ret;
}
static void finish(void){bool pending=false;for(unsigned n=0;n<QCOM_SLIM_NGD_DESC_NUM;n++)pending|=busy[n];check(!pending,"all submitted DMA tokens are retired at case end");check(!invalid_callback_attempts,"callbacks correspond to outstanding DMA owners");check(!engine_cookie_clobbers,"client does not write a DMA descriptor after submission handoff");check(!stale_attempts,"DMA never completes a retired logical stack frame");check(!alias_attempts,"no hardware-owned slot is reused");check(!lock_errors,"reservation and cleanup hold the transfer mutex");for(unsigned n=0;n<QCOM_SLIM_NGD_DESC_NUM;n++)check(!ctrl.txdesc[n].comp,"no descriptor retains a returned completion token");}
static void *send_thread(void *arg){unsigned id=(uintptr_t)arg;transfer(id,calls[id].type);return NULL;}
static void *callback_thread(void *arg){caller=2;invoke_callback((uintptr_t)arg);return NULL;}
int main(int argc,char **argv){
 for(unsigned pos=0;pos<QCOM_SLIM_NGD_DESC_NUM;pos++)for(unsigned type=0;type<7;type++)for(unsigned failure=0;failure<5;failure++){
  if((failure==1||failure==4)&&!(type>=1&&type<=3))continue;
  char label[100];snprintf(label,sizeof(label),"ring-%u-type-%u-failure-%u",pos,type,failure);reset(label,pos);
  calls[0].prep_fail=failure==2;calls[0].tid_fail=failure==1;calls[0].tx_timeout=failure==3;calls[0].ack_timeout=failure==4;
  int ret=transfer(0,type);check(ret==(failure==1?-ENOSPC:failure==2?-EINVAL:failure>=3?-ETIMEDOUT:0),"transfer returns the established result");
  bool submitted=failure!=1&&failure!=2;check(submit_calls==submitted&&issue_calls==submitted,"failed preparation does not submit or issue DMA");
  check(ctrl.tx_tail==(int)((pos+(submitted?1:0))%QCOM_SLIM_NGD_DESC_NUM),"only submitted reservations remain in the ring");
  if(failure==3){check(busy[pos]&&ctrl.tx_head==(int)pos,"timed-out DMA keeps its slot until callback");caller=2;invoke_callback(pos);}
  check(ctrl.tx_head==ctrl.tx_tail,"the ring is empty after all submitted callbacks finish");finish();
 }
 for(unsigned type=7;type<10;type++){char label[80];snprintf(label,sizeof(label),"validation-type-%u",type);reset(label,0);int ret=transfer(0,type);check(ret==(type==7?-EPROTONOSUPPORT:type==8?0:-EINVAL),"validation result is preserved");check(!prep_calls&&ctrl.tx_tail==0,"validation does not reserve a buffer");finish();}
 for(unsigned pos=0;pos<QCOM_SLIM_NGD_DESC_NUM;pos++){
  char label[80];snprintf(label,sizeof(label),"pipeline-full-at-%u",pos);reset(label,pos);calls[0].tx_timeout=true;
  for(unsigned n=0;n<QCOM_SLIM_NGD_DESC_NUM-1;n++)check(transfer(0,0)==-ETIMEDOUT,"outstanding DMA timeout is bounded");
  check(transfer(0,0)==-ENOMEM,"a full ring refuses a new reservation");check(submit_calls==QCOM_SLIM_NGD_DESC_NUM-1,"no extra DMA is queued when full");
  for(unsigned n=0;n<QCOM_SLIM_NGD_DESC_NUM-1;n++){caller=2;invoke_callback((pos+n)%QCOM_SLIM_NGD_DESC_NUM);}
  check(ctrl.tx_head==ctrl.tx_tail,"late callbacks retire all hardware-owned slots");calls[0].tx_timeout=false;check(!transfer(0,0),"the fully drained ring can send again");finish();
 }
 for(unsigned pos=0;pos<QCOM_SLIM_NGD_DESC_NUM;pos++)for(unsigned q=0;q<3;q++)for(unsigned failure=0;failure<2;failure++){
  unsigned counts[]={1,15,30},pending=counts[q];char label[100];snprintf(label,sizeof(label),"older-DMA-at-%u-count-%u-failure-%u",pos,pending,failure);reset(label,pos);calls[0].tx_timeout=true;bool bounded=true;
  for(unsigned n=0;n<pending;n++)bounded&=transfer(0,0)==-ETIMEDOUT;
  check(bounded,"older DMA senders have returned from bounded waits");int reserved_tail=ctrl.tx_tail;calls[0].tx_timeout=false;calls[0].prep_fail=!failure;calls[0].tid_fail=failure;
  check(transfer(0,failure?1:0)==(failure?-ENOSPC:-EINVAL),"a later unsubmitted send returns its original error");
  check(ctrl.tx_tail==reserved_tail,"rollback returns only the newest unsubmitted slot");check(ctrl.tx_head==(int)pos,"rollback does not advance older DMA owners");
  check(submit_calls==pending,"a failed new reservation does not change queued DMA count");
  for(unsigned n=0;n<pending;n++){caller=2;invoke_callback((pos+n)%QCOM_SLIM_NGD_DESC_NUM);}
  check(ctrl.tx_head==ctrl.tx_tail,"older callbacks finish without a hole from the failed reservation");finish();
 }
 reset("concurrent-reservation",0);hold_wait=true;pthread_t a,b;calls[1].type=0;REQUIRE(!pthread_create(&a,NULL,send_thread,(void *)0));pthread_mutex_lock(&coordination);while(!wait_entered)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);
 REQUIRE(!pthread_create(&b,NULL,send_thread,(void *)1));pthread_mutex_lock(&coordination);while(!second_attempt)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);
 caller=2;spin_take(&ctrl.tx_buf_lock);check(ctrl.tx_tail==1,"a blocked sender cannot reserve before owning the transfer mutex");spin_drop(&ctrl.tx_buf_lock);
 pthread_mutex_lock(&coordination);release_wait=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(a,NULL));REQUIRE(!pthread_join(b,NULL));check(!calls[0].result&&!calls[1].result,"serialized concurrent sends finish");check(ctrl.tx_head==ctrl.tx_tail,"concurrent sends retire in ring order");finish();
 reset("timeout-races-active-callback",0);hold_wait=hold_complete=true;calls[0].tx_timeout=true;REQUIRE(!pthread_create(&a,NULL,send_thread,(void *)0));pthread_mutex_lock(&coordination);while(!wait_entered)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);
 REQUIRE(!pthread_create(&b,NULL,callback_thread,(void *)0));pthread_mutex_lock(&coordination);while(!complete_entered)pthread_cond_wait(&changed,&coordination);release_wait=true;pthread_cond_broadcast(&changed);while(!helper_waiting&&!call_done)pthread_cond_wait(&changed,&coordination);
 check(!call_done,"return waits for a callback already using its completion token");release_complete=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(a,NULL));REQUIRE(!pthread_join(b,NULL));check(calls[0].result==-ETIMEDOUT,"timeout result remains bounded after callback serialization");finish();
 if(argc==2){FILE *f=fopen(argv[1],"wb");REQUIRE(f&&fwrite(wire_trace,1,wire_length,f)==wire_length);REQUIRE(!fclose(f));}
 REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u,\"wire_FNV64\":\"%016llx\"}\n",cases,checks,failures,(unsigned long long)wire_hash);return 0;
}
