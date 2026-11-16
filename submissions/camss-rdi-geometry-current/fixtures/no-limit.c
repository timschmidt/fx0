// SPDX-License-Identifier: GPL-2.0-only
/*
 * Extracted Linux and pinned vendor kernel functions, with generated model
 * operation stubs and registration wrapper. Original source notices:
 * camss-vfe-4-1.c, camss-vfe-gen1.h, camss-video.c, camss-video.h,
 * camss-vfe.c: Copyright (c) 2013-2015, The Linux Foundation.
 * All rights reserved. Copyright (C) 2015-2018 Linaro Ltd.
 * camss-vfe-gen1.c: Copyright (C) 2020 Linaro Ltd.
 * msm_isp40.c: Copyright (c) 2013, The Linux Foundation.
 * All rights reserved.
 * msm_isp_util.c: Copyright (c) 2013-2014, The Linux Foundation.
 * All rights reserved.
 * Vendor code is GNU GPL version 2 only. Full sources, original notices,
 * LICENSES and NOTICE accompany these extracted fixtures.
 */
/* BEGIN EXECUTED BODY */
struct vfe_hw_ops_gen1 {
	u32 max_frame_height;
	void (*bus_connect_wm_to_rdi)(struct vfe_device *vfe, u8 wm, enum vfe_line_id id);
	void (*bus_disconnect_wm_from_rdi)(struct vfe_device *vfe, u8 wm, enum vfe_line_id id);
	void (*bus_enable_wr_if)(struct vfe_device *vfe, u8 enable);
	void (*bus_reload_wm)(struct vfe_device *vfe, u8 wm);
	int (*camif_wait_for_stop)(struct vfe_device *vfe, struct device *dev);
	void (*enable_irq_common)(struct vfe_device *vfe);
	void (*enable_irq_wm_line)(struct vfe_device *vfe, u8 wm, enum vfe_line_id line_id,
				   u8 enable);
	void (*enable_irq_pix_line)(struct vfe_device *vfe, u8 comp, enum vfe_line_id line_id,
				    u8 enable);
	u16 (*get_ub_size)(u8 vfe_id);
	void (*halt_clear)(struct vfe_device *vfe);
	void (*halt_request)(struct vfe_device *vfe);
	void (*set_camif_cfg)(struct vfe_device *vfe, struct vfe_line *line);
	void (*set_camif_cmd)(struct vfe_device *vfe, u8 enable);
	void (*set_cgc_override)(struct vfe_device *vfe, u8 wm, u8 enable);
	void (*set_clamp_cfg)(struct vfe_device *vfe);
	void (*set_crop_cfg)(struct vfe_device *vfe, struct vfe_line *line);
	void (*set_demux_cfg)(struct vfe_device *vfe, struct vfe_line *line);
	void (*set_ds)(struct vfe_device *vfe);
	void (*set_module_cfg)(struct vfe_device *vfe, u8 enable);
	void (*set_scale_cfg)(struct vfe_device *vfe, struct vfe_line *line);
	void (*set_rdi_cid)(struct vfe_device *vfe, enum vfe_line_id id, u8 cid);
	void (*set_realign_cfg)(struct vfe_device *vfe, struct vfe_line *line, u8 enable);
	void (*set_qos)(struct vfe_device *vfe);
	void (*set_xbar_cfg)(struct vfe_device *vfe, struct vfe_output *output, u8 enable);
	void (*wm_frame_based)(struct vfe_device *vfe, u8 wm, u8 enable);
	int (*wm_frame_size)(struct vfe_device *vfe, u8 wm,
			     struct v4l2_pix_format_mplane *pix);
	void (*wm_line_based)(struct vfe_device *vfe, u32 wm, struct v4l2_pix_format_mplane *pix,
			      u8 plane, u32 enable);
	void (*wm_set_ub_cfg)(struct vfe_device *vfe, u8 wm, u16 offset, u16 depth);
	void (*wm_set_subsample)(struct vfe_device *vfe, u8 wm);
	void (*wm_set_framedrop_period)(struct vfe_device *vfe, u8 wm, u8 per);
	void (*wm_set_framedrop_pattern)(struct vfe_device *vfe, u8 wm, u32 pattern);
	void (*wm_set_ping_addr)(struct vfe_device *vfe, u8 wm, u32 addr);
	void (*wm_set_pong_addr)(struct vfe_device *vfe, u8 wm, u32 addr);
	int (*wm_get_ping_pong_status)(struct vfe_device *vfe, u8 wm);
	void (*wm_enable)(struct vfe_device *vfe, u8 wm, u8 enable);
};
#define VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(n)		(0x06c + 0x24 * (n))
#define VFE_0_BUS_IMAGE_MASTER_n_WR_CFG_WR_PATH_SHIFT	0
#define VFE_0_BUS_IMAGE_MASTER_n_WR_CFG_FRM_BASED_SHIFT	1
#define VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(n)	(0x084 + 0x24 * (n))
#define VFE_WM_BUFFER_CFG_MAX_HEIGHT		4096
#define VFE_WM_BUFFER_CFG_MAX_WORDS		0xffff
#define VFE40_BURST_LEN 1
#define VFE40_WM_BASE(idx) (0x6C + 0x24 * idx)
#define CAL_WORD(width, M, N) ((width * M + N - 1) / N)
#ifndef V4L2_PIX_FMT_QBGGR8
#define V4L2_PIX_FMT_QBGGR8  v4l2_fourcc('Q', 'B', 'G', '8')
#endif
#ifndef V4L2_PIX_FMT_QGBRG8
#define V4L2_PIX_FMT_QGBRG8  v4l2_fourcc('Q', 'G', 'B', '8')
#endif
#ifndef V4L2_PIX_FMT_QGRBG8
#define V4L2_PIX_FMT_QGRBG8  v4l2_fourcc('Q', 'G', 'R', '8')
#endif
#ifndef V4L2_PIX_FMT_QRGGB8
#define V4L2_PIX_FMT_QRGGB8  v4l2_fourcc('Q', 'R', 'G', '8')
#endif
#ifndef V4L2_PIX_FMT_QBGGR10
#define V4L2_PIX_FMT_QBGGR10 v4l2_fourcc('Q', 'B', 'G', '0')
#endif
#ifndef V4L2_PIX_FMT_QGBRG10
#define V4L2_PIX_FMT_QGBRG10 v4l2_fourcc('Q', 'G', 'B', '0')
#endif
#ifndef V4L2_PIX_FMT_QGRBG10
#define V4L2_PIX_FMT_QGRBG10 v4l2_fourcc('Q', 'G', 'R', '0')
#endif
#ifndef V4L2_PIX_FMT_QRGGB10
#define V4L2_PIX_FMT_QRGGB10 v4l2_fourcc('Q', 'R', 'G', '0')
#endif
#ifndef V4L2_PIX_FMT_QBGGR12
#define V4L2_PIX_FMT_QBGGR12 v4l2_fourcc('Q', 'B', 'G', '2')
#endif
#ifndef V4L2_PIX_FMT_QGBRG12
#define V4L2_PIX_FMT_QGBRG12 v4l2_fourcc('Q', 'G', 'B', '2')
#endif
#ifndef V4L2_PIX_FMT_QGRBG12
#define V4L2_PIX_FMT_QGRBG12 v4l2_fourcc('Q', 'G', 'R', '2')
#endif
#ifndef V4L2_PIX_FMT_QRGGB12
#define V4L2_PIX_FMT_QRGGB12 v4l2_fourcc('Q', 'R', 'G', '2')
#endif
#ifndef V4L2_PIX_FMT_NV14
#define V4L2_PIX_FMT_NV14 v4l2_fourcc('N', 'V', '1', '4')
#endif
#ifndef V4L2_PIX_FMT_NV41
#define V4L2_PIX_FMT_NV41 v4l2_fourcc('N', 'V', '4', '1')
#endif
#ifndef V4L2_PIX_FMT_META
#define V4L2_PIX_FMT_META v4l2_fourcc('Q', 'M', 'E', 'T')
#endif
int msm_isp_cal_word_per_line(uint32_t output_format,
	uint32_t pixel_per_line)
{
	int val = -1;
	switch (output_format) {
	case V4L2_PIX_FMT_SBGGR8:
	case V4L2_PIX_FMT_SGBRG8:
	case V4L2_PIX_FMT_SGRBG8:
	case V4L2_PIX_FMT_SRGGB8:
	case V4L2_PIX_FMT_QBGGR8:
	case V4L2_PIX_FMT_QGBRG8:
	case V4L2_PIX_FMT_QGRBG8:
	case V4L2_PIX_FMT_QRGGB8:
	case V4L2_PIX_FMT_JPEG:
	case V4L2_PIX_FMT_META:
		val = CAL_WORD(pixel_per_line, 1, 8);
		break;
	case V4L2_PIX_FMT_SBGGR10:
	case V4L2_PIX_FMT_SGBRG10:
	case V4L2_PIX_FMT_SGRBG10:
	case V4L2_PIX_FMT_SRGGB10:
		val = CAL_WORD(pixel_per_line, 5, 32);
		break;
	case V4L2_PIX_FMT_SBGGR12:
	case V4L2_PIX_FMT_SGBRG12:
	case V4L2_PIX_FMT_SGRBG12:
	case V4L2_PIX_FMT_SRGGB12:
		val = CAL_WORD(pixel_per_line, 3, 16);
		break;
	case V4L2_PIX_FMT_QBGGR10:
	case V4L2_PIX_FMT_QGBRG10:
	case V4L2_PIX_FMT_QGRBG10:
	case V4L2_PIX_FMT_QRGGB10:
		val = CAL_WORD(pixel_per_line, 1, 6);
		break;
	case V4L2_PIX_FMT_QBGGR12:
	case V4L2_PIX_FMT_QGBRG12:
	case V4L2_PIX_FMT_QGRBG12:
	case V4L2_PIX_FMT_QRGGB12:
		val = CAL_WORD(pixel_per_line, 1, 5);
		break;
	case V4L2_PIX_FMT_NV12:
	case V4L2_PIX_FMT_NV21:
	case V4L2_PIX_FMT_NV14:
	case V4L2_PIX_FMT_NV41:
	case V4L2_PIX_FMT_NV16:
	case V4L2_PIX_FMT_NV61:
		val = CAL_WORD(pixel_per_line, 1, 8);
		break;
		/*TD: Add more image format*/
	default:
		msm_isp_print_fourcc_error(__func__, output_format);
		break;
	}
	return val;
}

