/* SPDX-License-Identifier: MIT */
#define FX0_NATIVE_RETURN_TEST
#include "../diagnostics/kernel-maintenance/native-return.c"
#include <assert.h>
#include <stdlib.h>
#include <sys/stat.h>

static int tick, wait_calls, arm_calls, sync_calls, reboot_calls, fault;
static int now(struct timespec *value)
{
	value->tv_sec = tick;
	return fault == 1 ? -1 : 0;
}
static int wait_until(const struct timespec *deadline)
{
	assert(deadline->tv_sec == 420 && !deadline->tv_nsec);
	assert(arm_calls == 1 && !sync_calls && !reboot_calls);
	wait_calls++;
	if (fault == 2)
		return EINVAL;
	if (fault == 3 && wait_calls == 1)
		return EINTR;
	return 0;
}
static int armed(void) { arm_calls++; return fault == 4 ? -1 : 0; }
static void sync_all(void) { assert(wait_calls); sync_calls++; }
static int restart(void) { assert(sync_calls == 1); reboot_calls++; return 0; }
static const struct timer_ops ops = { now, wait_until, armed, sync_all, restart };
static void reset(void)
{
	tick = 2; wait_calls = arm_calls = sync_calls = reboot_calls = fault = 0;
}
int main(void)
{
	assert(identity_ok(FX0_RELEASE, "quiet " FX0_TOKEN " panic=60\n"));
	assert(!identity_ok("6.18.59-fx0-dmp", FX0_TOKEN));
	assert(!identity_ok(FX0_RELEASE, ""));
	assert(!identity_ok(FX0_RELEASE, "x" FX0_TOKEN));
	assert(!identity_ok(FX0_RELEASE, FX0_TOKEN "extra"));
	reset(); assert(run_trial("6.18.59-fx0-dmp", FX0_TOKEN, false, &ops) == 2);
	assert(!arm_calls && !wait_calls && !reboot_calls);
	reset(); tick = 120; assert(run_trial(FX0_RELEASE, FX0_TOKEN, false, &ops) == 3);
	assert(!arm_calls && !reboot_calls);
	reset(); fault = 1; assert(run_trial(FX0_RELEASE, FX0_TOKEN, false, &ops) == 3);
	assert(!arm_calls && !reboot_calls);
	reset(); assert(!run_trial(FX0_RELEASE, FX0_TOKEN, true, &ops));
	assert(!arm_calls && !wait_calls && !reboot_calls);
	reset(); fault = 4; assert(run_trial(FX0_RELEASE, FX0_TOKEN, false, &ops) == 4);
	assert(!wait_calls && !reboot_calls);
	reset(); fault = 2; assert(run_trial(FX0_RELEASE, FX0_TOKEN, false, &ops) == 5);
	assert(!sync_calls && !reboot_calls);
	reset(); fault = 3; assert(!run_trial(FX0_RELEASE, FX0_TOKEN, false, &ops));
	assert(wait_calls == 2 && sync_calls == 1 && reboot_calls == 1);
	{
		char directory[] = "/tmp/fx0-return-test-XXXXXX";
		char temporary[256], ready[256], data[256] = { 0 };
		struct stat metadata;
		FILE *file;

		assert(mkdtemp(directory));
		snprintf(temporary, sizeof(temporary), "%s/arming", directory);
		snprintf(ready, sizeof(ready), "%s/armed", directory);
		assert(!write_armed(temporary, ready));
		assert(access(temporary, F_OK) && !stat(ready, &metadata));
		assert((metadata.st_mode & 0777) == 0600);
		file = fopen(ready, "r"); assert(file);
		assert(fread(data, 1, sizeof(data) - 1, file) > 0); fclose(file);
		assert(strstr(data, "DEADLINE=420\nTOKEN=" FX0_TOKEN));
		assert(write_armed(temporary, ready) == -1);
		assert(access(temporary, F_OK) && !stat(ready, &metadata));
		assert(!unlink(ready) && !rmdir(directory));
	}
	puts("13 native-return identity, deadline, error, ordering and atomic-file cases passed");
	return 0;
}
