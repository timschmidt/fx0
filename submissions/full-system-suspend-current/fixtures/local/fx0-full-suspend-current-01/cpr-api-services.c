// SPDX-License-Identifier: GPL-2.0-only
#define EPROBE_DEFER 517
#define EXPORT_SYMBOL_GPL(x)
#define READ_ONCE(x) (x)
#define PM_SUSPEND_TO_IDLE 1
#define PM_SUSPEND_MEM 3
#define REG_RBCPR_CTL 0
#define RBCPR_CTL_LOOP_EN BIT(0)
#define REG_RBIF_IRQ_EN(n) 4
#define REG_RBCPR_RESULT_0 8
#define RBCPR_RESULT0_BUSY_MASK BIT(19)
static int pm_suspend_target_state;
struct mutex {bool held;};
static void mutex_lock(struct mutex *m) {CHECK(!m->held);m->held=true;}
static void mutex_unlock(struct mutex *m) {CHECK(m->held);m->held=false;}
static struct mutex *model_guard_acquire(struct mutex *m) {mutex_lock(m);return m;}
static void model_guard_cleanup(struct mutex **m) {mutex_unlock(*m);}
#define guard(t) __attribute__((cleanup(model_guard_cleanup))) struct mutex *model_guard = model_guard_acquire
struct device {void *data;void *driver;};
static struct {int driver;} cpr_driver;
struct corner {unsigned long freq;int min_uV,max_uV;};
struct cpr_msm8926_data {struct regulator *mx_sleep;struct clk *aux_clk,*pll_clk;struct regmap *apcs;struct device *suspend_owner;struct cpr_msm8926_suspend sleep;bool applied,suspend_irq_disabled,suspend_was_applied;};
struct cpr_drv {struct cpr_msm8926_data *msm8926;struct mutex lock;bool initialized,suspended;struct corner *corner;struct cpr_voltage rails;struct clk *cpu_clk;void *base;int irq;};
static struct cpr_drv *observed;
static int disable_calls,enable_calls,irq_depth,config_calls,corner_saves,config_error,rate_error,polls;
static u32 cpr_regs[3];
static void *dev_get_drvdata(struct device *d) {return d->data;}
static u32 cpr_read(struct cpr_drv *d,u32 off) {CHECK(d==observed&&off<12);return cpr_regs[off/4];}
static u32 readl_relaxed(void *p) {polls++;return *(u32 *)p;}
#define readl_poll_timeout(p,v,condition,delay,bound) ({int res=-ETIMEDOUT;for(int i=0;i<=(bound);i++){(v)=readl_relaxed(p);if(condition){res=0;break;}}res;})
static void disable_irq(int irq) {CHECK(irq==79&&observed&&!observed->lock.held&&local_irqs);disable_calls++;irq_depth++;}
static void enable_irq(int irq) {CHECK(irq==79&&!observed->lock.held&&irq_depth>0);irq_depth--;enable_calls++;}
static bool cpr_is_allowed(struct cpr_drv *d) {return d->msm8926->applied&&!d->suspended;}
static void cpr_corner_save(struct cpr_drv *d,struct corner *c) {CHECK(d->lock.held&&c==d->corner);corner_saves++;}
static void cpr_ctl_disable(struct cpr_drv *d) {CHECK(d->lock.held);cpr_regs[0]=cpr_regs[1]=0;quiescent=true;}
static int cpr_config(struct cpr_drv *d) {CHECK(d->lock.held);config_calls++;CHECK(!d->msm8926->sleep.active&&!d->msm8926->suspend_irq_disabled);return config_error;}
static int cpr_msm8926_check_cpu_rate(struct cpr_drv *d,unsigned long freq) {CHECK(d->lock.held&&quiescent&&irq_depth>0&&d->suspended);return rate_error?rate_error:clk_get_rate(d->cpu_clk)==freq?0:-ERANGE;}