static void msm_vfe40_axi_cfg_wm_reg(
	struct vfe_device *vfe_dev,
	struct msm_vfe_axi_stream *stream_info,
	uint8_t plane_idx)
{
	uint32_t val;
	uint32_t wm_base = VFE40_WM_BASE(stream_info->wm[plane_idx]);

	if (!stream_info->frame_based) {
		msm_camera_io_w(0x0, vfe_dev->vfe_base + wm_base);
		/*WR_IMAGE_SIZE*/
		val =
			((msm_isp_cal_word_per_line(
				stream_info->output_format,
				stream_info->plane_cfg[plane_idx].
				output_width)+1)/2 - 1) << 16 |
				(stream_info->plane_cfg[plane_idx].
				output_height - 1);
		msm_camera_io_w(val, vfe_dev->vfe_base + wm_base + 0x14);

		/*WR_BUFFER_CFG*/
		val =
			msm_isp_cal_word_per_line(stream_info->output_format,
			stream_info->plane_cfg[
				plane_idx].output_stride) << 16 |
			(stream_info->plane_cfg[
				plane_idx].output_height - 1) << 4 |
			VFE40_BURST_LEN;
		msm_camera_io_w(val, vfe_dev->vfe_base + wm_base + 0x18);
	} else {
		msm_camera_io_w(0x2, vfe_dev->vfe_base + wm_base);
		val =
			msm_isp_cal_word_per_line(stream_info->output_format,
			stream_info->plane_cfg[
				plane_idx].output_width) << 16 |
			(stream_info->plane_cfg[
				plane_idx].output_height - 1) << 4 |
			VFE40_BURST_LEN;
		msm_camera_io_w(val, vfe_dev->vfe_base + wm_base + 0x18);
	}

	/*WR_IRQ_SUBSAMPLE_PATTERN*/
	msm_camera_io_w(0xFFFFFFFF,
		vfe_dev->vfe_base + wm_base + 0x20);
	/* TD: Add IRQ subsample pattern */
	return;
}

