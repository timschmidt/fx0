// SPDX-License-Identifier: GPL-2.0-only
/* Only test services below: no firmware, USB, audio or network operations. */
enum { ACK, SEND_ERROR, TIMEOUT, NACK, BLOCK_ACK, BOUNDARY_ACK, STALE_ACK };
static pthread_mutex_t gate=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t gate_cond=PTHREAD_COND_INITIALIZER;
static bool entered,release_send;
static _Thread_local int response_mode;
static void put32(u8 *p,u32 v) { for (int i=0;i<4;i++) p[i]=(v>>(8*i))&255; }
static void response(struct qcom_smd_rpm *rpm,u32 id,bool nack) {
 u8 storage[81]={0},*p=storage+1;size_t size=20;
 put32(p,RPM_SERVICE_TYPE_REQUEST);put32(p+4,12);
 put32(p+8,RPM_MSG_TYPE_MSG_ID);put32(p+12,4);put32(p+16,id);
 if (nack) { const char err[]="resource does not exist";put32(p+20,RPM_MSG_TYPE_ERR);put32(p+24,sizeof(err));memcpy(p+28,err,sizeof(err));size=28+ALIGN(sizeof(err),4);put32(p+4,size-8); }
 struct rpmsg_device d={.dev={.data=rpm}};CHECK(!qcom_smd_rpm_callback(&d,p,size,NULL,0));
}
static int rpmsg_send(struct rpmsg_endpoint *ep,void *data,size_t size) {
 atomic_fetch_add(&sends,1);CHECK(size>=28&&size<256);CHECK(ep->rpm->waiting);
 CHECK(!ep->rpm->sleep_owner);u32 id=get_unaligned_le32((u8 *)data+8);
 response_mode=ep->mode;
 if (response_mode==SEND_ERROR) return -EIO;
 if (response_mode==BLOCK_ACK) {
  CHECK(!pthread_mutex_lock(&gate));entered=true;CHECK(!pthread_cond_broadcast(&gate_cond));
  while (!release_send) CHECK(!pthread_cond_wait(&gate_cond,&gate));
  CHECK(!pthread_mutex_unlock(&gate));
 }
 if (response_mode==ACK||response_mode==BLOCK_ACK||response_mode==BOUNDARY_ACK) response(ep->rpm,id,false);
 if (response_mode==NACK) response(ep->rpm,id,true);
 if (response_mode==STALE_ACK) response(ep->rpm,id+1,false);
 return 0;
}
static int wait_for_completion_timeout(struct completion *c,int timeout) {
 CHECK(timeout==5*HZ);CHECK(!pthread_mutex_lock(&c->native));
 int result=c->done;if (result) c->done--;
 CHECK(!pthread_mutex_unlock(&c->native));
 return response_mode==BOUNDARY_ACK?0:result;
}
static void init(struct qcom_smd_rpm *r,struct rpmsg_endpoint *ep) {
 memset(r,0,sizeof(*r));CHECK(!pthread_mutex_init(&r->lock.native,NULL));
 CHECK(!pthread_mutex_init(&r->ack_lock.native,NULL));CHECK(!pthread_mutex_init(&r->ack.native,NULL));
 ep->rpm=r;ep->mode=ACK;r->rpm_channel=ep;
}
static void fini(struct qcom_smd_rpm *r) {
 CHECK(!r->waiting&&!r->sleep_owner);CHECK(!pthread_mutex_destroy(&r->lock.native));
 CHECK(!pthread_mutex_destroy(&r->ack_lock.native));CHECK(!pthread_mutex_destroy(&r->ack.native));
}
static int write_vote(struct qcom_smd_rpm *r) { u32 value=0x12345678;return qcom_rpm_smd_write(r,1,0x616f646c,3,&value,sizeof(value)); }
static void identity_cases(void) {
 struct qcom_smd_rpm r,other;struct rpmsg_endpoint ep,ep2;init(&r,&ep);init(&other,&ep2);
 struct qcom_rpm_smd_sleep_token t={0},copy={0},second={0};
 CHECK(qcom_rpm_smd_freeze(NULL,&t)==-EINVAL);CHECK(qcom_rpm_smd_freeze(&r,NULL)==-EINVAL);
 CHECK(qcom_rpm_smd_thaw(NULL,&t)==-EINVAL);CHECK(qcom_rpm_smd_thaw(&r,NULL)==-EINVAL);
 irq_off=true;CHECK(qcom_rpm_smd_freeze(&r,&t)==-EPERM);CHECK(!r.sleep_owner&&!t.cookie);irq_off=false;
 CHECK(qcom_rpm_smd_thaw(&r,&t)==-ESTALE);
 for (int cycle=0;cycle<100;cycle++) {
  CHECK(!qcom_rpm_smd_freeze(&r,&t));CHECK(t.cookie==(u64)cycle+1);CHECK(r.sleep_owner==&t);
  CHECK(qcom_rpm_smd_freeze(&r,&second)==-EBUSY);CHECK(qcom_rpm_smd_freeze(&r,&t)==-EINVAL);
  copy=t;CHECK(qcom_rpm_smd_thaw(&r,&copy)==-ESTALE);CHECK(qcom_rpm_smd_thaw(&other,&t)==-ESTALE);
  int sent=atomic_load(&sends);CHECK(write_vote(&r)==-EBUSY);CHECK(atomic_load(&sends)==sent);
  CHECK(!write_vote(&other));
  irq_off=true;CHECK(qcom_rpm_smd_thaw(&r,&t)==-EPERM);irq_off=false;CHECK(r.sleep_owner==&t);
  u64 id=t.cookie;t.cookie++;CHECK(qcom_rpm_smd_thaw(&r,&t)==-ESTALE);t.cookie=id;
  CHECK(!qcom_rpm_smd_thaw(&r,&t));CHECK(!t.cookie&&!r.sleep_owner);
  CHECK(qcom_rpm_smd_thaw(&r,&copy)==-ESTALE);CHECK(!write_vote(&r));
  atomic_fetch_add(&cases,1);
 }
 r.sleep_sequence=U64_MAX;CHECK(qcom_rpm_smd_freeze(&r,&t)==-EOVERFLOW);CHECK(!t.cookie&&!r.sleep_owner);
 fini(&r);fini(&other);
}
static void uncertain_cases(void) {
 for (int mode=ACK;mode<=STALE_ACK;mode++) {
  if (mode==BLOCK_ACK) continue;
  struct qcom_smd_rpm r;struct rpmsg_endpoint ep;init(&r,&ep);ep.mode=mode;
  struct qcom_rpm_smd_sleep_token t={0};int ret=write_vote(&r);
  CHECK((ret==0)==(mode==ACK));CHECK(r.uncertain==(mode!=ACK));
  CHECK(!r.waiting);response(&r,r.msg_id,false); /* A late ACK cannot erase uncertainty. */
  ep.mode=ACK;CHECK(!write_vote(&r));
  if (mode==ACK) { CHECK(!qcom_rpm_smd_freeze(&r,&t));CHECK(!qcom_rpm_smd_thaw(&r,&t)); }
  else { CHECK(qcom_rpm_smd_freeze(&r,&t)==-EIO);CHECK(!t.cookie&&!r.sleep_owner); }
  fini(&r);atomic_fetch_add(&cases,1);
 }
 struct qcom_smd_rpm r;struct rpmsg_endpoint ep;init(&r,&ep);struct qcom_rpm_smd_sleep_token t={0};
 allocation_fail=true;CHECK(write_vote(&r)==-ENOMEM);allocation_fail=false;
 CHECK(qcom_rpm_smd_write(&r,0,0,0,NULL,SIZE_MAX)==-EINVAL);CHECK(!r.uncertain&&!r.msg_id);
 CHECK(!qcom_rpm_smd_freeze(&r,&t));CHECK(!qcom_rpm_smd_thaw(&r,&t));fini(&r);atomic_fetch_add(&cases,1);
}
struct threaded { struct qcom_smd_rpm *r;struct qcom_rpm_smd_sleep_token token;atomic_int started,done;int ret; };
static void *writer(void *arg) { struct threaded *t=arg;atomic_store(&t->started,1);t->ret=write_vote(t->r);atomic_store(&t->done,1);return NULL; }
static void *freezer(void *arg) { struct threaded *t=arg;atomic_store(&t->started,1);t->ret=qcom_rpm_smd_freeze(t->r,&t->token);atomic_store(&t->done,1);return NULL; }
static void concurrency_cases(void) {
 for (int n=0;n<40;n++) {
  struct qcom_smd_rpm r;struct rpmsg_endpoint ep;init(&r,&ep);ep.mode=BLOCK_ACK;
  struct threaded w={.r=&r},f={.r=&r};pthread_t wt,ft;entered=false;release_send=false;
  CHECK(!pthread_create(&wt,NULL,writer,&w));CHECK(!pthread_mutex_lock(&gate));
  while (!entered) CHECK(!pthread_cond_wait(&gate_cond,&gate));CHECK(!pthread_mutex_unlock(&gate));
  CHECK(r.waiting);CHECK(!pthread_create(&ft,NULL,freezer,&f));
  while (!atomic_load(&f.started)) sched_yield();
  CHECK(!atomic_load(&f.done)); /* Request mutex is held by the blocked sender. */
  CHECK(!pthread_mutex_lock(&gate));release_send=true;CHECK(!pthread_cond_broadcast(&gate_cond));CHECK(!pthread_mutex_unlock(&gate));
  CHECK(!pthread_join(wt,NULL));CHECK(!pthread_join(ft,NULL));CHECK(!w.ret&&!f.ret&&!r.waiting);
  CHECK(r.sleep_owner==&f.token);CHECK(!pthread_mutex_trylock(&r.lock.native));CHECK(!pthread_mutex_unlock(&r.lock.native));
  ep.mode=ACK;
  struct threaded late[8]={0};pthread_t threads[8];int before=atomic_load(&sends);
  for (int i=0;i<8;i++) { late[i].r=&r;CHECK(!pthread_create(&threads[i],NULL,writer,&late[i])); }
  for (int i=0;i<8;i++) { CHECK(!pthread_join(threads[i],NULL));CHECK(late[i].ret==-EBUSY); }
  CHECK(atomic_load(&sends)==before);CHECK(!qcom_rpm_smd_thaw(&r,&f.token));CHECK(!write_vote(&r));
  fini(&r);atomic_fetch_add(&cases,1);
 }
}
int main(void) {
 alarm(50);identity_cases();uncertain_cases();concurrency_cases();CHECK(!atomic_load(&allocations));
 printf("{\"cases\":%d,\"checks\":%d,\"failures\":0,\"threaded_drain_cases\":40}\n",atomic_load(&cases),atomic_load(&checks));return 0;
}
