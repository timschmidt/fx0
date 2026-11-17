// SPDX-License-Identifier: GPL-2.0-only
static unsigned int checks, failures;
static void check(bool ok, const char *label)
{
	checks++;
	if (!ok) {
		if (failures < 20) printf("FAIL %s\n", label);
		failures++;
	}
}
static void model_reg_clear(struct vfe_device *vfe, enum vfe_line_id id)
{
	(void)vfe; event("reg_clear", id, 0);
}
static void model_reg_update(struct vfe_device *vfe, enum vfe_line_id id)
{
	(void)vfe; event("reg_update", id, 0);
}
static const struct vfe_hw_ops hw_ops = {.reg_update_clear = model_reg_clear,
	.reg_update = model_reg_update};
static const struct vfe_subdev_resources resources = {.hw_ops = &hw_ops};
static struct device dev;
static struct camss camss = {.dev = &dev};
static struct vfe_device vfe;
static struct vfe_line line;
static struct vfe_hw_ops_gen1 selected;
static void reset(unsigned int id, unsigned int wm, unsigned int bpl, unsigned int height, unsigned int buffers)
{
	memset(regs, 0, sizeof(regs));
	memset(vendor_regs, 0, sizeof(vendor_regs));
	memset(&vfe, 0, sizeof(vfe));
	memset(&line, 0, sizeof(line));
	nevents = pending_calls = sensor_skip = 0;
	pending_count = buffers;
	sensor_present = false;
	model_ub_size = 512;
	selected = qualified_ops;
#if HAS_GEOMETRY
	if (MUTANT_NO_HOOK) selected.wm_frame_size = NULL;
#endif
	vfe.base = (u8 *)regs;
	vfe.vfe_base = (u8 *)vendor_regs;
	vfe.ops_gen1 = &selected;
	vfe.res = &resources;
	vfe.camss = &camss;
	line.vfe = &vfe;
	line.id = id;
	line.output.state = VFE_OUTPUT_RESERVED;
	line.output.wm_num = 1;
	line.output.wm_idx[0] = wm;
	line.output.sequence = 123;
	line.output.gen1.wait_sof = line.output.wait_reg_update = 1;
	line.video_out.active_fmt.fmt.pix_mp.height = height;
	line.video_out.active_fmt.fmt.pix_mp.plane_fmt[0].bytesperline = bpl;
	for (unsigned int n = 0; n < 2; n++)
		for (unsigned int p = 0; p < 3; p++) pending[n].addr[p] = 0x10000000 + n * 0x01000000 + p * 0x00100000;
}
static unsigned int writes(unsigned int addr)
{
	unsigned int n = 0;
	for (unsigned int i = 0; i < nevents; i++)
		if (!strcmp(events[i].name, "write") && events[i].a == addr) n++;
	return n;
}
static bool geometry_before_enable(unsigned int wm)
{
	int geometry = -1, enable = -1;
	for (unsigned int i = 0; i < nevents; i++) {
		if (strcmp(events[i].name, "write")) continue;
		if (events[i].a == VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm)) geometry = i;
		if (events[i].a == VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(wm) && (events[i].b & 1)) enable = i;
	}
	return geometry >= 0 && enable > geometry;
}
static unsigned int named_events(const char *name)
{
	unsigned int n = 0;
	for (unsigned int i = 0; i < nevents; i++) if (!strcmp(events[i].name, name)) n++;
	return n;
}
static void check_format_limits(void)
{
	const unsigned int heights[] = {0, 1, 1200, 2464, 4096, 4097, 8191, 8192};
	const unsigned int bits[] = {8, 10, 12, 16};
	for (unsigned int limited = 0; limited < 2; limited++)
	for (unsigned int pix = 0; pix < 2; pix++)
	for (unsigned int m = 0; m < 4; m++)
	for (unsigned int h = 0; h < 8; h++)
	for (unsigned int which = 0; which < 2; which++) {
		reset(pix ? VFE_LINE_PIX : VFE_LINE_RDI0, 0, 4104, heights[h], 2);
#if HAS_HEIGHT_LIMIT
		if (!limited) selected.max_frame_height = 0;
#endif
		struct camss_format_info format = {.code = MEDIA_BUS_FMT_UYVY8_1X16,
			.pixelformat = V4L2_PIX_FMT_UYVY, .planes = 1, .bpp = {bits[m]},
			.hsub = {{1,1}}, .vsub = {{1,1}}};
		struct camss_video *video = &line.video_out;
		video->formats = line.formats = &format;
		video->nformats = line.nformats = 1;
		video->bpl_alignment = 8;
		video->line_based = pix;
		if (!pix) register_rdi_limit(&vfe, video);
		unsigned int limit = limited && !pix ? 4096 : 8191;
		unsigned int expected = heights[h] ? min(heights[h], limit) : 1;
		struct v4l2_subdev_state state = {0};
		struct v4l2_mbus_framefmt mbus = {.code = format.code, .width = 1024, .height = heights[h]};
		enum v4l2_subdev_format_whence selection = which ? V4L2_SUBDEV_FORMAT_ACTIVE : V4L2_SUBDEV_FORMAT_TRY;
		vfe_try_format(&line, &state, MSM_VFE_PAD_SINK, &mbus, selection);
		check(mbus.height == expected, "VFE sink TRY/ACTIVE respects generation-specific RDI height");
		state.fmt[0] = line.fmt[0] = mbus;
		state.crop.width = line.crop.width = 1024;
		state.crop.height = line.crop.height = min(expected, 4096U);
		vfe_try_format(&line, &state, MSM_VFE_PAD_SRC, &mbus, selection);
		check(mbus.height == (pix ? min(expected, 4096U) : expected), "VFE source TRY/ACTIVE preserves negotiated height or existing PIX crop");
		struct file file = {.video = video};
		struct v4l2_frmsizeenum sizes = {.pixel_format = format.pixelformat};
		check(video_enum_framesizes(&file, NULL, &sizes) == 0 &&
		      sizes.stepwise.max_height == (pix ? 4096 : limit), "capture node advertises applicable height limit");
		struct v4l2_format request = {0};
		request.fmt.pix_mp.pixelformat = format.pixelformat;
		request.fmt.pix_mp.width = 1024;
		request.fmt.pix_mp.height = heights[h];
		check(__video_try_fmt(video, &request) == 0 && request.fmt.pix_mp.height == expected,
		      "capture TRY_FMT applies RDI limit and preserves other legacy paths");
	}
}
int main(void)
{
	const struct {unsigned int width, height, bpp, vendor_format;} modes[] = {
		{3280, 2464, 10, V4L2_PIX_FMT_SRGGB10},
		{1640, 1232, 10, V4L2_PIX_FMT_SRGGB10},
		{1976, 1200, 10, V4L2_PIX_FMT_SRGGB10},
		{1976, 1144, 10, V4L2_PIX_FMT_SRGGB10},
		{1920, 1080, 8, V4L2_PIX_FMT_SBGGR8},
		{640, 480, 12, V4L2_PIX_FMT_SBGGR12}
	};
	for (unsigned int id = 0; id < 3; id++)
	for (unsigned int wm = 0; wm < 7; wm++)
	for (unsigned int m = 0; m < 6; m++)
	for (unsigned int buffers = 0; buffers <= 2; buffers++)
	for (unsigned int skip = 0; skip <= 1; skip++) {
		unsigned int bpl = ((modes[m].width * modes[m].bpp / 8 + 7) / 8) * 8;
		reset(id, wm, bpl, modes[m].height, buffers);
		sensor_present = true;
		sensor_skip = skip ? 31 : 0;
		struct msm_vfe_axi_stream vendor = {.wm = {wm}, .frame_based = true,
			.output_format = modes[m].vendor_format,
			.plane_cfg = {{modes[m].width, modes[m].height, modes[m].width}}};
		msm_vfe40_axi_cfg_wm_reg(&vfe, &vendor, 0);
		u32 expected = vendor_regs[VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm) / 4];
		check(vfe_enable_output(&line) == 0, "valid RDI output starts");
		check(regs[VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm) / 4] == expected,
		      "RDI geometry matches actual pinned vendor register trace");
		check(writes(VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm)) == 1 &&
		      geometry_before_enable(wm), "exactly one geometry write precedes WM enable");
		bool others = true;
		for (unsigned int other = 0; other < 7; other++)
			if (other != wm && regs[VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(other) / 4]) others = false;
		check(others, "geometry affects only selected write master");
		check(line.output.state == (buffers == 0 ? VFE_OUTPUT_IDLE :
		      buffers == 1 ? VFE_OUTPUT_SINGLE : VFE_OUTPUT_CONTINUOUS) && pending_calls == 2,
		      "normal buffer ownership/state preserved");
		check(!vfe.output_lock && line.output.sequence == 0 &&
		      line.output.sof.resets == 1 && line.output.reg_update.resets == 1,
		      "output initialization and lock balance preserved");
		check(named_events("bus_reload_wm") == 1 && named_events("wm_line_based") == 0,
		      "RDI reload and dispatch preserved");
	}
	const unsigned int invalid[][2] = {{8, 0}, {8, 4097}, {8, 8191}, {0, 1}, {524288, 1}};
	for (unsigned int wm = 0; wm < 7; wm++)
	for (unsigned int i = 0; i < 5; i++) {
		reset(0, wm, invalid[i][0], invalid[i][1], 2);
		check(vfe_enable_output(&line) == -EINVAL, "unrepresentable geometry rejected");
		check(line.output.state == VFE_OUTPUT_RESERVED && pending_calls == 0 &&
		      !line.output.buf[0] && !line.output.buf[1] && !vfe.output_lock,
		      "invalid geometry rejected before consuming pending buffers");
		check(!writes(VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(wm)) &&
		      !(regs[VFE_0_BUS_IMAGE_MASTER_n_WR_CFG(wm)/4] & 1), "invalid geometry never enables DMA");
	}
	const unsigned int edges[][2] = {{1,1}, {7,4096}, {8,4096}, {9,1}, {524280,4096}};
	for (unsigned int i = 0; i < 5; i++) {
		reset(2, 6, edges[i][0], edges[i][1], 2);
		u32 expected = ((edges[i][0] + 7) / 8) * 65536 + (edges[i][1] - 1) * 16 + 1;
		check(vfe_enable_output(&line) == 0 && regs[(0x84 + 0x24 * 6)/4] == expected,
		      "word rounding and representable field boundaries preserved");
	}
	for (unsigned int id = 0; id < 3; id++) {
		reset(id, id + 1, 4104, 2464, 2);
#if HAS_GEOMETRY
		selected.wm_frame_size = NULL;
#endif
		check(vfe_enable_output(&line) == 0 && line.output.state == VFE_OUTPUT_CONTINUOUS &&
		      !writes(VFE_0_BUS_IMAGE_MASTER_n_WR_BUFFER_CFG(id + 1)),
		      "gen1 variants without optional geometry callback unchanged");
	}
	reset(VFE_LINE_PIX, 0, 4104, 8191, 2);
	line.output.wm_num = 3;
	line.output.wm_idx[0] = 0; line.output.wm_idx[1] = 1; line.output.wm_idx[2] = 2;
	check(vfe_enable_output(&line) == 0 && named_events("wm_line_based") == 3 &&
	      named_events("bus_reload_wm") == 3 && !writes(0x84) && !writes(0xa8) && !writes(0xcc),
	      "PIX keeps existing line-based path and does not call RDI geometry");
	reset(0, 0, 4104, 2464, 2);
	line.output.state = VFE_OUTPUT_ON;
	check(vfe_enable_output(&line) == -EINVAL && pending_calls == 0 && !vfe.output_lock,
	      "invalid output state still rejects before buffer ownership");
	reset(0, 0, 4104, 2464, 2);
	model_ub_size = 0;
	check(vfe_enable_output(&line) == -EINVAL && pending_calls == 0 && !vfe.output_lock,
	      "unsupported VFE instance still rejects before buffer ownership");
	reset(0, 3, 4104, 2464, 2);
	int first = vfe_enable_output(&line);
	vfe_wm_enable(&vfe, 3, 0);
	line.output.state = VFE_OUTPUT_RESERVED; pending_calls = nevents = 0;
	line.video_out.active_fmt.fmt.pix_mp.height = 1200;
	line.video_out.active_fmt.fmt.pix_mp.plane_fmt[0].bytesperline = 2472;
	check(first == 0 && vfe_enable_output(&line) == 0 && regs[(0x84 + 0x24 * 3)/4] == 0x01354af1,
	      "next reserved start replaces old frame geometry after modeled WM disable");
	check_format_limits();
	printf("{\"checks\":%u,\"failures\":%u}\n", checks, failures);
	return failures ? 1 : 0;
}
