/* SPDX-License-Identifier: GPL-2.0-only */
/* Synthetic SLIMbus services: no device, firmware, DMA, audio or sockets. */
#include <pthread.h>
#include <stdatomic.h>
#include <limits.h>
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define MSEC_PER_SEC 1000
#define GFP_KERNEL 0
#define IRQF_TRIGGER_HIGH 1
#define IRQF_NO_AUTOEN 2
#define SLIM_ROOT_FREQ 24576000
#define SLIM_CL_PER_SUPERFRAME_DIV8 6144
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define SLIM_MIN_CLK_GEAR 1
#define SLIM_MAX_CLK_GEAR 10
#define QCOM_SSR_BEFORE_SHUTDOWN 1
#define QCOM_SSR_AFTER_POWERUP 2
#define SERVREG_SERVICE_STATE_DOWN 3
#define SERVREG_SERVICE_STATE_UP 4
#define NOTIFY_OK 0
#define EXPORT_SYMBOL_GPL(x)
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "model invariant %d: %s\n", __LINE__, #x); exit(3); } } while (0)
struct mutex { pthread_mutex_t lock; bool held; };
struct completion { _Atomic unsigned done; };
struct wait_queue_head { bool initialized; };
#define READ_ONCE(x) atomic_load_explicit(&(x), memory_order_relaxed)
#define WRITE_ONCE(x,v) atomic_store_explicit(&(x),(v),memory_order_relaxed)
#define AF_QIPCRTR 42
#define SLIMBUS_QMI_SVC_ID 0x0301
#define SLIMBUS_QMI_SVC_V1 1
#define SLIMBUS_QMI_INS_ID 0
struct qmi_handle;
struct qmi_service { unsigned node,port; };
struct qmi_ops { int (*new_server)(struct qmi_handle *,struct qmi_service *); void (*del_server)(struct qmi_handle *,struct qmi_service *); };
struct qmi_handle { const struct qmi_ops *ops; };
struct sockaddr_qrtr { _Atomic unsigned sq_family,sq_node,sq_port; };
struct qcom_slim_ngd_qmi { void *handle; struct completion qmi_comp; struct qmi_handle svc_event_hdl; struct sockaddr_qrtr svc_info; };
struct work_struct { void (*fn)(struct work_struct *); bool queued, running; };
struct device { void *data; struct device *parent; bool pm_enabled, suspended; int usage; };
struct platform_device { struct device dev; };
struct notifier_block { int (*notifier_call)(struct notifier_block *, unsigned long, void *); };
struct pdr_handle { int unused; };
struct pdr_service { int unused; };
struct qcom_slim_ngd { struct platform_device *pdev; };
struct slim_device { struct device dev; };
struct slim_controller {
 struct device *dev;
 int id, min_cg, max_cg, laddr_ida, tid_idr, txn_lock;
 struct mutex lock;
 struct { struct mutex m_reconf; struct completion pause_comp; } sched;
 const char *name;
 void *a_framer;
 int clkgear;
 void (*get_laddr)(void), (*enable_stream)(void), (*disable_stream)(void), (*xfer_msg)(void), (*wakeup)(void);
};
enum qcom_slim_ngd_state {
 QCOM_SLIM_NGD_CTRL_AWAKE, QCOM_SLIM_NGD_CTRL_IDLE,
 QCOM_SLIM_NGD_CTRL_ASLEEP, QCOM_SLIM_NGD_CTRL_DOWN,
};
struct qcom_slim_ngd_ctrl {
 struct slim_controller ctrl;
 struct device *dev;
 struct qcom_slim_ngd_qmi qmi;
 struct wait_queue_head qmi_wait;
 _Atomic bool qmi_ready;
 struct completion qmi_up;
 struct mutex ssr_lock;
 struct work_struct ngd_up_work;
 enum qcom_slim_ngd_state state;
 bool registered, pm_ref_held;
 _Atomic bool parent_ready,child_ready,up_requested;
 struct { unsigned rootfreq, superfreq; } framer;
 struct qcom_slim_ngd *ngd;
 void *base, *mwq, *notifier;
 struct notifier_block nb;
 struct pdr_handle *pdr;
 struct mutex tx_lock;
 int tx_buf_lock, irq;
 struct completion reconf;
 struct work_struct m_work;
};
static int ctrl_ida;
static bool allocated_ids[64];
static struct slim_device children[64];
static unsigned child_count, ida_live, unowned_frees, qmi_live;
static unsigned qmi_inits, qmi_exits, registrations, unregistrations, resumes, powerups;
static int qmi_error, registration_error, power_error;
static void *qmi_allocations[64];
static long wait_result;
static unsigned wait_calls, wait_locked, enable_calls, cases, checks, failures;
static const char *current_case;
static struct qcom_slim_ngd_ctrl ctrl;
static struct platform_device parent, child;
static struct qcom_slim_ngd ngd;
static struct pdr_handle pdr;
static struct pdr_service pds;
static pthread_mutex_t model_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static pthread_t worker_thread, action_thread;
static _Thread_local bool worker_context, action_context;
static _Thread_local unsigned ssr_held;
static bool worker_started, worker_joined, wait_entered, init_entered, release_worker;
static bool block_wait, block_init, action_done, cancel_entered, mutex_waiter;
static bool bound, discovery_live, pdr_live, ssr_live, queue_live, mutexes_live;
static bool bind_on_add, fail_lookup, fail_ssr, fail_add;
static bool irq_enabled, base_ready, closing_expected, bind_in_cancel, bind_completed;
static bool DOWN_at_lookup, UP_at_ssr_registration, DOWN_at_ssr_registration;
static bool QMI_at_lookup, DOWN_at_pdr_release;
static bool run_before_irq, probe_discovery_drain;
static unsigned premature_schedules, invalid_parent_startup;
static unsigned parent_cancel_without_notification, wait_entry_notifications;
static int bind_child(void);