static inline void vfe_reg_clr(struct vfe_device *vfe, u32 reg, u32 clr_bits)
{
	u32 bits = readl_relaxed(vfe->base + reg);

	writel_relaxed(bits & ~clr_bits, vfe->base + reg);
}

static inline void vfe_reg_set(struct vfe_device *vfe, u32 reg, u32 set_bits)
{
	u32 bits = readl_relaxed(vfe->base + reg);

	writel_relaxed(bits | set_bits, vfe->base + reg);
}

static void vfe_wm_enable(struct vfe_device *vfe, u8 wm, u8 enable)
{
	if (enable)
		vfe_reg_set(vfe, VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(wm),
			    1 << VFE_0_BUS_IMAGE_MASTER_n_WR_CFG_WR_PATH_SHIFT);
	else
		vfe_reg_clr(vfe, VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(wm),
			    1 << VFE_0_BUS_IMAGE_MASTER_n_WR_CFG_WR_PATH_SHIFT);
}

static void vfe_wm_frame_based(struct vfe_device *vfe, u8 wm, u8 enable)
{
	if (enable)
		vfe_reg_set(vfe, VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(wm),
			1 << VFE_0_BUS_IMAGE_MASTER_n_WR_CFG_FRM_BASED_SHIFT);
	else
		vfe_reg_clr(vfe, VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(wm),
			1 << VFE_0_BUS_IMAGE_MASTER_n_WR_CFG_FRM_BASED_SHIFT);
}

