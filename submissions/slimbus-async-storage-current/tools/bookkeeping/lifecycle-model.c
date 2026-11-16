/* SPDX-License-Identifier: GPL-2.0-only */
/* Synthetic SLIMbus services: no device, firmware, DMA, audio or sockets. */
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#define MSEC_PER_SEC 1000
#define GFP_KERNEL 0
#define SLIM_MIN_CLK_GEAR 1
#define SLIM_MAX_CLK_GEAR 10
#define QCOM_SSR_BEFORE_SHUTDOWN 1
#define QCOM_SSR_AFTER_POWERUP 2
#define SERVREG_SERVICE_STATE_DOWN 3
#define SERVREG_SERVICE_STATE_UP 4
#define NOTIFY_OK 0
#define EXPORT_SYMBOL_GPL(x)
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define wake_up_all(q) ((void)(q))
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define REQUIRE(x) do { if (!(x)) { fprintf(stderr, "model invariant %d: %s\n", __LINE__, #x); exit(3); } } while (0)
struct mutex { bool held; };
struct completion { int done; };
struct work_struct { bool queued; };
struct device { void *data; bool pm_enabled, suspended; int usage; };
struct slim_device { struct device dev; };
struct slim_controller { bool transactions_initialized;
 struct device *dev;
 int id, min_cg, max_cg, laddr_ida, tid_idr, txn_lock;
 struct mutex lock;
 struct { struct mutex m_reconf; struct completion pause_comp; } sched;
 const char *name;
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
 bool registered, parent_ready, child_ready, up_requested, pm_ref_held, qmi_ready;
 int qmi_wait;
};
static int ctrl_ida;
static bool allocated_ids[64];
static struct slim_device children[64];
static unsigned child_count, ida_live, unowned_frees, qmi_live;
static unsigned qmi_inits, qmi_exits, registrations, unregistrations, resumes, powerups;
static int qmi_error, registration_error;
static void *qmi_allocations[64];
static long wait_result;
static unsigned wait_calls, wait_locked, enable_calls, cases, checks, failures;
static const char *current_case;
static struct qcom_slim_ngd_ctrl ctrl;
static struct device dev;
static void check(bool ok, const char *what)
{ checks++; if (!ok) { failures++; fprintf(stderr, "%s: %s\n", current_case, what); } }
static void mutex_init(struct mutex *m) { m->held = false; }
static void mutex_lock(struct mutex *m) { REQUIRE(!m->held); m->held = true; }
static void mutex_unlock(struct mutex *m) { REQUIRE(m->held); m->held = false; }
#define lockdep_assert_held(m) REQUIRE((m)->held)
static void init_completion(struct completion *c) { c->done = 0; }
static void complete(struct completion *c) { c->done++; }
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
 REQUIRE(parent == &dev);
 unsigned n = child_count;
 for (unsigned i = n; i > 0; i--) callback(&children[i - 1].dev, data);
 return 0;
}
static void slim_report_absent(struct slim_device *d) { REQUIRE(d); }
/* Transaction services stay synthetic in this lifecycle fixture. */
static void slim_init_transactions(struct slim_controller *c) { if (!c->transactions_initialized) { idr_init(&c->tid_idr); spin_lock_init(&c->txn_lock); c->transactions_initialized = true; } }
static void slim_start_transactions(struct slim_controller *c) { }
static void slim_stop_transactions(struct slim_controller *c) { }
/* ACTUAL_CORE */
static void *dev_get_drvdata(struct device *d) { return d->data; }
static bool pm_runtime_enabled(struct device *d) { return d->pm_enabled; }
static bool pm_runtime_suspended(struct device *d) { return d->suspended; }
static void pm_runtime_get_noresume(struct device *d) { d->usage++; }
static void pm_runtime_mark_last_busy(struct device *d) { REQUIRE(d == &dev); }
static void pm_runtime_put(struct device *d) { d->usage--; }
static int qcom_slim_ngd_power_up(struct qcom_slim_ngd_ctrl *c)
{ REQUIRE(c == &ctrl && c->qmi.handle); powerups++; return 0; }
/* ACTUAL_RESUME */
static int pm_runtime_resume(struct device *d)
{ resumes++; int r = qcom_slim_ngd_runtime_resume(d); if (!r) d->suspended = false; return r; }
static int qcom_slim_qmi_init(struct qcom_slim_ngd_ctrl *c, bool master)
{
 REQUIRE(c == &ctrl && !master); qmi_inits++;
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
 wait_calls++; wait_locked += ctrl.ssr_lock.held; return wait_result;
}
static int msecs_to_jiffies(int ms) { return ms; }
#if FIXTURE_USES_EVENT_WAIT
static long fixture_wait_result(int timeout) { return wait_for_completion_interruptible_timeout(&ctrl.qmi_up, timeout); }
#define wait_event_interruptible_timeout(q,condition,timeout) fixture_wait_result(timeout)
#endif
/* ACTUAL_UP */
static void schedule_work(struct work_struct *w) { REQUIRE(w == &ctrl.ngd_up_work); w->queued = true; }
static void qcom_slim_ngd_exit_dma(struct qcom_slim_ngd_ctrl *c) { REQUIRE(c == &ctrl); }
/* ACTUAL_NOTIFY */
static void reset_case(const char *name)
{
 /* Recover all modeled resources after measuring ownership; this is fixture cleanup. */
 for (unsigned n = 0; n < 64; n++) { free(qmi_allocations[n]); qmi_allocations[n] = NULL; }
 memset(&ctrl, 0, sizeof(ctrl)); memset(&dev, 0, sizeof(dev));
 memset(allocated_ids, 0, sizeof(allocated_ids));
 child_count = ida_live = unowned_frees = qmi_live = 0;
 qmi_inits = qmi_exits = registrations = unregistrations = resumes = powerups = 0;
 qmi_error = registration_error = 0;
 wait_calls = wait_locked = enable_calls = 0;
 dev.data = &ctrl; dev.pm_enabled = true; dev.suspended = true; dev.usage = 1;
 ctrl.parent_ready = ctrl.child_ready = ctrl.up_requested = ctrl.pm_ref_held = ctrl.qmi_ready = true;
 ctrl.dev = ctrl.ctrl.dev = &dev; ctrl.state = QCOM_SLIM_NGD_CTRL_DOWN;
 current_case = name; cases++;
}
static int enable(bool on)
{
 mutex_lock(&ctrl.ssr_lock); enable_calls++;
 int ret = qcom_slim_ngd_enable(&ctrl, on);
 mutex_unlock(&ctrl.ssr_lock); return ret;
}
static void live_one(void)
{
 check(ida_live == 1, "one controller ID"); check(child_count == 2, "one child enumeration");
 check(qmi_live == 1, "one QMI client"); check(dev.usage == 0, "one PM bootstrap put");
 check(!unowned_frees, "no unowned controller release");
}
int main(int argc, char **argv)
{
 REQUIRE(argc == 2);
 bool run_wait = !strcmp(argv[1], "wait") || !strcmp(argv[1], "all");
 bool run_registration = !strcmp(argv[1], "registration") || !strcmp(argv[1], "all");
 REQUIRE(run_wait || run_registration);
 if (run_wait) {
  const long values[] = {-512, -4, -1, 0, 1, 7, 1000};
  for (unsigned n = 0; n < sizeof(values) / sizeof(values[0]); n++) {
   char label[64]; snprintf(label, sizeof(label), "wait-%ld", values[n]); reset_case(label);
   wait_result = values[n]; ctrl.qmi_ready = values[n] > 0; qcom_slim_ngd_up_worker(&ctrl.ngd_up_work);
   check(wait_calls == 1 && !wait_locked, "one bounded wait outside SSR lock");
   check(qmi_inits == (unsigned)(values[n] > 0), "initialize only after positive completion");
   check(!ctrl.ssr_lock.held, "SSR lock released");
   if (values[n] > 0) live_one();
   else check(dev.usage == 1 && !ida_live && !qmi_live, "unsatisfied wait leaves ownership unchanged");
  }
 }
 if (run_registration) {
  for (unsigned n = 0; n < 4; n++) {
   char label[64]; snprintf(label, sizeof(label), "duplicate-up-pm-%u", n); reset_case(label);
   dev.pm_enabled = n & 1; dev.suspended = n & 2;
   check(!enable(true), "first enable succeeds"); check(!enable(true), "second enable succeeds");
   check(!enable(true), "third enable succeeds"); live_one();
   check(qmi_inits == 1 && registrations == 1, "duplicates do not reinitialize resources");
  }
  for (unsigned n = 0; n < 2; n++) {
   char label[64]; snprintf(label, sizeof(label), "registered-runtime-resume-%u", n); reset_case(label);
   check(!enable(true), "initial registration succeeds");
   ctrl.state = QCOM_SLIM_NGD_CTRL_ASLEEP; dev.suspended = true; dev.pm_enabled = n;
   check(!enable(true), "registered controller wake succeeds");
   check(ctrl.state == QCOM_SLIM_NGD_CTRL_AWAKE && powerups == 2, "repeated UP retains runtime wakeup");
   check(qmi_inits == 1 && registrations == 1, "runtime wake reuses registration and client");
   live_one();
  }
  const int errors[] = {-517, -ENOMEM, -EIO};
  for (unsigned n = 0; n < sizeof(errors) / sizeof(errors[0]); n++) {
   char label[64]; snprintf(label, sizeof(label), "qmi-error-%d", errors[n]); reset_case(label);
   qmi_error = errors[n]; check(enable(true) == errors[n], "QMI error propagated");
   check(!qmi_live && !ida_live && !registrations && dev.usage == 1, "QMI error retains bootstrap ownership");
   qmi_error = 0; check(!enable(true), "retry after QMI failure succeeds"); live_one();
  }
  const int reg_errors[] = {-ENOMEM, -ENOSPC};
  for (unsigned n = 0; n < sizeof(reg_errors) / sizeof(reg_errors[0]); n++) {
   char label[64]; snprintf(label, sizeof(label), "registration-error-%d", reg_errors[n]); reset_case(label);
   registration_error = reg_errors[n]; check(enable(true) == reg_errors[n], "registration error propagated");
   check(!ida_live && !child_count && !qmi_live, "failed registration releases QMI client");
   check(dev.usage == 1, "failed registration retains bootstrap PM reference");
   registration_error = 0; check(!enable(true), "retry after registration failure succeeds"); live_one();
   check(!enable(false) && !ida_live && !qmi_live && !child_count && !unowned_frees, "successful retry can be removed");
  }
  reset_case("disable-without-registration"); check(!enable(false), "disable succeeds");
  check(!unregistrations && !unowned_frees && !qmi_live && dev.usage == 1, "unowned controller not released");
  reset_case("double-disable"); check(!enable(true), "enable succeeds");
  check(!enable(false) && !enable(false), "repeated disable succeeds");
  check(unregistrations == 1 && !unowned_frees && !ida_live && !qmi_live && !child_count, "registered controller released exactly once");
  reset_case("SSR-cycle"); check(!enable(true), "initial enable succeeds");
  check(qcom_slim_ngd_ssr_pdr_notify(&ctrl, QCOM_SSR_BEFORE_SHUTDOWN) == NOTIFY_OK, "SSR down accepted");
  check(!ida_live && !qmi_live && dev.usage == 1, "SSR down restores bootstrap reference");
  check(!enable(true), "SSR up succeeds"); live_one();
 }
 /* No modeled allocations escape the fixture, including on baseline mismatches. */
 for (unsigned n = 0; n < 64; n++) free(qmi_allocations[n]);
 printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
 return 0;
}
