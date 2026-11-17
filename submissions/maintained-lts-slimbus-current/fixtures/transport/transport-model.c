/* SPDX-License-Identifier: GPL-2.0-only */
/* All providers, callbacks, work and lifetime observations are logical services. */
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
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define BIT(n) (1u<<(n))
#define GENMASK(h,l) (((~0u)>>(31-(h)))&((~0u)<<(l)))
#define HZ 100
#define GFP_KERNEL 0
#define DMA_DEV_TO_MEM 1
#define DMA_MEM_TO_DEV 2
#define DMA_PREP_INTERRUPT 1
#define IS_ERR(p) ((uintptr_t)(p)>=(uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define __maybe_unused
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define READ_ONCE(x) atomic_load(&(x))
#define WRITE_ONCE(x,v) atomic_store(&(x),(v))
#define QCOM_SSR_BEFORE_SHUTDOWN 1
#define SERVREG_SERVICE_STATE_DOWN 2
#define QCOM_SSR_AFTER_POWERUP 3
#define SERVREG_SERVICE_STATE_UP 4
#define NOTIFY_OK 0
/* ACTUAL_DEFINES */
struct completion {unsigned unused;};
struct mutex {pthread_mutex_t lock;};
struct device {void *data;bool pm_enabled,suspended;int usage;};
struct platform_device {struct device dev;};
struct work_struct {void (*fn)(struct work_struct *);bool queued,running;};
struct dma_chan {bool live,rx,terminating,issued;unsigned running;};
struct dma_async_tx_descriptor {void (*callback)(void *);void *callback_param;int cookie;struct dma_chan *chan;bool submitted;unsigned index;};
struct qcom_slim_ngd_ctrl;
/* ACTUAL_TYPES */
struct slim_controller {struct device *dev;};
struct qcom_slim_ngd {void *base;};
struct qcom_slim_ngd_ctrl {
 struct device *dev;struct slim_controller ctrl;struct qcom_slim_ngd *ngd;void *base;
 _Atomic(struct dma_chan *) dma_rx_channel,dma_tx_channel;
 struct qcom_slim_ngd_dma_desc rx_desc[QCOM_SLIM_NGD_DESC_NUM],txdesc[QCOM_SLIM_NGD_DESC_NUM];
 void *rx_base,*tx_base;dma_addr_t rx_phys_base,tx_phys_base;int tx_head,tx_tail;
 pthread_mutex_t tx_buf_lock;struct mutex tx_lock,dma_lock,ssr_lock;
 _Atomic bool dma_ready,parent_ready,child_ready,up_requested,qmi_ready;
 unsigned dma_stopping;bool registered,pm_ref_held;enum qcom_slim_ngd_state state;
 struct work_struct m_work,slave_work,ngd_up_work;void *mwq;int qmi_wait;
 struct {void *handle;} qmi;struct completion reconf;
};
static struct qcom_slim_ngd_ctrl ctrl;static struct device parent;static struct platform_device child;static struct qcom_slim_ngd ngd;static u32 regs[64];
static struct dma_chan channels[32];static unsigned channel_count;
static struct dma_async_tx_descriptor descriptors[4096];static unsigned descriptor_count;
static void *buffers[8];static unsigned buffer_count;
static pthread_mutex_t coordination=PTHREAD_MUTEX_INITIALIZER;static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
enum {MAIN,RX,SEND,MASTER,STOP_A,STOP_B,INIT,SLAVE};
static _Thread_local unsigned role,held;
enum {SSR=1,LIFE=2,TX=4,BUF=8};
static bool locks_live,block_rearm,rearm_entered,release_rearm,block_sender,sender_waiting,release_sender,block_notify,notify_entered,release_notify;
static bool rx_term_entered;
static bool stop_buf_waiting,stop_tx_waiting,stop_life_waiting,block_setup,setup_entered,release_setup,stop_finished;
static unsigned cancels,barriers,rx_preps,tx_preps,submits,issues,notifications,resumes,pm_marks,active_tx_holds;
static unsigned issue_during_termination,invalid_channel,release_before_drain,cookie_clobbers,bad_wait_locks,lock_errors,closed_master_queues,unregister_order_errors,gate_open_at_terminate;
static unsigned fault_at,rx_prepare_count,rx_submit_count;static int fault_kind,submit_errno;
static int sender_result,setup_result,stop_result;static unsigned cases,checks,failures;static const char *case_name;
static bool block_master_complete,master_completed,release_master_complete;static unsigned closed_slave_queues,PM_from_handshake,powerup_calls,wrong_notification_queue;
static bool hold_cancel,cancel_waiting[2],release_cancel[2];
static bool notified_after_close;static pthread_t master_handle;static bool master_joinable;static pthread_t slave_handle;static bool slave_joinable;
static void check(bool ok,const char *message){checks++;if(!ok){failures++;fprintf(stderr,"%s: %s\n",case_name,message);}}
static unsigned lock_bit(struct mutex *m){return m==&ctrl.tx_lock?TX:m==&ctrl.dma_lock?LIFE:SSR;}
static void mutex_lock(struct mutex *m){
 unsigned bit=lock_bit(m);int ret=pthread_mutex_trylock(&m->lock);
 if(ret==EBUSY){pthread_mutex_lock(&coordination);if(role==STOP_A||role==STOP_B){if(bit==TX)stop_tx_waiting=true;if(bit==LIFE)stop_life_waiting=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);REQUIRE(!pthread_mutex_lock(&m->lock));}else REQUIRE(!ret);
 held|=bit;if(bit==TX&&(role==SEND||role==MASTER)){pthread_mutex_lock(&coordination);active_tx_holds++;pthread_mutex_unlock(&coordination);}
}
static void mutex_unlock(struct mutex *m){unsigned bit=lock_bit(m);REQUIRE(held&bit);if(bit==TX&&(role==SEND||role==MASTER)){pthread_mutex_lock(&coordination);REQUIRE(active_tx_holds);active_tx_holds--;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);}held&=~bit;REQUIRE(!pthread_mutex_unlock(&m->lock));}
static void spin_take(pthread_mutex_t *m){REQUIRE(m==&ctrl.tx_buf_lock);int ret=pthread_mutex_trylock(m);if(ret==EBUSY){pthread_mutex_lock(&coordination);if(role==STOP_A||role==STOP_B){stop_buf_waiting=true;pthread_cond_broadcast(&changed);}pthread_mutex_unlock(&coordination);REQUIRE(!pthread_mutex_lock(m));}else REQUIRE(!ret);held|=BUF;}
static void spin_drop(pthread_mutex_t *m){REQUIRE(held&BUF);held&=~BUF;REQUIRE(!pthread_mutex_unlock(m));}
#define spin_lock_irqsave(m,f) do{(f)=0;spin_take(m);}while(0)
#define spin_unlock_irqrestore(m,f) do{(void)(f);spin_drop(m);}while(0)
#define lockdep_assert_held(m) do{if(!(held&lock_bit(m)))lock_errors++;}while(0)
static void *dev_get_drvdata(struct device *d){return d->data;}
static void *platform_get_drvdata(struct platform_device *p){return p->dev.data;}
struct token {struct completion *p;bool done,live;};static struct token tokens[64];static unsigned token_count;
static void register_token(struct completion *p){pthread_mutex_lock(&coordination);REQUIRE(token_count<64);tokens[token_count++]=(struct token){p,false,true};pthread_mutex_unlock(&coordination);}
#define DECLARE_COMPLETION_ONSTACK(n) struct completion n;register_token(&n)
static void complete(struct completion *p){pthread_mutex_lock(&coordination);if(p==&ctrl.reconf){master_completed=true;pthread_cond_broadcast(&changed);while(block_master_complete&&!release_master_complete)pthread_cond_wait(&changed,&coordination);}bool found=false;for(unsigned n=0;n<token_count;n++)if(tokens[n].p==p&&tokens[n].live){tokens[n].done=true;found=true;}if(!found&&p!=&ctrl.reconf)lock_errors++;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);}
static void pm_runtime_mark_last_busy(struct device *d){REQUIRE(d==&child.dev);pm_marks++;}
static void pm_runtime_get_noresume(struct device *d){REQUIRE(d==&child.dev);d->usage++;}
static void pm_runtime_put_noidle(struct device *d){REQUIRE(d==&child.dev);d->usage--;}
static void pm_runtime_dont_use_autosuspend(struct device *d){REQUIRE(d==&child.dev);}
static void pm_runtime_disable(struct device *d){REQUIRE(d==&child.dev);d->pm_enabled=false;}
static int pm_runtime_barrier(struct device *d){REQUIRE(d==&child.dev);barriers++;return 0;}
static void wake_up_all(int *q){REQUIRE(q==&ctrl.qmi_wait);}
static void schedule_work(struct work_struct *w){REQUIRE(w==&ctrl.ngd_up_work||w==&ctrl.slave_work);pthread_mutex_lock(&coordination);if(w==&ctrl.slave_work)closed_slave_queues+=!READ_ONCE(ctrl.dma_ready);w->queued=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);}
static bool queue_work(void *q,struct work_struct *w){REQUIRE(q==&ctrl&&(w==&ctrl.m_work||w==&ctrl.slave_work));pthread_mutex_lock(&coordination);wrong_notification_queue+=w==&ctrl.slave_work;closed_master_queues+=!READ_ONCE(ctrl.dma_ready);w->queued=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return true;}
static void cancel_work_sync(struct work_struct *w){
 REQUIRE(w==&ctrl.m_work||w==&ctrl.slave_work);pthread_mutex_lock(&coordination);cancels++;w->queued=false;pthread_cond_broadcast(&changed);
 if((held&TX)||(w==&ctrl.slave_work&&((held&LIFE)||((role==STOP_A||role==STOP_B)&&w->running)))){bad_wait_locks++;pthread_mutex_unlock(&coordination);return;}
 if(hold_cancel){unsigned n=role==STOP_B;cancel_waiting[n]=true;pthread_cond_broadcast(&changed);while(!release_cancel[n])pthread_cond_wait(&changed,&coordination);}
 while(w->running)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);
}
static struct dma_chan *dma_request_chan(struct device *d,const char *which){REQUIRE(d==&parent);bool rx=!strcmp(which,"rx");if(fault_kind==(rx?1:2))return (void *)(intptr_t)-EIO;pthread_mutex_lock(&coordination);REQUIRE(channel_count<32);struct dma_chan *c=&channels[channel_count++];*c=(struct dma_chan){.live=true,.rx=rx};pthread_mutex_unlock(&coordination);return c;}
static void *dmam_alloc_coherent(struct device *d,size_t size,dma_addr_t *phys,int flags){REQUIRE(d==&parent);bool rx=size==QCOM_SLIM_NGD_DESC_NUM*SLIM_MSGQ_BUF_LEN;if(fault_kind==(rx?3:4))return NULL;REQUIRE(buffer_count<8);void *p=calloc(1,size);REQUIRE(p);buffers[buffer_count++]=p;*phys=(uintptr_t)p;return p;}
static void dma_release_channel(struct dma_chan *c){pthread_mutex_lock(&coordination);if(!c||!c->live){invalid_channel++;pthread_mutex_unlock(&coordination);return;}release_before_drain+=c->running||ctrl.m_work.running||ctrl.m_work.queued||active_tx_holds;c->live=false;pthread_mutex_unlock(&coordination);}
static int dmaengine_terminate_sync(struct dma_chan *c){
 pthread_mutex_lock(&coordination);if(!c||!c->live){invalid_channel++;pthread_mutex_unlock(&coordination);return 0;}gate_open_at_terminate+=READ_ONCE(ctrl.dma_ready);c->terminating=true;if(c->rx)rx_term_entered=true;c->issued=false;pthread_cond_broadcast(&changed);while(c->running)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);return 0;
}
static struct dma_async_tx_descriptor *dmaengine_prep_slave_single(struct dma_chan *c,dma_addr_t physical,int len,int direction,int flags){
 pthread_mutex_lock(&coordination);if(!c||!c->live){invalid_channel++;pthread_mutex_unlock(&coordination);return NULL;}
 if(c->rx){unsigned at=rx_prepare_count++;rx_preps++;if(role==RX&&block_rearm){rearm_entered=true;pthread_cond_broadcast(&changed);while(!release_rearm)pthread_cond_wait(&changed,&coordination);}if(role==INIT&&block_setup){setup_entered=true;pthread_cond_broadcast(&changed);while(!release_setup)pthread_cond_wait(&changed,&coordination);}if(fault_kind==5&&at%QCOM_SLIM_NGD_DESC_NUM==fault_at){pthread_mutex_unlock(&coordination);return NULL;}}
 else tx_preps++;
 REQUIRE(descriptor_count<4096);struct dma_async_tx_descriptor *desc=&descriptors[descriptor_count++];*desc=(struct dma_async_tx_descriptor){.chan=c,.index=c->rx?0:(physical-ctrl.tx_phys_base)/SLIM_MSGQ_BUF_LEN};pthread_mutex_unlock(&coordination);return desc;
}
static dma_cookie_t dmaengine_submit(struct dma_async_tx_descriptor *d){pthread_mutex_lock(&coordination);d->submitted=true;d->cookie=-999;submits++;int ret=17;if(d->chan->rx){unsigned at=rx_submit_count++;if(fault_kind==6&&at%QCOM_SLIM_NGD_DESC_NUM==fault_at)ret=submit_errno;}pthread_mutex_unlock(&coordination);return ret;}
static int dma_submit_error(dma_cookie_t cookie){return cookie<0?cookie:0;}
static void dma_async_issue_pending(struct dma_chan *c){pthread_mutex_lock(&coordination);if(!c||!c->live)invalid_channel++;else{issue_during_termination+=c->terminating;c->issued=true;}issues++;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);}
static int slim_alloc_txn_tid(struct slim_controller *c,struct slim_msg_txn *t){t->tid=1;return 0;}
static int slim_prepare_txn(struct slim_controller *c,struct slim_msg_txn *t){return 0;}
static bool slim_free_txn_tid(struct slim_controller *c,struct slim_msg_txn *t){return true;}
static void slim_msg_response(struct slim_controller *c,u8 *reply,u8 tid,u8 len){REQUIRE(c==&ctrl.ctrl);}
/* ACTUAL_LOW */
static unsigned long wait_for_completion_timeout(struct completion *p,unsigned long time){
 pthread_mutex_lock(&coordination);if(role==SEND&&block_sender){sender_waiting=true;pthread_cond_broadcast(&changed);while(!release_sender)pthread_cond_wait(&changed,&coordination);}bool live=ctrl.dma_tx_channel&&ctrl.dma_tx_channel->live&&ctrl.dma_tx_channel->issued;pthread_mutex_unlock(&coordination);
 if(live){unsigned slot=(ctrl.tx_tail+QCOM_SLIM_NGD_DESC_NUM-1)%QCOM_SLIM_NGD_DESC_NUM;qcom_slim_ngd_tx_msg_dma_cb(&ctrl.txdesc[slot]);return 1;}return 0;
}
/* ACTUAL_slim_tid_txn */
/* ACTUAL_slim_ec_txn */
static int qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *ctrl);
/* ACTUAL_RX */
/* ACTUAL_INIT */
/* ACTUAL_XFER */
static u32 readl_relaxed(void *p){return *(u32 *)p;}
static void writel_relaxed(u32 value,void *p){*(u32 *)p=value;}
/* ACTUAL_LIFE */
static int qcom_slim_ngd_power_up(struct qcom_slim_ngd_ctrl *c){REQUIRE(c==&ctrl);powerup_calls++;return qcom_slim_ngd_setup(c);}
/* ACTUAL_RESUME */
static void qcom_slim_ngd_notify_slaves(struct qcom_slim_ngd_ctrl *c){
 REQUIRE(c==&ctrl);pthread_mutex_lock(&coordination);notifications++;PM_from_handshake+=role==MASTER;notify_entered=true;pthread_cond_broadcast(&changed);while(block_notify&&!release_notify)pthread_cond_wait(&changed,&coordination);notified_after_close=!READ_ONCE(ctrl.dma_ready);pthread_mutex_unlock(&coordination);resumes++;(void)qcom_slim_ngd_runtime_resume(&child.dev);
}
static void msleep(unsigned long ms){REQUIRE(ms==DEF_RETRY_MS);}
/* ACTUAL_SLAVE */
/* ACTUAL_MASTER */
static int qcom_slim_ngd_update_device_status(struct device *d,void *unused){return 0;}
static int device_for_each_child(struct device *d,void *data,int (*fn)(struct device *,void *)){REQUIRE(d==&child.dev);pthread_mutex_lock(&coordination);unregister_order_errors+=ctrl.m_work.running||ctrl.m_work.queued||ctrl.slave_work.running||ctrl.slave_work.queued||active_tx_holds||ctrl.dma_rx_channel||ctrl.dma_tx_channel;pthread_mutex_unlock(&coordination);return 0;}
static int qcom_slim_ngd_enable(struct qcom_slim_ngd_ctrl *c,bool enable){REQUIRE(c==&ctrl&&!enable);pthread_mutex_lock(&coordination);unregister_order_errors+=ctrl.m_work.running||ctrl.m_work.queued||ctrl.slave_work.running||ctrl.slave_work.queued||active_tx_holds||ctrl.dma_rx_channel||ctrl.dma_tx_channel;pthread_mutex_unlock(&coordination);ctrl.qmi.handle=NULL;ctrl.registered=false;return 0;}
/* ACTUAL_DOWN */
/* ACTUAL_NOTIFY */
static void qcom_slim_ngd_stop_up(struct qcom_slim_ngd_ctrl *c){REQUIRE(c==&ctrl);WRITE_ONCE(c->child_ready,false);}
static void qcom_slim_ngd_qmi_svc_event_deinit(void *qmi){REQUIRE(qmi==&ctrl.qmi);}
/* ACTUAL_REMOVE */
static void join_master(void){if(master_joinable){REQUIRE(!pthread_join(master_handle,NULL));master_joinable=false;}}
static void *master_thread(void *unused){role=MASTER;held=0;pthread_mutex_lock(&coordination);ctrl.m_work.queued=false;ctrl.m_work.running=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);qcom_slim_ngd_master_worker(&ctrl.m_work);pthread_mutex_lock(&coordination);ctrl.m_work.running=false;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return NULL;}
static void start_master(void){REQUIRE(!master_joinable);master_joinable=true;REQUIRE(!pthread_create(&master_handle,NULL,master_thread,NULL));}
static void *slave_thread(void *unused){role=SLAVE;held=0;pthread_mutex_lock(&coordination);ctrl.slave_work.queued=false;ctrl.slave_work.running=true;pthread_mutex_unlock(&coordination);
#if FIXTURE_ADMISSION
 qcom_slim_ngd_slave_worker(&ctrl.slave_work);
#endif
 pthread_mutex_lock(&coordination);ctrl.slave_work.running=false;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return NULL;}