static int vfe_wm_frame_size(struct vfe_device *vfe, u8 wm,
			     struct v4l2_pix_format_mplane *pix)
{
	u32 words = DIV_ROUND_UP(pix->plane_fmt[0].bytesperline, 8);
	u32 reg;

	/* Height occupies bits 15:4 and words per line occupy bits 31:16. */
	if (!pix->height || pix->height > VFE_WM_BUFFER_CFG_MAX_HEIGHT ||
	    !words || words > VFE_WM_BUFFER_CFG_MAX_WORDS)
		return -EINVAL;

	reg = (words << 16) | ((pix->height - 1) << 4) | 1;
	writel_relaxed(reg, vfe->base +
		       VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm));

	return 0;
}

static void model_bus_connect_wm_to_rdi(struct vfe_device *vfe, u8 wm, enum vfe_line_id id) { (void)vfe; (void)wm; (void)id; event("bus_connect_wm_to_rdi", wm, 0);  }
static void model_bus_disconnect_wm_from_rdi(struct vfe_device *vfe, u8 wm, enum vfe_line_id id) { (void)vfe; (void)wm; (void)id; event("bus_disconnect_wm_from_rdi", wm, 0);  }
static void model_bus_enable_wr_if(struct vfe_device *vfe, u8 enable) { (void)vfe; (void)enable; event("bus_enable_wr_if", 0, 0);  }
static void model_bus_reload_wm(struct vfe_device *vfe, u8 wm) { (void)vfe; (void)wm; event("bus_reload_wm", wm, 0);  }
static int model_camif_wait_for_stop(struct vfe_device *vfe, struct device *dev) { (void)vfe; (void)dev; event("camif_wait_for_stop", 0, 0); return 0; }
static void model_enable_irq_common(struct vfe_device *vfe) { (void)vfe; event("enable_irq_common", 0, 0);  }
static void model_enable_irq_wm_line(struct vfe_device *vfe, u8 wm, enum vfe_line_id line_id,
				   u8 enable) { (void)vfe; (void)wm; (void)line_id; (void)enable; event("enable_irq_wm_line", wm, 0);  }
static void model_enable_irq_pix_line(struct vfe_device *vfe, u8 comp, enum vfe_line_id line_id,
				    u8 enable) { (void)vfe; (void)comp; (void)line_id; (void)enable; event("enable_irq_pix_line", 0, 0);  }
static u16 model_get_ub_size(u8 vfe_id) { (void)vfe_id; event("get_ub_size", 0, 0); return model_ub_size; }
static void model_halt_clear(struct vfe_device *vfe) { (void)vfe; event("halt_clear", 0, 0);  }
static void model_halt_request(struct vfe_device *vfe) { (void)vfe; event("halt_request", 0, 0);  }
static void model_set_camif_cfg(struct vfe_device *vfe, struct vfe_line *line) { (void)vfe; (void)line; event("set_camif_cfg", 0, 0);  }
static void model_set_camif_cmd(struct vfe_device *vfe, u8 enable) { (void)vfe; (void)enable; event("set_camif_cmd", 0, 0);  }
static void model_set_cgc_override(struct vfe_device *vfe, u8 wm, u8 enable) { (void)vfe; (void)wm; (void)enable; event("set_cgc_override", wm, 0);  }
static void model_set_clamp_cfg(struct vfe_device *vfe) { (void)vfe; event("set_clamp_cfg", 0, 0);  }
static void model_set_crop_cfg(struct vfe_device *vfe, struct vfe_line *line) { (void)vfe; (void)line; event("set_crop_cfg", 0, 0);  }
static void model_set_demux_cfg(struct vfe_device *vfe, struct vfe_line *line) { (void)vfe; (void)line; event("set_demux_cfg", 0, 0);  }
static void model_set_ds(struct vfe_device *vfe) { (void)vfe; event("set_ds", 0, 0);  }
static void model_set_module_cfg(struct vfe_device *vfe, u8 enable) { (void)vfe; (void)enable; event("set_module_cfg", 0, 0);  }
static void model_set_scale_cfg(struct vfe_device *vfe, struct vfe_line *line) { (void)vfe; (void)line; event("set_scale_cfg", 0, 0);  }
static void model_set_rdi_cid(struct vfe_device *vfe, enum vfe_line_id id, u8 cid) { (void)vfe; (void)id; (void)cid; event("set_rdi_cid", 0, 0);  }
static void model_set_realign_cfg(struct vfe_device *vfe, struct vfe_line *line, u8 enable) { (void)vfe; (void)line; (void)enable; event("set_realign_cfg", 0, 0);  }
static void model_set_qos(struct vfe_device *vfe) { (void)vfe; event("set_qos", 0, 0);  }
static void model_set_xbar_cfg(struct vfe_device *vfe, struct vfe_output *output, u8 enable) { (void)vfe; (void)output; (void)enable; event("set_xbar_cfg", 0, 0);  }
static void model_wm_line_based(struct vfe_device *vfe, u32 wm, struct v4l2_pix_format_mplane *pix,
			      u8 plane, u32 enable) { (void)vfe; (void)wm; (void)pix; (void)plane; (void)enable; event("wm_line_based", wm, 0);  }
