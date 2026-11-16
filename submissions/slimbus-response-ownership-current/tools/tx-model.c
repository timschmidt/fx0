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
struct slim_msg_txn;
struct idr {struct slim_msg_txn *entries[256];unsigned cursor;};
struct slim_controller {struct device *dev;pthread_mutex_t txn_lock;struct idr tid_idr;struct {int clk_state;} sched;int (*xfer_msg)(struct slim_controller *,struct slim_msg_txn *);};
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
static _Thread_local unsigned caller;static _Thread_local bool tx_held,buf_held,txn_held,response_context,alloc_hook;
struct token {struct completion *address;bool done,inner;bool tx;};
struct call_state {bool live,inner_live,driver_started;struct token tokens[8];unsigned token_count;bool prep_fail,tid_fail,tx_timeout,ack_timeout;int slot,result;unsigned type;};
static struct call_state calls[2];
static bool locks_live,second_attempt;
static unsigned prep_calls,submit_calls,issue_calls,stale_attempts,alias_attempts,lock_errors,tid_allocs,callback_calls,engine_cookie_clobbers,invalid_callback_attempts;
static u8 wire_trace[131072];static unsigned wire_length;
static uint64_t wire_hash=UINT64_C(14695981039346656037);
static unsigned cases,checks,failures;static const char *case_name;
static void check(bool ok,const char *message){checks++;if(!ok){failures++;fprintf(stderr,"%s: %s\n",case_name,message);}}
static void mutex_lock(struct mutex *m){REQUIRE(m==&ctrl.tx_lock);pthread_mutex_lock(&coordination);if(caller==1){second_attempt=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);REQUIRE(!pthread_mutex_lock(&m->lock));tx_held=true;}
static void mutex_unlock(struct mutex *m){REQUIRE(tx_held);tx_held=false;REQUIRE(!pthread_mutex_unlock(&m->lock));}
static bool emit_early,emit_driver_return,block_copy,copy_entered,release_copy,cancel_waiting,operation_done,hold_reply,reply_waiting,release_reply;
static int pm_result,submit_error,reply_mode,force_driver_error;
static unsigned external_refs,caller_PM_dropped_early;
static _Atomic unsigned pm_gets,pm_puts;
static unsigned response_copies,invalid_copy,retired_copy,retired_completion,unowned_idr_remove,early_callbacks,unlocked_completions;
static _Atomic int pm_usage;
struct request {struct slim_msg_txn txn;struct slim_val_inf msg;u8 read[64],write[16];bool converted;};
static struct request requests[2];
static void emit_response(void);
static void spin_take(pthread_mutex_t *m){REQUIRE(m==&ctrl.tx_buf_lock||m==&ctrl.ctrl.txn_lock);int ret=pthread_mutex_trylock(m);if(ret==EBUSY){pthread_mutex_lock(&coordination);if(m==&ctrl.ctrl.txn_lock&&caller==0&&copy_entered){cancel_waiting=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);REQUIRE(!pthread_mutex_lock(m));}else REQUIRE(!ret);if(m==&ctrl.tx_buf_lock)buf_held=true;else txn_held=true;}
static void spin_drop(pthread_mutex_t *m){if(m==&ctrl.tx_buf_lock){REQUIRE(buf_held);buf_held=false;}else{REQUIRE(txn_held);txn_held=false;}REQUIRE(!pthread_mutex_unlock(m));if(m==&ctrl.ctrl.txn_lock&&alloc_hook){alloc_hook=false;if(emit_early){emit_early=false;early_callbacks++;emit_response();}}}
#define spin_lock_irqsave(m,f) do{(f)=0;(void)(f);spin_take(m);}while(0)
#define spin_unlock_irqrestore(m,f) do{(void)(f);spin_drop(m);}while(0)
static void fixture_assert_lock(struct mutex *m){REQUIRE(m==&ctrl.tx_lock);if(!tx_held)lock_errors++;}
#define lockdep_assert_held(m) fixture_assert_lock(m)
static void register_completion(struct completion *p,const char *name){REQUIRE(caller<2);struct call_state *c=&calls[caller];REQUIRE(c->token_count<8);bool tx=!strcmp(name,"tx_sent");if(tx){c->driver_started=c->inner_live=true;}c->tokens[c->token_count++]=(struct token){.address=p,.inner=c->driver_started,.tx=tx};}
#define DECLARE_COMPLETION_ONSTACK(n) struct completion n;register_completion(&n,#n)
static struct token *find_token(struct completion *p,unsigned *owner){for(unsigned id=0;id<2;id++)for(unsigned n=0;n<calls[id].token_count;n++)if(calls[id].tokens[n].address==p){*owner=id;return &calls[id].tokens[n];}return NULL;}
static void complete(struct completion *p){
 if(!buf_held&&!txn_held)unlocked_completions++;pthread_mutex_lock(&coordination);unsigned owner=0;struct token *t=find_token(p,&owner);
 if(!t||!calls[owner].live||(t->inner&&!calls[owner].inner_live))retired_completion++;else t->done=true;
 pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);
}
static void *dev_get_drvdata(struct device *d){return d->data;}
static void pm_runtime_get_noresume(struct device *d){REQUIRE(d==&dev);atomic_fetch_add(&pm_usage,1);}
static int pm_runtime_get_sync(struct device *d){REQUIRE(d==&dev);pm_gets++;atomic_fetch_add(&pm_usage,1);return pm_result;}
static void pm_runtime_mark_last_busy(struct device *d){REQUIRE(d==&dev);}
static void pm_runtime_put_autosuspend(struct device *d){REQUIRE(d==&dev&&!txn_held&&!buf_held);pm_puts++;atomic_fetch_sub(&pm_usage,1);}
static void pm_runtime_put(struct device *d){pm_runtime_put_autosuspend(d);}
static void *idr_find(struct idr *idr,int tid){REQUIRE(idr==&ctrl.ctrl.tid_idr&&txn_held);return tid>=0&&tid<256?idr->entries[tid]:NULL;}
static int idr_alloc_cyclic(struct idr *idr,void *ptr,int first,int end,int flags){REQUIRE(txn_held&&first==1&&end==256);tid_allocs++;if(calls[0].tid_fail)return -ENOSPC;for(unsigned n=0;n<255;n++){unsigned tid=1+(idr->cursor+n)%255;if(!idr->entries[tid]){idr->entries[tid]=ptr;idr->cursor=tid;alloc_hook=true;return tid;}}return -ENOSPC;}
static void *idr_remove(struct idr *idr,int tid){REQUIRE(txn_held);void *old=idr_find(idr,tid);if(!old)unowned_idr_remove++;if(tid>0&&tid<256)idr->entries[tid]=NULL;return old;}
static void *fixture_memcpy(void *dest,const void *src,size_t length){
 if(response_context){pthread_mutex_lock(&coordination);copy_entered=true;pthread_cond_broadcast(&changed);while(block_copy&&!release_copy)pthread_cond_wait(&changed,&coordination);
  if(!calls[0].live||(requests[0].converted&&!calls[0].inner_live)){retired_copy++;pthread_mutex_unlock(&coordination);return dest;}
  if(length>requests[0].msg.num_bytes){invalid_copy++;pthread_mutex_unlock(&coordination);return dest;}
  response_copies++;pthread_mutex_unlock(&coordination);
 }
 return memcpy(dest,src,length);
}
#define memcpy fixture_memcpy
#define GFP_ATOMIC 0
#define SLIM_MAX_TIDS 256
#define SLIM_CLK_ACTIVE 0
#define SLIM_CLK_ENTERING_PAUSE 1
#define EXPORT_SYMBOL_GPL(x)
static struct dma_async_tx_descriptor *dmaengine_prep_slave_single(void *channel,dma_addr_t phys,int len,int direction,int flags){
 REQUIRE(caller<2&&channel==ctrl.dma_tx_channel&&direction==DMA_MEM_TO_DEV&&flags==DMA_PREP_INTERRUPT&&buf_held);prep_calls++;unsigned index=(phys-ctrl.tx_phys_base)/SLIM_MSGQ_BUF_LEN;REQUIRE(index<QCOM_SLIM_NGD_DESC_NUM&&len<=SLIM_MSGQ_BUF_LEN);calls[caller].slot=index;
 if(calls[caller].prep_fail)return NULL;if(busy[index])alias_attempts++;transfers[index]=(struct dma_async_tx_descriptor){.index=index,.len=len};return &transfers[index];
}
static dma_cookie_t dmaengine_submit(struct dma_async_tx_descriptor *d){REQUIRE(buf_held);submit_calls++;if(submit_error)return submit_error;busy[d->index]=true;d->cookie=-999;const u8 *bytes=(const u8 *)ctrl.tx_base+d->index*SLIM_MSGQ_BUF_LEN;REQUIRE(wire_length+1+d->len<=sizeof(wire_trace));wire_trace[wire_length++]=d->len;memcpy(wire_trace+wire_length,bytes,d->len);wire_length+=d->len;for(unsigned n=0;n<d->len;n++){wire_hash^=bytes[n];wire_hash*=UINT64_C(1099511628211);}return 17;}
static void dma_async_issue_pending(void *channel){REQUIRE(channel==ctrl.dma_tx_channel&&buf_held);issue_calls++;if(transfers[calls[caller].slot].cookie!=-999)engine_cookie_clobbers++;}
static int dma_submit_error(dma_cookie_t cookie){return cookie<0?cookie:0;}
/* ACTUAL_LOW */
static void invoke_callback(unsigned index){REQUIRE(index<QCOM_SLIM_NGD_DESC_NUM);if(!busy[index]){invalid_callback_attempts++;return;}callback_calls++;transfers[index].callback(transfers[index].callback_param);busy[index]=false;}
static unsigned long msecs_to_jiffies(unsigned long ms){return ms;}
static unsigned long wait_for_completion_timeout(struct completion *p,unsigned long timeout){
 REQUIRE(caller<2&&timeout>0);unsigned owner=0;struct token *t=find_token(p,&owner);REQUIRE(t&&owner==caller);
 if(t->tx){
  if(calls[caller].tx_timeout)return 0;
  if(reply_mode==1){emit_response();if(atomic_load(&pm_usage)<(int)external_refs+1)caller_PM_dropped_early++;}
  invoke_callback(calls[caller].slot);
  if(reply_mode==2)emit_response();
  return t->done;
 }
 if(!t->inner)calls[caller].inner_live=false;
 pthread_mutex_lock(&coordination);if(hold_reply){reply_waiting=true;pthread_cond_broadcast(&changed);while(!release_reply)pthread_cond_wait(&changed,&coordination);}pthread_mutex_unlock(&coordination);
 if(reply_mode==3||reply_mode==5||reply_mode==6||reply_mode==7)emit_response();
 if(reply_mode==5||reply_mode==0||hold_reply)return 0;
 return t->done;
}
/* ACTUAL_MESSAGE_HELPERS */
/* ACTUAL_CORE */
/* ACTUAL_TX */
/* ACTUAL_SYNC */
static bool core_clock_bad;
static void emit_one(unsigned len){u8 reply[64];for(unsigned n=0;n<64;n++)reply[n]=0xa0+n;bool was=response_context;response_context=true;slim_msg_response(&ctrl.ctrl,reply,requests[0].txn.tid,len);response_context=was;}
static void emit_response(void){unsigned len=requests[0].msg.num_bytes;if(reply_mode==7){emit_one(len+1);emit_one(len);}else{emit_one(len);if(reply_mode==6)emit_one(len);}}
static int call_ngd(struct slim_controller *s,struct slim_msg_txn *txn){int ret=qcom_slim_ngd_xfer_msg(s,txn);calls[0].inner_live=false;if(emit_driver_return)emit_response();return force_driver_error?force_driver_error:ret;}
static unsigned ids(void){unsigned count=0;for(unsigned n=1;n<256;n++)count+=ctrl.ctrl.tid_idr.entries[n]!=NULL;return count;}
static void reset_case(const char *name,unsigned external){
 if(locks_live){REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));REQUIRE(!pthread_mutex_destroy(&ctrl.ctrl.txn_lock));}
 memset(&ctrl,0,sizeof(ctrl));memset(coherent,0,sizeof(coherent));memset(transfers,0,sizeof(transfers));memset(busy,0,sizeof(busy));memset(calls,0,sizeof(calls));memset(requests,0,sizeof(requests));
 dev.data=&ctrl;ctrl.dev=ctrl.ctrl.dev=&dev;ctrl.ctrl.xfer_msg=call_ngd;ctrl.ctrl.sched.clk_state=SLIM_CLK_ACTIVE;ctrl.tx_base=coherent;ctrl.tx_phys_base=0x1000;ctrl.dma_tx_channel=&ctrl;
 REQUIRE(!pthread_mutex_init(&ctrl.tx_lock.lock,NULL));REQUIRE(!pthread_mutex_init(&ctrl.tx_buf_lock,NULL));REQUIRE(!pthread_mutex_init(&ctrl.ctrl.txn_lock,NULL));locks_live=true;
 emit_early=emit_driver_return=block_copy=copy_entered=release_copy=cancel_waiting=operation_done=hold_reply=reply_waiting=release_reply=false;core_clock_bad=false;
 pm_result=submit_error=force_driver_error=0;reply_mode=3;external_refs=external;atomic_store(&pm_usage,external);pm_gets=pm_puts=0;
 prep_calls=submit_calls=issue_calls=stale_attempts=alias_attempts=lock_errors=tid_allocs=callback_calls=engine_cookie_clobbers=invalid_callback_attempts=0;
 response_copies=invalid_copy=retired_copy=retired_completion=unowned_idr_remove=early_callbacks=unlocked_completions=caller_PM_dropped_early=0;wire_length=0;caller=0;tx_held=buf_held=txn_held=response_context=alloc_hook=false;
 for(unsigned id=0;id<2;id++){for(unsigned n=0;n<16;n++)requests[id].write[n]=0x10+n;requests[id].msg=(struct slim_val_inf){.num_bytes=4,.rbuf=requests[id].read};requests[id].txn=(struct slim_msg_txn){.rl=7,.mt=SLIM_MSG_MT_CORE,.mc=SLIM_MSG_MC_REQUEST_VALUE,.dt=SLIM_MSG_DEST_LOGICALADDR,.la=1,.msg=&requests[id].msg,.tid=13};}
 case_name=name;cases++;
}
static int execute(unsigned kind){
 caller=0;struct request *r=&requests[0];struct slim_msg_txn *t=&r->txn;r->converted=kind>=2&&kind<=4;
 if(kind==1){t->mc=SLIM_MSG_MC_CHANGE_VALUE;t->rl=10;r->msg.wbuf=r->write;}
 if(r->converted){t->mc=kind==2?SLIM_MSG_MC_CONNECT_SOURCE:kind==3?SLIM_MSG_MC_CONNECT_SINK:SLIM_MSG_MC_DISCONNECT_PORT;t->rl=6;r->msg.wbuf=r->write;r->msg.num_bytes=2;}
 if(kind==5){t->mt=SLIM_MSG_MT_DEST_REFERRED_USER;t->mc=SLIM_USR_MC_ADDR_QUERY;t->rl=11;r->msg.num_bytes=7;r->msg.wbuf=r->write;}
 if(kind==6){t->mc=SLIM_MSG_MC_BEGIN_RECONFIGURATION;t->rl=4;ctrl.ctrl.sched.clk_state=SLIM_CLK_ENTERING_PAUSE;}
 pthread_mutex_lock(&coordination);calls[0].live=true;pthread_mutex_unlock(&coordination);
 int ret;
 if(kind==5){ret=slim_alloc_txn_tid(&ctrl.ctrl,t);if(!ret){r->write[0]=t->tid;ret=qcom_slim_ngd_xfer_msg_sync(&ctrl.ctrl,t);}}
 else ret=slim_do_transfer(&ctrl.ctrl,t);
 pthread_mutex_lock(&coordination);calls[0].live=calls[0].inner_live=false;calls[0].result=ret;operation_done=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return ret;
}
static void audit_return(int expected){
 check(calls[0].result==expected,"operation returns the expected PM, allocation, DMA or response result");
 check(atomic_load(&pm_usage)==(int)external_refs,"only the operation references are released at return");
 check(!ids(),"all synchronous TIDs are retired before return");
 check(!invalid_copy&&!retired_copy&&!retired_completion&&!unlocked_completions,"response copy and completion stay within their logical lifetimes");
 check(!caller_PM_dropped_early,"an early reply cannot release the sender PM reference");
 check(!engine_cookie_clobbers&&!alias_attempts&&!lock_errors,"TX client and DMA ownership remain valid");
 for(unsigned n=0;n<QCOM_SLIM_NGD_DESC_NUM;n++)check(!ctrl.txdesc[n].comp,"no returned DMA completion reference remains");
}
static void audit_late(void){
 unsigned copies=response_copies,puts=atomic_load(&pm_puts);emit_response();
 check(response_copies==copies&&atomic_load(&pm_puts)==puts,"late or duplicate response cannot use a retired transaction or PM vote");
 for(unsigned n=0;n<QCOM_SLIM_NGD_DESC_NUM;n++)if(busy[n]){caller=2;invoke_callback(n);}caller=0;
 check(!retired_copy&&!retired_completion,"late callbacks never access retired logical frames");
 check(ctrl.tx_head==ctrl.tx_tail,"all hardware-owned or locally failed TX slots are retired after late callbacks");
}
static bool prepare(struct slim_msg_txn *t){
#if FIXTURE_PREPARED_API
 return !slim_prepare_txn(&ctrl.ctrl,t);
#else
 return true;
#endif
}
static bool cancel(struct slim_msg_txn *t){
#if FIXTURE_PREPARED_API
 return slim_free_txn_tid(&ctrl.ctrl,t);
#else
 bool own=ctrl.ctrl.tid_idr.entries[t->tid]==t;slim_free_txn_tid(&ctrl.ctrl,t);return own;
#endif
}
static unsigned threaded_kind;
static void *operation_thread(void *unused){execute(threaded_kind);return NULL;}
static void *response_thread(void *unused){caller=2;emit_response();return NULL;}
int main(void){
 unsigned refs[]={0,1,3};int timings[]={0,1,2,3,5,6,7};
 for(unsigned ext=0;ext<3;ext++)for(unsigned kind=0;kind<6;kind++)for(unsigned timing=0;timing<7;timing++)for(unsigned fault=0;fault<8;fault++){
  if(kind==5&&fault==7)continue;char label[120];snprintf(label,sizeof(label),"kind-%u-reply-%d-fault-%u-external-%u",kind,timings[timing],fault,refs[ext]);reset_case(label,refs[ext]);reply_mode=timings[timing];
  calls[0].prep_fail=fault==1;submit_error=fault==2?-EIO:0;calls[0].tx_timeout=fault==3;calls[0].tid_fail=fault==4;pm_result=fault==5?-EIO:fault==6?1:0;
  if(fault==7)ctrl.ctrl.sched.clk_state=9;
  bool need_reply=kind!=1;emit_driver_return=kind>=2&&kind<=4&&(fault||!reply_mode||reply_mode==5);
  int expected=fault==5?-EIO:fault==7?-EREMOTEIO:fault==4&&need_reply?-ENOSPC:fault==1?-EINVAL:fault==2?-EIO:fault==3?-ETIMEDOUT:need_reply&&(!reply_mode||reply_mode==5)?-ETIMEDOUT:0;
  execute(kind);audit_return(expected);audit_late();
 }
 for(unsigned kind=0;kind<6;kind++){char label[80];snprintf(label,sizeof(label),"unprepared-early-response-kind-%u",kind);reset_case(label,2);emit_early=true;execute(kind);audit_return(0);audit_late();}
 for(unsigned n=0;n<3;n++){char label[80];snprintf(label,sizeof(label),"clock-pause-PM-result-%u",n);reset_case(label,1);pm_result=n==0?-EIO:n==1?0:1;execute(6);audit_return(0);check(!pm_gets&&!pm_puts,"clock-pause traffic adds no PM references");audit_late();}
 for(unsigned kind=0;kind<6;kind++){
  if(kind==1||kind==3||kind==4)continue;
  int errors[]={-ENOMEM,-ENOSPC,-EPIPE};for(unsigned n=0;n<3;n++){
   char label[90];snprintf(label,sizeof(label),"submit-error-%d-kind-%u",errors[n],kind);reset_case(label,3);submit_error=errors[n];execute(kind);audit_return(errors[n]);check(!issue_calls,"a failed submission never issues DMA");audit_late();
  }
 }
 for(unsigned kind=0;kind<5;kind++)for(unsigned replied=0;replied<2;replied++){
  char label[90];snprintf(label,sizeof(label),"controller-error-kind-%u-response-%u",kind,replied);reset_case(label,1);reply_mode=replied?1:0;force_driver_error=-EPIPE;execute(kind);audit_return(-EPIPE);audit_late();
 }
 reset_case("reused-prepared-state-is-cleared",2);
#if FIXTURE_PREPARED_API
 requests[0].txn.prepared=true;
#endif
 emit_early=true;execute(0);audit_return(0);audit_late();
 reset_case("duplicate-preparation-does-not-add-PM-pin",1);calls[0].live=true;pm_runtime_get_sync(&dev);check(!slim_alloc_txn_tid(&ctrl.ctrl,&requests[0].txn)&&prepare(&requests[0].txn),"preparation publishes one response pin");int before=atomic_load(&pm_usage);
#if FIXTURE_PREPARED_API
 int second=slim_prepare_txn(&ctrl.ctrl,&requests[0].txn);
#else
 int second=0;
#endif
 check(second==-EALREADY,"duplicate preparation is rejected");check(atomic_load(&pm_usage)==before,"duplicate preparation preserves PM ownership");cancel(&requests[0].txn);pm_runtime_put(&dev);check(!ids()&&atomic_load(&pm_usage)==1,"response and caller references balance after rejected preparation");
 for(unsigned ext=0;ext<3;ext++){
  reset_case("identity-preserving-retirement",refs[ext]);calls[0].live=true;struct completion token;register_completion(&token,"done");requests[0].txn.comp=&token;pm_runtime_get_sync(&dev);check(!slim_alloc_txn_tid(&ctrl.ctrl,&requests[0].txn)&&prepare(&requests[0].txn),"old transaction is allocated and prepared");unsigned tid=requests[0].txn.tid;check(cancel(&requests[0].txn),"first cancellation owns old transaction");ctrl.ctrl.tid_idr.cursor=tid-1;check(!slim_alloc_txn_tid(&ctrl.ctrl,&requests[1].txn)&&prepare(&requests[1].txn),"new transaction reuses numeric TID");check(!cancel(&requests[0].txn),"an old owner cannot cancel its replacement");check(ctrl.ctrl.tid_idr.entries[tid]==&requests[1].txn,"replacement survives stale cancellation");cancel(&requests[1].txn);pm_runtime_put(&dev);check(!ids()&&atomic_load(&pm_usage)==(int)refs[ext],"both response pins and the caller vote retire exactly once");
 }
 for(unsigned kind=0;kind<2;kind++){
  reset_case(kind?"response-copy-versus-NGD-timeout":"response-copy-versus-core-timeout",1);threaded_kind=kind?5:0;reply_mode=0;hold_reply=block_copy=true;pthread_t op,response;
  REQUIRE(!pthread_create(&op,NULL,operation_thread,NULL));pthread_mutex_lock(&coordination);while(!reply_waiting)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);
  REQUIRE(!pthread_create(&response,NULL,response_thread,NULL));pthread_mutex_lock(&coordination);while(!copy_entered)pthread_cond_wait(&changed,&coordination);release_reply=true;pthread_cond_broadcast(&changed);while(!cancel_waiting&&!operation_done)pthread_cond_wait(&changed,&coordination);
  check(!operation_done,"timeout retirement waits for an admitted response copy and completion");release_copy=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(op,NULL));REQUIRE(!pthread_join(response,NULL));audit_return(-ETIMEDOUT);audit_late();
 }
 REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));REQUIRE(!pthread_mutex_destroy(&ctrl.ctrl.txn_lock));printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