static void start_slave(void){REQUIRE(!slave_joinable);slave_joinable=true;REQUIRE(!pthread_create(&slave_handle,NULL,slave_thread,NULL));}
static void join_slave(void){if(slave_joinable){REQUIRE(!pthread_join(slave_handle,NULL));slave_joinable=false;}}
static void *rx_thread(void *unused){role=RX;held=0;struct dma_chan *c=ctrl.dma_rx_channel;pthread_mutex_lock(&coordination);if(!c){invalid_channel++;pthread_mutex_unlock(&coordination);return NULL;}c->running++;pthread_mutex_unlock(&coordination);qcom_slim_ngd_rx_msgq_cb(&ctrl.rx_desc[0]);pthread_mutex_lock(&coordination);c->running--;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return NULL;}
static void *stop_thread(void *unused){role=unused?(unsigned)(uintptr_t)unused:STOP_A;held=0;stop_result=qcom_slim_ngd_exit_dma(&ctrl);pthread_mutex_lock(&coordination);stop_finished=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return NULL;}
static void *sender_thread(void *unused){role=SEND;held=0;struct slim_val_inf msg={.num_bytes=1};u8 bytes[]={0x42};msg.wbuf=bytes;struct slim_msg_txn txn={.rl=7,.mt=SLIM_MSG_MT_CORE,.mc=SLIM_MSG_MC_CHANGE_VALUE,.dt=SLIM_MSG_DEST_LOGICALADDR,.msg=&msg};sender_result=qcom_slim_ngd_xfer_msg(&ctrl.ctrl,&txn);return NULL;}
static void *setup_thread(void *unused){role=INIT;held=0;setup_result=qcom_slim_ngd_setup(&ctrl);return NULL;}
static void reset_case(const char *label){
 join_master();join_slave();if(locks_live){REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.dma_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.ssr_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));}
 for(unsigned n=0;n<buffer_count;n++)free(buffers[n]);buffer_count=channel_count=descriptor_count=0;memset(&ctrl,0,sizeof(ctrl));memset(channels,0,sizeof(channels));memset(descriptors,0,sizeof(descriptors));memset(regs,0,sizeof(regs));memset(tokens,0,sizeof(tokens));token_count=0;
 REQUIRE(!pthread_mutex_init(&ctrl.tx_lock.lock,NULL));REQUIRE(!pthread_mutex_init(&ctrl.dma_lock.lock,NULL));REQUIRE(!pthread_mutex_init(&ctrl.ssr_lock.lock,NULL));REQUIRE(!pthread_mutex_init(&ctrl.tx_buf_lock,NULL));locks_live=true;role=MAIN;held=0;
 parent.data=child.dev.data=&ctrl;child.dev.pm_enabled=true;child.dev.usage=1;ctrl.dev=&parent;ctrl.ctrl.dev=&child.dev;ctrl.ngd=&ngd;ngd.base=regs;ctrl.mwq=&ctrl;ctrl.m_work.fn=qcom_slim_ngd_master_worker;ctrl.qmi.handle=&ctrl;ctrl.state=QCOM_SLIM_NGD_CTRL_DOWN;ctrl.registered=ctrl.pm_ref_held=true;
 WRITE_ONCE(ctrl.parent_ready,true);WRITE_ONCE(ctrl.child_ready,true);WRITE_ONCE(ctrl.up_requested,true);WRITE_ONCE(ctrl.qmi_ready,true);
 block_rearm=rearm_entered=release_rearm=block_sender=sender_waiting=release_sender=block_notify=notify_entered=release_notify=false;stop_buf_waiting=stop_tx_waiting=stop_life_waiting=block_setup=setup_entered=release_setup=stop_finished=false;
 cancels=barriers=rx_preps=tx_preps=submits=issues=notifications=resumes=pm_marks=active_tx_holds=issue_during_termination=invalid_channel=release_before_drain=cookie_clobbers=bad_wait_locks=lock_errors=closed_master_queues=unregister_order_errors=gate_open_at_terminate=0;fault_kind=0;fault_at=rx_prepare_count=rx_submit_count=0;submit_errno=-ENOSPC;sender_result=setup_result=stop_result=0;notified_after_close=hold_cancel=block_master_complete=master_completed=release_master_complete=false;closed_slave_queues=PM_from_handshake=powerup_calls=wrong_notification_queue=0;rx_term_entered=false;cancel_waiting[0]=cancel_waiting[1]=release_cancel[0]=release_cancel[1]=false;case_name=label;cases++;
}
static int setup(void){int ret=qcom_slim_ngd_setup(&ctrl);
#if !FIXTURE_ADMISSION
 if(!ret)WRITE_ONCE(ctrl.dma_ready,true);
#endif
 return ret;}