static bool UP_at_discovery, UP_at_lookup, run_at_lookup, UP_at_pdr_release, UP_at_ssr_release;
static int discovery_error, action_kind, action_result;
static int qmi_init_error,qmi_lookup_error;
static bool auto_service,UP_during_lookup,lookup_error_after_server;
static bool service_live[2],hold_after_wait,wait_returned,emit_in_cancel;
static unsigned wait_wakes,invalid_endpoint_init,connected_node,connected_port,closed_schedule_attempts;
static long last_wait_result;
static struct qmi_service services[2]={{17,0x3011},{23,0x3012}};
static void emit_new(unsigned which);
static void emit_del(unsigned which);
static unsigned invalid_client_init, invalid_resume, dma_closes, discovery_inits, discovery_exits, schedules, cancels, cancel_under_lock;
static bool parent_resources_ready(void)
{return irq_enabled && base_ready && pdr_live && ssr_live && queue_live;}
static void start_pending(void);
static void await_point(bool *flag);
static void drain(void);
static void check(bool ok, const char *what)
{ checks++; if (!ok) { failures++; fprintf(stderr, "%s: %s\n", current_case, what); } }
static void mutex_init(struct mutex *m)
{ if (m == &ctrl.ssr_lock || m == &ctrl.tx_lock) REQUIRE(!pthread_mutex_init(&m->lock, NULL)); else m->held=false; }
static void mutex_lock(struct mutex *m)
{
 if (m != &ctrl.ssr_lock && m != &ctrl.tx_lock) { REQUIRE(!m->held); m->held=true; return; }
 if (m == &ctrl.ssr_lock && action_context) {
  pthread_mutex_lock(&model_lock);
  if (init_entered && block_init) { mutex_waiter = true; pthread_cond_broadcast(&changed); }
  pthread_mutex_unlock(&model_lock);
 }
 REQUIRE(!pthread_mutex_lock(&m->lock)); if (m == &ctrl.ssr_lock) ssr_held++;
}
static void mutex_unlock(struct mutex *m)
{ if (m != &ctrl.ssr_lock && m != &ctrl.tx_lock) { REQUIRE(m->held); m->held=false; return; }
 if (m == &ctrl.ssr_lock) { REQUIRE(ssr_held); ssr_held--; } REQUIRE(!pthread_mutex_unlock(&m->lock)); }
static void lockdep_assert_held(struct mutex *m) { REQUIRE(m == &ctrl.ssr_lock && ssr_held); }
static void init_completion(struct completion *c) { atomic_store(&c->done,0); }
static void complete(struct completion *c)
{ pthread_mutex_lock(&model_lock); wait_wakes++; if(atomic_load(&c->done)!=UINT_MAX)atomic_fetch_add(&c->done,1);pthread_cond_broadcast(&changed);pthread_mutex_unlock(&model_lock); }
static void reinit_completion(struct completion *c) { atomic_store(&c->done,0); }
static void init_waitqueue_head(struct wait_queue_head *q) {q->initialized=true;}
static void wake_up_all(struct wait_queue_head *q)
{REQUIRE(q==&ctrl.qmi_wait && q->initialized);pthread_mutex_lock(&model_lock);wait_wakes++;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&model_lock);}
static void validate_wait_queue(struct wait_queue_head *q,int timeout)
{REQUIRE(q==&ctrl.qmi_wait && q->initialized && timeout==MSEC_PER_SEC);}
static long finish_wait(long ret)
{pthread_mutex_lock(&model_lock);last_wait_result=ret;wait_returned=true;pthread_cond_broadcast(&changed);while(hold_after_wait&&!release_worker)pthread_cond_wait(&changed,&model_lock);pthread_mutex_unlock(&model_lock);return ret;}
#define wait_event_interruptible_timeout(q,condition,timeout) ({ \
 validate_wait_queue(&(q),(timeout)); \
 pthread_mutex_lock(&model_lock);wait_calls++;wait_locked+=ssr_held;wait_entered=true;wait_entry_notifications=wait_wakes;pthread_cond_broadcast(&changed);long fixture_ret; \
 for(;;){if(condition){fixture_ret=1;break;}if(wait_result<0){fixture_ret=wait_result;break;}if(!block_wait||release_worker){fixture_ret=0;break;}pthread_cond_wait(&changed,&model_lock);} \
 pthread_mutex_unlock(&model_lock);finish_wait(fixture_ret); })
