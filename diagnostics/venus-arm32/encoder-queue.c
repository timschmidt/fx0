// SPDX-License-Identifier: GPL-2.0-only
/* Run the fixed Fx0 H.264 fixture directly through the V4L2 encoder. */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <time.h>
#include <unistd.h>
#include <linux/videodev2.h>

enum { WIDTH = 320, HEIGHT = 240, FPS = 15, FRAMES = 12, MAX_BUFFERS = 32,
       MAX_ENCODED_BYTES = 8 * 1024 * 1024 };

struct mapping {
	unsigned char *data;
	size_t size;
};

struct queue {
	enum v4l2_buf_type type;
	struct mapping buffers[MAX_BUFFERS];
	unsigned int count;
};

static void require(bool condition, const char *message)
{
	if (!condition) {
		fprintf(stderr, "%s\n", message);
		exit(EXIT_FAILURE);
	}
}

static int ioctl_retry(int fd, unsigned long op, void *argument)
{
	int result;

	do {
		result = ioctl(fd, op, argument);
	} while (result < 0 && errno == EINTR);
	return result;
}

static void must_ioctl(int fd, unsigned long op, void *argument, const char *name)
{
	if (ioctl_retry(fd, op, argument) < 0) {
		perror(name);
		exit(EXIT_FAILURE);
	}
}

static struct v4l2_format set_format(int fd, enum v4l2_buf_type type,
				    unsigned int pixel_format)
{
	struct v4l2_format format = {
		.type = type,
		.fmt.pix_mp = {
			.width = WIDTH, .height = HEIGHT, .pixelformat = pixel_format,
			.field = V4L2_FIELD_NONE,
		},
	};

	must_ioctl(fd, VIDIOC_S_FMT, &format, "VIDIOC_S_FMT");
	require(format.fmt.pix_mp.pixelformat == pixel_format &&
		format.fmt.pix_mp.num_planes == 1, "unexpected V4L2 format");
	return format;
}

static struct v4l2_buffer buffer_for(const struct queue *queue,
				     struct v4l2_plane *plane)
{
	return (struct v4l2_buffer) {
		.type = queue->type, .memory = V4L2_MEMORY_MMAP,
		.length = 1, .m.planes = plane,
	};
}

static void map_queue(int fd, struct queue *queue)
{
	struct v4l2_requestbuffers req = {
		.type = queue->type, .memory = V4L2_MEMORY_MMAP, .count = 4,
	};
	unsigned int i;

	must_ioctl(fd, VIDIOC_REQBUFS, &req, "VIDIOC_REQBUFS");
	require(req.count > 0 && req.count <= MAX_BUFFERS, "unexpected queue depth");
	queue->count = req.count;
	for (i = 0; i < queue->count; i++) {
		struct v4l2_plane plane = {0};
		struct v4l2_buffer buffer = buffer_for(queue, &plane);

		buffer.index = i;
		must_ioctl(fd, VIDIOC_QUERYBUF, &buffer, "VIDIOC_QUERYBUF");
		require(buffer.length == 1 && plane.length > 0, "unexpected plane layout");
		queue->buffers[i].size = plane.length;
		queue->buffers[i].data = mmap(NULL, plane.length, PROT_READ | PROT_WRITE,
					     MAP_SHARED, fd, plane.m.mem_offset);
		require(queue->buffers[i].data != MAP_FAILED, "could not map buffer");
	}
}

static void make_frame(unsigned char *buffer, unsigned int stride,
		       unsigned int padded_height, unsigned int frame)
{
	size_t y_size = (size_t)stride * padded_height;
	unsigned int x, y, cell;

	memset(buffer, 16, y_size);
	for (y = 0; y < HEIGHT; y++) {
		for (x = 0; x < WIDTH; x += 80) {
			cell = y / 80 * 4 + x / 80;
			memset(buffer + (size_t)y * stride + x,
			       cell == frame ? 214 : 41 + 11 * (cell % 6), 80);
		}
	}
	for (size_t i = 0; i < y_size / 2; i += 2) {
		buffer[y_size + i] = 95;
		buffer[y_size + i + 1] = 159;
	}
}