static void audit(void){for(unsigned n=0;n<descriptor_count;n++)if(descriptors[n].submitted&&descriptors[n].cookie!=-999)cookie_clobbers++;check(!gate_open_at_terminate,"RX and master admission close before channel termination");check(!invalid_channel,"no DMA operation uses a released or missing channel");check(!issue_during_termination,"no descriptor is issued between termination and callback synchronization");check(!release_before_drain,"DMA channels are released after callbacks, master work and active senders drain");check(!cookie_clobbers,"submitted descriptor cookies remain owned by the provider");check(!bad_wait_locks&&!lock_errors,"worker drains and callback locks preserve the required lock order");check(!closed_slave_queues&&!PM_from_handshake&&!wrong_notification_queue,"PM-dependent notification stays outside the master handshake and closes with its producer");check(!closed_master_queues,"closed RX admission cannot queue master work");check(!unregister_order_errors,"client and QMI release follow producer drain");}
static void shutdown(void){qcom_slim_ngd_exit_dma(&ctrl);check(!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel,"shutdown clears both channel pointers");audit();}
int main(void){
 reset_case("normal-setup-rearm-and-shutdown");check(!setup(),"initial setup succeeds");qcom_slim_ngd_rx_msgq_cb(&ctrl.rx_desc[0]);shutdown();
 for(int kind=1;kind<=6;kind++)for(unsigned at=0;at<(kind>=5?32:1);at++){
  char label[90];snprintf(label,sizeof(label),"setup-failure-kind-%d-at-%u",kind,at);reset_case(label);fault_kind=kind;fault_at=at;int expected=kind<=2?-EIO:kind<=4?-ENOMEM:kind==5?-EINVAL:-ENOSPC;check(setup()==expected,"setup preserves request, allocation, preparation and submission errors");check(!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel,"failed setup releases its partial channel pair");check(!READ_ONCE(ctrl.dma_ready),"failed setup never opens RX or master admission");fault_kind=0;check(!setup(),"setup can retry after a fully unwound initial failure");check(ctrl.dma_tx_channel&&ctrl.dma_rx_channel,"a successful retry owns both live message channels");shutdown();
 }
 for(unsigned flag=0;flag<4;flag++){
  char label[90];snprintf(label,sizeof(label),"setup-denies-closed-lifecycle-flag-%u",flag);reset_case(label);if(flag==0)WRITE_ONCE(ctrl.parent_ready,false);if(flag==1)WRITE_ONCE(ctrl.child_ready,false);if(flag==2)WRITE_ONCE(ctrl.up_requested,false);if(flag==3)WRITE_ONCE(ctrl.qmi_ready,false);
  check(setup()==-ESHUTDOWN,"setup rejects closed startup or concurrent shutdown admission");check(!channel_count&&!issues,"closed setup does not acquire or issue DMA");shutdown();
 }
 reset_case("closed-TX-admission");check(!setup(),"setup succeeds before close");shutdown();sender_thread(NULL);role=MAIN;held=0;check(sender_result==-ESHUTDOWN,"new non-TID sends reject closed DMA before reserving a buffer");audit();
 reset_case("closed-master-admission");check(!setup(),"setup succeeds before master close");shutdown();u8 master[]={SLIM_MSG_MT_SRC_REFERRED_USER<<5|4,SLIM_USR_MC_MASTER_CAPABILITY,0,0};qcom_slim_ngd_rx(&ctrl,master);check(!ctrl.m_work.queued,"a late master capability cannot enqueue after shutdown");ctrl.m_work.queued=false;audit();
 reset_case("RX-resubmission-versus-shutdown");check(!setup(),"setup succeeds before callback race");block_rearm=true;pthread_t rx,stop;REQUIRE(!pthread_create(&rx,NULL,rx_thread,NULL));pthread_mutex_lock(&coordination);while(!rearm_entered)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);
