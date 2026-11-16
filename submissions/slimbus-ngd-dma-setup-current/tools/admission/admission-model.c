/* SPDX-License-Identifier: GPL-2.0-only */
/* Synthetic SLIMbus services: no device, firmware, DMA, audio or sockets. */
#include <pthread.h>
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
struct completion { int done; };
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
 struct { void *handle; struct completion qmi_comp; } qmi;
 struct completion qmi_up;
 struct mutex ssr_lock;
 struct work_struct ngd_up_work;
 enum qcom_slim_ngd_state state;
 bool registered, child_ready, up_requested, pm_ref_held;
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
static bool UP_at_discovery, UP_at_lookup, run_at_lookup, UP_at_pdr_release, UP_at_ssr_release;
static int discovery_error, action_kind, action_result;
static unsigned invalid_client_init, invalid_resume, dma_closes, discovery_inits, discovery_exits, schedules, cancels, cancel_under_lock;
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
static void init_completion(struct completion *c) { c->done = 0; }
static void complete(struct completion *c) { c->done++; }
static void reinit_completion(struct completion *c) { c->done = 0; }
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
{ REQUIRE(c == &ctrl && c->qmi.handle); powerups++; if (!discovery_live || !child.dev.pm_enabled) invalid_resume++; return power_error; }
/* ACTUAL_RESUME */
static int pm_runtime_resume(struct device *d)
{ resumes++; int r = qcom_slim_ngd_runtime_resume(d); if (!r) d->suspended = false; return r; }
static int qcom_slim_qmi_init(struct qcom_slim_ngd_ctrl *c, bool master)
{
 REQUIRE(c == &ctrl && !master);
 pthread_mutex_lock(&model_lock); init_entered = true; pthread_cond_broadcast(&changed);
 while (block_init && !release_worker) pthread_cond_wait(&changed, &model_lock);
 pthread_mutex_unlock(&model_lock);
 qmi_inits++; if (!discovery_live || !child.dev.pm_enabled) invalid_client_init++;
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
static long wait_for_completion_interruptible_timeout(struct completion *c, int timeout)
{
 REQUIRE(c == &ctrl.qmi_up && timeout == MSEC_PER_SEC);
 wait_calls++; wait_locked += ssr_held;
 pthread_mutex_lock(&model_lock); wait_entered = true; pthread_cond_broadcast(&changed);
 while (block_wait && !release_worker) pthread_cond_wait(&changed, &model_lock);
 pthread_mutex_unlock(&model_lock); return wait_result;
}
static int msecs_to_jiffies(int ms) { return ms; }
/* ACTUAL_UP */
static void schedule_work(struct work_struct *w)
{ REQUIRE(w == &ctrl.ngd_up_work); pthread_mutex_lock(&model_lock); schedules++; w->queued = true; pthread_mutex_unlock(&model_lock); }
static void qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *c) { REQUIRE(c == &ctrl); dma_closes++; }
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
 REQUIRE(w == &ctrl.ngd_up_work); cancel_under_lock += ssr_held != 0;
 pthread_mutex_lock(&model_lock); cancels++; cancel_entered = true; w->queued = false; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock);
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
static int qcom_slim_ngd_qmi_svc_event_init(struct qcom_slim_ngd_ctrl *c)
{
 REQUIRE(c == &ctrl); discovery_inits++;
 if (UP_at_discovery) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, c);
 if (discovery_error) return discovery_error;
 discovery_live = true; return 0;
}
static void qcom_slim_ngd_qmi_svc_event_deinit(void *q)
{ REQUIRE(q == &ctrl.qmi && discovery_live); discovery_live = false; discovery_exits++; }
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
static void enable_irq(int n) { REQUIRE(n == 42); }
static void disable_irq(int n) { REQUIRE(n == 42); }
static void *create_singlethread_workqueue(const char *s) { queue_live = true; return &queue_live; }
static void destroy_workqueue(void *p) { REQUIRE(queue_live); queue_live = false; }
static struct pdr_handle *pdr_handle_alloc(void (*fn)(int, char *, void *), void *data)
{ REQUIRE(fn == slim_pd_status && data == &ctrl); pdr_live = true; return &pdr; }
static struct pdr_service *pdr_add_lookup(struct pdr_handle *p, const char *s, const char *path)
{
 if (fail_lookup) return (void *)(intptr_t)-ENOENT;
 if (UP_at_lookup) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, &ctrl);
 if (run_at_lookup) { start_pending(); await_point(&init_entered); }
 return &pds;
}
static void pdr_handle_release(struct pdr_handle *p)
{ REQUIRE(pdr_live); if (UP_at_pdr_release) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, &ctrl); pdr_live = false; }
static void *qcom_register_ssr_notifier(const char *s, struct notifier_block *nb)
{ if (fail_ssr) return (void *)(intptr_t)-EIO; ssr_live = true; return nb; }
static void qcom_unregister_ssr_notifier(void *p, struct notifier_block *nb)
{ REQUIRE(ssr_live); if (UP_at_ssr_release) nb->notifier_call(nb, QCOM_SSR_AFTER_POWERUP, NULL); ssr_live = false; }
static int of_qcom_slim_ngd_register(struct device *d, struct qcom_slim_ngd_ctrl *c)
{
 if (fail_add) return -ENODEV;
 ngd.pdev = &child; c->ngd = &ngd;
 if (bind_on_add) bound = qcom_slim_ngd_probe(&child) == 0;
 return 0;
}
static void platform_device_unregister(struct platform_device *d)
{ REQUIRE(d == &child); if (bound) { qcom_slim_ngd_remove(d); bound = false; } }
/* ACTUAL_PARENT */
static void reset_case(const char *name)
{
 if (mutexes_live) { REQUIRE(!pthread_mutex_destroy(&ctrl.ssr_lock.lock)); REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock)); }
 for (unsigned n=0; n<64; n++) { free(qmi_allocations[n]); qmi_allocations[n]=NULL; }
 memset(&ctrl,0,sizeof(ctrl)); memset(&parent,0,sizeof(parent)); memset(&child,0,sizeof(child));
 memset(allocated_ids,0,sizeof(allocated_ids)); parent.dev.data=&ctrl; child.dev.parent=&parent.dev;
 child_count=ida_live=unowned_frees=qmi_live=qmi_inits=qmi_exits=registrations=unregistrations=resumes=powerups=0;
 qmi_error=registration_error=discovery_error=power_error=0; wait_calls=wait_locked=enable_calls=0; wait_result=1;
 worker_started=worker_joined=wait_entered=init_entered=release_worker=false;
 block_wait=block_init=action_done=cancel_entered=mutex_waiter=false;
 bound=discovery_live=pdr_live=ssr_live=queue_live=mutexes_live=false;
 fail_lookup=fail_ssr=fail_add=UP_at_discovery=UP_at_lookup=run_at_lookup=UP_at_pdr_release=UP_at_ssr_release=false;
 bind_on_add=true; invalid_client_init=invalid_resume=dma_closes=discovery_inits=discovery_exits=schedules=cancels=cancel_under_lock=0;
 current_case=name; cases++;
}
static int bind_child(void) { int r=qcom_slim_ngd_probe(&child); bound=!r; return r; }
static void parent_up(void)
{ REQUIRE(!qcom_slim_ngd_ctrl_probe(&parent)); mutexes_live=true; }
static void up(void) { check(qcom_slim_ngd_ssr_notify(&ctrl.nb,QCOM_SSR_AFTER_POWERUP,NULL)==NOTIFY_OK,"UP accepted"); }
static void down(void) { slim_pd_status(SERVREG_SERVICE_STATE_DOWN,NULL,&ctrl); }
static void remove_child(void) { REQUIRE(bound); qcom_slim_ngd_remove(&child); bound=false; }
static void audit_removed(void)
{
 check(!invalid_client_init && !invalid_resume,"client initialization and power-up require active child services");
 check(!qmi_live && !ida_live && !child_count,"all child client/controller resources released");
 check(child.dev.usage==0,"child driver PM references balanced");
 check(!discovery_live && !child.dev.pm_enabled,"discovery and runtime PM closed");
 check(!ctrl.ngd_up_work.queued && !ctrl.ngd_up_work.running,"startup work quiescent at child removal");
 check(!cancel_under_lock && !wait_locked,"wait and cancel outside SSR mutex");
 check(!unowned_frees,"controller ID released only by owner");
}
static void finish(void)
{
 if(pdr_live && ssr_live) qcom_slim_ngd_ctrl_remove(&parent);
 if(ctrl.ctrl.dev) drain(); else ctrl.ngd_up_work.queued=false;
 audit_removed();
 check(!pdr_live && !ssr_live && !queue_live,"parent providers and master queue closed");
}
static void *action(void *unused)
{
 action_context=true;
 if(action_kind==0)remove_child();
 else if(action_kind==1)down();
 else if(action_kind==2)qcom_slim_ngd_ctrl_remove(&parent);
 else { action_result=qcom_slim_ngd_ctrl_probe(&parent); mutexes_live=true; }
 pthread_mutex_lock(&model_lock); action_done=true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock); return NULL;
}
static void concurrent_action(int kind)
{
 action_kind=kind; REQUIRE(!pthread_create(&action_thread,NULL,action,NULL));
 pthread_mutex_lock(&model_lock);
 while(!action_done && !cancel_entered && !mutex_waiter) pthread_cond_wait(&changed,&model_lock);
 release_worker=true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock);
 REQUIRE(!pthread_join(action_thread,NULL)); join_worker();
}
static void live(void)
{
 check(qmi_live==1 && ida_live==1 && child_count==2,"one initialized controller and its children");
 check(child.dev.usage==0,"successful registration drops one bootstrap reference");
 check(!invalid_client_init && !invalid_resume,"no client use outside child lifetime");
}
int main(void)
{
 reset_case("bound-idle-remove"); parent_up(); finish();
 reset_case("UP-before-bind"); bind_on_add=false; parent_up(); up();
 check(!ctrl.ngd_up_work.queued,"unbound UP does not queue startup");
 check(!bind_child(),"later child bind succeeds"); drain(); live(); finish();
 reset_case("UP-then-DOWN-before-bind"); bind_on_add=false; parent_up(); up(); down();
 check(!ctrl.ngd_up_work.queued,"unbound notifications do not queue startup");
 check(!bind_child(),"child bind succeeds after unbound DOWN"); drain();
 check(!qmi_inits && !ida_live,"last DOWN suppresses remembered UP"); finish();
 reset_case("UP-during-discovery"); UP_at_discovery=true; parent_up(); drain(); live(); finish();
 reset_case("discovery-failure"); discovery_error=-EIO; parent_up();
 check(!bound && child.dev.usage==0,"failed discovery drops bootstrap reference"); up();
 check(!ctrl.ngd_up_work.queued,"failed child probe excludes startup");
 if(ctrl.ngd_up_work.queued)drain();
 discovery_error=0; check(!bind_child(),"discovery retry binds"); drain(); live(); finish();
 reset_case("failed-discovery-with-UP-during-probe"); discovery_error=-EAGAIN; UP_at_discovery=true; parent_up();
 check(!bound && !ctrl.ngd_up_work.queued && child.dev.usage==0,"UP during failed discovery stays unqueued and PM balanced");
 UP_at_discovery=false; discovery_error=0; check(!bind_child(),"probe retry succeeds"); drain(); live(); finish();
 reset_case("success-duplicate-UP"); parent_up(); up(); drain(); up(); drain(); up(); drain(); live();
 check(qmi_inits==1 && registrations==1,"repeated UP retains one registration/client"); finish();
 reset_case("repeated-DOWN-after-UP"); parent_up(); up(); drain(); down(); down(); down();
 check(child.dev.usage==1 && !ida_live && !qmi_live,"repeated DOWN owns only one bootstrap reference"); finish();
 reset_case("DOWN-after-initial-QMI-error"); parent_up(); qmi_error=-EIO; up(); drain(); down(); down();
 check(child.dev.usage==1 && !qmi_live && !ida_live,"failed enable and DOWN retain one bootstrap reference"); finish();
 reset_case("DOWN-after-registered-power-failure"); parent_up(); power_error=-EIO; up(); drain();
 check(ctrl.state==QCOM_SLIM_NGD_CTRL_DOWN && ctrl.registered,"existing resume error behavior leaves registered controller DOWN"); down();
 check(!qmi_live && !ida_live && child.dev.usage==1,"DOWN releases registered controller despite failed power-up state"); finish();
 reset_case("external-PM-reference"); parent_up(); child.dev.usage+=3; remove_child();
 check(child.dev.usage==3,"child removal preserves external PM references"); child.dev.usage-=3; finish();
 reset_case("registration-error-remove"); parent_up(); registration_error=-ENOSPC; up(); drain();
 check(child.dev.usage==1 && !qmi_live && !ida_live,"registration failure retains bootstrap until removal"); finish();
 reset_case("remove-queued-UP"); parent_up(); up(); remove_child();
 check(!ctrl.ngd_up_work.queued,"child remove cancels queued startup"); drain(); finish();
 reset_case("DOWN-before-queued-UP-runs"); parent_up(); up(); down(); drain();
 check(!qmi_inits && child.dev.usage==1,"last DOWN rejects queued UP before QMI wait");
 check(!wait_calls,"inadmissible queued work does not wait for QMI"); finish();
 reset_case("UP-while-unbound-rebind"); parent_up(); up(); drain(); unsigned old_power=powerups; remove_child(); up();
 check(!ctrl.ngd_up_work.queued,"unbound UP remains unqueued"); check(!bind_child(),"rebind succeeds"); drain(); live();
 check(powerups==old_power+1,"rebind resets state and powers the new child session"); finish();
 reset_case("rebind-retains-last-UP"); parent_up(); up(); drain(); remove_child();
 ctrl.qmi_up.done=19; ctrl.qmi.qmi_comp.done=23;
 check(!bind_child(),"rebind after UP succeeds");
 check(!ctrl.qmi_up.done && !ctrl.qmi.qmi_comp.done,"rebind clears previous discovery completions");
 drain(); live(); finish();
 reset_case("unbound-DOWN-cancels-replay"); parent_up(); up(); drain(); remove_child(); down();
 unsigned old_init=qmi_inits; check(!bind_child(),"rebind after DOWN succeeds"); drain();
 check(qmi_inits==old_init && !qmi_live,"DOWN while unbound cancels replay"); finish();
 reset_case("unbound-duplicate-DOWN"); parent_up(); up(); drain(); remove_child(); down(); down();
 check(child.dev.usage==0,"unbound DOWN takes no child PM reference"); finish();
 reset_case("unknown-notification"); parent_up();
 check(qcom_slim_ngd_ssr_pdr_notify(&ctrl,9999)==NOTIFY_OK,"unknown notification accepted");
 check(!schedules && child.dev.usage==1 && !qmi_inits,"unknown notification leaves child unchanged"); finish();
 const long results[]={-512,-4,0,1,1000};
 for(unsigned i=0;i<sizeof(results)/sizeof(results[0]);i++){
  char name[64];snprintf(name,sizeof(name),"bound-wait-%ld",results[i]);reset_case(name);parent_up();wait_result=results[i];up();drain();
  check(qmi_inits==(unsigned)(results[i]>0),"only successful completion admits startup");finish();
 }
 for(int kind=0;kind<3;kind++)for(int at=0;at<2;at++){
  char name[64];snprintf(name,sizeof(name),"interleave-action-%d-worker-%s",kind,at?"initializing":"waiting");reset_case(name);parent_up();
  block_wait=!at;block_init=at;up();start_pending();await_point(at?&init_entered:&wait_entered);concurrent_action(kind);
  block_wait=block_init=false;drain();
  if(kind==1)check(!qmi_live && !ida_live && child.dev.usage==1,"DOWN wins over waiting startup or tears down completed startup");
  else audit_removed();
  if(!at && kind!=2)check(!qmi_inits,"post-wait check rejects startup after DOWN/removal");
  finish();
 }
 for(int mode=0;mode<6;mode++){
  char name[64];snprintf(name,sizeof(name),"parent-remove-mode-%d",mode);reset_case(name);parent_up();
  if(mode==1||mode==2||mode==5)up();
  if(mode==2||mode==5){block_init=true;start_pending();await_point(&init_entered);}
  UP_at_pdr_release=mode==3||mode==5;UP_at_ssr_release=mode==4||mode==5;
  concurrent_action(2);block_init=false;drain();finish();
 }
 for(int mode=0;mode<6;mode++){
  char name[64];snprintf(name,sizeof(name),"parent-probe-error-mode-%d",mode);reset_case(name);
  fail_ssr=mode<=3;fail_lookup=mode==4;fail_add=mode==5;
  UP_at_lookup=mode==1||mode==2;run_at_lookup=mode==2;block_init=mode==2;UP_at_pdr_release=mode==3;
  concurrent_action(3);block_init=false;drain();
  check(action_result<0,"parent probe returns injected error");finish();
 }
 if(mutexes_live){REQUIRE(!pthread_mutex_destroy(&ctrl.ssr_lock.lock));REQUIRE(!pthread_mutex_destroy(&ctrl.tx_lock.lock));}
 for(unsigned n=0;n<64;n++)free(qmi_allocations[n]);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n",cases,checks,failures);return 0;
}
