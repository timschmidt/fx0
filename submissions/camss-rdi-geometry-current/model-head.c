// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic VFE core services and register storage; no device access. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <linux/videodev2.h>
#include <linux/v4l2-subdev.h>
#include <linux/media-bus-format.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define DIV_ROUND_UP(n, d) (((n) + (d) - 1) / (d))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define clamp_t(t, n, low, high) ((t)(n) < (t)(low) ? (t)(low) : ((t)(n) > (t)(high) ? (t)(high) : (t)(n)))
#define roundup(n, alignment) (DIV_ROUND_UP(n, alignment) * (alignment))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define VFE_FRAME_DROP_UPDATES 2
#define VFE_FRAME_DROP_VAL 30
enum vfe_line_id { VFE_LINE_NONE = -1, VFE_LINE_RDI0, VFE_LINE_RDI1, VFE_LINE_RDI2, VFE_LINE_PIX };
enum vfe_output_state { VFE_OUTPUT_OFF, VFE_OUTPUT_RESERVED, VFE_OUTPUT_SINGLE,
	VFE_OUTPUT_CONTINUOUS, VFE_OUTPUT_IDLE, VFE_OUTPUT_STOPPING, VFE_OUTPUT_ON };
struct vfe_device;
struct vfe_line;
struct vfe_output;
struct device { int unused; };
struct media_entity { int unused; };
struct media_pad { struct media_entity *entity; };
struct v4l2_subdev { struct media_entity entity; };
struct completion { unsigned int resets; };
struct camss_buffer { u32 addr[3]; };
struct camss_format_info {
	u32 code, pixelformat;
	int planes;
	unsigned int bpp[3];
	struct v4l2_fract hsub[3], vsub[3];
};
struct camss_video {
	struct v4l2_format active_fmt;
	unsigned int bpl_alignment, line_based, max_height;
	int nformats;
	const struct camss_format_info *formats;
};
struct vfe_output {
	u8 wm_num, wm_idx[3];
	struct camss_buffer *buf[2];
	unsigned int drop_update_idx;
	struct { int active_buf, wait_sof; } gen1;
	enum vfe_output_state state;
	unsigned int sequence;
	int wait_reg_update;
	struct completion sof, reg_update;
};
struct vfe_line {
	struct vfe_device *vfe;
	enum vfe_line_id id;
	struct v4l2_subdev subdev;
	struct camss_video video_out;
	struct vfe_output output;
	unsigned int nformats;
	const struct camss_format_info *formats;
	struct v4l2_mbus_framefmt fmt[2];
	struct v4l2_rect crop;
};
struct vfe_hw_ops {
	void (*reg_update_clear)(struct vfe_device *, enum vfe_line_id);
	void (*reg_update)(struct vfe_device *, enum vfe_line_id);
};
struct vfe_subdev_resources { const struct vfe_hw_ops *hw_ops; };
struct camss { struct device *dev; };
struct vfe_hw_ops_gen1;
struct vfe_device {
	u8 id;
	u8 *base, *vfe_base;
	bool output_lock;
	struct camss *camss;
	const struct vfe_subdev_resources *res;
	const struct vfe_hw_ops_gen1 *ops_gen1;
};
struct event { const char *name; u32 a, b; };
static struct event events[256];
static unsigned int nevents;
static void event(const char *name, u32 a, u32 b)
{
	assert(nevents < 256);
	events[nevents++] = (struct event){name, a, b};
}
static u32 regs[1024], vendor_regs[1024];
static void writel_relaxed(u32 val, void *addr)
{
	u8 *p = addr;
	assert(p >= (u8 *)regs && p + 4 <= (u8 *)(regs + 1024));
	memcpy(p, &val, 4);
	event("write", p - (u8 *)regs, val);
}
static u32 readl_relaxed(void *addr)
{
	u32 val;
	u8 *p = addr;
	assert(p >= (u8 *)regs && p + 4 <= (u8 *)(regs + 1024));
	memcpy(&val, p, 4);
	return val;
}
static void msm_camera_io_w(u32 val, void *addr)
{
	u8 *p = addr;
	assert(p >= (u8 *)vendor_regs && p + 4 <= (u8 *)(vendor_regs + 1024));
	memcpy(p, &val, 4);
}
static bool sensor_present;
static unsigned int sensor_skip, pending_count, pending_calls;
static u16 model_ub_size = 512;
static struct media_pad model_sensor_pad;
static struct camss_buffer pending[2];
static struct camss_buffer *vfe_buf_get_pending(struct vfe_output *output)
{
	(void)output;
	unsigned int n = pending_calls++;
	return n < pending_count ? &pending[n] : NULL;
}
#define to_vfe(line) ((line)->vfe)
#define camss_find_sensor_pad(entity) ((void)(entity), sensor_present ? &model_sensor_pad : NULL)
#define media_entity_to_v4l2_subdev(entity) ((void)(entity), &dummy_subdev)
#define v4l2_subdev_call(sd, block, op, p) do { (void)(sd); *(p) = sensor_skip; } while (0)
static struct v4l2_subdev dummy_subdev;
#define spin_lock_irqsave(lock, flags) do { assert(!*(lock)); *(lock) = true; (flags) = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)(flags); assert(*(lock)); *(lock) = false; } while (0)
#define dev_err(dev, fmt, ...) ((void)(dev))
#define reinit_completion(c) ((c)->resets++)
#define msm_isp_print_fourcc_error(name, fmt) ((void)(name), (void)(fmt))
struct msm_vfe_axi_plane_cfg { u32 output_width, output_height, output_stride; };
struct msm_vfe_axi_stream {
	u8 wm[3];
	bool frame_based;
	u32 output_format;
	struct msm_vfe_axi_plane_cfg plane_cfg[3];
};
struct v4l2_subdev_state { struct v4l2_mbus_framefmt fmt[2]; struct v4l2_rect crop; };
#define MSM_VFE_PAD_SINK 0
#define MSM_VFE_PAD_SRC 1
static struct v4l2_mbus_framefmt *__vfe_get_format(struct vfe_line *line,
	struct v4l2_subdev_state *state, unsigned int pad, enum v4l2_subdev_format_whence which)
{
	return which == V4L2_SUBDEV_FORMAT_TRY ? &state->fmt[pad] : &line->fmt[pad];
}
static struct v4l2_rect *__vfe_get_crop(struct vfe_line *line,
	struct v4l2_subdev_state *state, enum v4l2_subdev_format_whence which)
{
	return which == V4L2_SUBDEV_FORMAT_TRY ? &state->crop : &line->crop;
}
static u32 vfe_src_pad_code(struct vfe_line *line, u32 sink, unsigned int index, u32 desired)
{
	(void)line; (void)index; (void)desired; return sink;
}
static unsigned int camss_format_get_bpl_alignment(const struct camss_format_info *format)
{
	(void)format; return 8;
}
struct file { struct camss_video *video; };
#define video_drvdata(file) ((file)->video)
