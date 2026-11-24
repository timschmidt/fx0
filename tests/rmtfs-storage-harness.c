// SPDX-License-Identifier: MIT
/* Actual upstream storage.c; synthetic files only, with guarded syscalls. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <limits.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include "rmtfs.h"

static const char *fixture;
static const char *scenario;
static unsigned ro_opens, rw_opens, backing_writes, backing_syncs, reads;
int __real_open(const char *, int, ...);
ssize_t __real_read(int, void *, size_t);
ssize_t __real_pread(int, void *, size_t, off_t);
ssize_t __real_pwrite(int, const void *, size_t, off_t);
int __real_fdatasync(int);
void *__real_realloc(void *, size_t);

#define CHECK(test) do { if (!(test)) { \
    fprintf(stderr, "FAIL %s line %d: %s errno=%d\n", scenario, __LINE__, #test, errno); \
    exit(1); } } while (0)

int __wrap_open(const char *path, int flags, ...)
{
    size_t len = strlen(fixture);
    CHECK(!strncmp(path, fixture, len) && path[len] == '/');
    CHECK(!strchr(path + len + 1, '/'));
    CHECK(!(flags & (O_CREAT | O_TRUNC)));
    if ((flags & O_ACCMODE) == O_RDONLY) ro_opens++;
    else rw_opens++;
    return __real_open(path, flags);
}

ssize_t __wrap_read(int fd, void *buf, size_t count)
{
    reads++;
    if (!strcmp(scenario, "interrupted-read") && reads == 1) {
        errno = EINTR;
        return -1;
    }
    if (!strcmp(scenario, "read-io-error")) {
        errno = EIO;
        return -1;
    }
    if (!strcmp(scenario, "early-eof")) {
        if (reads > 1) return 0;
        count /= 4;
    }
    if (!strcmp(scenario, "short-read") && reads == 1) count /= 2;
    return __real_read(fd, buf, count);
}

ssize_t __wrap_pwrite(int fd, const void *buf, size_t count, off_t offset)
{
    backing_writes++;
    return __real_pwrite(fd, buf, count, offset);
}

ssize_t __wrap_pread(int fd, void *buf, size_t count, off_t offset)
{
    if (!strcmp(scenario, "pread-io-error")) {
        errno = EIO;
        return -1;
    }
    return __real_pread(fd, buf, count, offset);
}

void *__wrap_realloc(void *ptr, size_t size)
{
    void *result = __real_realloc(ptr, size);
    /* Emulate valid nonzero allocator contents in newly grown memory. */
    if (result && !strcmp(scenario, "growth-hole") && size > 4096)
        memset((char *)result + 4096, 0xa5, size - 4096);
    return result;
}

int __wrap_fdatasync(int fd)
{
    backing_syncs++;
    return __real_fdatasync(fd);
}

static void zeros(const unsigned char *data, size_t size)
{
    for (size_t i = 0; i < size; i++) CHECK(data[i] == 0);
}