#if FIXTURE_ADMISSION
 while(!stop_buf_waiting&&!rx_term_entered&&!stop_finished)pthread_cond_wait(&changed,&coordination);check(!stop_finished&&!rx_term_entered,"close serializes with an admitted RX rearm before terminating DMA");
#else
 while(!ctrl.dma_rx_channel->terminating&&!stop_finished)pthread_cond_wait(&changed,&coordination);
#endif
 release_rearm=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(rx,NULL));REQUIRE(!pthread_join(stop,NULL));audit();
 reset_case("active-non-TID-sender-versus-shutdown");check(!setup(),"setup succeeds before sender race");block_sender=true;pthread_t sender;REQUIRE(!pthread_create(&sender,NULL,sender_thread,NULL));pthread_mutex_lock(&coordination);while(!sender_waiting)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);
#if FIXTURE_ADMISSION
 while(!stop_tx_waiting&&!stop_finished)pthread_cond_wait(&changed,&coordination);check(!stop_finished,"shutdown waits for the active non-TID sender before terminating channels");
#else
 while(!stop_finished)pthread_cond_wait(&changed,&coordination);
#endif
 release_sender=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(sender,NULL));REQUIRE(!pthread_join(stop,NULL));check(sender_result==0,"an admitted sender can finish before shutdown releases its resources");audit();
 reset_case("PM-dependent-notification-does-not-block-runtime-DMA-stop");check(!setup(),"setup succeeds before notification PM race");
