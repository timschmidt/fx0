// SPDX-License-Identifier: MIT
/* Fixed Fx0 pulses through evdev, with read-only PM8226 target checks. */
#define _POSIX_C_SOURCE 200809L
#include <fcntl.h>
#include <linux/input.h>
#include <signal.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <time.h>
#include <unistd.h>

static volatile sig_atomic_t stopping;

static void stop(int signal_number)
{
	(void)signal_number;
	stopping = 1;
}

static long long milliseconds(void)
{
	struct timespec time;

	if (clock_gettime(CLOCK_MONOTONIC, &time))
		return -1;
	return time.tv_sec * 1000LL + time.tv_nsec / 1000000;
}

static int register_value(int fd, unsigned int address)
{
	char row[10], expected[7];
	unsigned int value;

	if (pread(fd, row, 9, (off_t)address * 9) != 9)
		return -1;
	row[9] = 0;
	snprintf(expected, sizeof(expected), "%04x: ", address);
	if (memcmp(row, expected, 6) || row[8] != '\n' || sscanf(row + 6, "%2x", &value) != 1)
		return -1;
	return (int)value;
}

static int event(int fd, int id, int enabled)
{
	struct input_event request = { .type = EV_FF, .code = (unsigned short)id, .value = enabled };

	return write(fd, &request, sizeof(request)) == sizeof(request) ? 0 : -1;
}

static int hold(int regmap, int expected, unsigned int duration)
{
	long long start = milliseconds(), now;
	struct timespec delay = { .tv_nsec = 10000000 };
	unsigned int samples = 0;
	bool matched = false;
	int drive, enable;

	if (start < 0)
		return -1;
	do {
		drive = register_value(regmap, 0xc041);
		enable = register_value(regmap, 0xc046);
		now = milliseconds();
		if (drive < 0 || drive > 24 || enable < 0 || stopping || now < start)
			return -1;
		if (drive == expected && enable == (expected ? 128 : 0)) {
			matched = true;
			samples++;
		} else if (matched || now - start > 60) {
			return -1;
		}
		nanosleep(&delay, NULL);
	} while (now - start < duration);
	printf("VIBRATOR_HOLD code=%d duration_ms=%u matched_samples=%u\n", expected, duration, samples);
	return matched && samples >= 5 ? 0 : -1;
}

static int pulse(int fd, int regmap, unsigned int duration)
{
	struct ff_effect effect = { .type = FF_RUMBLE, .id = -1,
		.replay = { .length = (unsigned short)duration }, .u.rumble = { .strong_magnitude = 39168 } };
	long long start, now, first = -1, last = -1, finished = -1;
	struct timespec delay = { .tv_nsec = 5000000 };
	unsigned int enabled_samples = 0;
	int result = -1, drive, enable;

	if (ioctl(fd, EVIOCSFF, &effect) || event(fd, effect.id, 1))
		goto out;
	start = milliseconds();
	if (start < 0)
		goto out;
	do {
		drive = register_value(regmap, 0xc041);
		enable = register_value(regmap, 0xc046);
		now = milliseconds();
		if (drive < 0 || drive > 24 || enable < 0 || now < start || stopping)
			goto out;
		if (enable == 128) {
			if (finished >= 0 || (drive != 24 && drive != 0))
				goto out;
			if (drive == 24) {
				if (first < 0)
					first = now;
				last = now;
				enabled_samples++;
			}
		} else if (!enable && first >= 0 && finished < 0) {
			finished = now;
		}
		nanosleep(&delay, NULL);
	} while (now - start < duration + 150);
	if (first < 0 || finished < 0 || enabled_samples < 5 ||
	    last - first > duration + 30 || finished - first < duration - 30 ||
	    register_value(regmap, 0xc041) || register_value(regmap, 0xc046))
		goto out;
	printf("VIBRATOR_PULSE requested_ms=%u observed_ms=%lld drive_code=24 enabled_samples=%u\n",
	       duration, finished - first, enabled_samples);
	result = 0;
out:
	if (effect.id >= 0) {
		event(fd, effect.id, 0);
		if (ioctl(fd, EVIOCRMFF, effect.id))
			result = -1;
	}
	return result;
}

static int change_intensity(int fd, int regmap)
{
	struct ff_effect effect = { .type = FF_RUMBLE, .id = -1,
		.replay = { .length = 2000 }, .u.rumble = { .strong_magnitude = 39168 } };
	int result = -1;

	if (ioctl(fd, EVIOCSFF, &effect) || event(fd, effect.id, 1) || hold(regmap, 24, 150))
		goto out;
	effect.u.rumble.strong_magnitude = 64 << 8;
	if (ioctl(fd, EVIOCSFF, &effect) || hold(regmap, 17, 150))
		goto out;
	effect.u.rumble.strong_magnitude = 128 << 8;
	if (ioctl(fd, EVIOCSFF, &effect) || hold(regmap, 22, 150))
		goto out;
	if (event(fd, effect.id, 0) || hold(regmap, 0, 100))
		goto out;
	result = 0;
out:
	if (effect.id >= 0) {
		event(fd, effect.id, 0);
		if (ioctl(fd, EVIOCRMFF, effect.id))
			result = -1;
	}
	return result;
}

int main(int argc, char **argv)
{
	struct sigaction action = { .sa_handler = stop };
	int fd, regmap, result = 1;
	const char *prefix = "/dev/input/event";

	if (argc != 2 || strncmp(argv[1], prefix, strlen(prefix)) ||
	    !argv[1][strlen(prefix)] || strspn(argv[1] + strlen(prefix), "0123456789") != strlen(argv[1] + strlen(prefix)))
		return 2;
	setvbuf(stdout, NULL, _IOLBF, 0);
	sigemptyset(&action.sa_mask);
	if (sigaction(SIGINT, &action, NULL) || sigaction(SIGTERM, &action, NULL))
		return 1;
	regmap = open("/sys/kernel/debug/regmap/0-01/registers", O_RDONLY | O_CLOEXEC);
	if (regmap < 0)
		return 1;
	fd = open(argv[1], O_RDWR | O_CLOEXEC);
	if (fd < 0)
		goto close_regmap;
	if (hold(regmap, 0, 100) || pulse(fd, regmap, 150) || pulse(fd, regmap, 300) ||
	    pulse(fd, regmap, 600) || change_intensity(fd, regmap) || hold(regmap, 0, 100))
		goto close_input;
	printf("VIBRATOR_PULSES_PASS\n");
	result = 0;
close_input:
	close(fd);
close_regmap:
	close(regmap);
	return result;
}