static void ida_init(int *p) { *p = 0; }
static void idr_init(int *p) { *p = 0; }
static void spin_lock_init(int *p) { *p = 0; }
static int ida_alloc(int *ida, int flags)
{
 REQUIRE(ida == &ctrl_ida && flags == GFP_KERNEL);
 registrations++;
 if (registration_error) return registration_error;
 for (unsigned n = 0; n < 64; n++) if (!allocated_ids[n]) {
  allocated_ids[n] = true; ida_live++; return n;
 }
 REQUIRE(0); return -ENOSPC;
}
static void ida_free(int *ida, int id)
{
 REQUIRE(ida == &ctrl_ida && id >= 0 && id < 64); unregistrations++;
 if (!allocated_ids[id]) unowned_frees++;
 else { allocated_ids[id] = false; ida_live--; }
}
static void of_register_slim_devices(struct slim_controller *c)
{ REQUIRE(c == &ctrl.ctrl && child_count + 2 <= 64); child_count += 2; }
static struct slim_device *to_slim_device(struct device *d)
{ return container_of(d, struct slim_device, dev); }
static void device_unregister(struct device *d)
{ REQUIRE(d && child_count); child_count--; }
static int device_for_each_child(struct device *parent, void *data,
                                 int (*callback)(struct device *, void *))
{
 REQUIRE(parent == &child.dev);
 unsigned n = child_count;
 for (unsigned i = n; i > 0; i--) callback(&children[i - 1].dev, data);
 return 0;
}
static void slim_report_absent(struct slim_device *d) { REQUIRE(d); }
/* ACTUAL_CORE */
static void *dev_get_drvdata(struct device *d) { return d->data; }
static bool pm_runtime_enabled(struct device *d) { return d->pm_enabled; }
static bool pm_runtime_suspended(struct device *d) { return d->suspended; }
static void pm_runtime_get_noresume(struct device *d) { d->usage++; }
static void pm_runtime_mark_last_busy(struct device *d) { REQUIRE(d == &child.dev); }
static void pm_runtime_put(struct device *d) { d->usage--; }
static void pm_runtime_put_noidle(struct device *d) { d->usage--; }
static int qcom_slim_ngd_power_up(struct qcom_slim_ngd_ctrl *c)
{ REQUIRE(c == &ctrl && c->qmi.handle); powerups++; invalid_parent_startup+=!parent_resources_ready(); if (!discovery_live || !child.dev.pm_enabled) invalid_resume++; return power_error; }
/* ACTUAL_RESUME */
static int pm_runtime_resume(struct device *d)
{ resumes++; int r = qcom_slim_ngd_runtime_resume(d); if (!r) d->suspended = false; return r; }
static int qcom_slim_qmi_init(struct qcom_slim_ngd_ctrl *c, bool master)
{
 REQUIRE(c == &ctrl && !master);
 invalid_parent_startup+=!parent_resources_ready() || closing_expected;
 pthread_mutex_lock(&model_lock); init_entered = true; pthread_cond_broadcast(&changed);
 while (block_init && !release_worker) pthread_cond_wait(&changed, &model_lock);
 pthread_mutex_unlock(&model_lock);
 qmi_inits++; if (!discovery_live || !child.dev.pm_enabled) invalid_client_init++;
 unsigned node=atomic_load(&c->qmi.svc_info.sq_node),port=atomic_load(&c->qmi.svc_info.sq_port);
 if(!node&&!port){invalid_endpoint_init++;return -ENODEV;}
 connected_node=node;connected_port=port;
 if (qmi_error) return qmi_error;
 for (unsigned n = 0; n < 64; n++) if (!qmi_allocations[n]) {
  qmi_allocations[n] = calloc(1, 1); REQUIRE(qmi_allocations[n]);
  c->qmi.handle = qmi_allocations[n]; qmi_live++; return 0;
 }
 REQUIRE(0); return -ENOMEM;
}
static void qcom_slim_qmi_exit(struct qcom_slim_ngd_ctrl *c)
{
 REQUIRE(c == &ctrl);
 if (!c->qmi.handle) return;
 for (unsigned n = 0; n < 64; n++) if (qmi_allocations[n] == c->qmi.handle) {
  free(qmi_allocations[n]); qmi_allocations[n] = NULL;
  c->qmi.handle = NULL; qmi_live--; qmi_exits++; return;
 }
 REQUIRE(0);
}
/* ACTUAL_ENABLE */
static long wait_for_completion_interruptible_timeout(struct completion *c,int timeout)
{
 REQUIRE(c==&ctrl.qmi_up && timeout==MSEC_PER_SEC);pthread_mutex_lock(&model_lock);wait_calls++;wait_locked+=ssr_held;wait_entered=true;pthread_cond_broadcast(&changed);long ret;
 for(;;){unsigned done=atomic_load(&c->done);if(done){if(done!=UINT_MAX)atomic_fetch_sub(&c->done,1);ret=1;break;}if(wait_result<0){ret=wait_result;break;}if(!block_wait||release_worker){ret=0;break;}pthread_cond_wait(&changed,&model_lock);}
 pthread_mutex_unlock(&model_lock);return finish_wait(ret);
}
static int msecs_to_jiffies(int ms) { return ms; }
/* ACTUAL_UP */
static void schedule_work(struct work_struct *w)
{ REQUIRE(w == &ctrl.ngd_up_work); pthread_mutex_lock(&model_lock); schedules++; premature_schedules+=!parent_resources_ready() || closing_expected; closed_schedule_attempts+=!READ_ONCE(ctrl.child_ready); w->queued = true; pthread_mutex_unlock(&model_lock); }
static void qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *c) { REQUIRE(c == &ctrl); dma_closes++; }
/* ACTUAL_QMI_CALLBACKS */
/* ACTUAL_QMI_OPS */
/* ACTUAL_NOTIFY */