static void model_wm_set_ub_cfg(struct vfe_device *vfe, u8 wm, u16 offset, u16 depth) { (void)vfe; (void)wm; (void)offset; (void)depth; event("wm_set_ub_cfg", wm, 0);  }
static void model_wm_set_subsample(struct vfe_device *vfe, u8 wm) { (void)vfe; (void)wm; event("wm_set_subsample", wm, 0);  }
static void model_wm_set_framedrop_period(struct vfe_device *vfe, u8 wm, u8 per) { (void)vfe; (void)wm; (void)per; event("wm_set_framedrop_period", wm, 0);  }
static void model_wm_set_framedrop_pattern(struct vfe_device *vfe, u8 wm, u32 pattern) { (void)vfe; (void)wm; (void)pattern; event("wm_set_framedrop_pattern", wm, 0);  }
static void model_wm_set_ping_addr(struct vfe_device *vfe, u8 wm, u32 addr) { (void)vfe; (void)wm; (void)addr; event("wm_set_ping_addr", wm, addr);  }
static void model_wm_set_pong_addr(struct vfe_device *vfe, u8 wm, u32 addr) { (void)vfe; (void)wm; (void)addr; event("wm_set_pong_addr", wm, addr);  }
static int model_wm_get_ping_pong_status(struct vfe_device *vfe, u8 wm) { (void)vfe; (void)wm; event("wm_get_ping_pong_status", wm, 0); return 0; }
static const struct vfe_hw_ops_gen1 qualified_ops = { .bus_connect_wm_to_rdi = model_bus_connect_wm_to_rdi, .bus_disconnect_wm_from_rdi = model_bus_disconnect_wm_from_rdi, .bus_enable_wr_if = model_bus_enable_wr_if, .bus_reload_wm = model_bus_reload_wm, .camif_wait_for_stop = model_camif_wait_for_stop, .enable_irq_common = model_enable_irq_common, .enable_irq_wm_line = model_enable_irq_wm_line, .enable_irq_pix_line = model_enable_irq_pix_line, .get_ub_size = model_get_ub_size, .halt_clear = model_halt_clear, .halt_request = model_halt_request, .set_camif_cfg = model_set_camif_cfg, .set_camif_cmd = model_set_camif_cmd, .set_cgc_override = model_set_cgc_override, .set_clamp_cfg = model_set_clamp_cfg, .set_crop_cfg = model_set_crop_cfg, .set_demux_cfg = model_set_demux_cfg, .set_ds = model_set_ds, .set_module_cfg = model_set_module_cfg, .set_scale_cfg = model_set_scale_cfg, .set_rdi_cid = model_set_rdi_cid, .set_realign_cfg = model_set_realign_cfg, .set_qos = model_set_qos, .set_xbar_cfg = model_set_xbar_cfg, .wm_frame_based = vfe_wm_frame_based, .wm_frame_size = vfe_wm_frame_size, .wm_line_based = model_wm_line_based, .wm_set_ub_cfg = model_wm_set_ub_cfg, .wm_set_subsample = model_wm_set_subsample, .wm_set_framedrop_period = model_wm_set_framedrop_period, .wm_set_framedrop_pattern = model_wm_set_framedrop_pattern, .wm_set_ping_addr = model_wm_set_ping_addr, .wm_set_pong_addr = model_wm_set_pong_addr, .wm_get_ping_pong_status = model_wm_get_ping_pong_status, .wm_enable = vfe_wm_enable, .max_frame_height = 0 };
#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
static void vfe_output_init_addrs(struct vfe_device *vfe,
				  struct vfe_output *output, u8 sync,
				  struct vfe_line *line)
{
	u32 ping_addr;
	u32 pong_addr;
	unsigned int i;

	output->gen1.active_buf = 0;

	for (i = 0; i < output->wm_num; i++) {
		if (output->buf[0])
			ping_addr = output->buf[0]->addr[i];
		else
			ping_addr = 0;

		if (output->buf[1])
			pong_addr = output->buf[1]->addr[i];
		else
			pong_addr = ping_addr;

		vfe->ops_gen1->wm_set_ping_addr(vfe, output->wm_idx[i], ping_addr);
		vfe->ops_gen1->wm_set_pong_addr(vfe, output->wm_idx[i], pong_addr);
		if (sync)
			vfe->ops_gen1->bus_reload_wm(vfe, output->wm_idx[i]);
	}
}

