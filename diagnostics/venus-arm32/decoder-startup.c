/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include <errno.h>
#include <fcntl.h>
#include <linux/videodev2.h>
#include <poll.h>
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
    SEQUENCE_FRAMES = 12,
    SEQUENCE_TIMEOUT_MS = 10000,
    DOWNSHIFT_WIDTH = 640,
    DOWNSHIFT_CODED_HEIGHT = 368,
    DOWNSHIFT_VISIBLE_HEIGHT = 360,
    DOWNSHIFT_DRAIN_MS = 150,
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

static int output_format(int fd, size_t input_bytes, unsigned int width, unsigned int height)
{
    struct v4l2_format format = {
        .type = output,
        .fmt.pix_mp = {
            .width = width,
            .height = height,
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
        pixels->width != width || pixels->height != height ||
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

static int wait_for_video(int fd, short events)
{
    struct pollfd ready = { .fd = fd, .events = events };
    int result = poll(&ready, 1, OBSERVATION_MS);

    if (result <= 0) {
        if (result == 0)
            errno = ETIMEDOUT;
        return -1;
    }
    if ((ready.revents & (POLLERR | POLLHUP | POLLNVAL)) || !(ready.revents & events)) {
        errno = EIO;
        return -1;
    }
    return 0;
}

static int write_picture(int fd, const struct v4l2_plane *plane,
                         unsigned int stride, unsigned int padded_height,
                         unsigned int width, unsigned int height, FILE *file)
{
    size_t chroma_offset = (size_t)stride * padded_height;
    unsigned char samples[DOWNSHIFT_WIDTH / 2];
    const unsigned char *mapping, *pixels;
    int status = -1, saved_errno;

    if (!width || !height || ((width | height) & 1) || width > sizeof(samples) * 2 ||
        width > stride || height > padded_height ||
        plane->bytesused > plane->length || plane->bytesused < plane->data_offset ||
        chroma_offset + (size_t)stride * (height / 2 - 1) + width >
            plane->bytesused - plane->data_offset) {
        errno = EPROTO;
        return -1;
    }
    mapping = mmap(NULL, plane->length, PROT_READ, MAP_SHARED, fd, plane->m.mem_offset);
    if (mapping == MAP_FAILED)
        return -1;
    pixels = mapping + plane->data_offset;
    for (unsigned int row = 0; row < height; row++)
        if (fwrite(pixels + row * stride, 1, width, file) != width)
            goto unmap;
    for (unsigned int component = 0; component < 2; component++) {
        for (unsigned int row = 0; row < height / 2; row++) {
            const unsigned char *line = pixels + chroma_offset + row * stride;

            for (unsigned int column = 0; column < width / 2; column++)
                samples[column] = line[column * 2 + component];
            if (fwrite(samples, 1, width / 2, file) != width / 2)
                goto unmap;
        }
    }
    status = 0;
unmap:
    saved_errno = errno;
    munmap((void *)mapping, plane->length);
    errno = saved_errno;
    return status;
}

static int queue_capture(int fd, unsigned int index)
{
    struct v4l2_plane plane = {0};
    struct v4l2_buffer buffer = {
        .type = capture, .memory = V4L2_MEMORY_MMAP, .index = index,
        .length = 1, .m.planes = &plane,
    };

    return video_ioctl(fd, VIDIOC_QBUF, &buffer);
}

static bool valid_capture_format(const struct v4l2_format *format,
                                 unsigned int width, unsigned int height)
{
    const struct v4l2_pix_format_mplane *pixels = &format->fmt.pix_mp;

    return pixels->pixelformat == V4L2_PIX_FMT_NV12 && pixels->num_planes == 1 &&
           pixels->width == width && pixels->height == (height + 31) / 32 * 32 &&
           pixels->plane_fmt[0].bytesperline == (width + 127) / 128 * 128;
}

static int read_capture_format(int fd, struct v4l2_format *format,
                               unsigned int width, unsigned int height)
{
    struct v4l2_event event = {0};

    if (wait_for_video(fd, POLLPRI) < 0 || video_ioctl(fd, VIDIOC_DQEVENT, &event) < 0 ||
        video_ioctl(fd, VIDIOC_G_FMT, format) < 0)
        return -1;
    if (event.type != V4L2_EVENT_SOURCE_CHANGE ||
        !(event.u.src_change.changes & V4L2_EVENT_SRC_CH_RESOLUTION) ||
        !valid_capture_format(format, width, height)) {
        errno = EPROTO;
        return -1;
    }
    return 0;
}

static int activate_capture(int fd, int count)
{
    enum v4l2_buf_type stream = capture;

    for (int index = 0; index < count; index++)
        if (queue_capture(fd, (unsigned int)index) < 0)
            return -1;
    if (video_ioctl(fd, VIDIOC_STREAMON, &stream) < 0)
        return -1;
    fputs("CAPTURE STREAMON accepted\n", stderr);
    return count;
}

static int start_capture(int fd, int count, struct v4l2_format *format)
{
    if (read_capture_format(fd, format, WIDTH, HEIGHT) < 0)
        return -1;
    if (!count) {
        fputs("Allocating CAPTURE after the source-change event\n", stderr);
        count = allocate(fd, capture, MAX_BUFFERS);
        if (count < 0 || report_capture_lengths(fd, (unsigned int)count) < 0)
            return -1;
    }
    return activate_capture(fd, count);
}

static int capture_first_frame(int fd, unsigned int count, const char *destination)
{
    struct v4l2_format format = { .type = capture };
    struct v4l2_plane plane = {0};
    struct v4l2_buffer buffer = {
        .type = capture, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane,
    };
    FILE *file;
    int status, saved_errno;

    if (start_capture(fd, count, &format) < 0)
        return -1;
    if (wait_for_video(fd, POLLIN) < 0 || video_ioctl(fd, VIDIOC_DQBUF, &buffer) < 0)
        return -1;
    if (buffer.length != 1 || buffer.index >= count || buffer.flags & V4L2_BUF_FLAG_ERROR) {
        errno = EPROTO;
        return -1;
    }
    fprintf(stderr, "CAPTURE picture: bytes %u offset %u flags %#x\n",
            plane.bytesused, plane.data_offset, buffer.flags);
    file = fopen(destination, "wbx");
    if (!file)
        return -1;
    status = write_picture(fd, &plane, format.fmt.pix_mp.plane_fmt[0].bytesperline,
                           format.fmt.pix_mp.height, WIDTH, HEIGHT, file);
    saved_errno = errno;
    if (fclose(file) < 0 && status == 0)
        return -1;
    errno = saved_errno;
    return status;
}

struct access_unit {
    long offset;
    uint32_t size;
};

static int read_sequence(FILE *input, long size, struct access_unit *units, unsigned int count)
{
    long position = 0;

    for (unsigned int index = 0; index < count; index++) {
        unsigned char header[4];
        uint32_t length;

        if (size - position < (long)sizeof(header) ||
            fread(header, 1, sizeof(header), input) != sizeof(header))
            goto invalid;
        position += sizeof(header);
        length = header[0] | (uint32_t)header[1] << 8 |
                 (uint32_t)header[2] << 16 | (uint32_t)header[3] << 24;
        if (!length || length > MAX_INPUT_BYTES || length > (uint32_t)(size - position))
            goto invalid;
        units[index] = (struct access_unit){ .offset = position, .size = length };
        position += length;
        if (fseek(input, position, SEEK_SET) != 0)
            return -1;
    }
    if (position == size)
        return fseek(input, units[0].offset, SEEK_SET) == 0 ? 0 : -1;
invalid:
    errno = EPROTO;
    return -1;
}

static int capture_sequence(int fd, int count, const char *destination,
                            FILE *input, const struct access_unit *units, bool early_capture)
{
    struct v4l2_format format = { .type = capture };
    struct v4l2_decoder_cmd stop = { .cmd = V4L2_DEC_CMD_STOP };
    unsigned int queued = 1, returned = 0, frames = 0;
    bool draining = false, last = false;
    int64_t deadline;
    int status = -1, saved_errno;
    FILE *file;

    if (early_capture) {
        if (read_capture_format(fd, &format, WIDTH, HEIGHT) < 0)
            return -1;
    } else {
        count = start_capture(fd, count, &format);
        if (count < 0)
            return -1;
    }
    file = fopen(destination, "wbx");
    if (!file)
        return -1;
    deadline = monotonic_ms();
    if (deadline < 0)
        goto finish;
    deadline += SEQUENCE_TIMEOUT_MS;

    while (!last || returned < queued) {
        struct pollfd ready = { .fd = fd, .events = POLLPRI };
        int64_t now = monotonic_ms();
        int results;

        if (now < 0)
            goto finish;
        if (now >= deadline) {
            errno = ETIMEDOUT;
            goto finish;
        }
        if (!last)
            ready.events |= POLLIN;
        if (returned < queued)
            ready.events |= POLLOUT;
        results = poll(&ready, 1, (int)(deadline - now));
        if (results < 0 && errno == EINTR)
            continue;
        if (results <= 0) {
            if (!results)
                errno = ETIMEDOUT;
            goto finish;
        }
        if (ready.revents & (POLLERR | POLLHUP | POLLNVAL | POLLPRI)) {
            fprintf(stderr, "Sequence poll flags %#x\n", (unsigned int)ready.revents);
            errno = EIO;
            goto finish;
        }
        if (ready.revents & POLLOUT) {
            struct v4l2_plane plane = {0};
            struct v4l2_buffer buffer = {
                .type = output, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane,
            };

            if (video_ioctl(fd, VIDIOC_DQBUF, &buffer) == 0) {
                if (returned >= queued || buffer.index != 0 || buffer.flags & V4L2_BUF_FLAG_ERROR)
                    goto invalid_sequence;
                returned++;
                if (queued < SEQUENCE_FRAMES) {
                    if (fseek(input, units[queued].offset, SEEK_SET) != 0 ||
                        queue_input(fd, input, units[queued].size) < 0)
                        goto finish;
                    queued++;
                }
                if (queued == SEQUENCE_FRAMES && !draining) {
                    if (video_ioctl(fd, VIDIOC_DECODER_CMD, &stop) < 0)
                        goto finish;
                    draining = true;
                }
            } else if (errno != EAGAIN) {
                goto finish;
            }
        }
        if (ready.revents & POLLIN) {
            struct v4l2_plane plane = {0};
            struct v4l2_buffer buffer = {
                .type = capture, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane,
            };

            if (video_ioctl(fd, VIDIOC_DQBUF, &buffer) < 0) {
                if (errno == EAGAIN)
                    continue;
                goto finish;
            }
            last = buffer.flags & V4L2_BUF_FLAG_LAST;
            if (buffer.index >= (unsigned int)count || buffer.length != 1 || buffer.flags & V4L2_BUF_FLAG_ERROR ||
                (last && !draining) || (!plane.bytesused && !last))
                goto invalid_sequence;
            if (plane.bytesused) {
                if (frames >= SEQUENCE_FRAMES)
                    goto invalid_sequence;
                if (write_picture(fd, &plane, format.fmt.pix_mp.plane_fmt[0].bytesperline,
                                  format.fmt.pix_mp.height, WIDTH, HEIGHT, file) < 0)
                    goto finish;
                frames++;
            }
            if (!last && queue_capture(fd, buffer.index) < 0)
                goto finish;
        }
    }
    if (frames != SEQUENCE_FRAMES)
        goto invalid_sequence;
    status = 0;
    goto finish;
invalid_sequence:
    errno = EPROTO;
finish:
    saved_errno = errno;
    fprintf(stderr, "Decoder sequence: queued %u returned %u frames %u STOP %u LAST %u\n",
            queued, returned, frames, (unsigned int)draining, (unsigned int)last);
    if (fclose(file) < 0 && status == 0)
        return -1;
    errno = saved_errno;
    return status;
}

static int replace_capture_queue(int fd, struct v4l2_format *format)
{
    enum v4l2_buf_type stream = capture;
    struct v4l2_requestbuffers release = { .type = capture, .memory = V4L2_MEMORY_MMAP };
    int count;

    if (video_ioctl(fd, VIDIOC_STREAMOFF, &stream) < 0 ||
        video_ioctl(fd, VIDIOC_REQBUFS, &release) < 0 ||
        video_ioctl(fd, VIDIOC_S_FMT, format) < 0)
        return -1;
    if (!valid_capture_format(format, WIDTH, HEIGHT)) {
        errno = EPROTO;
        return -1;
    }
    count = allocate(fd, capture, MAX_BUFFERS);
    if (count < 0 || report_capture_lengths(fd, (unsigned int)count) < 0)
        return -1;
    return activate_capture(fd, count);
}

static int decode_downshift(int fd, int count, FILE *input, const struct access_unit *units)
{
    struct v4l2_format format = { .type = capture }, next_format = { .type = capture };
    struct v4l2_decoder_cmd stop = { .cmd = V4L2_DEC_CMD_STOP };
    unsigned int queued = 1, returned = 0, first_frames = 0, new_frames = 0;
    bool source_changed = false, restarted = false, first_last = false;
    bool stop_sent = false, new_last = false;
    int64_t start = monotonic_ms(), deadline, drain_deadline = 0;
    int saved_errno, status = -1;

    if (start < 0 || read_capture_format(fd, &format, DOWNSHIFT_WIDTH, DOWNSHIFT_CODED_HEIGHT) < 0)
        goto done;
    deadline = start + SEQUENCE_TIMEOUT_MS;
    while (!new_last || returned < queued) {
        struct pollfd ready = { .fd = fd, .events = POLLPRI };
        int64_t now = monotonic_ms(), wake;
        int polled;

        if (now < 0)
            goto done;
        if (now >= deadline) {
            errno = ETIMEDOUT;
            goto done;
        }
        if (source_changed && !restarted && (first_last || now >= drain_deadline)) {
            /* The bounded fallback exposes restart even if LAST is missing. */
            count = replace_capture_queue(fd, &next_format);
            if (count < 0)
                goto done;
            format = next_format;
            restarted = true;
        }
        if (returned == queued && queued < (restarted ? 2 * SEQUENCE_FRAMES : SEQUENCE_FRAMES + 1)) {
            if (fseek(input, units[queued].offset, SEEK_SET) != 0 ||
                queue_input(fd, input, units[queued].size) < 0)
                goto done;
            queued++;
        }
        if (restarted && returned == 2 * SEQUENCE_FRAMES && !stop_sent) {
            if (video_ioctl(fd, VIDIOC_DECODER_CMD, &stop) < 0)
                goto done;
            stop_sent = true;
        }
        if (!(restarted ? new_last : first_last))
            ready.events |= POLLIN;
        if (returned < queued)
            ready.events |= POLLOUT;
        wake = source_changed && !restarted && drain_deadline < deadline ? drain_deadline : deadline;
        polled = poll(&ready, 1, (int)(wake - now));
        if (polled < 0 && errno != EINTR)
            goto done;
        if (polled <= 0)
            continue;
        if (ready.revents & (POLLERR | POLLHUP | POLLNVAL)) {
            errno = EIO;
            goto done;
        }
        if (ready.revents & POLLPRI) {
            if (source_changed || queued != SEQUENCE_FRAMES + 1)
                goto invalid;
            if (read_capture_format(fd, &next_format, WIDTH, HEIGHT) < 0)
                goto done;
            source_changed = true;
            drain_deadline = now + DOWNSHIFT_DRAIN_MS;
        }
        if (ready.revents & POLLIN) {
            struct v4l2_plane plane = {0};
            struct v4l2_buffer buffer = {
                .type = capture, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane,
            };
            unsigned int *frames = restarted ? &new_frames : &first_frames;
            bool *last = restarted ? &new_last : &first_last;

            if (video_ioctl(fd, VIDIOC_DQBUF, &buffer) < 0) {
                if (errno == EAGAIN)
                    continue;
                goto done;
            }
            *last = buffer.flags & V4L2_BUF_FLAG_LAST;
            if (buffer.index >= (unsigned int)count || buffer.length != 1) {
                fprintf(stderr, "CAPTURE invalid buffer: index %u planes %u\n", buffer.index, buffer.length);
                goto invalid;
            }
            if (!restarted && source_changed && !*last &&
                (buffer.flags & V4L2_BUF_FLAG_ERROR || !plane.bytesused || *frames == SEQUENCE_FRAMES)) {
                fprintf(stderr, "CAPTURE boundary buffer: flags %#x payload %u\n",
                        buffer.flags, plane.bytesused);
                drain_deadline = now;
                continue;
            }
            if (buffer.flags & V4L2_BUF_FLAG_ERROR || (!plane.bytesused && !*last))
                goto invalid;
            if (plane.bytesused) {
                if (*frames >= SEQUENCE_FRAMES)
                    goto invalid;
                if (write_picture(fd, &plane, format.fmt.pix_mp.plane_fmt[0].bytesperline,
                                  format.fmt.pix_mp.height,
                                  restarted ? WIDTH : DOWNSHIFT_WIDTH,
                                  restarted ? HEIGHT : DOWNSHIFT_VISIBLE_HEIGHT, stdout) < 0)
                    goto done;
                (*frames)++;
            }
            if (!*last && queue_capture(fd, buffer.index) < 0)
                goto done;
        }
        if (ready.revents & POLLOUT) {
            struct v4l2_plane plane = {0};
            struct v4l2_buffer buffer = {
                .type = output, .memory = V4L2_MEMORY_MMAP, .length = 1, .m.planes = &plane,
            };

            if (video_ioctl(fd, VIDIOC_DQBUF, &buffer) == 0) {
                if (returned >= queued || buffer.index != 0 || buffer.flags & V4L2_BUF_FLAG_ERROR)
                    goto invalid;
                returned++;
            } else if (errno != EAGAIN) {
                goto done;
            }
        }
    }
    if (!first_last || !stop_sent || first_frames != SEQUENCE_FRAMES || new_frames != SEQUENCE_FRAMES)
        goto invalid;
    status = 0;
    goto done;
invalid:
    errno = EPROTO;
done:
    saved_errno = errno;
    if (fflush(stdout) < 0 && !status) {
        status = -1;
        saved_errno = errno;
    }
    fprintf(stderr, "Downshift: queued %u returned %u old %u new %u event %d restart %d old-LAST %d new-LAST %d STOP %d\n",
            queued, returned, first_frames, new_frames, source_changed, restarted, first_last, new_last, stop_sent);
    errno = saved_errno;
    return status;
}

int main(int argc, char **argv)
{
    struct v4l2_event_subscription subscription = { .type = V4L2_EVENT_SOURCE_CHANGE };
    enum v4l2_buf_type stream = output;
    struct stat metadata;
    int fd = -1, capture_buffers = 0, status = 1;
    const char *step = "input";
    bool preallocate, first_frame, sequence, late_capture, early_capture, downshift;
    struct access_unit units[2 * SEQUENCE_FRAMES];
    size_t initial_bytes;
    FILE *input;

    first_frame = argc == 5 && !strcmp(argv[1], "capture-first-frame");
    late_capture = argc == 5 && !strcmp(argv[1], "capture-sequence-late");
    early_capture = argc == 5 && !strcmp(argv[1], "capture-sequence-early");
    downshift = argc == 4 && !strcmp(argv[1], "capture-downshift");
    sequence = early_capture || late_capture || (argc == 5 && !strcmp(argv[1], "capture-sequence"));
    if (!first_frame && !sequence && !downshift && (argc != 4 ||
        (strcmp(argv[1], "output-first") && strcmp(argv[1], "preallocate-capture") &&
         strcmp(argv[1], "headers-only")))) {
        fprintf(stderr, "Usage: %s {output-first|preallocate-capture|headers-only} VIDEO CHUNK\n", argv[0]);
        fprintf(stderr, "       %s capture-first-frame VIDEO ACCESS_UNIT RESULT\n", argv[0]);
        fprintf(stderr, "       %s {capture-sequence|capture-sequence-late} VIDEO FRAMED_ACCESS_UNITS RESULT\n", argv[0]);
        fprintf(stderr, "       %s capture-sequence-early VIDEO FRAMED_ACCESS_UNITS RESULT\n", argv[0]);
        fprintf(stderr, "       %s capture-downshift VIDEO FRAMED_ACCESS_UNITS\n", argv[0]);
        return 2;
    }
    preallocate = downshift || first_frame || (sequence && !late_capture) || !strcmp(argv[1], "preallocate-capture");
    input = fopen(argv[3], "rb");
    if (!input)
        goto done;
    if (fstat(fileno(input), &metadata) < 0)
        goto done;
    if (!S_ISREG(metadata.st_mode) || metadata.st_size <= 0 || metadata.st_size > MAX_INPUT_BYTES) {
        errno = EINVAL;
        goto done;
    }
    initial_bytes = (size_t)metadata.st_size;
    if (sequence || downshift) {
        step = "framed access units";
        if (read_sequence(input, (long)metadata.st_size, units, downshift ? 2 * SEQUENCE_FRAMES : SEQUENCE_FRAMES) < 0)
            goto done;
        initial_bytes = units[0].size;
    }
    step = "decoder identity";
    fd = open(argv[2], O_RDWR | O_NONBLOCK | O_CLOEXEC);
    if (fd < 0 || verify_decoder(fd) < 0)
        goto done;
    step = "source-event subscription";
    if (video_ioctl(fd, VIDIOC_SUBSCRIBE_EVENT, &subscription) < 0)
        goto done;
    step = "OUTPUT format and allocation";
    if (output_format(fd, initial_bytes, downshift ? DOWNSHIFT_WIDTH : WIDTH,
                      downshift ? DOWNSHIFT_CODED_HEIGHT : HEIGHT) < 0 || allocate(fd, output, 1) < 0)
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
    if (queue_input(fd, input, initial_bytes) < 0)
        goto done;
    if (early_capture || downshift) {
        step = "CAPTURE before OUTPUT start";
        if (activate_capture(fd, capture_buffers) < 0)
            goto done;
        fputs("CAPTURE started before OUTPUT\n", stderr);
    }
    step = "OUTPUT STREAMON";
    if (video_ioctl(fd, VIDIOC_STREAMON, &stream) < 0)
        goto done;
    if (downshift) {
        step = "CAPTURE downshift";
        if (!decode_downshift(fd, capture_buffers, input, units))
            status = 0;
    } else if (sequence) {
        step = "CAPTURE sequence";
        if (!capture_sequence(fd, capture_buffers, argv[4], input, units, early_capture))
            status = 0;
    } else if (first_frame) {
        step = "CAPTURE first frame";
        if (!capture_first_frame(fd, (unsigned int)capture_buffers, argv[4]))
            status = 0;
    } else {
        step = "observation";
        if (!observe(fd, argv[1], initial_bytes, capture_buffers))
            status = 0;
    }

done:
    if (status)
        fprintf(stderr, "%s: %s\n", step, strerror(errno));
    if (fd >= 0)
        close(fd);
    if (input)
        fclose(input);
    return status;
}
