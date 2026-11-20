#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise CAMSS's actual start, stop and VFE flush bodies with stubbed hardware."""
import argparse
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory


DRIVER = Path("drivers/media/platform/qcom/camss")


FIXTURE = r"""
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
#define ENOIOCTLCMD 515
#define MEDIA_PAD_FL_SINK 1
#define STAGE_COUNT 5

struct mutex { bool held; };
struct camss { struct mutex pipeline_lock; void *dev; };
struct media_pad;
struct v4l2_subdev;
struct media_entity { struct media_pad *pads; struct v4l2_subdev *subdev; };
struct media_pad {
    unsigned int flags;
    struct media_pad *remote;
    struct media_entity *entity;
};
struct v4l2_subdev {
    struct media_entity entity;
    struct media_pad pad;
    const char *name;
    unsigned int index;
    bool s_stream_enabled;
};
struct video_device { struct media_entity entity; };
struct vb2_queue { struct camss_video *video; };
enum vb2_buffer_state { VB2_BUF_STATE_QUEUED, VB2_BUF_STATE_ERROR };
struct camss_video_ops { int (*flush_buffers)(struct camss_video *, enum vb2_buffer_state); };
struct camss_video {
    struct camss *camss;
    struct video_device vdev;
    const struct camss_video_ops *ops;
};
struct vb2_buffer { unsigned int returns; enum vb2_buffer_state state; };
struct camss_buffer { struct { struct vb2_buffer vb2_buf; } vb; };
struct vfe_output {
    struct camss_buffer *buf[2];
    struct camss_buffer *last_buffer;
    struct camss_buffer *pending;
};
struct vfe_device { bool output_lock; };
struct vfe_line {
    struct camss_video video_out;
    struct vfe_output output;
    struct vfe_device *vfe;
};

enum {
    PIPE_START = 1, FORMAT, PIPE_STOP, QUEUED, ERROR,
    START = 10, STOP = 20,
};

static int events[32];
static size_t used;
static int alloc_error, format_error, failing_stage, missing_stage;
static bool pipeline;

static void event(int type)
{
    assert(used < ARRAY_SIZE(events));
    events[used++] = type;
}

static void verify_events(const int *expected, size_t count)
{
    if (used == count && !memcmp(events, expected, count * sizeof(*expected)))
        return;
    fputs("Unexpected CAMSS event order, actual:", stderr);
    for (size_t i = 0; i < used; i++)
        fprintf(stderr, " %d", events[i]);
    fputs(" expected:", stderr);
    for (size_t i = 0; i < count; i++)
        fprintf(stderr, " %d", expected[i]);
    fputc('\n', stderr);
    /* Exit without leaving a core file when checking the baseline. */
    exit(1);
}

static void mutex_lock(struct mutex *lock)
{
    assert(!lock->held);
    lock->held = true;
}

static void mutex_unlock(struct mutex *lock)
{
    assert(lock->held);
    lock->held = false;
}

#define lockdep_assert_held(lock) assert((lock)->held)
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock) = true; (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(flags); assert(*(lock)); *(lock) = false; } while (0)
#define dev_err(...) ((void)0)
#define vb2_get_drv_priv(q) ((q)->video)
#define to_vfe(line) ((line)->vfe)

static struct media_pad *media_pad_remote_pad_first(struct media_pad *pad)
{
    return pad->remote;
}

static bool is_media_entity_v4l2_subdev(struct media_entity *entity)
{
    return entity->subdev != NULL;
}

static struct v4l2_subdev *media_entity_to_v4l2_subdev(struct media_entity *entity)
{
    return entity->subdev;
}

static int video_device_pipeline_alloc_start(struct video_device *vdev)
{
    event(PIPE_START);
    assert(!pipeline);
    if (!alloc_error)
        pipeline = true;
    return alloc_error;
}

static void video_device_pipeline_stop(struct video_device *vdev)
{
    assert(pipeline);
    pipeline = false;
    event(PIPE_STOP);
}

static int video_check_format(struct camss_video *video)
{
    assert(pipeline);
    event(FORMAT);
    return format_error;
}

static int call_stream(struct v4l2_subdev *sd, bool enable)
{
    if ((int)sd->index == missing_stage)
        return -ENOIOCTLCMD;
    assert(pipeline);
    assert(sd->s_stream_enabled != enable);
    event((enable ? START : STOP) + sd->index);
    if (enable && (int)sd->index == failing_stage)
        return -EIO;
    sd->s_stream_enabled = enable;
    return 0;
}

#define v4l2_subdev_call(sd, group, op, enable) call_stream(sd, enable)

static int flush_video(struct camss_video *video, enum vb2_buffer_state state)
{
    assert(!pipeline);
    event(state == VB2_BUF_STATE_QUEUED ? QUEUED : ERROR);
    return 0;
}

static void vb2_buffer_done(struct vb2_buffer *buffer, enum vb2_buffer_state state)
{
    buffer->returns++;
    buffer->state = state;
}

static void vfe_buf_flush_pending(struct vfe_output *output, enum vb2_buffer_state state)
{
    if (output->pending) {
        vb2_buffer_done(&output->pending->vb.vb2_buf, state);
        output->pending = NULL;
    }
}
"""