#pragma clang diagnostic pop
static void vfe_output_frame_drop(struct vfe_device *vfe,
				  struct vfe_output *output,
				  u32 drop_pattern)
{
	u8 drop_period;
	unsigned int i;

	/* We need to toggle update period to be valid on next frame */
	output->drop_update_idx++;
	output->drop_update_idx %= VFE_FRAME_DROP_UPDATES;
	drop_period = VFE_FRAME_DROP_VAL + output->drop_update_idx;

	for (i = 0; i < output->wm_num; i++) {
		vfe->ops_gen1->wm_set_framedrop_period(vfe, output->wm_idx[i], drop_period);
		vfe->ops_gen1->wm_set_framedrop_pattern(vfe, output->wm_idx[i], drop_pattern);
	}

	vfe->res->hw_ops->reg_update(vfe, container_of(output, struct vfe_line, output)->id);
}

static int vfe_enable_output(struct vfe_line *line)
{
	struct vfe_device *vfe = to_vfe(line);
	struct vfe_output *output = &line->output;
	const struct vfe_hw_ops *ops = vfe->res->hw_ops;
	struct media_pad *sensor_pad;
	unsigned long flags;
	unsigned int frame_skip = 0;
	unsigned int i;
	u16 ub_size;
	int ret;

	ub_size = vfe->ops_gen1->get_ub_size(vfe->id);
	if (!ub_size)
		return -EINVAL;

	sensor_pad = camss_find_sensor_pad(&line->subdev.entity);
	if (sensor_pad) {
		struct v4l2_subdev *subdev =
			media_entity_to_v4l2_subdev(sensor_pad->entity);

		v4l2_subdev_call(subdev, sensor, g_skip_frames, &frame_skip);
		/* Max frame skip is 29 frames */
		if (frame_skip > VFE_FRAME_DROP_VAL - 1)
			frame_skip = VFE_FRAME_DROP_VAL - 1;
	}

	spin_lock_irqsave(&vfe->output_lock, flags);

	ops->reg_update_clear(vfe, line->id);

	if (output->state > VFE_OUTPUT_RESERVED) {
		dev_err(vfe->camss->dev, "Output is not in reserved state %d\n", output->state);
		spin_unlock_irqrestore(&vfe->output_lock, flags);
		return -EINVAL;
	}
	if (line->id != VFE_LINE_PIX && vfe->ops_gen1->wm_frame_size) {
		struct v4l2_pix_format_mplane *pix =
			&line->video_out.active_fmt.fmt.pix_mp;

		ret = vfe->ops_gen1->wm_frame_size(vfe, output->wm_idx[0], pix);
		if (ret) {
			spin_unlock_irqrestore(&vfe->output_lock, flags);
			return ret;
		}
	}
	output->state = VFE_OUTPUT_IDLE;

	output->buf[0] = vfe_buf_get_pending(output);
	output->buf[1] = vfe_buf_get_pending(output);

	if (!output->buf[0] && output->buf[1]) {
		output->buf[0] = output->buf[1];
		output->buf[1] = NULL;
	}

	if (output->buf[0])
		output->state = VFE_OUTPUT_SINGLE;

	if (output->buf[1])
		output->state = VFE_OUTPUT_CONTINUOUS;

	switch (output->state) {
	case VFE_OUTPUT_SINGLE:
		vfe_output_frame_drop(vfe, output, 1 << frame_skip);
		break;
	case VFE_OUTPUT_CONTINUOUS:
		vfe_output_frame_drop(vfe, output, 3 << frame_skip);
		break;
	default:
		vfe_output_frame_drop(vfe, output, 0);
		break;
	}

	output->sequence = 0;
	output->gen1.wait_sof = 0;
	output->wait_reg_update = 0;
	reinit_completion(&output->sof);
	reinit_completion(&output->reg_update);

	vfe_output_init_addrs(vfe, output, 0, line);

	if (line->id != VFE_LINE_PIX) {
		vfe->ops_gen1->set_cgc_override(vfe, output->wm_idx[0], 1);
		vfe->ops_gen1->enable_irq_wm_line(vfe, output->wm_idx[0], line->id, 1);
		vfe->ops_gen1->bus_connect_wm_to_rdi(vfe, output->wm_idx[0], line->id);
		vfe->ops_gen1->wm_set_subsample(vfe, output->wm_idx[0]);
		vfe->ops_gen1->set_rdi_cid(vfe, line->id, 0);
		vfe->ops_gen1->wm_set_ub_cfg(vfe, output->wm_idx[0],
					    (ub_size + 1) * output->wm_idx[0], ub_size);
		vfe->ops_gen1->wm_frame_based(vfe, output->wm_idx[0], 1);
		vfe->ops_gen1->wm_enable(vfe, output->wm_idx[0], 1);
		vfe->ops_gen1->bus_reload_wm(vfe, output->wm_idx[0]);
	} else {
		ub_size /= output->wm_num;
		for (i = 0; i < output->wm_num; i++) {
			vfe->ops_gen1->set_cgc_override(vfe, output->wm_idx[i], 1);
			vfe->ops_gen1->wm_set_subsample(vfe, output->wm_idx[i]);
			vfe->ops_gen1->wm_set_ub_cfg(vfe, output->wm_idx[i],
						     (ub_size + 1) * output->wm_idx[i], ub_size);
			vfe->ops_gen1->wm_line_based(vfe, output->wm_idx[i],
						     &line->video_out.active_fmt.fmt.pix_mp, i, 1);
			vfe->ops_gen1->wm_enable(vfe, output->wm_idx[i], 1);
			vfe->ops_gen1->bus_reload_wm(vfe, output->wm_idx[i]);
		}
		vfe->ops_gen1->enable_irq_pix_line(vfe, 0, line->id, 1);
		vfe->ops_gen1->set_module_cfg(vfe, 1);
		vfe->ops_gen1->set_camif_cfg(vfe, line);
		vfe->ops_gen1->set_realign_cfg(vfe, line, 1);
		vfe->ops_gen1->set_xbar_cfg(vfe, output, 1);
		vfe->ops_gen1->set_demux_cfg(vfe, line);
		vfe->ops_gen1->set_scale_cfg(vfe, line);
		vfe->ops_gen1->set_crop_cfg(vfe, line);
		vfe->ops_gen1->set_clamp_cfg(vfe);
		vfe->ops_gen1->set_camif_cmd(vfe, 1);
	}

	ops->reg_update(vfe, line->id);

	spin_unlock_irqrestore(&vfe->output_lock, flags);

	return 0;
}

