/* SPDX-License-Identifier: GPL-2.0-only */
/* Startup-work ownership model; all devices, IRQs, DMA and providers are synthetic. */
#include <pthread.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define GFP_KERNEL 0
#define IRQF_TRIGGER_HIGH 1
#define IRQF_NO_AUTOEN 2
#define MSEC_PER_SEC 1000
#define SLIM_ROOT_FREQ 24576000
#define SLIM_CL_PER_SUPERFRAME_DIV8 6144
#define SLIM_MAX_CLK_GEAR 10
#define QCOM_SSR_BEFORE_SHUTDOWN 1
#define QCOM_SSR_AFTER_POWERUP 2
#define SERVREG_SERVICE_STATE_DOWN 3
#define SERVREG_SERVICE_STATE_UP 4
#define QCOM_SLIM_NGD_CTRL_DOWN 3
#define NOTIFY_OK 0
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define dev_err(...) ((void)0)
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "fixture invariant %d: %s\n", __LINE__, #x); exit(3); } } while (0)
struct work_struct { void (*fn)(struct work_struct *); bool pending, running; };
struct mutex { pthread_mutex_t lock; };
struct completion { int done; };
struct device { void *data; struct device *parent; };
struct platform_device { struct device dev; };
struct notifier_block { int (*notifier_call)(struct notifier_block *, unsigned long, void *); };
struct pdr_handle { int dummy; };
struct pdr_service { int dummy; };
struct qcom_slim_ngd { struct platform_device *pdev; };
struct qcom_slim_ngd_ctrl {
 struct device *dev; void *base;
 struct { unsigned rootfreq, superfreq; } framer;
 struct { struct device *dev; void *a_framer; int clkgear;
  void (*get_laddr)(void), (*enable_stream)(void), (*disable_stream)(void), (*xfer_msg)(void), (*wakeup)(void);
 } ctrl;
 struct mutex tx_lock, ssr_lock; int tx_buf_lock, state, irq;
 struct completion reconf, qmi_up;
 struct { struct completion qmi_comp; } qmi;
 struct work_struct m_work, ngd_up_work;
 void *mwq, *notifier;
 struct notifier_block nb; struct pdr_handle *pdr;
 struct qcom_slim_ngd *ngd;
};
static pthread_mutex_t model_lock = PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t changed = PTHREAD_COND_INITIALIZER;
static struct platform_device parent, child;
static struct qcom_slim_ngd ngd;
static struct qcom_slim_ngd_ctrl *controller;
static struct pdr_handle pdr;
static struct pdr_service pds;
static pthread_t startup_thread, action_thread;
static bool worker_started, worker_joined, worker_entered, release_worker;
static bool block_worker, action_done, cancel_waiting, child_alive, child_removed;
static bool pdr_live, pdr_lookup, ssr_live, queue_live;
static bool error_context, fail_lookup, fail_child, fail_ssr;
static bool queue_at_lookup, run_at_lookup, queue_at_pdr_release, queue_at_ssr_release;
static unsigned late_enable, busy_at_child_remove, providers_at_child_remove, cancels, enables;
static unsigned cases, checks, failures;
static int action_ret;
static const char *case_name;
static void check(bool condition, const char *name)
{ checks++; if (!condition) { failures++; fprintf(stderr, "%s: %s\n", case_name, name); } }
static void *dev_get_drvdata(struct device *d) { return d->data; }
static void dev_set_drvdata(struct device *d, void *p) { d->data = p; }
static void *platform_get_drvdata(struct platform_device *d) { return d->dev.data; }
static void mutex_init(struct mutex *m) { REQUIRE(!pthread_mutex_init(&m->lock, NULL)); }
static void mutex_lock(struct mutex *m) { REQUIRE(!pthread_mutex_lock(&m->lock)); }
static void mutex_unlock(struct mutex *m) { REQUIRE(!pthread_mutex_unlock(&m->lock)); }
static void init_completion(struct completion *c) { c->done = 0; }
static void spin_lock_init(int *p) { *p = 0; }
#define INIT_WORK(w, callback) do { (w)->fn = callback; (w)->pending = (w)->running = false; } while (0)
static void qcom_slim_ngd_get_laddr(void) {}
static void qcom_slim_ngd_enable_stream(void) {}
static void qcom_slim_ngd_disable_stream(void) {}
static void qcom_slim_ngd_xfer_msg(void) {}
static void qcom_slim_ngd_master_worker(struct work_struct *w) { (void)w; }
static void qcom_slim_ngd_interrupt(void) {}
static void *devm_kzalloc(struct device *d, size_t n, int flags)
{ REQUIRE(d == &parent.dev && n == sizeof(*controller)); controller = calloc(1, n); REQUIRE(controller); return controller; }
static void *devm_platform_get_and_ioremap_resource(struct platform_device *d, int n, void *res)
{ REQUIRE(d == &parent && !n && !res); return &parent; }
static int platform_get_irq(struct platform_device *d, int n) { REQUIRE(d == &parent && !n); return 42; }
static int devm_request_irq(struct device *d, int irq, void (*fn)(void), int flags, const char *name, void *data)
{ REQUIRE(d == &parent.dev && irq == 42 && fn == qcom_slim_ngd_interrupt && flags == 3 && data == controller); return 0; }
static int dev_err_probe(struct device *d, int err, const char *message) { return err; }
static void enable_irq(int irq) { REQUIRE(irq == 42); }
static void disable_irq(int irq) { REQUIRE(irq == 42); }
static void *create_singlethread_workqueue(const char *name) { REQUIRE(!queue_live); queue_live = true; return &queue_live; }
static void destroy_workqueue(void *q) { REQUIRE(q == &queue_live && queue_live); queue_live = false; }
static int qcom_slim_ngd_enable(struct qcom_slim_ngd_ctrl *c, bool on)
{
 REQUIRE(c == controller && on);
 REQUIRE(!pthread_mutex_lock(&model_lock)); worker_entered = true; pthread_cond_broadcast(&changed);
 while (block_worker && !release_worker) pthread_cond_wait(&changed, &model_lock);
 enables++; if (!child_alive) late_enable++;
 REQUIRE(!pthread_mutex_unlock(&model_lock)); return 0;
}
static long wait_for_completion_interruptible_timeout(struct completion *c, int timeout)
{ REQUIRE(c == &controller->qmi_up && timeout == 1000); return 1; }
static int msecs_to_jiffies(int n) { return n; }
static void schedule_work(struct work_struct *w)
{ REQUIRE(w == &controller->ngd_up_work && w->fn); pthread_mutex_lock(&model_lock); w->pending = true; pthread_mutex_unlock(&model_lock); }
static void pm_runtime_get_noresume(struct device *d) { REQUIRE(d == &child.dev); }
static void qcom_slim_ngd_down(struct qcom_slim_ngd_ctrl *c) { REQUIRE(0); }
static void qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *c) { REQUIRE(0); }
/* ACTUAL_CALLBACKS */
static void *startup(void *unused)
{
 struct work_struct *w = &controller->ngd_up_work;
 pthread_mutex_lock(&model_lock); REQUIRE(w->pending); w->pending = false; w->running = true; pthread_mutex_unlock(&model_lock);
 w->fn(w);
 pthread_mutex_lock(&model_lock); w->running = false; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock); return NULL;
}
static void start_pending(void)
{
 REQUIRE(!worker_started || worker_joined); worker_started = true; worker_joined = false; worker_entered = false;
 REQUIRE(!pthread_create(&startup_thread, NULL, startup, NULL));
}
static void await_entered(void)
{ pthread_mutex_lock(&model_lock); while (!worker_entered) pthread_cond_wait(&changed, &model_lock); pthread_mutex_unlock(&model_lock); }
static void cancel_work_sync(struct work_struct *w)
{
 REQUIRE(w == &controller->ngd_up_work); pthread_mutex_lock(&model_lock); cancels++; w->pending = false;
 cancel_waiting = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock);
 if (worker_started && !worker_joined) { REQUIRE(!pthread_join(startup_thread, NULL)); worker_joined = true; }
 pthread_mutex_lock(&model_lock); REQUIRE(!w->running); w->pending = false; pthread_mutex_unlock(&model_lock);
}
static struct pdr_handle *pdr_handle_alloc(void (*callback)(int, char *, void *), void *data)
{ REQUIRE(callback == slim_pd_status && data == controller); pdr_live = true; return &pdr; }
static struct pdr_service *pdr_add_lookup(struct pdr_handle *handle, const char *service, const char *path)
{
 REQUIRE(handle == &pdr && pdr_live);
 if (fail_lookup) return (void *)(intptr_t)-ENOENT;
 pdr_lookup = true;
 if (queue_at_lookup) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, controller);
 if (run_at_lookup) { start_pending(); await_entered(); }
 return &pds;
}
static void pdr_handle_release(struct pdr_handle *handle)
{
 REQUIRE(handle == &pdr && pdr_live);
 if (pdr_lookup && queue_at_pdr_release) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, controller);
 pdr_live = pdr_lookup = false;
}
static void *qcom_register_ssr_notifier(const char *name, struct notifier_block *nb)
{ REQUIRE(nb == &controller->nb); if (fail_ssr) return (void *)(intptr_t)-EIO; ssr_live = true; return nb; }
static void qcom_unregister_ssr_notifier(void *handle, struct notifier_block *nb)
{
 REQUIRE(handle == &controller->nb && nb == &controller->nb && ssr_live);
 if (queue_at_ssr_release) nb->notifier_call(nb, QCOM_SSR_AFTER_POWERUP, NULL);
 ssr_live = false;
}
static int of_qcom_slim_ngd_register(struct device *d, struct qcom_slim_ngd_ctrl *c)
{
 REQUIRE(d == &parent.dev && c == controller && c->ngd_up_work.fn);
 if (fail_child) return -ENODEV;
 ngd.pdev = &child; c->ngd = &ngd; c->ctrl.dev = &child.dev; child.dev.data = c;
 child_alive = true; return 0;
}
static void platform_device_del(struct platform_device *d)
{
 REQUIRE(d == &child); pthread_mutex_lock(&model_lock); REQUIRE(child_alive);
 busy_at_child_remove += controller->ngd_up_work.running || controller->ngd_up_work.pending;
 providers_at_child_remove += pdr_live || ssr_live;
 child_alive = false; child_removed = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock);
}
static void platform_device_unregister(struct platform_device *d) { platform_device_del(d); }
/* ACTUAL_PARENT */
static void *action(void *unused)
{
 if (error_context) action_ret = qcom_slim_ngd_ctrl_probe(&parent);
 else qcom_slim_ngd_ctrl_remove(&parent);
 pthread_mutex_lock(&model_lock); action_done = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock); return NULL;
}
static void reset_case(const char *name)
{
 memset(&parent, 0, sizeof(parent)); memset(&child, 0, sizeof(child));
 worker_started = worker_joined = worker_entered = release_worker = false;
 block_worker = action_done = cancel_waiting = child_alive = child_removed = false;
 pdr_live = pdr_lookup = ssr_live = queue_live = false;
 fail_lookup = fail_child = fail_ssr = queue_at_lookup = run_at_lookup = false;
 queue_at_pdr_release = queue_at_ssr_release = false;
 late_enable = busy_at_child_remove = providers_at_child_remove = cancels = enables = 0;
 controller = NULL; case_name = name; cases++;
}
static void execute_case(const char *name, bool probe_error, int mode)
{
 reset_case(name); error_context = probe_error;
 if (!probe_error) {
  REQUIRE(!qcom_slim_ngd_ctrl_probe(&parent));
  if (mode == 1 || mode == 2 || mode == 5) slim_pd_status(SERVREG_SERVICE_STATE_UP, NULL, controller);
  if (mode == 2 || mode == 5) { block_worker = true; start_pending(); await_entered(); }
  queue_at_pdr_release = mode == 3 || mode == 5;
  queue_at_ssr_release = mode == 4 || mode == 5;
 } else {
  fail_ssr = mode <= 3; fail_lookup = mode == 4; fail_child = mode == 5;
  queue_at_lookup = mode == 1 || mode == 2; run_at_lookup = mode == 2; block_worker = mode == 2;
  queue_at_pdr_release = mode == 3;
 }
 REQUIRE(!pthread_create(&action_thread, NULL, action, NULL));
 pthread_mutex_lock(&model_lock);
 while (!action_done && !child_removed && !cancel_waiting) pthread_cond_wait(&changed, &model_lock);
 release_worker = true; pthread_cond_broadcast(&changed); pthread_mutex_unlock(&model_lock);
 REQUIRE(!pthread_join(action_thread, NULL));
 if (worker_started && !worker_joined) { REQUIRE(!pthread_join(startup_thread, NULL)); worker_joined = true; }
 /* Drain any baseline leftover against live fixture memory; record ownership violations, never dereference freed memory. */
 while (controller->ngd_up_work.pending) { start_pending(); REQUIRE(!pthread_join(startup_thread, NULL)); worker_joined = true; }
 check(!busy_at_child_remove, "startup work drained before child removal");
 check(!providers_at_child_remove, "startup producers stopped before child removal");
 check(!late_enable, "no startup after child removal");
 check(!pdr_live && !ssr_live && !queue_live, "all parent providers and queue released");
 check(!controller->ngd_up_work.pending && !controller->ngd_up_work.running, "no pending/running startup work escapes");
 check(probe_error ? action_ret < 0 : child_removed, "action completed expected path");
 REQUIRE(!child_alive); REQUIRE(!pthread_mutex_destroy(&controller->ssr_lock.lock)); REQUIRE(!pthread_mutex_destroy(&controller->tx_lock.lock)); free(controller);
}
int main(void)
{
 const char *normal[] = {"remove-idle", "remove-queued", "remove-running", "remove-PDR-inflight", "remove-SSR-inflight", "remove-running-requeued"};
 const char *error[] = {"probe-SSR-error-idle", "probe-SSR-error-queued", "probe-SSR-error-running", "probe-SSR-error-PDR-inflight", "probe-PDR-error", "probe-child-error"};
 for (int n = 0; n < 6; n++) execute_case(normal[n], false, n);
 for (int n = 0; n < 6; n++) execute_case(error[n], true, n);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
 return 0;
}