CASES = r"""
static const struct camss_video_ops ops = { .flush_buffers = flush_video };

struct test_route {
    struct camss camss;
    struct camss_video video;
    struct vb2_queue q;
    struct media_pad sink;
    struct v4l2_subdev stage[STAGE_COUNT];
};

static void route_init(struct test_route *route)
{
    memset(route, 0, sizeof(*route));
    route->video.camss = &route->camss;
    route->video.ops = &ops;
    route->q.video = &route->video;
    route->video.vdev.entity.pads = &route->sink;
    route->sink.flags = MEDIA_PAD_FL_SINK;
    route->sink.remote = &route->stage[0].pad;
    for (unsigned int i = 0; i < STAGE_COUNT; i++) {
        struct v4l2_subdev *sd = &route->stage[i];

        sd->index = i;
        sd->name = "callback";
        sd->entity.pads = &sd->pad;
        sd->entity.subdev = sd;
        sd->pad.entity = &sd->entity;
        if (i + 1 < STAGE_COUNT) {
            sd->pad.flags = MEDIA_PAD_FL_SINK;
            sd->pad.remote = &route->stage[i + 1].pad;
        }
    }
    used = 0;
    alloc_error = format_error = 0;
    failing_stage = missing_stage = -1;
    assert(!pipeline);
}

static void verify_idle(const struct test_route *route, int foreign)
{
    for (unsigned int i = 0; i < STAGE_COUNT; i++)
        assert(route->stage[i].s_stream_enabled == ((int)i == foreign));
    assert(!pipeline && !route->camss.pipeline_lock.held);
}

static void success(struct test_route *route, int missing)
{
    int expected[32];
    size_t count = 0;

    used = 0;
    failing_stage = -1;
    assert(video_start_streaming(&route->q, 4) == 0);
    video_stop_streaming(&route->q);

    expected[count++] = PIPE_START;
    expected[count++] = FORMAT;
    for (int i = 0; i < STAGE_COUNT; i++)
        if (i != missing)
            expected[count++] = START + i;
    for (int i = 0; i < STAGE_COUNT; i++)
        if (i != missing)
            expected[count++] = STOP + i;
    expected[count++] = PIPE_STOP;
    expected[count++] = ERROR;
    verify_events(expected, count);
    verify_idle(route, -1);
}

static void verify_failed_start(int fail, int missing, bool foreign)
{
    struct test_route route;
    int expected[32];
    size_t count = 0;

    route_init(&route);
    missing_stage = missing;
    if (foreign)
        route.stage[fail].s_stream_enabled = true;
    else
        failing_stage = fail;

    assert(video_start_streaming(&route.q, 4) == (foreign ? -EBUSY : -EIO));
    expected[count++] = PIPE_START;
    expected[count++] = FORMAT;
    for (int i = 0; i < fail + !foreign; i++)
        if (i != missing)
            expected[count++] = START + i;
    for (int i = 0; i < fail; i++)
        if (i != missing)
            expected[count++] = STOP + i;
    expected[count++] = PIPE_STOP;
    expected[count++] = QUEUED;
    verify_events(expected, count);
    verify_idle(&route, foreign ? fail : -1);

    if (foreign)
        route.stage[fail].s_stream_enabled = false;
    success(&route, missing);
}

static void verify_flush(void)
{
    struct vfe_device vfe = { 0 };
    struct vfe_line line = { .vfe = &vfe };
    struct camss_buffer buffers[4] = { 0 };

    line.output.buf[0] = &buffers[0];
    line.output.buf[1] = &buffers[1];
    line.output.last_buffer = &buffers[2];
    line.output.pending = &buffers[3];

    vfe_flush_buffers(&line.video_out, VB2_BUF_STATE_QUEUED);
    vfe_flush_buffers(&line.video_out, VB2_BUF_STATE_ERROR);
    assert(!vfe.output_lock);
    for (size_t i = 0; i < ARRAY_SIZE(buffers); ++i) {
        if (buffers[i].vb.vb2_buf.returns != 1 ||
            buffers[i].vb.vb2_buf.state != VB2_BUF_STATE_QUEUED) {
            fputs("VFE returned a buffer more than once or changed its state\n", stderr);
            exit(1);
        }
    }
}

int main(int argc, char **argv)
{
    struct test_route route;

    if (argc == 2 && !strcmp(argv[1], "flush")) {
        verify_flush();
        puts("VFE returns each active, last and pending buffer once");
        return 0;
    }
    route_init(&route);
    alloc_error = -ENOMEM;
    assert(video_start_streaming(&route.q, 4) == -ENOMEM);
    verify_events((int[]){ PIPE_START, QUEUED }, 2);
    verify_idle(&route, -1);

    route_init(&route);
    format_error = -EPIPE;
    assert(video_start_streaming(&route.q, 4) == -EPIPE);
    verify_events((int[]){ PIPE_START, FORMAT, PIPE_STOP, QUEUED }, 4);
    verify_idle(&route, -1);

    for (int i = 0; i < STAGE_COUNT; i++)
        verify_failed_start(i, -1, false);
    verify_failed_start(STAGE_COUNT - 1, 2, false);
    verify_failed_start(2, 1, true);

    puts("Seven callback failures or conflicts unwind in capture-to-source order");
    puts("Pre-callback failures, retry and normal stop pass");
    return 0;
}
"""