#define HAS_GEOMETRY 1
#define MUTANT_NO_HOOK 0
#define HAS_HEIGHT_LIMIT 1
#define CAMSS_FRAME_MIN_WIDTH		1
#define CAMSS_FRAME_MAX_WIDTH		8191
#define CAMSS_FRAME_MIN_HEIGHT		1
#define CAMSS_FRAME_MAX_HEIGHT_RDI	8191
#define CAMSS_FRAME_MAX_HEIGHT_PIX	4096
static void vfe_try_format(struct vfe_line *line,
			   struct v4l2_subdev_state *sd_state,
			   unsigned int pad,
			   struct v4l2_mbus_framefmt *fmt,
			   enum v4l2_subdev_format_whence which)
{
	struct vfe_device *vfe = to_vfe(line);
	unsigned int max_height = 8191;
	unsigned int i;
	u32 code;

	if (line->id != VFE_LINE_PIX && vfe->ops_gen1 &&
	    vfe->ops_gen1->max_frame_height)
		max_height = min(max_height, vfe->ops_gen1->max_frame_height);

	switch (pad) {
	case MSM_VFE_PAD_SINK:
		/* Set format on sink pad */

		for (i = 0; i < line->nformats; i++)
			if (fmt->code == line->formats[i].code)
				break;

		/* If not found, use UYVY as default */
		if (i >= line->nformats)
			fmt->code = MEDIA_BUS_FMT_UYVY8_1X16;

		fmt->width = clamp_t(u32, fmt->width, 1, 8191);
		fmt->height = clamp_t(u32, fmt->height, 1, max_height);

		fmt->field = V4L2_FIELD_NONE;
		fmt->colorspace = V4L2_COLORSPACE_SRGB;

		break;

	case MSM_VFE_PAD_SRC:
		/* Set and return a format same as sink pad */
		code = fmt->code;

		*fmt = *__vfe_get_format(line, sd_state, MSM_VFE_PAD_SINK,
					 which);

		fmt->code = vfe_src_pad_code(line, fmt->code, 0, code);

		if (line->id == VFE_LINE_PIX) {
			struct v4l2_rect *rect;

			rect = __vfe_get_crop(line, sd_state, which);

			fmt->width = rect->width;
			fmt->height = rect->height;
		}

		break;
	}

	fmt->colorspace = V4L2_COLORSPACE_SRGB;
}

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wunused-parameter"
static int video_enum_framesizes(struct file *file, void *fh,
				 struct v4l2_frmsizeenum *fsize)
{
	struct camss_video *video = video_drvdata(file);
	int i;

	if (fsize->index)
		return -EINVAL;

	/* Only accept pixel format present in the formats[] table */
	for (i = 0; i < video->nformats; i++) {
		if (video->formats[i].pixelformat == fsize->pixel_format)
			break;
	}

