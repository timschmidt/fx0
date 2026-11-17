// SPDX-License-Identifier: GPL-2.0-only

struct device;
#define regmap_get_device(m) ((struct device *)(m))

#define dev_dbg(...) ((void)0)
static int pm_refs, pm_error;
static int lock_held, irq_depth, wake_depth, wake_enable_error, wake_disable_error;
static int can_wake=1;
static void mutex_lock(void *p) { (void)p; assert(!lock_held);lock_held=1; }
static void mutex_unlock(void *p) { (void)p; assert(lock_held);lock_held=0; }
static void disable_irq(int irq) { (void)irq;assert(!lock_held);irq_depth++; }
static void enable_irq(int irq) { (void)irq;assert(!lock_held && irq_depth>0);irq_depth--; }
static int enable_irq_wake(int irq) { (void)irq;if(wake_enable_error)return wake_enable_error;wake_depth++;return 0; }
static int disable_irq_wake(int irq) { (void)irq;if(wake_disable_error)return wake_disable_error;assert(wake_depth>0);wake_depth--;return 0; }
static int device_may_wakeup(struct device *dev) { (void)dev;return can_wake; }
static void pm_wakeup_event(struct device *dev,int ms) { (void)dev;(void)ms; }
static int pm_runtime_resume_and_get(struct device *dev) { (void)dev; if(pm_error)return pm_error; pm_refs++; return 0; }
static void pm_runtime_put_autosuspend(struct device *dev) { (void)dev; assert(pm_refs>0); pm_refs--; }
static void model_unlock(void **p) { if (*p) mutex_unlock(*p); }
static void *model_lock(void *p) { mutex_lock(p); return p; }
#define guard(x) void *model_guard_var __attribute__((cleanup(model_unlock))) = model_lock