def function(source, name, optional=False):
    start = re.search(r"^\w[^\n]*\b" + name + r"\(", source, re.MULTILINE)
    if optional and start is None:
        return ""
    assert start, name
    return source[start.start():source.index("\n}", start.start()) + 2]


def build_fixture(temp, cc, video, vfe):
    functions = [
        function(video, "video_pipeline_upstream", optional=True),
        function(video, "video_pipeline_stop_subdevs", optional=True),
        function(video, "video_start_streaming"),
        function(video, "video_stop_streaming"),
        function(vfe, "vfe_flush_buffers"),
    ]
    testcase = temp / "unwind.c"
    binary = temp / "unwind"
    testcase.write_text(FIXTURE + "\n".join(functions) + CASES)
    subprocess.run(
        [cc, "-std=c11", "-Wall", "-Wextra", "-Werror", "-Wno-unused-parameter",
         "-Wno-unused-function", "-o", binary, testcase],
        check=True,
    )
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("linux", type=Path)
    parser.add_argument("--cc", default="cc")
    parser.add_argument("--baseline", help="Git revision used for the negative controls")
    args = parser.parse_args()

    video, vfe = (DRIVER / name for name in ("camss-video.c", "camss-vfe.c"))
    with TemporaryDirectory(prefix="fx0-camss-unwind-test-") as tmp:
        binary = build_fixture(Path(tmp), args.cc, (args.linux / video).read_text(),
                               (args.linux / vfe).read_text())
        subprocess.run([binary], check=True)
        subprocess.run([binary, "flush"], check=True)

        if args.baseline:
            revisions = [subprocess.check_output(
                ["git", "-C", args.linux, "show", "--end-of-options", f"{args.baseline}:{file}"], text=True,
            ) for file in (video, vfe)]
            control = build_fixture(Path(tmp), args.cc, *revisions)
            for arguments, message in (
                ([], "Unexpected CAMSS event order"),
                (["flush"], "VFE returned a buffer more than once"),
            ):
                result = subprocess.run([control, *arguments], capture_output=True, text=True)
                assert result.returncode == 1 and message in result.stderr, result.stderr
            print("Base kernel fails both negative controls")


if __name__ == "__main__":
    main()
