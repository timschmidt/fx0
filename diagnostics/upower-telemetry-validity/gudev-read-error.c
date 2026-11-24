/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Test-only libudev NULL-read injection as observed through GUdev. No host sysfs or hardware writes. */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <fcntl.h>
#include <pthread.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

static const char *(*real_get_attr)(void *, const char *);
static const char *(*real_get_path)(void *);
static pthread_once_t initialized = PTHREAD_ONCE_INIT;

static void resolve_symbols(void)
{
	real_get_attr = dlsym(RTLD_NEXT, "udev_device_get_sysattr_value");
	real_get_path = dlsym(RTLD_NEXT, "udev_device_get_syspath");
	if (!real_get_attr || !real_get_path)
		abort();
}

const char *udev_device_get_sysattr_value(void *device, const char *key)
{
	const char *wanted = getenv("FX0_GUDEV_READ_ERROR_ATTRIBUTE");
	const char *trigger = getenv("FX0_GUDEV_READ_ERROR_TRIGGER");
	const char *log = getenv("FX0_GUDEV_READ_ERROR_LOG");
	const char *path;

	pthread_once(&initialized, resolve_symbols);
	path = real_get_path(device);
	if (wanted && !strcmp(key, wanted) && path &&
	    strstr(path, "/validity-battery") &&
	    (!trigger || access(trigger, F_OK) == 0)) {
		if (log) {
			int fd = open(log, O_WRONLY | O_CREAT | O_APPEND, 0600);
			if (fd >= 0) {
				(void)write(fd, key, strlen(key));
				(void)write(fd, "\n", 1);
				close(fd);
			}
		}
		errno = ENODATA;
		return NULL;
	}
	return real_get_attr(device, key);
}
