/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <sys/stat.h>
#include <time.h>
#include <unistd.h>

enum {
    WIDTH = 320,
    HEIGHT = 240,
    MAX_BUFFERS = 32,
    MAX_INPUT_BYTES = 64 * 1024,
    OBSERVATION_MS = 2500,
};

static const enum v4l2_buf_type output = V4L2_BUF_TYPE_VIDEO_OUTPUT_MPLANE;
static const enum v4l2_buf_type capture = V4L2_BUF_TYPE_VIDEO_CAPTURE_MPLANE;

static int video_ioctl(int fd, unsigned long command, void *arg)
{
    int status;

    do {
        status = ioctl(fd, command, arg);
    } while (status < 0 && errno == EINTR);
    return status;
}

static int64_t monotonic_ms(void)
{
    struct timespec now;

    if (clock_gettime(CLOCK_MONOTONIC, &now) < 0)
        return -1;
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static int allocate(int fd, enum v4l2_buf_type type, unsigned int count)
{
    struct v4l2_requestbuffers request = {
        .type = type,
        .count = count,
        .memory = V4L2_MEMORY_MMAP,
    };

    if (video_ioctl(fd, VIDIOC_REQBUFS, &request) < 0)
        return -1;
    if (!request.count || request.count > MAX_BUFFERS) {
        errno = EPROTO;
        return -1;
    }
    return (int)request.count;
}

static int report_capture_lengths(int fd, unsigned int count)
{
    unsigned int min_length = 0, max_length = 0;

    for (unsigned int index = 0; index < count; index++) {
        struct v4l2_plane plane = {0};
        struct v4l2_buffer buffer = {
            .type = capture, .memory = V4L2_MEMORY_MMAP, .index = index,
            .length = 1, .m.planes = &plane,
        };

        if (video_ioctl(fd, VIDIOC_QUERYBUF, &buffer) < 0)
            return -1;
        if (buffer.length != 1 || !plane.length) {
            errno = EPROTO;
            return -1;
        }
        if (!min_length || plane.length < min_length)
            min_length = plane.length;
        if (plane.length > max_length)
            max_length = plane.length;
    }

    fprintf(stderr, "CAPTURE planes: count %u min %u max %u\n",
            count, min_length, max_length);
    return 0;
}

static int verify_decoder(int fd)
{
    struct v4l2_capability capability = {0};
    const uint32_t expected = V4L2_CAP_VIDEO_M2M_MPLANE | V4L2_CAP_STREAMING;
    uint32_t active;

    if (video_ioctl(fd, VIDIOC_QUERYCAP, &capability) < 0)
        return -1;
    active = capability.capabilities & V4L2_CAP_DEVICE_CAPS
        ? capability.device_caps : capability.capabilities;
    if (strncmp((const char *)capability.driver, "qcom-venus", sizeof(capability.driver)) ||
        strncmp((const char *)capability.card, "Qualcomm Venus video decoder", sizeof(capability.card)) ||
        strncmp((const char *)capability.bus_info, "platform:qcom-venus", sizeof(capability.bus_info)) ||
        (active & expected) != expected) {
        errno = ENODEV;
        return -1;
    }
    return 0;
}

static int output_format(int fd, size_t input_bytes)
{
    struct v4l2_format format = {
        .type = output,
        .fmt.pix_mp = {
            .width = WIDTH,
            .height = HEIGHT,
            .pixelformat = V4L2_PIX_FMT_H264,
            .field = V4L2_FIELD_NONE,
            .num_planes = 1,
            .plane_fmt = {{ .sizeimage = MAX_INPUT_BYTES }},
        },
    };
    struct v4l2_pix_format_mplane *pixels = &format.fmt.pix_mp;

    if (video_ioctl(fd, VIDIOC_S_FMT, &format) < 0)
        return -1;
    if (pixels->pixelformat != V4L2_PIX_FMT_H264 || pixels->num_planes != 1 ||
        pixels->width != WIDTH || pixels->height != HEIGHT ||
        pixels->plane_fmt[0].sizeimage < input_bytes) {
        errno = EPROTO;
        return -1;
    }
    return 0;
}

static int queue_input(int fd, FILE *input, size_t input_bytes)
{
    struct v4l2_plane plane = {0};
    struct v4l2_buffer buffer = {
        .type = output, .memory = V4L2_MEMORY_MMAP,
        .index = 0, .length = 1, .m.planes = &plane,
    };
    void *mapping;
    int saved_errno, status = -1;

    if (video_ioctl(fd, VIDIOC_QUERYBUF, &buffer) < 0)
        return -1;
    if (buffer.length != 1 || input_bytes > plane.length) {
        errno = EPROTO;
        return -1;
    }
    mapping = mmap(NULL, plane.length, PROT_READ | PROT_WRITE, MAP_SHARED,
                   fd, plane.m.mem_offset);
    if (mapping == MAP_FAILED)
        return -1;
    if (fread(mapping, 1, input_bytes, input) == input_bytes) {
        plane.bytesused = (uint32_t)input_bytes;
        buffer.field = V4L2_FIELD_NONE;
        status = video_ioctl(fd, VIDIOC_QBUF, &buffer);
    } else {
        errno = EIO;
    }
    saved_errno = errno;
    munmap(mapping, plane.length);
    errno = saved_errno;
    return status;
}

static int observe(int fd, const char *mode, size_t bytes, int capture_buffers)
{
    struct v4l2_plane plane = {0};
    struct v4l2_buffer buffer = {
        .type = output, .memory = V4L2_MEMORY_MMAP,
        .length = 1, .m.planes = &plane,
    };
    int64_t began = monotonic_ms();
    int dequeue_errno = 0, event_errno = 0;
    int64_t event_ms = -1, output_ms = -1;
    unsigned int width = 0, height = 0;
    bool output_error = false;
    int64_t elapsed;

    if (began < 0)
        return -1;
    for (;;) {
        struct v4l2_event event = {0};
        struct timespec delay = { .tv_nsec = 20000000 };

        elapsed = monotonic_ms() - began;
        if (elapsed < 0) {
            errno = EIO;
            return -1;
        }
        if (elapsed >= OBSERVATION_MS)
            break;
        if (event_ms < 0 && !event_errno) {
            if (!video_ioctl(fd, VIDIOC_DQEVENT, &event)) {
                if (event.type == V4L2_EVENT_SOURCE_CHANGE &&
                    (event.u.src_change.changes & V4L2_EVENT_SRC_CH_RESOLUTION)) {
                    struct v4l2_format format = { .type = capture };

                    event_ms = elapsed;
                    if (!video_ioctl(fd, VIDIOC_G_FMT, &format)) {
                        width = format.fmt.pix_mp.width;
                        height = format.fmt.pix_mp.height;
                    } else {
                        event_errno = errno;
                    }
                }
            } else if (errno != ENOENT && errno != EAGAIN) {
                event_errno = errno;
            }
        }
        if (output_ms < 0 && !dequeue_errno) {
            if (!video_ioctl(fd, VIDIOC_DQBUF, &buffer)) {
                output_ms = elapsed;
                output_error = (buffer.flags & V4L2_BUF_FLAG_ERROR) != 0;
            } else if (errno != EAGAIN) {
                dequeue_errno = errno;
            }
        }
        nanosleep(&delay, NULL);
    }
    printf("{\"mode\":\"%s\",\"input_bytes\":%zu,\"preallocated_capture_buffers\":%d,"
           "\"capture_stream_started\":false,\"source_change_ms\":%lld,"
           "\"capture_width\":%u,\"capture_height\":%u,\"event_errno\":%d,"
           "\"output_dequeued_ms\":%lld,\"output_error_flag\":%s,\"output_errno\":%d,"
           "\"observation_ms\":%lld}\n",
           mode, bytes, capture_buffers, (long long)event_ms, width, height, event_errno,
           (long long)output_ms, output_error ? "true" : "false", dequeue_errno,
           (long long)elapsed);
    return fflush(stdout);
}

int main(int argc, char **argv)
{
    struct v4l2_event_subscription subscription = { .type = V4L2_EVENT_SOURCE_CHANGE };
    enum v4l2_buf_type stream = output;
    struct stat metadata;
    int fd = -1, capture_buffers = 0, status = 1;
    const char *step = "input";
    bool preallocate;
    FILE *input;

    if (argc != 4 ||
        (strcmp(argv[1], "output-first") && strcmp(argv[1], "preallocate-capture") &&
         strcmp(argv[1], "headers-only"))) {
        fprintf(stderr, "Usage: %s {output-first|preallocate-capture|headers-only} VIDEO CHUNK\n", argv[0]);
        return 2;
    }
    preallocate = !strcmp(argv[1], "preallocate-capture");
    input = fopen(argv[3], "rb");
    if (!input)
        goto done;
    if (fstat(fileno(input), &metadata) < 0)
        goto done;
    if (!S_ISREG(metadata.st_mode) || metadata.st_size <= 0 || metadata.st_size > MAX_INPUT_BYTES) {
        errno = EINVAL;
        goto done;
    }
    step = "decoder identity";
    fd = open(argv[2], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0 || verify_decoder(fd) < 0)
        goto done;
    step = "source-event subscription";
    if (video_ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, &subscription) < 0)
        goto done;
    step = "OUTPUT format and allocation";
    if (output_format(fd, (size_t)metadata.st_size) < 0 || allocate(fd, output, 1) < 0)
        goto done;
    if (preallocate) {
        step = "CAPTURE preallocation";
        capture_buffers = allocate(fd, capture, MAX_BUFFERS);
        if (capture_buffers < 0)
            goto done;
        step = "CAPTURE lengths";
        if (report_capture_lengths(fd, (unsigned int)capture_buffers) < 0)
            goto done;
    }
    step = "first coded buffer";
    if (queue_input(fd, input, (size_t)metadata.st_size) < 0)
        goto done;
    step = "OUTPUT STREAMON";
    if (video_ioctl(fd, VIDIOC_STREAMON, &stream) < 0)
        goto done;
    step = "observation";
    if (!observe(fd, argv[1], (size_t)metadata.st_size, capture_buffers))
        status = 0;

done:
    if (status)
        fprintf(stderr, "%s: %s\n", step, strerror(errno));
    if (fd >= 0)
        close(fd);
    if (input)
        fclose(input);
    return status;
}
