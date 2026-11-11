// SPDX-License-Identifier: MIT
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <sys/reboot.h>
#include <sys/utsname.h>
#include <time.h>
#include <unistd.h>

#define FX0_RELEASE "6.18.63-fx0-vibrator-alpine"
#define FX0_TOKEN "fx0.native_trial=stable-6.18.63-01"
#define FX0_DEADLINE 420

struct timer_ops {
	int (*now)(struct timespec *);
	int (*wait_until)(const struct timespec *);
	int (*armed)(void);
	void (*sync_all)(void);
	int (*restart)(void);
};

static bool identity_ok(const char *release, const char *cmdline)
{
	const char *p = cmdline;
	size_t length = strlen(FX0_TOKEN);

	if (strcmp(release, FX0_RELEASE))
		return false;
	while (*p) {
		size_t word;

		p += strspn(p, " \t\r\n");
		word = strcspn(p, " \t\r\n");
		if (word == length && !memcmp(p, FX0_TOKEN, length))
			return true;
		p += word;
	}
	return false;
}

static int run_trial(const char *release, const char *cmdline, bool check,
		     const struct timer_ops *ops)
{
	struct timespec now, deadline = { .tv_sec = FX0_DEADLINE };
	int error;

	if (!identity_ok(release, cmdline))
		return 2;
	if (ops->now(&now) || now.tv_sec < 0 || now.tv_sec >= 120)
		return 3;
	if (check)
		return 0;
	if (ops->armed())
		return 4;
	do {
		error = ops->wait_until(&deadline);
	} while (error == EINTR);
	if (error)
		return 5;
	ops->sync_all();
	return ops->restart();
}

static int write_armed(const char *temporary, const char *ready)
{
	int fd = open(temporary, O_WRONLY | O_CREAT | O_EXCL, 0600);
	int count, closed;

	if (fd < 0)
		return -1;
	count = dprintf(fd, "PID=%ld\nDEADLINE=%d\nTOKEN=%s\n", (long)getpid(),
			FX0_DEADLINE, FX0_TOKEN);
	closed = close(fd);
	if (closed || count <= 0 || link(temporary, ready)) {
		unlink(temporary);
		return -1;
	}
	return unlink(temporary);
}

#ifndef FX0_NATIVE_RETURN_TEST
static int real_now(struct timespec *value)
{
	return clock_gettime(CLOCK_BOOTTIME, value);
}

static int real_wait(const struct timespec *deadline)
{
	return clock_nanosleep(CLOCK_BOOTTIME, TIMER_ABSTIME, deadline, NULL);
}

static int real_armed(void)
{
	return write_armed("/tmp/fx0-native-return-arming",
			   "/tmp/fx0-native-return-armed");
}

static void real_sync(void)
{
	sync();
}

static int real_restart(void)
{
	return reboot(RB_AUTOBOOT) ? 6 : 0;
}

int main(int argc, char **argv)
{
	const struct timer_ops ops = { real_now, real_wait, real_armed, real_sync,
				       real_restart };
	struct utsname name;
	char command[4096];
	bool check = argc == 2 && !strcmp(argv[1], "--check");
	int fd;
	ssize_t count;

	if ((argc != 1 && !check) || geteuid() || uname(&name))
		return 1;
	fd = open("/proc/cmdline", O_RDONLY | O_CLOEXEC);
	if (fd < 0)
		return 1;
	count = read(fd, command, sizeof(command) - 1);
	close(fd);
	if (count <= 0 || (size_t)count == sizeof(command) - 1)
		return 1;
	command[count] = '\0';
	int result = run_trial(name.release, command, check, &ops);
	if (result)
		dprintf(2, "<2>FX0_NATIVE_RETURN_STATUS code=%d errno=%d release_match=%d identity_match=%d\n",
			result, errno, !strcmp(name.release, FX0_RELEASE),
			identity_ok(name.release, command));
	return result;
}
#endif