static void submit(int fd, const struct queue *queue, unsigned int index,
		   unsigned int stride, unsigned int height, unsigned int frame)
{
	size_t bytes = (size_t)stride * height * 3 / 2;
	struct v4l2_plane plane = {.length = queue->buffers[index].size, .bytesused = bytes};
	struct v4l2_buffer buffer = buffer_for(queue, &plane);

	require(bytes <= queue->buffers[index].size, "NV12 exceeds mapped buffer");
	make_frame(queue->buffers[index].data, stride, height, frame);
	buffer.index = index;
	buffer.timestamp.tv_sec = 1;
	buffer.timestamp.tv_usec = frame * 1000000 / FPS;
	must_ioctl(fd, VIDIOC_QBUF, &buffer, "VIDIOC_QBUF output");
	printf("input_submitted %u\n", frame);
}

static void queue_capture(int fd, const struct queue *queue, unsigned int index)
{
	struct v4l2_plane plane = {.length = queue->buffers[index].size};
	struct v4l2_buffer buffer = buffer_for(queue, &plane);

	buffer.index = index;
	must_ioctl(fd, VIDIOC_QBUF, &buffer, "VIDIOC_QBUF capture");
}

static int dequeue(int fd, const struct queue *queue, struct v4l2_buffer *buffer)
{
	if (ioctl_retry(fd, VIDIOC_DQBUF, buffer) < 0) {
		if (errno == EAGAIN)
			return 0;
		perror("VIDIOC_DQBUF");
		exit(EXIT_FAILURE);
	}
	require(buffer->index < queue->count && buffer->length == 1,
		"invalid dequeued buffer");
	require(!(buffer->flags & V4L2_BUF_FLAG_ERROR), "driver reported a buffer error");
	return 1;
}

static void stream(int fd, struct queue *output, struct queue *capture,
		   unsigned int stride, unsigned int height, FILE *encoded)
{
	struct v4l2_encoder_cmd stop = {.cmd = V4L2_ENC_CMD_STOP};
	unsigned int submitted = 0, returned = 0, payloads = 0;
	size_t bytes = 0;
	bool stopping = false, last = false;
	unsigned int i;

	for (i = 0; i < capture->count; i++)
		queue_capture(fd, capture, i);
	for (i = 0; i < output->count && submitted < FRAMES; i++)
		submit(fd, output, i, stride, height, submitted++);
	must_ioctl(fd, VIDIOC_STREAMON, &output->type, "VIDIOC_STREAMON output");
	must_ioctl(fd, VIDIOC_STREAMON, &capture->type, "VIDIOC_STREAMON capture");

	while (!last || returned < FRAMES) {
		struct pollfd watched = {
			.fd = fd,
			.events = (last ? 0 : POLLIN) | (returned < FRAMES ? POLLOUT : 0),
		};

		if (!stopping && submitted == FRAMES) {
			must_ioctl(fd, VIDIOC_ENCODER_CMD, &stop, "VIDIOC_ENCODER_CMD stop");
			stopping = true;
			puts("stop_accepted");
		}
		require(poll(&watched, 1, 4000) > 0, "encoder queue poll timed out");
		require(!(watched.revents & (POLLERR | POLLHUP | POLLNVAL)),
			"encoder queue poll failed");
		if (watched.revents & POLLOUT) {
			struct v4l2_plane plane = {0};
			struct v4l2_buffer buffer = buffer_for(output, &plane);

			if (dequeue(fd, output, &buffer)) {
				returned++;
				printf("input_returned %u %ld.%06ld\n", buffer.sequence,
				       (long)buffer.timestamp.tv_sec, (long)buffer.timestamp.tv_usec);
				if (submitted < FRAMES)
					submit(fd, output, buffer.index, stride, height, submitted++);
			}
		}
		if (!last && (watched.revents & POLLIN)) {
			struct v4l2_plane plane = {0};
			struct v4l2_buffer buffer = buffer_for(capture, &plane);
			size_t body;

			if (!dequeue(fd, capture, &buffer))
				continue;
			require(plane.data_offset <= plane.bytesused &&
				plane.bytesused <= capture->buffers[buffer.index].size,
				"invalid encoded payload bounds");
			body = plane.bytesused - plane.data_offset;
			if (body) {
				require(body <= MAX_ENCODED_BYTES - bytes, "encoded stream too large");
				require(fwrite(capture->buffers[buffer.index].data + plane.data_offset,
					       1, body, encoded) == body, "failed writing encoded stream");
				bytes += body;
				payloads++;
			}
			last = buffer.flags & V4L2_BUF_FLAG_LAST;
			printf("capture_returned %u %zu %u\n", buffer.sequence, body, last);
			if (!last)
				queue_capture(fd, capture, buffer.index);
		}
	}
	must_ioctl(fd, VIDIOC_STREAMOFF, &output->type, "VIDIOC_STREAMOFF output");
	must_ioctl(fd, VIDIOC_STREAMOFF, &capture->type, "VIDIOC_STREAMOFF capture");
	printf("result %u %u %u %zu\n", submitted, returned, payloads, bytes);
}