#if FIXTURE_ADMISSION
 start_master();join_master();check(ctrl.slave_work.queued&&!notifications,"master handshake queues separate PM-dependent notification work");block_notify=true;start_slave();
#else
 block_notify=true;start_master();check(false,"PM-dependent notifications require a separate work item and execution queue");
#endif
 pthread_mutex_lock(&coordination);while(!notify_entered)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);while(!stop_finished)pthread_cond_wait(&changed,&coordination);check(!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel,"runtime DMA stop completes while notification waits for PM progress");release_notify=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);join_master();join_slave();REQUIRE(!pthread_join(stop,NULL));shutdown();
 reset_case("master-postprocessing-cannot-publish-notification-after-close");check(!setup(),"setup succeeds before post-handshake closure race");block_master_complete=true;start_master();pthread_mutex_lock(&coordination);while(!master_completed)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);
#if FIXTURE_ADMISSION
 while(!cancels&&!stop_finished)pthread_cond_wait(&changed,&coordination);check(!stop_finished,"close drains a handshake that has finished TX but not postprocessing");
#else
 while(!stop_finished)pthread_cond_wait(&changed,&coordination);
#endif
 release_master_complete=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);join_master();REQUIRE(!pthread_join(stop,NULL));check(!ctrl.slave_work.queued,"closed master postprocessing cannot publish new notification work");audit();
 reset_case("notification-entry-after-runtime-close-does-not-reopen-DMA");check(!setup(),"setup succeeds before delayed notification");
