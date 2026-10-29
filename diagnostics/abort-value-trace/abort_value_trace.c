// SPDX-License-Identifier: GPL-2.0-only
/* Fx0 RAM diagnostic: retain abort arguments as named function-trace entries. */
#include <linux/atomic.h>
#include <linux/init.h>
#include <linux/kprobes.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/uaccess.h>
#include <linux/utsname.h>
#include <generated/utsrelease.h>
#include <asm/memory.h>
#include <asm/ptrace.h>

static bool selftest;
module_param(selftest, bool, 0400);
static bool selftest_pass;
module_param(selftest_pass, bool, 0400);
static atomic_t captured = ATOMIC_INIT(0);

#define DIGIT(n) \
static noinline void fx0_abort_digit_##n(void) \
{ \
	asm volatile("" : : "r" (0x##n) : "memory"); \
}
DIGIT(0)
DIGIT(1)
DIGIT(2)
DIGIT(3)
DIGIT(4)
DIGIT(5)
DIGIT(6)
DIGIT(7)
DIGIT(8)
DIGIT(9)
DIGIT(a)
DIGIT(b)
DIGIT(c)
DIGIT(d)
DIGIT(e)
DIGIT(f)

static void (* const digits[])(void) = {
	fx0_abort_digit_0, fx0_abort_digit_1, fx0_abort_digit_2,
	fx0_abort_digit_3, fx0_abort_digit_4, fx0_abort_digit_5,
	fx0_abort_digit_6, fx0_abort_digit_7, fx0_abort_digit_8,
	fx0_abort_digit_9, fx0_abort_digit_a, fx0_abort_digit_b,
	fx0_abort_digit_c, fx0_abort_digit_d, fx0_abort_digit_e,
	fx0_abort_digit_f,
};

#define MARKER(name, value) \
static noinline void fx0_abort_##name(void) \
{ \
	asm volatile("" : : "r" (value) : "memory"); \
}
MARKER(address, 0xa1)
MARKER(fsr, 0xa2)
MARKER(pc, 0xa3)
MARKER(cpsr, 0xa4)
MARKER(end, 0xa5)
MARKER(selftest_end, 0xa6)

static void notrace encode(u32 value)
{
	int shift;

	for (shift = 28; shift >= 0; shift -= 4)
		digits[(value >> shift) & 0xf]();
}

static int notrace capture(struct kprobe *probe, struct pt_regs *regs)
{
	struct pt_regs *frame = (void *)regs->ARM_r2;

	if (regs->ARM_r0 < TASK_SIZE)
		return 0;
	if ((unsigned long)frame < PAGE_OFFSET || user_mode(frame))
		return 0;
	if (atomic_cmpxchg(&captured, 0, 1))
		return 0;

	fx0_abort_address();
	encode(regs->ARM_r0);
	fx0_abort_fsr();
	encode(regs->ARM_r1);
	fx0_abort_pc();
	encode(frame->ARM_pc);
	fx0_abort_cpsr();
	encode(frame->ARM_cpsr);
	fx0_abort_end();
	return 0;
}
NOKPROBE_SYMBOL(capture);

static struct kprobe fault_probe = {
	.symbol_name = "do_bad",
	.pre_handler = capture,
};

static int __init abort_value_trace_init(void)
{
	struct pt_regs frame = {};
	struct pt_regs test_regs = {};
	const u32 expected = 0x5a3cc3a5;
	u32 word;
	long status;
	int ret;

	if (!of_machine_is_compatible("lg,madai") ||
	    strcmp(utsname()->release, UTS_RELEASE))
		return -ENODEV;

	if (selftest) {
		/* Known RAM succeeds; an invalid address must be rejected safely. */
		status = copy_from_kernel_nofault(&word, &expected, sizeof(word));
		if (status || word != expected)
			return -EINVAL;
		status = copy_from_kernel_nofault(&word, NULL, sizeof(word));
		if (status >= 0)
			return -EINVAL;
		/* Known-value frame validates encoding, not a real abort context. */
		frame.ARM_pc = 0xc0010100;
		frame.ARM_cpsr = 0x600001d3;
		test_regs.ARM_r0 = 0xfabcdef0;
		test_regs.ARM_r1 = 0x12345678;
		test_regs.ARM_r2 = (unsigned long)&frame;
		ret = capture(NULL, &test_regs);
		if (ret || atomic_read(&captured) != 1) {
			pr_info("Fx0 abort selftest: encode ret=%d captured=%d frame=%px mode=%lx\n",
				ret, atomic_read(&captured), &frame, frame.ARM_cpsr);
			return -EINVAL;
		}
		selftest_pass = true;
		fx0_abort_selftest_end();
		atomic_set(&captured, 0);
	}

	return register_kprobe(&fault_probe);
}

static void __exit abort_value_trace_exit(void)
{
	unregister_kprobe(&fault_probe);
}

module_init(abort_value_trace_init);
module_exit(abort_value_trace_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fx0 RAM-only ARM abort argument function tracing");
