/* SPDX-License-Identifier: MIT */
/*
 * Run a STREAMON retry on the capture fd already configured by libcamera.
 * Use only in an owned cam process with the guarded Fx0 test module.
 */
#define _GNU_SOURCE
#include <dlfcn.h>
#include <errno.h>
#include <poll.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <unistd.h>

#include <linux/videodev2.h>

enum { BUFFER_COUNT = 4, FRAME_COUNT = 24 };
static const enum v4l2_buf_type capture = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;
typedef int (*ioctl_call)(int, int, uintptr_t);

static void fail(const char *step)
{
	fprintf(stderr, "FX0_SAME_QUEUE_FAILURE %s errno=%d\n", step, errno);
	_exit(1);
}

static void check(int condition, const char *step)
{
	if (!condition)
		fail(step);
}

static int call(ioctl_call native, int fd, int request, void *arg)
{
	return native(fd, request, (uintptr_t)arg);
}

static struct v4l2_buffer buffer(unsigned int index, struct v4l2_plane *planes)
{
	memset(planes, 0, sizeof(*planes) * VIDEO_MAX_PLANES);
	return (struct v4l2_buffer){
		.index = index,
		.type = capture,
		.memory = V4L2_MEMORY_MMAP,
		.length = VIDEO_MAX_PLANES,
		.m.planes = planes,
	};
}

static void release_unused_queue(ioctl_call native, int fd)
{
	struct v4l2_requestbuffers release = { .type = capture };
	unsigned int index;

	for (index = 0; index < VIDEO_MAX_FRAME; index++) {
		struct v4l2_plane planes[VIDEO_MAX_PLANES];
		struct v4l2_buffer item = buffer(index, planes);

		if (call(native, fd, VIDIOC_QUERYBUF, &item) < 0) {
			check(errno == EINVAL, "query-initial-queue");
			break;
		}
		check(!(item.flags & (V4L2_BUF_FLAG_QUEUED | V4L2_BUF_FLAG_DONE)),
		      "initial-queue-idle");
		check(!index || item.memory == release.memory, "initial-queue-memory");
		release.memory = item.memory;
	}
	check(index < VIDEO_MAX_FRAME, "initial-queue-bound");
	if (index)
		check(!call(native, fd, VIDIOC_REQBUFS, &release), "release-unused-buffers");
}

static void test_queue(ioctl_call native, int fd, const struct stat *identity)
{
	struct v4l2_requestbuffers request = {
		.count = BUFFER_COUNT,
		.type = capture,
		.memory = V4L2_MEMORY_MMAP,
	};
	struct v4l2_format format = { .type = capture };
	struct v4l2_pix_format_mplane *pix = &format.fmt.pix_mp;
	enum v4l2_buf_type type = capture;
	struct v4l2_plane planes[VIDEO_MAX_PLANES];
	struct stat checked;
	struct pollfd wait = { .fd = fd, .events = POLLIN };
	unsigned int first = 0, last = 0, seen = 0;

	check(!call(native, fd, VIDIOC_G_FMT, &format), "get-capture-format");
	check(pix->num_planes == 1 && pix->width > 0 && pix->height > 0,
	      "configured-single-plane-capture");

	release_unused_queue(native, fd);
	check(!call(native, fd, VIDIOC_REQBUFS, &request) && request.count == BUFFER_COUNT,
	      "allocate-test-queue");

	for (unsigned int index = 0; index < BUFFER_COUNT; index++) {
		struct v4l2_buffer item = buffer(index, planes);

		check(!call(native, fd, VIDIOC_QUERYBUF, &item), "query-allocated-buffer");
		check(!call(native, fd, VIDIOC_QBUF, &item), "queue-buffer");
	}

	check(call(native, fd, VIDIOC_STREAMON, &type) == -1 && errno == EIO,
	      "expected-injected-eio");
	for (unsigned int index = 0; index < BUFFER_COUNT; index++) {
		struct v4l2_buffer item = buffer(index, planes);

		check(!call(native, fd, VIDIOC_QUERYBUF, &item), "query-after-failure");
		check(item.index == index && (item.flags & V4L2_BUF_FLAG_QUEUED) &&
		      !(item.flags & (V4L2_BUF_FLAG_DONE | V4L2_BUF_FLAG_ERROR)),
		      "still-queued-after-failure");
	}
	check(!fstat(fd, &checked) && checked.st_dev == identity->st_dev &&
	      checked.st_ino == identity->st_ino && checked.st_rdev == identity->st_rdev,
	      "capture-descriptor-identity");
	check(!call(native, fd, VIDIOC_STREAMON, &type), "retry-streamon");

	for (unsigned int frame = 0; frame < FRAME_COUNT; frame++) {
		struct v4l2_buffer item = buffer(0, planes);

		check(poll(&wait, 1, 2500) == 1 && (wait.revents & POLLIN), "wait-frame");
		check(!call(native, fd, VIDIOC_DQBUF, &item), "dequeue-frame");
		check(item.index < BUFFER_COUNT && item.length == 1 &&
		      planes[0].bytesused == pix->height * pix->plane_fmt[0].bytesperline &&
		      !(item.flags & V4L2_BUF_FLAG_ERROR), "frame-integrity");
		if (!frame)
			first = item.sequence;
		check(item.sequence == first + frame, "frame-sequence");
		last = item.sequence;
		seen |= 1U << item.index;
		if (frame + BUFFER_COUNT < FRAME_COUNT)
			check(!call(native, fd, VIDIOC_QBUF, &item), "requeue-frame");
	}
	check(seen == (1U << BUFFER_COUNT) - 1, "all-original-buffer-indices");
	check(!call(native, fd, VIDIOC_STREAMOFF, &type), "streamoff");
	request.count = 0;
	check(!call(native, fd, VIDIOC_REQBUFS, &request), "release-test-queue");
	printf("FX0_SAME_QUEUE {\"fd\":%d,\"first_errno\":%d,\"queued_after_error\":%d,"
	       "\"frames\":%d,\"width\":%u,\"height\":%u,\"stride\":%u,\"indices_mask\":%u,"
	       "\"first_sequence\":%u,\"last_sequence\":%u}\n",
	       fd, EIO, BUFFER_COUNT, FRAME_COUNT, pix->width, pix->height,
	       pix->plane_fmt[0].bytesperline, seen, first, last);
	check(!fflush(stdout), "flush-result");
	_exit(0);
}

/*
 * AAPCS passes the raw optional ioctl argument in r2. Forward that register
 * unchanged, including for requests that ignore their third argument.
 */
#if !defined(__arm__)
#error This preload adapter is specific to the handset ARM ABI.
#endif
__attribute__((visibility("default")))
int fx0_ioctl(int fd, int request, uintptr_t arg) __asm__("ioctl");

int fx0_ioctl(int fd, int request, uintptr_t arg)
{
	ioctl_call native = (ioctl_call)dlsym(RTLD_NEXT, "ioctl");
	const char *node;
	struct stat identity, target;

	check(native != NULL, "resolve-ioctl");
	if ((unsigned int)request != VIDIOC_STREAMON)
		return native(fd, request, arg);
	node = getenv("FX0_CAMSS_TEST_NODE");
	if (!node || strcmp(node, "/dev/video0") || fstat(fd, &identity) ||
	    stat(node, &target) || !S_ISCHR(identity.st_mode) ||
	    identity.st_rdev != target.st_rdev)
		return native(fd, request, arg);
	check(arg && *(const enum v4l2_buf_type *)arg == capture,
	      "capture-queue-type");
	test_queue(native, fd, &identity);
	return -1;
}