#if FIXTURE_ADMISSION
 start_master();join_master();qcom_slim_ngd_exit_dma(&ctrl);start_slave();join_slave();check(!notifications&&!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel,"delayed notification discards a closed DMA generation");
#else
 check(false,"delayed PM work requires its own entry admission check");
#endif
 shutdown();
 reset_case("setup-versus-shutdown");block_setup=true;pthread_t init;REQUIRE(!pthread_create(&init,NULL,setup_thread,NULL));pthread_mutex_lock(&coordination);while(!setup_entered)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);
#if FIXTURE_ADMISSION
 while(!stop_life_waiting&&!stop_finished)pthread_cond_wait(&changed,&coordination);check(!stop_finished,"shutdown serializes against setup before touching its channels");
#else
 while(!stop_finished)pthread_cond_wait(&changed,&coordination);
#endif
 release_setup=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(init,NULL));REQUIRE(!pthread_join(stop,NULL));check(setup_result==0,"an admitted setup completes before serialized shutdown");audit();
 reset_case("SSR-DOWN-drains-before-QMI-and-client-release");check(!setup(),"setup succeeds before SSR shutdown");ctrl.state=QCOM_SLIM_NGD_CTRL_AWAKE;ctrl.m_work.queued=ctrl.slave_work.queued=true;qcom_slim_ngd_ssr_pdr_notify(&ctrl,QCOM_SSR_BEFORE_SHUTDOWN);check(!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel&&!ctrl.m_work.queued,"SSR shutdown drains DMA and queued master work");check(barriers==1,"SSR shutdown waits for PM callbacks before freeing its QMI client");audit();
 reset_case("child-remove-drains-before-QMI-and-client-release");check(!setup(),"setup succeeds before child removal");ctrl.m_work.queued=ctrl.slave_work.queued=true;qcom_slim_ngd_remove(&child);check(!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel&&!ctrl.m_work.queued,"child removal drains master and DMA resources");check(barriers==1,"child removal observes its PM callback barrier");audit();
 for(unsigned flag=0;flag<4;flag++){char label[90];snprintf(label,sizeof(label),"runtime-resume-denies-closed-lifecycle-%u",flag);reset_case(label);if(flag==0)WRITE_ONCE(ctrl.parent_ready,false);if(flag==1)WRITE_ONCE(ctrl.child_ready,false);if(flag==2)WRITE_ONCE(ctrl.up_requested,false);if(flag==3)WRITE_ONCE(ctrl.qmi_ready,false);check(qcom_slim_ngd_runtime_resume(&child.dev)==-ESHUTDOWN,"runtime resume rejects closed parent, child, UP or QMI admission");check(!channel_count&&!powerup_calls,"rejected resume never enters QMI powerup or reacquires DMA");shutdown();}
 for(unsigned n=0;n<5;n++){
  char label[90];snprintf(label,sizeof(label),"RX-rearm-error-%u",n);reset_case(label);check(!setup(),"setup succeeds before callback error");fault_kind=n?6:5;fault_at=0;int errors[]={0,-EIO,-ENOMEM,-ENOSPC,-EPIPE};submit_errno=errors[n];unsigned before=issues;qcom_slim_ngd_rx_msgq_cb(&ctrl.rx_desc[0]);check(issues==before,"failed callback preparation or submission never issues DMA");if(n)check(ctrl.rx_desc[0].cookie==errors[n],"callback keeps the precise submission error in client-owned storage");fault_kind=0;shutdown();
 }
 reset_case("overlapping-shutdowns-serialize-resource-release");check(!setup(),"setup succeeds before overlapping stop operations");