int main(int argc, char **argv)
{
    CHECK(argc == 3);
    scenario = argv[1]; fixture = argv[2];
    bool writable = !strcmp(scenario, "read-write-control") || !strcmp(scenario, "pread-io-error");
    bool partitions = !strcmp(scenario, "partition-labels");
    CHECK(storage_init(fixture, !writable, partitions) == 0);
    if (!strcmp(scenario, "unknown")) {
        CHECK(!storage_open(7, "/boot/../outside", ""));
        CHECK(!storage_open(7, "/other", ""));
        CHECK(ro_opens == 0 && rw_opens == 0);
        storage_exit();
        puts("STORAGE_CASE_PASS unknown");
        return 0;
    }
    if (!strcmp(scenario, "negative-caller")) {
        CHECK(!storage_get(7, -1));
        CHECK(!storage_get(7, INT_MIN));
        CHECK(!storage_get(7, INT_MAX));
        storage_exit();
        puts("STORAGE_CASE_PASS negative-caller");
        return 0;
    }
    struct rmtfd *fd = storage_open(7, "/boot/modem_fs1", "");
    if (!strcmp(scenario, "early-eof") || !strcmp(scenario, "read-io-error")) {
        CHECK(!fd && errno == EIO);
        storage_exit();
        printf("STORAGE_CASE_PASS %s\n", scenario);
        return 0;
    }
    CHECK(fd);
    unsigned char buf[4096], payload[512];
    memset(payload, 0x5a, sizeof(payload));
    if (!strcmp(scenario, "shadow") || partitions) {
        const char *paths[] = {"/boot/modem_fs1", "/boot/modem_fs2", "/boot/modem_fsg", "/boot/modem_fsc"};
        for (unsigned i = 0; i < 4; i++) {
            struct rmtfd *handle = storage_open(7, paths[i], "");
            CHECK(handle && storage_get(7, storage_get_caller_id(handle)) == handle);
            CHECK(storage_open(7, paths[i], "") == handle);
            CHECK(!storage_get(8, storage_get_caller_id(handle)));
            CHECK(storage_pread(handle, buf, 32, 0) == 32 && buf[0] == 0x21);
            CHECK(storage_pwrite(handle, payload, 32, 0) == 32);
            CHECK(storage_pread(handle, buf, 32, 0) == 32 && !memcmp(buf, payload, 32));
            CHECK(storage_sync(handle) == 0);
        }
        CHECK(ro_opens == 4);
    } else if (!strcmp(scenario, "pread-io-error")) {
        memset(buf, 0xa5, 16);
        errno = 0;
        CHECK(storage_pread(fd, buf, 16, 0) == -1 && errno == EIO);
        for (unsigned i = 0; i < 16; i++) CHECK(buf[i] == 0xa5);
    } else if (writable) {
        CHECK(storage_pwrite(fd, payload, 32, 0) == 32);
        CHECK(storage_sync(fd) == 0);
        CHECK(rw_opens == 1 && backing_writes == 1 && backing_syncs == 1);
    } else if (!strcmp(scenario, "closed")) {
        int id = storage_get_caller_id(fd);
        storage_close(fd);
        CHECK(!storage_get(7, id));
    } else if (!strcmp(scenario, "invalid-handle")) {
        errno = 0;
        CHECK(storage_sync(NULL) == -1 && errno == EBADF);
        storage_close(fd);
        errno = 0;
        CHECK(storage_pread(fd, buf, 16, 0) == -1 && errno == EBADF);
        errno = 0;
        CHECK(storage_pwrite(fd, payload, 16, 0) == -1 && errno == EBADF);
    } else if (!strcmp(scenario, "negative-read")) {
        errno = 0;
        CHECK(storage_pread(fd, buf, 16, -1) == -1 && errno == EINVAL);
    } else if (!strcmp(scenario, "negative-write")) {
        errno = 0;
        CHECK(storage_pwrite(fd, payload, 16, -1) == -1 && errno == EINVAL);
    } else if (!strcmp(scenario, "growth-hole")) {
        CHECK(storage_pwrite(fd, payload, sizeof(payload), 8192) == sizeof(payload));
        CHECK(storage_pread(fd, buf, sizeof(buf), 4096) == sizeof(buf));
        zeros(buf, sizeof(buf));
    } else if (!strcmp(scenario, "short-read") || !strcmp(scenario, "interrupted-read")) {
        CHECK(reads >= 2);
        CHECK(storage_pread(fd, buf, 1, 4095) == 1 && buf[0] == 0x21);
    } else if (!strcmp(scenario, "limit-errno")) {
        errno = 0;
        CHECK(storage_pwrite(fd, payload, 16, (16*1024*1024)-8) == -1 && errno == EINVAL);
    } else if (!strcmp(scenario, "large-read-count")) {
        errno = 0;
        CHECK(storage_pread(fd, buf, SIZE_MAX, 0) == -1 && errno == EINVAL);
    } else if (!strcmp(scenario, "large-write-count")) {
        errno = 0;
        CHECK(storage_pwrite(fd, payload, SIZE_MAX, 1) == -1 && errno == EINVAL);
    } else if (!strcmp(scenario, "far-read")) {
        memset(buf, 0xa5, 16);
        CHECK(storage_pread(fd, buf, 16, ((off_t)1 << 31)+8192) == 16);
        zeros(buf, 16);
    } else if (!strcmp(scenario, "far-write")) {
        errno = 0;
        CHECK(storage_pwrite(fd, payload, 16, (off_t)1 << 32) == -1 && errno == EINVAL);
    } else CHECK(false);
    if (!writable) CHECK(rw_opens == 0 && backing_writes == 0 && backing_syncs == 0);
    storage_exit();
    printf("STORAGE_CASE_PASS %s opens_ro=%u opens_rw=%u backing_writes=%u\n", scenario, ro_opens, rw_opens, backing_writes);
    return 0;
}