	if (i == video->nformats)
		return -EINVAL;

	fsize->type = V4L2_FRMSIZE_TYPE_CONTINUOUS;
	fsize->stepwise.min_width = CAMSS_FRAME_MIN_WIDTH;
	fsize->stepwise.max_width = CAMSS_FRAME_MAX_WIDTH;
	fsize->stepwise.min_height = CAMSS_FRAME_MIN_HEIGHT;
	fsize->stepwise.max_height = video->max_height ?: (video->line_based ?
		CAMSS_FRAME_MAX_HEIGHT_PIX : CAMSS_FRAME_MAX_HEIGHT_RDI);
	fsize->stepwise.step_width = 1;
	fsize->stepwise.step_height = 1;

	return 0;
}

#pragma clang diagnostic pop
static int __video_try_fmt(struct camss_video *video, struct v4l2_format *f)
{
	unsigned int alignment = video->bpl_alignment;
	struct v4l2_pix_format_mplane *pix_mp;
	const struct camss_format_info *fi;
	struct v4l2_plane_pix_format *p;
	u32 bytesperline[3] = { 0 };
	u32 sizeimage[3] = { 0 };
	u32 max_height = video->max_height ?: CAMSS_FRAME_MAX_HEIGHT_RDI;
	u32 width, height;
	u32 bpl, lines;
	int i, j;

	pix_mp = &f->fmt.pix_mp;

	if (video->line_based)
		for (i = 0; i < pix_mp->num_planes && i < 3; i++) {
			p = &pix_mp->plane_fmt[i];
			bytesperline[i] = clamp_t(u32, p->bytesperline,
						  1, 65528);
			sizeimage[i] = clamp_t(u32, p->sizeimage,
					       bytesperline[i],
					       bytesperline[i] * CAMSS_FRAME_MAX_HEIGHT_PIX);
		}

	for (j = 0; j < video->nformats; j++)
		if (pix_mp->pixelformat == video->formats[j].pixelformat)
			break;

	if (j == video->nformats)
		j = 0; /* default format */

	fi = &video->formats[j];
	width = pix_mp->width;
	height = pix_mp->height;

	if (!alignment)
		alignment = camss_format_get_bpl_alignment(fi);

	memset(pix_mp, 0, sizeof(*pix_mp));

	pix_mp->pixelformat = fi->pixelformat;
	pix_mp->width = clamp_t(u32, width, 1, CAMSS_FRAME_MAX_WIDTH);
	pix_mp->height = clamp_t(u32, height, 1, max_height);
	pix_mp->num_planes = fi->planes;
	for (i = 0; i < pix_mp->num_planes; i++) {
		bpl = pix_mp->width / fi->hsub[i].numerator *
			fi->hsub[i].denominator * fi->bpp[i] / 8;
		bpl = roundup(bpl, alignment);
		pix_mp->plane_fmt[i].bytesperline = bpl;
		pix_mp->plane_fmt[i].sizeimage = pix_mp->height /
			fi->vsub[i].numerator * fi->vsub[i].denominator * bpl;
	}

	pix_mp->field = V4L2_FIELD_NONE;
	pix_mp->colorspace = V4L2_COLORSPACE_SRGB;
	pix_mp->flags = 0;
	pix_mp->ycbcr_enc = V4L2_MAP_YCBCR_ENC_DEFAULT(pix_mp->colorspace);
	pix_mp->quantization = V4L2_MAP_QUANTIZATION_DEFAULT(true,
					pix_mp->colorspace, pix_mp->ycbcr_enc);
	pix_mp->xfer_func = V4L2_MAP_XFER_FUNC_DEFAULT(pix_mp->colorspace);

	if (video->line_based)
		for (i = 0; i < pix_mp->num_planes; i++) {
			p = &pix_mp->plane_fmt[i];
			p->bytesperline = clamp_t(u32, p->bytesperline,
						  1, 65528);
			p->sizeimage = clamp_t(u32, p->sizeimage,
					       p->bytesperline,
					       p->bytesperline * CAMSS_FRAME_MAX_HEIGHT_PIX);
			lines = p->sizeimage / p->bytesperline;

			if (p->bytesperline < bytesperline[i])
				p->bytesperline = roundup(bytesperline[i], alignment);

			if (p->sizeimage < p->bytesperline * lines)
				p->sizeimage = p->bytesperline * lines;

			if (p->sizeimage < sizeimage[i])
				p->sizeimage = sizeimage[i];
		}

	return 0;
}

static void register_rdi_limit(struct vfe_device *vfe, struct camss_video *video_out) { (void)vfe; (void)video_out; video_out->max_height = vfe->ops_gen1 ?
				vfe->ops_gen1->max_frame_height : 0; }
/* END EXECUTED BODY */