#if FIXTURE_ADMISSION
 hold_cancel=true;pthread_t first,second;REQUIRE(!pthread_create(&first,NULL,stop_thread,(void *)(uintptr_t)STOP_A));pthread_mutex_lock(&coordination);while(!cancel_waiting[0]&&!stop_finished)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&second,NULL,stop_thread,(void *)(uintptr_t)STOP_B));pthread_mutex_lock(&coordination);while(!stop_life_waiting&&!cancel_waiting[1]&&!stop_finished)pthread_cond_wait(&changed,&coordination);check(!stop_finished&&!cancel_waiting[1],"overlapping stop operations serialize before releasing channels");release_cancel[0]=release_cancel[1]=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(first,NULL));REQUIRE(!pthread_join(second,NULL));hold_cancel=false;check(!setup(),"a new setup can run after serialized shutdowns complete");
#else
 check(false,"overlapping stop operations need serialized resource release");
#endif
 shutdown();
 reset_case("already-running-RX-callback-after-close-before-termination");check(!setup(),"setup succeeds before closing callback admission");
#if FIXTURE_ADMISSION
 hold_cancel=true;REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);while(!cancel_waiting[0]&&!stop_finished)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);unsigned before_preps=rx_preps,before_issue=issues;rx_thread(NULL);role=MAIN;held=0;check(rx_preps==before_preps&&issues==before_issue,"an already-dispatched RX callback cannot rearm after the close gate");pthread_mutex_lock(&coordination);release_cancel[0]=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_join(stop,NULL));hold_cancel=false;