/* ACTUAL_WRAPPERS */
static void *startup(void *unused)
{
 worker_context = true;
 pthread_mutex_lock(&model_lock); REQUIRE(ctrl.ngd_up_work.queued); ctrl.ngd_up_work.queued = false; ctrl.ngd_up_work.running = true; pthread_mutex_unlock(&model_lock);
 qcom_slim_ngd_up_worker(&ctrl.ngd_up_work);
 pthread_mutex_lock(&model_lock); ctrl.ngd_up_work.running = false; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock); return NULL;
}
static void start_pending(void)
{
 REQUIRE(!worker_started || worker_joined); worker_started = true; worker_joined = false;
 REQUIRE(!pthread_create(&worker_thread, NULL, startup, NULL));
}
static void await_point(bool *flag)
{ pthread_mutex_lock(&model_lock); while (!*flag) pthread_cond_wait(&changed, &model_lock); pthread_mutex_unlock(&model_lock); }
static void join_worker(void)
{ if (worker_started && !worker_joined) { REQUIRE(!pthread_join(worker_thread, NULL)); worker_joined = true; } }
static void drain(void)
{ join_worker(); for (unsigned n=0; ctrl.ngd_up_work.queued; n++) { REQUIRE(n<4); start_pending(); join_worker(); } }
static void cancel_work_sync(struct work_struct *w)
{
 REQUIRE(w == &ctrl.ngd_up_work); if(ssr_held){cancel_under_lock++;return;}
 if(block_wait && wait_entered && !READ_ONCE(ctrl.parent_ready) && READ_ONCE(ctrl.child_ready) && wait_wakes==wait_entry_notifications)parent_cancel_without_notification++;
 pthread_mutex_lock(&model_lock); cancels++; cancel_entered = true; w->queued = false; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock);
 if(bind_in_cancel){bind_in_cancel=false;REQUIRE(!bound);REQUIRE(!bind_child());bind_completed=true;}
 if(emit_in_cancel && discovery_live)emit_new(1);
 join_worker(); pthread_mutex_lock(&model_lock); w->queued = false; REQUIRE(!w->running); pthread_mutex_unlock(&model_lock);
}
static void *platform_get_drvdata(struct platform_device *d) { return d->dev.data; }
static void platform_set_drvdata(struct platform_device *d, void *data) { d->dev.data = data; }
static void dev_set_drvdata(struct device *d, void *data) { d->data = data; }
static void pm_runtime_use_autosuspend(struct device *d) { REQUIRE(d == &child.dev); }
static void pm_runtime_set_autosuspend_delay(struct device *d, int delay) { REQUIRE(d == &child.dev && delay == 100); }
static void pm_runtime_set_suspended(struct device *d) { d->suspended = true; }
static void pm_runtime_enable(struct device *d) { d->pm_enabled = true; }
static void pm_runtime_dont_use_autosuspend(struct device *d) { REQUIRE(d == &child.dev); }
static void pm_runtime_disable(struct device *d) { d->pm_enabled = false; }
static int qmi_handle_init(struct qmi_handle *h,int bytes,const struct qmi_ops *ops,void *handlers)
{REQUIRE(h==&ctrl.qmi.svc_event_hdl && bytes==0 && !handlers);discovery_inits++;if(qmi_init_error)return qmi_init_error;h->ops=ops;discovery_live=true;return 0;}
static void qmi_handle_release(struct qmi_handle *h)
{REQUIRE(h==&ctrl.qmi.svc_event_hdl && discovery_live);for(unsigned i=0;i<2;i++)if(service_live[i])emit_del(i);discovery_live=false;discovery_exits++;}
static int qmi_add_lookup(struct qmi_handle *h,unsigned service,unsigned version,unsigned instance)
{REQUIRE(h==&ctrl.qmi.svc_event_hdl && discovery_live && service==SLIMBUS_QMI_SVC_ID && version==SLIMBUS_QMI_SVC_V1 && instance==SLIMBUS_QMI_INS_ID);if(UP_during_lookup)slim_pd_status(SERVREG_SERVICE_STATE_UP,NULL,&ctrl);if(auto_service && (!qmi_lookup_error||lookup_error_after_server))emit_new(0);return qmi_lookup_error;}
static void emit_new(unsigned i)
{REQUIRE(i<2 && discovery_live);REQUIRE(!ctrl.qmi.svc_event_hdl.ops->new_server(&ctrl.qmi.svc_event_hdl,&services[i]));service_live[i]=true;}
static void emit_del(unsigned i)
{REQUIRE(i<2 && discovery_live);ctrl.qmi.svc_event_hdl.ops->del_server(&ctrl.qmi.svc_event_hdl,&services[i]);service_live[i]=false;}
/* ACTUAL_DISCOVERY */
/* ACTUAL_STOP_UP */
/* ACTUAL_STOP_PARENT_UP */
/* ACTUAL_CHILD */
#define INIT_WORK(w, f) do { (w)->fn = f; (w)->queued = (w)->running = false; } while (0)
static void qcom_slim_ngd_get_laddr(void) {}
static void qcom_slim_ngd_enable_stream(void) {}
static void qcom_slim_ngd_disable_stream(void) {}
static void qcom_slim_ngd_xfer_msg(void) {}
static void qcom_slim_ngd_master_worker(struct work_struct *w) {}
static void qcom_slim_ngd_interrupt(void) {}
static void *devm_kzalloc(struct device *d, size_t bytes, int flags)
{ REQUIRE(d == &parent.dev && bytes == sizeof(ctrl)); memset(&ctrl, 0, sizeof(ctrl)); return &ctrl; }
static void *devm_platform_get_and_ioremap_resource(struct platform_device *d, int n, void *p) { return &parent; }
static int platform_get_irq(struct platform_device *d, int n) { return 42; }
static int devm_request_irq(struct device *d, int irq, void (*fn)(void), int flags, const char *s, void *p) { return 0; }
static int dev_err_probe(struct device *d, int r, const char *s) { return r; }
static void enable_irq(int n) { REQUIRE(n == 42); if(run_before_irq)drain(); irq_enabled=true; }
static void disable_irq(int n) { REQUIRE(n == 42); irq_enabled=false; }
static void *create_singlethread_workqueue(const char *s) { queue_live = true; return &queue_live; }
static void destroy_workqueue(void *p) { REQUIRE(queue_live); queue_live = false; }
static struct pdr_handle *pdr_handle_alloc(void (*fn)(int, char *, void *), void *data)
{ REQUIRE(fn == slim_pd_status && data == &ctrl); pdr_live = true; return &pdr; }
static struct pdr_service *pdr_add_lookup(struct pdr_handle *p, const char *s, const char *path)
{
 if (UP_at_lookup) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, &ctrl);
 if (QMI_at_lookup)emit_new(1);
 if (run_at_lookup && ctrl.ngd_up_work.queued) { start_pending(); if(block_init){pthread_mutex_lock(&model_lock);while(!init_entered && (ctrl.ngd_up_work.queued || ctrl.ngd_up_work.running))pthread_cond_wait(&changed,&model_lock);pthread_mutex_unlock(&model_lock);}else join_worker(); }
 if (DOWN_at_lookup) slim_pd_status(SERVREG_SERVICE_STATE_DOWN,NULL,&ctrl);
 if (fail_lookup) return (void *)(intptr_t)-ENOENT;
 return &pds;
}
static void pdr_handle_release(struct pdr_handle *p)
{ REQUIRE(pdr_live); if (UP_at_pdr_release) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, &ctrl); if(DOWN_at_pdr_release){unsigned before=dma_closes;slim_pd_status(SERVREG_SERVICE_STATE_DOWN,NULL,&ctrl);check(dma_closes==before,"late DOWN leaves teardown to child removal after parent closure");} pdr_live = false; }
static void *qcom_register_ssr_notifier(const char *s, struct notifier_block *nb)
{ if(UP_at_ssr_registration)nb->notifier_call(nb,QCOM_SSR_AFTER_POWERUP,NULL);if(DOWN_at_ssr_registration)nb->notifier_call(nb,QCOM_SSR_BEFORE_SHUTDOWN,NULL);if (fail_ssr) return (void *)(intptr_t)-EIO; ssr_live = true; return nb; }
static void qcom_unregister_ssr_notifier(void *p, struct notifier_block *nb)
{ REQUIRE(ssr_live); if (UP_at_ssr_release) nb->notifier_call(nb, QCOM_SSR_AFTER_POWERUP, NULL); ssr_live = false; }
static int of_qcom_slim_ngd_register(struct device *d, struct qcom_slim_ngd_ctrl *c)
{
 if (fail_add) return -ENODEV;
 ngd.pdev = &child; c->ngd = &ngd;
 if (bind_on_add) bound = qcom_slim_ngd_probe(&child) == 0;
 if(probe_discovery_drain)drain();
 base_ready=true;
 return 0;
}
static void platform_device_unregister(struct platform_device *d)
{ REQUIRE(d == &child); if (bound) { qcom_slim_ngd_remove(d); bound = false; } }
/* ACTUAL_PARENT */
static void reset_case(const char *name)
{
 if(mutexes_live){REQUIRE(!pthread_mutex_destroy(&ctrl.ssr_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));}
 for(unsigned n=0;n<64;n++){free(qmi_allocations[n]);qmi_allocations[n]=NULL;}
 memset(&ctrl,0,sizeof(ctrl));memset(&parent,0,sizeof(parent));memset(&child,0,sizeof(child));memset(allocated_ids,0,sizeof(allocated_ids));
 parent.dev.data=&ctrl;child.dev.parent=&parent.dev;services[0]=(struct qmi_service){17,0x3011};services[1]=(struct qmi_service){23,0x3012};
 child_count=ida_live=unowned_frees=qmi_live=qmi_inits=qmi_exits=registrations=unregistrations=resumes=powerups=0;
 qmi_error=registration_error=discovery_error=power_error=qmi_init_error=qmi_lookup_error=0;
 wait_calls=wait_locked=enable_calls=wait_wakes=invalid_endpoint_init=connected_node=connected_port=closed_schedule_attempts=0;wait_result=1;last_wait_result=0;
 worker_started=worker_joined=wait_entered=init_entered=release_worker=false;
 block_wait=block_init=hold_after_wait=wait_returned=action_done=cancel_entered=mutex_waiter=false;
 bound=discovery_live=pdr_live=ssr_live=queue_live=mutexes_live=false;
 fail_lookup=fail_ssr=fail_add=UP_at_discovery=UP_at_lookup=run_at_lookup=UP_at_pdr_release=UP_at_ssr_release=false;
 bind_on_add=auto_service=true;UP_during_lookup=lookup_error_after_server=emit_in_cancel=false;service_live[0]=service_live[1]=false;
 invalid_client_init=invalid_resume=dma_closes=discovery_inits=discovery_exits=schedules=cancels=cancel_under_lock=0;
 irq_enabled=base_ready=closing_expected=bind_in_cancel=DOWN_at_lookup=UP_at_ssr_registration=DOWN_at_ssr_registration=run_before_irq=probe_discovery_drain=false;premature_schedules=invalid_parent_startup=0;
 QMI_at_lookup=DOWN_at_pdr_release=bind_completed=false;parent_cancel_without_notification=wait_entry_notifications=0;
 current_case=name;cases++;
}
static void parent_up(void){REQUIRE(!qcom_slim_ngd_ctrl_probe(&parent));mutexes_live=true;}
static int bind_child(void){int ret=qcom_slim_ngd_probe(&child);bound=!ret;return ret;}
static void up(void){check(qcom_slim_ngd_ssr_notify(&ctrl.nb,QCOM_SSR_AFTER_POWERUP,NULL)==NOTIFY_OK,"UP accepted");}
static void down(void){slim_pd_status(SERVREG_SERVICE_STATE_DOWN,NULL,&ctrl);}
static void remove_child(void){REQUIRE(bound);qcom_slim_ngd_remove(&child);bound=false;}
static void live(unsigned server)
{
 check(ctrl.registered && ida_live==1 && child_count==2,"one controller and its children");
 check(qmi_live==1 && ctrl.qmi.handle,"one QMI client");
 check(connected_node==services[server].node && connected_port==services[server].port,"client uses the admitted complete endpoint");
 check(child.dev.usage==0 && !ctrl.pm_ref_held,"one bootstrap reference consumed");
 check(!invalid_client_init && !invalid_endpoint_init && !unowned_frees,"no invalid endpoint or unowned resource use");
}
static void finish(void)
{
 if(pdr_live && ssr_live)qcom_slim_ngd_ctrl_remove(&parent);
 block_wait=block_init=hold_after_wait=false;release_worker=true;drain();
 check(!qmi_live && !ida_live && !child_count,"all client/controller resources released");
 check(!child.dev.usage && !ctrl.pm_ref_held,"all driver PM references balanced");
 check(!discovery_live && !service_live[0] && !service_live[1],"service callbacks drained at discovery release");
 check(!ctrl.ngd_up_work.queued && !ctrl.ngd_up_work.running,"no startup work escapes removal");
 check(!cancel_under_lock && !wait_locked,"wait and synchronous cancellation outside worker mutex");
 check(!closed_schedule_attempts,"QMI producer cannot queue startup after child admission closes");
 check(!pdr_live && !ssr_live && !queue_live,"parent providers and master queue closed");
 check(!invalid_client_init && !invalid_endpoint_init && !unowned_frees,"no invalid service/endpoint/owner use");
 check(!parent_cancel_without_notification,"parent wait notification precedes its synchronous cancellation");
 check(!premature_schedules,"startup producers respect complete parent resources and parent closure");
 check(!invalid_parent_startup,"no client initialization or power operation before parent readiness or after closure");
}
static void *action(void *unused)
{
 action_context=true;
 if(action_kind==0)remove_child();
 else if(action_kind==1)down();
 else if(action_kind==2)qcom_slim_ngd_ctrl_remove(&parent);
 else if(action_kind==3){action_result=qcom_slim_ngd_ctrl_probe(&parent);mutexes_live=true;}
 else if(action_kind==4)emit_del(0);else emit_new(1);
 pthread_mutex_lock(&model_lock);action_done=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&model_lock);return NULL;
}
static void concurrent_action(int kind)
{
 action_kind=kind;REQUIRE(!pthread_create(&action_thread,NULL,action,NULL));
 pthread_mutex_lock(&model_lock);while(!action_done&&!cancel_entered&&!mutex_waiter)pthread_cond_wait(&changed,&model_lock);
 release_worker=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&model_lock);REQUIRE(!pthread_join(action_thread,NULL));join_worker();
}
static void release_and_join(void)
{pthread_mutex_lock(&model_lock);release_worker=true;pthread_cond_broadcast(&changed);pthread_mutex_unlock(&model_lock);join_worker();}
int main(void)
{
 for(unsigned stage=0;stage<3;stage++)for(unsigned last_down=0;last_down<2;last_down++){
  char label[96];snprintf(label,sizeof(label),"partial-parent-probe-stage-%u-last-DOWN-%u",stage,last_down);reset_case(label);
  if(stage==0){UP_during_lookup=true;probe_discovery_drain=true;DOWN_at_lookup=last_down;}
  else if(stage==1){UP_at_lookup=run_at_lookup=true;DOWN_at_lookup=last_down;}
  else{UP_at_ssr_registration=run_before_irq=true;DOWN_at_ssr_registration=last_down;}
  parent_up();check(!qmi_inits && !premature_schedules,"no startup during partial parent probe");drain();
  if(last_down)check(!qmi_inits && !ctrl.up_requested,"last DOWN suppresses parent-ready replay");else live(0);
  finish();
 }
 for(unsigned producer=0;producer<2;producer++){
  char label[96];snprintf(label,sizeof(label),"parent-cancel-child-bind-producer-%u",producer);reset_case(label);bind_on_add=false;parent_up();up();
  bind_in_cancel=true;emit_in_cancel=producer;closing_expected=true;qcom_slim_ngd_ctrl_remove(&parent);drain();
  check(bind_completed,"concurrent child binding completes during parent cancellation");
  check(!qmi_inits && !premature_schedules,"a child completing bind cannot reopen closed parent startup");finish();
 }
 reset_case("partial-parent-QMI-after-UP");UP_at_lookup=QMI_at_lookup=run_at_lookup=true;parent_up();check(!qmi_inits && !premature_schedules,"late QMI during parent probe cannot queue startup");drain();live(1);finish();
 reset_case("child-rebind-QMI-arrival-during-probe");parent_up();remove_child();up();UP_during_lookup=true;check(!bind_child(),"child rebinds with UP and QMI callbacks in its probe");drain();live(0);finish();
 reset_case("DOWN-during-parent-provider-release");parent_up();up();drain();DOWN_at_pdr_release=true;closing_expected=true;qcom_slim_ngd_ctrl_remove(&parent);drain();finish();
 reset_case("closed-parent-forced-queued-worker");parent_up();up();WRITE_ONCE(ctrl.parent_ready,false);irq_enabled=false;drain();
 check(!wait_calls && !qmi_inits,"a queued worker rejects a closed parent before waiting");finish();
 reset_case("parent-close-after-positive-wait");parent_up();hold_after_wait=true;up();start_pending();await_point(&wait_returned);closing_expected=true;concurrent_action(2);hold_after_wait=false;drain();
 check(!qmi_inits,"worker rechecks parent after its successful service wait");finish();
 for(unsigned error=0;error<2;error++)for(unsigned stage=0;stage<3;stage++){
  char label[96];snprintf(label,sizeof(label),"partial-parent-error-%u-stage-%u",error,stage);reset_case(label);
  fail_lookup=!error;fail_ssr=error;
  if(stage==0){UP_during_lookup=probe_discovery_drain=true;}
  else if(stage==1){UP_at_lookup=run_at_lookup=true;}
  else{UP_at_ssr_registration=true;}
  action_result=qcom_slim_ngd_ctrl_probe(&parent);mutexes_live=true;check(action_result<0,"parent fails with outstanding remembered UP");
  check(!qmi_inits && !premature_schedules,"failed parent never permits startup");finish();
 }

 reset_case("idle-ready-without-UP");parent_up();check(!ctrl.ngd_up_work.queued && !qmi_inits,"discovery alone does not add initial DSP bootstrap");finish();
 reset_case("service-before-UP");parent_up();up();drain();live(0);finish();
 reset_case("service-after-expired-UP");auto_service=false;parent_up();up();drain();check(!qmi_inits && child.dev.usage==1,"unavailable service leaves startup uninitialized");emit_new(0);drain();live(0);finish();
 reset_case("service-after-two-expired-UPs");auto_service=false;parent_up();up();drain();up();drain();emit_new(1);drain();live(1);finish();
 reset_case("repeated-UP-retains-readiness");parent_up();up();drain();ctrl.state=QCOM_SLIM_NGD_CTRL_ASLEEP;child.dev.suspended=true;up();drain();
 check(powerups==2 && ctrl.state==QCOM_SLIM_NGD_CTRL_AWAKE,"second UP can wake an existing controller without another announcement");live(0);check(qmi_inits==1 && registrations==1,"repeated UP reuses ownership");finish();
 reset_case("old-delete-does-not-clear-replacement");parent_up();emit_new(1);emit_del(0);up();drain();live(1);finish();
 for(unsigned variant=0;variant<2;variant++){
  char label[80];snprintf(label,sizeof(label),"stale-delete-endpoint-component-%u",variant);reset_case(label);parent_up();if(!variant)services[1].node=services[0].node;else services[1].port=services[0].port;
  emit_new(1);emit_del(0);up();drain();live(1);finish();
 }
 for(unsigned zero=0;zero<2;zero++){
  char label[80];snprintf(label,sizeof(label),"valid-zero-endpoint-component-%u",zero);reset_case(label);auto_service=false;parent_up();if(!zero)services[0].node=0;else services[0].port=0;emit_new(0);up();drain();live(0);finish();
 }
 reset_case("matching-delete-blocks-startup");parent_up();emit_del(0);up();drain();check(!qmi_inits && child.dev.usage==1,"deleted service cannot initialize a client");emit_new(1);drain();live(1);finish();
 reset_case("QMI-arrival-during-child-probe");UP_during_lookup=true;parent_up();drain();live(0);finish();
 for(unsigned failure=0;failure<3;failure++){
  char label[80];snprintf(label,sizeof(label),"failed-discovery-%u-retry-UP",failure);reset_case(label);UP_during_lookup=true;
  if(!failure)qmi_init_error=-ENOMEM;else{qmi_lookup_error=-EIO;lookup_error_after_server=failure==2;}
  parent_up();check(!bound && !discovery_live && child.dev.usage==0,"failed discovery balances PM and its handle");up();check(!ctrl.ngd_up_work.queued,"failed probe excludes startup");
  qmi_init_error=qmi_lookup_error=0;UP_during_lookup=lookup_error_after_server=false;check(!bind_child(),"discovery retry binds child");drain();live(0);finish();
 }
 reset_case("UP-before-child-bind");bind_on_add=false;parent_up();up();check(!ctrl.ngd_up_work.queued,"unbound UP stays remembered");check(!bind_child(),"child binds later");drain();live(0);finish();
 reset_case("DOWN-before-child-bind");bind_on_add=false;parent_up();up();down();check(!bind_child(),"child binds after DOWN");drain();check(!qmi_inits,"last DOWN suppresses initial replay");finish();
 reset_case("UP-replayed-after-child-rebind");parent_up();up();drain();remove_child();check(!bind_child(),"child rebind succeeds");drain();live(0);check(qmi_inits==2,"fresh child discovery initializes a new client");finish();
 reset_case("DOWN-while-unbound-suppresses-replay");parent_up();up();drain();remove_child();down();check(!bind_child(),"child rebind succeeds after DOWN");drain();check(!qmi_live && qmi_inits==1,"unbound DOWN cancels replay");finish();
 reset_case("new-service-after-DOWN-stays-idle");auto_service=false;parent_up();up();drain();down();unsigned before_late=schedules;emit_new(0);check(schedules==before_late,"late service does not queue work after last DOWN");drain();check(!qmi_inits && !ctrl.ngd_up_work.queued,"late service respects last DOWN");up();drain();live(0);finish();
 reset_case("queued-UP-then-DOWN");parent_up();up();down();drain();check(!qmi_inits,"queued UP rejected after DOWN");finish();
 reset_case("queued-UP-then-child-remove");parent_up();up();remove_child();drain();check(!qmi_inits,"child removal cancels queued startup");finish();
 reset_case("retry-client-error-without-new-server");parent_up();qmi_error=-EIO;up();drain();check(!qmi_live && child.dev.usage==1,"failed client setup retains bootstrap");qmi_error=0;up();drain();live(0);finish();
 reset_case("retry-registration-error-without-new-server");parent_up();registration_error=-ENOSPC;up();drain();check(!qmi_live && !ida_live && child.dev.usage==1,"failed registration unwinds its new client");registration_error=0;up();drain();live(0);finish();
 for(unsigned n=0;n<3;n++){
  const long errors[]={-512,-4,0};char label[80];snprintf(label,sizeof(label),"wait-failure-%ld-late-service",errors[n]);reset_case(label);auto_service=false;parent_up();wait_result=errors[n];up();drain();check(!qmi_inits,"unsatisfied wait never initializes client");emit_new(0);drain();live(0);finish();
 }
 reset_case("server-deleted-after-positive-wait");parent_up();hold_after_wait=true;up();start_pending();await_point(&wait_returned);emit_del(0);release_and_join();hold_after_wait=false;drain();
 check(!qmi_inits && !invalid_endpoint_init,"post-wait readiness check rejects the deleted endpoint");emit_new(1);drain();live(1);finish();
 reset_case("DOWN-after-positive-wait");parent_up();hold_after_wait=true;up();start_pending();await_point(&wait_returned);down();release_and_join();hold_after_wait=false;drain();check(!qmi_inits,"post-wait admission rejects DOWN");finish();
 reset_case("service-arrives-during-wait");auto_service=false;parent_up();block_wait=true;up();start_pending();await_point(&wait_entered);unsigned before_ready=wait_wakes;emit_new(0);check(wait_wakes>before_ready,"service arrival notifies an existing waiter");release_and_join();block_wait=false;drain();live(0);finish();
 for(int kind=0;kind<3;kind++){
  char label[80];snprintf(label,sizeof(label),"cancel-wait-action-%d",kind);reset_case(label);auto_service=false;parent_up();block_wait=true;up();start_pending();await_point(&wait_entered);unsigned before_close=wait_wakes;concurrent_action(kind);block_wait=false;drain();
  check(wait_wakes>before_close,"lifecycle predicate change notifies its waiting worker");
  check(last_wait_result>0,"lifecycle closure satisfies wait predicate without a service or timeout");check(!qmi_inits,"cancellation never starts a client");finish();
 }
 reset_case("delete-serialized-with-client-initialization");parent_up();block_init=true;up();start_pending();await_point(&init_entered);concurrent_action(4);block_init=false;drain();
 check(connected_node==services[0].node && connected_port==services[0].port,"endpoint remains stable throughout admitted initialization");check(!invalid_endpoint_init,"delete cannot clear an endpoint in use under SSR lock");finish();
 reset_case("new-server-serialized-with-client-initialization");parent_up();block_init=true;up();start_pending();await_point(&init_entered);concurrent_action(5);block_init=false;
 check(connected_node==services[0].node && connected_port==services[0].port,"new announcement cannot change an endpoint during admitted initialization");down();drain();up();drain();live(1);finish();
 reset_case("QMI-arrival-during-parent-cancel");auto_service=false;parent_up();block_wait=emit_in_cancel=true;up();start_pending();await_point(&wait_entered);concurrent_action(2);block_wait=false;drain();check(!qmi_inits && !closed_schedule_attempts,"parent closure excludes the still-live discovery producer");finish();
 reset_case("PDR-cycle-rebinds-latest-service");parent_up();up();drain();down();emit_new(1);emit_del(0);up();drain();live(1);check(qmi_inits==2 && unregistrations==1,"PDR cycle transfers client/controller ownership once");finish();
 reset_case("registered-DOWN-after-failed-wake");parent_up();up();drain();ctrl.state=QCOM_SLIM_NGD_CTRL_DOWN;child.dev.suspended=true;power_error=-EIO;up();drain();
 check(powerups==2,"registered failed wake is attempted without a new announcement");check(ctrl.registered && ctrl.state==QCOM_SLIM_NGD_CTRL_DOWN,"failed registered wake retains its DOWN controller");down();check(!qmi_live && !ida_live && child.dev.usage==1,"DOWN tears down the registered failed wake once");finish();
 reset_case("repeated-DOWN-PM-balance");parent_up();up();drain();down();down();down();check(child.dev.usage==1 && !qmi_live && !ida_live,"duplicate DOWN retains only one bootstrap reference");finish();
 reset_case("external-PM-reference");parent_up();child.dev.usage+=3;remove_child();check(child.dev.usage==3,"child removal preserves external PM references");child.dev.usage-=3;finish();
 for(int mode=0;mode<6;mode++){
  char label[80];snprintf(label,sizeof(label),"parent-remove-mode-%d",mode);reset_case(label);parent_up();
  if(mode==1||mode==2||mode==5)up();if(mode==2||mode==5){block_init=true;start_pending();await_point(&init_entered);}
  UP_at_pdr_release=mode==3||mode==5;UP_at_ssr_release=mode==4||mode==5;concurrent_action(2);block_init=false;drain();finish();
 }
 for(int mode=0;mode<6;mode++){
  char label[80];snprintf(label,sizeof(label),"parent-probe-error-mode-%d",mode);reset_case(label);fail_ssr=mode<=3;fail_lookup=mode==4;fail_add=mode==5;
  UP_at_lookup=mode==1||mode==2;run_at_lookup=mode==2;block_init=mode==2;UP_at_pdr_release=mode==3;concurrent_action(3);block_init=false;drain();check(action_result<0,"parent probe returns injected error");finish();
 }
 if(mutexes_live){REQUIRE(!pthread_mutex_destroy(&ctrl.ssr_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));}
 for(unsigned n=0;n<64;n++)free(qmi_allocations[n]);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