int main(int argc, char **argv)
{
	struct queue output = {.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE};
	struct queue capture = {.type = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE};
	struct v4l2_capability capability = {0};
	struct v4l2_selection crop = {
		.type = V4L2_BUF_TYPE_VIDEO_OUTPUT, .target = V4L2_SEL_TGT_CROP,
		.r = {.width = WIDTH, .height = HEIGHT},
	};
	struct v4l2_streamparm interval = {
		.type = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE,
		.parm.output.timeperframe = {.numerator = 1, .denominator = FPS},
	};
	struct v4l2_format input;
	unsigned int stride, height;
	int fd, out;
	FILE *encoded;

	require(argc == 2, "usage: encoder-queue /dev/videoN");
	setvbuf(stdout, NULL, _IOLBF, 0);
	alarm(22);
	fd = open(argv[1], O_RDWR | O_NONBLOCK | O_CLOEXEC | O_NOFOLLOW);
	require(fd >= 0, "could not open encoder");
	must_ioctl(fd, VIDIOC_QUERYCAP, &capability, "VIDIOC_QUERYCAP");
	require(strncmp((const char *)capability.driver, "qcom-venus",
			sizeof(capability.driver)) == 0 &&
		strncmp((const char *)capability.card, "Qualcomm Venus video encoder",
			sizeof(capability.card)) == 0 &&
		(capability.device_caps & (V4L2_CAP_VIDEO_M2M_MPLANE | V4L2_CAP_STREAMING)) ==
			(V4L2_CAP_VIDEO_M2M_MPLANE | V4L2_CAP_STREAMING),
		"device is not the Venus encoder");
	input = set_format(fd, output.type, V4L2_PIX_FMT_NV12);
	set_format(fd, capture.type, V4L2_PIX_FMT_H264);
	stride = input.fmt.pix_mp.plane_fmt[0].bytesperline;
	height = input.fmt.pix_mp.height;
	require(stride >= WIDTH && stride <= 512 && !(stride & 1) &&
		height >= HEIGHT && height <= 320 && !(height & 1),
		"unexpected raw alignment");
	must_ioctl(fd, VIDIOC_S_SELECTION, &crop, "VIDIOC_S_SELECTION crop");
	require(crop.r.width == WIDTH && crop.r.height == HEIGHT &&
		crop.r.left == 0 && crop.r.top == 0, "encoder adjusted the requested crop");
	printf("format %u %u %u %u\n", stride, height, crop.r.width, crop.r.height);
	must_ioctl(fd, VIDIOC_S_PARM, &interval, "VIDIOC_S_PARM");
	map_queue(fd, &output);
	map_queue(fd, &capture);
	out = open("hardware.h264", O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
	require(out >= 0, "could not create hardware.h264");
	encoded = fdopen(out, "wb");
	require(encoded != NULL, "could not open encoded output stream");
	stream(fd, &output, &capture, stride, height, encoded);
	require(fclose(encoded) == 0, "could not finish hardware.h264");
	close(fd);
	return EXIT_SUCCESS;
}