#else
 check(false,"RX callback rearm requires serialized shutdown admission");qcom_slim_ngd_exit_dma(&ctrl);
#endif
 audit();
 reset_case("master-postprocessing-cannot-enqueue-notification-after-close");check(!setup(),"setup succeeds before master postprocessing race");
#if FIXTURE_ADMISSION
 block_master_complete=true;start_master();pthread_mutex_lock(&coordination);while(!master_completed)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);REQUIRE(!pthread_create(&stop,NULL,stop_thread,NULL));pthread_mutex_lock(&coordination);while(!cancels&&!stop_finished)pthread_cond_wait(&changed,&coordination);release_master_complete=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);join_master();REQUIRE(!pthread_join(stop,NULL));check(!ctrl.slave_work.queued,"a finishing master cannot publish new notification work after closure");
#else
 check(false,"master postprocessing requires notification admission closure");qcom_slim_ngd_exit_dma(&ctrl);
#endif
 audit();
 reset_case("queued-notification-starting-after-runtime-close-is-suppressed");check(!setup(),"setup succeeds before queued notification closure");
#if FIXTURE_ADMISSION
 start_master();join_master();check(ctrl.slave_work.queued,"master can publish notification while transport is live");qcom_slim_ngd_exit_dma(&ctrl);start_slave();join_slave();check(!notifications&&!ctrl.dma_rx_channel&&!ctrl.dma_tx_channel,"a queued notification cannot wake the controller after its admission closes");
#else
 check(false,"notifications require their own guarded work item");qcom_slim_ngd_exit_dma(&ctrl);
#endif
 audit();
 join_master();join_slave();for(unsigned n=0;n<buffer_count;n++)free(buffers[n]);REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.dma_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.ssr_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_buf_lock));printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
