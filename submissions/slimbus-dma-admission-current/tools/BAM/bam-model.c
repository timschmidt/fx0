/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical channel/tasklet services. All descriptor storage survives the audit. */
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define REQUIRE(x) do {if(!(x)){fprintf(stderr,"fixture invariant %d: %s\n",__LINE__,#x);exit(3);}}while(0)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
struct list_head {struct list_head *next,*prev;};
#define LIST_HEAD(n) struct list_head n={&n,&n}
static void INIT_LIST_HEAD(struct list_head *h){h->next=h->prev=h;}
static bool list_empty(const struct list_head *h){return h->next==h;}
static void list_add(struct list_head *n,struct list_head *h){n->next=h->next;n->prev=h;h->next->prev=n;h->next=n;}
static void list_add_tail(struct list_head *n,struct list_head *h){n->prev=h->prev;n->next=h;h->prev->next=n;h->prev=n;}
static void list_del(struct list_head *n){n->prev->next=n->next;n->next->prev=n->prev;INIT_LIST_HEAD(n);}
static void list_splice_tail_init(struct list_head *h,struct list_head *to){if(list_empty(h))return;struct list_head *first=h->next,*last=h->prev;first->prev=to->prev;to->prev->next=first;last->next=to;to->prev=last;INIT_LIST_HEAD(h);}
#define list_first_entry(h,t,m) container_of((h)->next,t,m)
#define list_for_each_entry_safe(p,n,h,m) \
 for(struct list_head *walk=(h)->next,*following;walk!=(h) && ((following=walk->next),(p=container_of(walk,__typeof__(*p),m)),(n=(following==(h)?NULL:container_of(following,__typeof__(*n),m))),1);walk=following)
struct virt_dma_chan;
struct tasklet_struct {unsigned id;bool scheduled,started,joined,active,entered;pthread_t thread;};
struct spinlock {pthread_mutex_t mutex;unsigned id;};
struct dma_chan {struct dma_device *device;};
struct dma_device {int (*device_terminate_all)(struct dma_chan *);void (*device_synchronize)(struct dma_chan *);};
struct virt_dma_chan {struct dma_chan chan;struct spinlock lock;struct tasklet_struct task;struct list_head desc_allocated,desc_submitted,desc_issued,desc_completed,desc_terminated;};
struct virt_dma_desc {struct list_head node;unsigned id,freed;};
struct bam_device {struct dma_device common;struct tasklet_struct task;};
struct bam_chan {struct virt_dma_chan vc;struct bam_device *bdev;struct list_head desc_list;};
struct bam_async_desc {struct virt_dma_desc vd;struct list_head desc_node;int dir;};
static struct bam_device bdev_storage;
static struct bam_chan channels[2];
static struct bam_async_desc descs[2][18];
static pthread_mutex_t coordination=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed=PTHREAD_COND_INITIALIZER;
static _Thread_local unsigned depths[2];
static unsigned bad_lock,wrong_tasklet,barriers[2],term_calls,reset_calls,barrier_with_pending_descriptors;
static unsigned logical_retired_owner_use,callback_count[2],descriptor_frees[2],double_frees;
static bool owner_live[2],release_callback[2],action_done,sync_seen;
static int action_result;
static unsigned selected_channel;
static bool split_api;
static pthread_t action_thread;
static unsigned cases,checks,failures;
static const char *case_name;
static void check(bool ok,const char *message){checks++;if(!ok){failures++;fprintf(stderr,"%s: %s\n",case_name,message);}}
static void fixture_lock(struct spinlock *lock){if(depths[lock->id]++){bad_lock++;return;}REQUIRE(!pthread_mutex_lock(&lock->mutex));}
static void fixture_unlock(struct spinlock *lock){REQUIRE(depths[lock->id]);if(!--depths[lock->id])REQUIRE(!pthread_mutex_unlock(&lock->mutex));}
#define spin_lock_irqsave(l,f) do{(f)=0;(void)(f);fixture_lock(l);}while(0)
#define spin_unlock_irqrestore(l,f) do{(void)(f);fixture_unlock(l);}while(0)
#define lockdep_assert_held(l) REQUIRE(depths[(l)->id])
struct fixture_guard {struct spinlock *lock;};
static struct fixture_guard make_guard(struct spinlock *l){fixture_lock(l);return (struct fixture_guard){l};}
static void drop_guard(struct fixture_guard *g){if(g->lock)fixture_unlock(g->lock);}
#define scoped_guard(kind,l) for(struct fixture_guard guard __attribute__((cleanup(drop_guard)))=make_guard(l);guard.lock;fixture_unlock(guard.lock),guard.lock=NULL)
static struct bam_chan *to_bam_chan(struct dma_chan *c){return container_of(c,struct bam_chan,vc.chan);}
static struct virt_dma_chan *to_virt_chan(struct dma_chan *c){return container_of(c,struct virt_dma_chan,chan);}
static void might_sleep(void){}
static void vchan_vdesc_fini(struct virt_dma_desc *vd){unsigned ch=vd->id/18;REQUIRE(ch<2);if(vd->freed++)double_frees++;else descriptor_frees[ch]++;}
/* ACTUAL_VCHAN_FREE */
/* ACTUAL_VCHAN_GET_ALL */
static void *callback(void *arg){
 struct tasklet_struct *t=arg;unsigned id=t->id;
 pthread_mutex_lock(&coordination);t->active=t->entered=true;pthread_cond_broadcast(&changed);
 while(!release_callback[id])pthread_cond_wait(&changed,&coordination);
 if(!owner_live[id])logical_retired_owner_use++;callback_count[id]++;
 pthread_mutex_unlock(&coordination);
 fixture_lock(&channels[id].vc.lock);vchan_vdesc_fini(&descs[id][17].vd);fixture_unlock(&channels[id].vc.lock);
 pthread_mutex_lock(&coordination);t->active=t->scheduled=false;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return NULL;
}
static void tasklet_kill(struct tasklet_struct *t){
 pthread_mutex_lock(&coordination);sync_seen=true;pthread_cond_broadcast(&changed);
 if(t->id>1){wrong_tasklet++;pthread_mutex_unlock(&coordination);return;}
 struct bam_chan *c=&channels[t->id];
 if(!list_empty(&c->desc_list)||!list_empty(&c->vc.desc_allocated)||!list_empty(&c->vc.desc_submitted)||!list_empty(&c->vc.desc_issued)||!list_empty(&c->vc.desc_completed))barrier_with_pending_descriptors++;
 barriers[t->id]++;bool locked=depths[t->id];if(locked)bad_lock++;
 pthread_mutex_unlock(&coordination);
 if(locked)return;
 if(t->started&&!t->joined){REQUIRE(!pthread_join(t->thread,NULL));t->joined=true;}
 t->scheduled=false;
}
/* ACTUAL_VCHAN_SYNC */
static void bam_chan_init_hw(struct bam_chan *c,int dir){REQUIRE(depths[c->vc.lock.id]);reset_calls++;}
/* ACTUAL_BAM_TERMINATE */
/* ACTUAL_BAM_SYNC */
/* ACTUAL_API */
static void wire(struct bam_device *bdev){
/* ACTUAL_PROBE_OPS */
}
static void *terminate(void *arg){
 term_calls++;if(split_api){action_result=dmaengine_terminate_async(&channels[selected_channel].vc.chan);if(!action_result)dmaengine_synchronize(&channels[selected_channel].vc.chan);}else action_result=dmaengine_terminate_sync(&channels[selected_channel].vc.chan);
 pthread_mutex_lock(&coordination);action_done=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);return NULL;
}
static void init_channel(unsigned id){
 struct bam_chan *c=&channels[id];memset(c,0,sizeof(*c));c->bdev=&bdev_storage;c->vc.chan.device=&bdev_storage.common;c->vc.lock.id=c->vc.task.id=id;
 REQUIRE(!pthread_mutex_init(&c->vc.lock.mutex,NULL));
 INIT_LIST_HEAD(&c->desc_list);INIT_LIST_HEAD(&c->vc.desc_allocated);INIT_LIST_HEAD(&c->vc.desc_submitted);INIT_LIST_HEAD(&c->vc.desc_issued);INIT_LIST_HEAD(&c->vc.desc_completed);INIT_LIST_HEAD(&c->vc.desc_terminated);
 for(unsigned n=0;n<18;n++){struct bam_async_desc *d=&descs[id][n];memset(d,0,sizeof(*d));d->vd.id=id*18+n;INIT_LIST_HEAD(&d->vd.node);INIT_LIST_HEAD(&d->desc_node);}
 owner_live[id]=true;release_callback[id]=false;barriers[id]=callback_count[id]=descriptor_frees[id]=0;
}
static void start_callback(unsigned id){struct tasklet_struct *t=&channels[id].vc.task;t->started=t->scheduled=true;REQUIRE(!pthread_create(&t->thread,NULL,callback,t));pthread_mutex_lock(&coordination);while(!t->entered)pthread_cond_wait(&changed,&coordination);pthread_mutex_unlock(&coordination);}
static void run(unsigned mode,unsigned count,bool active,bool peer,unsigned channel,unsigned api){
 selected_channel=channel;split_api=api;
 char label[100];snprintf(label,sizeof(label),"selected-%u-api-%u-state-%u-descriptors-%u-active-%u-peer-%u",channel,api,mode,count,active,peer);case_name=label;cases++;
 memset(&bdev_storage,0,sizeof(bdev_storage));bdev_storage.task.id=2;wire(&bdev_storage);init_channel(0);init_channel(1);
 action_done=sync_seen=false;bad_lock=wrong_tasklet=logical_retired_owner_use=double_frees=term_calls=reset_calls=barrier_with_pending_descriptors=0;action_result=-999;
 struct list_head *heads[]={NULL,&channels[selected_channel].vc.desc_allocated,&channels[selected_channel].vc.desc_submitted,&channels[selected_channel].vc.desc_issued,&channels[selected_channel].vc.desc_completed};
 for(unsigned n=0;n<count;n++){struct bam_async_desc *d=&descs[selected_channel][n];if(mode==5)list_add_tail(&d->desc_node,&channels[selected_channel].desc_list);else list_add_tail(&d->vd.node,heads[mode]);}
 if(mode==4)channels[selected_channel].vc.task.scheduled=true;
 if(active)start_callback(selected_channel);if(peer)start_callback(selected_channel^1);
 REQUIRE(!pthread_create(&action_thread,NULL,terminate,NULL));
 pthread_mutex_lock(&coordination);while(!action_done&&!sync_seen)pthread_cond_wait(&changed,&coordination);
 check(!active||!action_done,"termination cannot return while the selected channel callback remains active");
 check(barriers[selected_channel]==1,"the selected channel synchronization callback is dispatched");
 check(!barriers[selected_channel^1]&&!wrong_tasklet,"another channel and the shared tasklet are not synchronized");
 if(action_done)owner_live[selected_channel]=false;
 release_callback[0]=release_callback[1]=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&coordination);
 REQUIRE(!pthread_join(action_thread,NULL));
 for(unsigned id=0;id<2;id++){struct tasklet_struct *t=&channels[id].vc.task;if(t->started&&!t->joined){REQUIRE(!pthread_join(t->thread,NULL));t->joined=true;}}
 owner_live[selected_channel]=false;
 check(!barrier_with_pending_descriptors,"descriptor termination precedes callback synchronization");
 check(action_result==0 && term_calls==1,"successful termination is preserved");
 check(!logical_retired_owner_use,"callback resources stay logically live until its barrier completes");
 check(descriptor_frees[selected_channel]==count+active,"all selected-channel descriptor owners are released once");
 check(descriptor_frees[selected_channel^1]==peer,"unrelated descriptors are only retired by their own callbacks");
 check(callback_count[selected_channel]==active && callback_count[selected_channel^1]==peer,"queued cancellation does not invent or suppress an active callback");
 check(!channels[selected_channel].vc.task.active&&!channels[selected_channel].vc.task.scheduled,"selected callback tasklet is drained before resource retirement");
 check(reset_calls==(mode==5 && count>0),"hardware-active descriptors follow the existing reset path");
 check(list_empty(&channels[selected_channel].desc_list)&&list_empty(&channels[selected_channel].vc.desc_allocated)&&list_empty(&channels[selected_channel].vc.desc_submitted)&&list_empty(&channels[selected_channel].vc.desc_issued)&&list_empty(&channels[selected_channel].vc.desc_completed)&&list_empty(&channels[selected_channel].vc.desc_terminated),"all selected channel lists are drained");
 check(!bad_lock&&!double_frees,"callback barrier and descriptor release preserve locking and ownership");
 for(unsigned id=0;id<2;id++)REQUIRE(!pthread_mutex_destroy(&channels[id].vc.lock.mutex));
}
int main(void){
 for(unsigned channel=0;channel<2;channel++)for(unsigned api=0;api<2;api++)for(unsigned mode=0;mode<6;mode++)for(unsigned n=0;n<(mode?3:1);n++)for(unsigned active=0;active<2;active++)for(unsigned peer=0;peer<2;peer++){unsigned counts[]={1,2,16};run(mode,mode?counts[n]:0,active,peer,channel,api);}
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
