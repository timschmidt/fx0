/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <setjmp.h>
#include <stdatomic.h>
#include <string.h>

typedef atomic_int atomic_t;
#define atomic_read atomic_load
#define DEFINE_PER_CPU(type, name) type name[4]
#define per_cpu_ptr(member, cpu) (&(*(member))[cpu])
#define this_cpu_ptr(member) per_cpu_ptr(member, 3)

static int atomic_cmpxchg(atomic_t *state, int expected, int next)
{
	atomic_compare_exchange_strong(state, &expected, next);
	return expected;
}

static jmp_buf exit_point;
static bool pm_active = true;
static bool accept_at_send;
static bool request_at_resume;
static int send_status, enable_status, collapses, enables;
static void (*during_send)(void);
static void (*during_resume)(void);

static bool qcom_msm8226_pm_active(void) { return pm_active; }
static int gic_cpu_quiesce_ppis(unsigned int gic) { assert(!gic); return 0; }
static int gic_cpu_enable_wake_sgi(unsigned int gic, unsigned int sgi)
{
	assert(!gic && sgi == 1);
	enables++;
	return enable_status;
}
static int gic_send_cpu_wakeup_sgi(unsigned int cpu, unsigned int sgi)
{
	assert(cpu == 3 && sgi == 1);
	if (accept_at_send)
		during_send();
	return send_status;
}
static int qcom_msm8226_cpu_collapse(unsigned int cpu)
{
	assert(cpu == 3);
	collapses++;
	if (request_at_resume)
		during_resume();
	return collapses == 1 ? 0 : -EAGAIN;
}
static void wfi(void) { longjmp(exit_point, 1); }
static void arm_secondary_restart(void) { longjmp(exit_point, 2); }
#define atomic_set atomic_store
#include "msm8226-restart-source.h"

static void accept_request(void)
{
	assert(atomic_cmpxchg(&msm8226_restart[3], MSM8226_RESTART_REQUESTED,
			     MSM8226_RESTART_ACCEPTED) == MSM8226_RESTART_REQUESTED);
}

static void request_restart(void)
{
	assert(msm8226_restart_secondary(3, &msm8226_restart[3]) == 0);
}

static int run_dying_cpu(void)
{
	int result = setjmp(exit_point);

	if (!result)
		msm8226_cpu_die(3);
	return result;
}

struct task_struct { int stack; };
static struct { void *stack; struct task_struct *task; } secondary_data;
static struct {
	int (*smp_boot_secondary)(unsigned int, struct task_struct *);
	bool (*smp_cancel_secondary_boot)(unsigned int);
} smp_ops;
static bool online_state;
static int wait_calls, boot_error;
static bool complete_after_timeout;
static int cpu_running;
#define THREAD_START_SP 0
#define task_stack_page(idle) ((void *)&(idle)->stack)
#define sync_cache_w(pointer) ((void)(pointer))
#define msecs_to_jiffies(ms) (ms)
#define pr_crit(...) ((void)0)
#define pr_err(...) ((void)0)
#define panic(...) longjmp(exit_point, 3)

static int secondary_biglittle_prepare(unsigned int cpu) { assert(cpu == 3); return 0; }
static bool cpu_online(unsigned int cpu) { assert(cpu == 3); return online_state; }
static int wait_for_completion_timeout(int *completion, unsigned int duration)
{
	assert(completion == &cpu_running && secondary_data.task);
	assert(duration == (wait_calls ? 5000 : 1000));
	wait_calls++;
	if (wait_calls == 2 && complete_after_timeout)
		return online_state = true;
	return 0;
}
static int boot_secondary(unsigned int cpu, struct task_struct *idle)
{
	assert(cpu == 3 && idle == secondary_data.task);
	return boot_error;
}
#include "arm-secondary-boot-source.h"

int main(void)
{
	struct task_struct idle = {};
	int stall;

	assert(msm8226_cpu_disable(0) == -EPERM);
	assert(msm8226_cpu_disable(3) == 0);
	request_restart();
	assert(run_dying_cpu() == 2 && enables == 1 && collapses == 0);
	assert(!msm8226_cancel_secondary_boot(3));

	assert(msm8226_cpu_disable(3) == 0);
	request_restart();
	assert(msm8226_cancel_secondary_boot(3));
	assert(run_dying_cpu() == 1 && collapses == 2);
	assert(atomic_read(&msm8226_restart[3]) == MSM8226_RESTART_OFFLINE);

	send_status = -EIO;
	assert(msm8226_restart_secondary(3, &msm8226_restart[3]) == -EIO);
	assert(atomic_read(&msm8226_restart[3]) == MSM8226_RESTART_OFFLINE);
	during_send = accept_request;
	accept_at_send = true;
	request_restart();
	assert(!msm8226_cancel_secondary_boot(3));

	assert(msm8226_cpu_disable(3) == 0);
	send_status = 0;
	accept_at_send = false;
	request_at_resume = true;
	during_resume = request_restart;
	collapses = 0;
	assert(run_dying_cpu() == 2 && collapses == 1);

	assert(msm8226_cpu_disable(3) == 0);
	enable_status = -EIO;
	collapses = 0;
	assert(run_dying_cpu() == 1 && !collapses);
	enable_status = 0;

	smp_ops.smp_boot_secondary = boot_secondary;
	smp_ops.smp_cancel_secondary_boot = msm8226_cancel_secondary_boot;
	request_restart();
	assert(__cpu_up(3, &idle) == -EIO && wait_calls == 1 && !secondary_data.task);
	assert(atomic_read(&msm8226_restart[3]) == MSM8226_RESTART_OFFLINE);

	wait_calls = 0;
	request_restart();
	accept_request();
	complete_after_timeout = true;
	assert(__cpu_up(3, &idle) == 0 && wait_calls == 2 && !secondary_data.task);

	wait_calls = 0;
	online_state = false;
	complete_after_timeout = false;
	stall = setjmp(exit_point);
	if (!stall)
		__cpu_up(3, &idle);
	assert(stall == 3 && wait_calls == 2 && secondary_data.task == &idle);
	return 0;
}
