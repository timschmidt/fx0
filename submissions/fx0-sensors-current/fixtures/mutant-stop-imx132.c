/*
 * Extracted Linux sensor/framework fixture. GPL-2.0-only combined work.
 * Original notices follow; see NOTICE and LICENSE.GPL-2.0.
 */
// SPDX-License-Identifier: GPL-2.0-only
/*
 * Sony IMX132 2.4 MP CMOS image sensor.
 *
 * The register sequence follows NVIDIA's GPLv2 Tegra imx132.c (Copyright (c)
 * 2012-2014, NVIDIA CORPORATION). The lane selection and the PLL relationship
 * follow the historical AtomISP imx driver.
 */
// SPDX-License-Identifier: GPL-2.0-only
/*
 * Sony IMX179 8 MP CMOS image sensor.
 *
 * The full-resolution register sequence follows NVIDIA's GPLv2 Tegra
 * imx179.c (Copyright (c) 2014, NVIDIA CORPORATION).
 */
// SPDX-License-Identifier: GPL-2.0-only
/*
 * V4L2 sub-device
 *
 * Copyright (C) 2010 Nokia Corporation
 *
 * Contact: Laurent Pinchart <laurent.pinchart@ideasonboard.com>
 *	    Sakari Ailus <sakari.ailus@iki.fi>
 */
// SPDX-License-Identifier: GPL-2.0
/*
 * MIPI Camera Control Interface (CCI) register access helpers.
 *
 * Copyright (C) 2023 Hans de Goede <hansg@kernel.org>
 */
// SPDX-License-Identifier: GPL-2.0-or-later
/*
 *	Video for Linux Two
 *
 *	A generic video device interface for the LINUX operating system
 *	using a set of device structures/vectors for low level operations.
 *
 *	This file replaces the videodev.c file that comes with the
 *	regular kernel distribution.
 *
 * Author:	Bill Dirks <bill@thedirks.org>
 *		based on code by Alan Cox, <alan@cymru.net>
 */

/*
 * Video capture interface for Linux
 *
 *	A generic video device interface for the LINUX operating system
 *	using a set of device structures/vectors for low level operations.
 *
 * Author:	Alan Cox, <alan@lxorguk.ukuu.org.uk>
 *
 * Fixes:
 */

/*
 * Video4linux 1/2 integration by Justin Schoeman
 * <justin@suntiger.ee.up.ac.za>
 * 2.4 PROCFS support ported from 2.4 kernels by
 *  Iñaki García Etxebarria <garetxe@euskalnet.net>
 * Makefile fix by "W. Michael Petullo" <mike@flyn.org>
 * 2.4 devfs support ported from 2.4 kernels by
 *  Dan Merillat <dan@merillat.org>
 * Added Gerd Knorrs v4l1 enhancements (Justin Schoeman)
 */
// SPDX-License-Identifier: GPL-2.0
/*
 * drivers/base/power/runtime.c - Helper functions for device runtime PM
 *
 * Copyright (c) 2009 Rafael J. Wysocki <rjw@sisk.pl>, Novell Inc.
 * Copyright (C) 2010 Alan Stern <stern@rowland.harvard.edu>
 */
/* SPDX-License-Identifier: GPL-2.0 */
/*
 * MIPI Camera Control Interface (CCI) register access helpers.
 *
 * Copyright (C) 2023 Hans de Goede <hansg@kernel.org>
 */
/* SPDX-License-Identifier: GPL-2.0-or-later */
/*
    v4l2 common internal API header

    This header contains internal shared ioctl definitions for use by the
    internal low-level v4l2 drivers.
    Each ioctl begins with VIDIOC_INT_ to clearly mark that it is an internal
    define,

    Copyright (C) 2005  Hans Verkuil <hverkuil@kernel.org>

 */
/* SPDX-License-Identifier: GPL-2.0 */

// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <linux/v4l2-controls.h>
#include <linux/v4l2-subdev.h>
#include <linux/media-bus-format.h>
typedef uint8_t u8;
typedef uint32_t u32;
typedef int32_t s32;
typedef uint64_t u64;
typedef int64_t s64;
#define U32_MAX UINT32_MAX
#define BIT(n) (1U<<(n))
#define BIT_ULL(n) (1ULL<<(n))
#define GENMASK(h,l) ((~0U<<(l)) & (~0U>>(31-(h))))
#define FIELD_GET(mask,x) (((x)&(mask))>>__builtin_ctz(mask))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define BITS_PER_BYTE 8
#define BUILD_BUG_ON(c) _Static_assert(!(c),"build bug")
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define min(a,b) ((a)<(b)?(a):(b))
#define MEDIA_PAD_FL_SOURCE 2
#define V4L2_SUBDEV_FL_STREAMS 0x100
#define RPM_ACTIVE 0
static unsigned underflows;
#define dev_warn(...) ((void)underflows++)
#define dev_err(...) ((void)0)
#define dev_dbg(dev,...) ((void)(dev))
#define dev_get_drvdata(d) ((d)->driver_data)
#define spin_lock_irqsave(lock,flags) do {(void)(lock);(flags)=0;} while(0)
#define spin_unlock_irqrestore(lock,flags) do {(void)(lock);(void)(flags);} while(0)
#define trace_rpm_usage(...) ((void)0)
struct device {
 void *driver_data;
 struct {int usage_count,child_count,disable_depth,runtime_status,lock;bool ignore_children;} power;
};
static int atomic_sub_return(int value,int *p) {return *p-=value;}
static void atomic_inc(int *p) {++*p;}
static int atomic_read(const int *p) {return *p;}
static int atomic_inc_not_zero(int *p) {if(!*p)return 0;++*p;return 1;}
struct regmap {struct device *dev;u8 bytes[65536];};
struct clk {bool enabled;};
struct gpio_desc {int value;};
struct regulator_bulk_data {const char *supply;};
struct media_pad {unsigned flags;};
struct media_device {struct device *dev;};
struct media_entity {struct {struct media_device *mdev;} graph_obj;unsigned num_pads;struct media_pad *pads;const char *name;};
struct v4l2_subdev_client_info {int unused;};
struct v4l2_subdev_stream_config {u32 pad,stream;bool enabled;};
struct v4l2_subdev_state {
 bool locked;struct v4l2_mbus_framefmt format;
 struct {unsigned num_configs;struct v4l2_subdev_stream_config *configs;} stream_configs;
};
struct v4l2_subdev;
struct v4l2_ctrl;
struct v4l2_ctrl_handler {struct v4l2_ctrl *exposure,*vblank;};
struct v4l2_ctrl {unsigned id;int val,minimum,maximum,step;struct v4l2_ctrl_handler *handler;};
struct v4l2_subdev_pad_ops {
 int (*enable_streams)(struct v4l2_subdev *,struct v4l2_subdev_state *,u32,u64);
 int (*disable_streams)(struct v4l2_subdev *,struct v4l2_subdev_state *,u32,u64);
};
struct v4l2_subdev_video_ops {int (*s_stream)(struct v4l2_subdev *,int);};
struct v4l2_subdev_ops {const struct v4l2_subdev_pad_ops *pad;const struct v4l2_subdev_video_ops *video;};
struct v4l2_subdev {
 struct device *dev;struct media_entity entity;const struct v4l2_subdev_ops *ops;
 struct v4l2_subdev_state *active;u64 enabled_pads;unsigned flags;bool s_stream_enabled;
};
#define v4l2_subdev_has_op(sd,group,op) ((sd)->ops->group && (sd)->ops->group->op)
#define v4l2_subdev_call(sd,group,op,...) ((sd)->ops->group->op(sd,__VA_ARGS__))
static struct v4l2_subdev_state *v4l2_subdev_lock_and_get_active_state(struct v4l2_subdev *sd)
{assert(!sd->active->locked);sd->active->locked=true;return sd->active;}
static struct v4l2_subdev_state *v4l2_subdev_get_locked_active_state(struct v4l2_subdev *sd)
{assert(sd->active->locked);return sd->active;}
static void v4l2_subdev_unlock_state(struct v4l2_subdev_state *s) {assert(s->locked);s->locked=false;}
static void v4l2_subdev_enable_privacy_led(struct v4l2_subdev *sd) {(void)sd;}
static void v4l2_subdev_disable_privacy_led(struct v4l2_subdev *sd) {(void)sd;}
static struct v4l2_mbus_framefmt *v4l2_subdev_state_get_format(struct v4l2_subdev_state *s,unsigned pad)
{assert(!pad);return &s->format;}
static unsigned writes,fail_write_at;
static int resume_error,setup_error,bulk_error,clock_error;
static unsigned power_refs,bulk_calls,clock_calls,range_updates;
static void put_bytes(u64 val,u8 *p,unsigned size,bool le)
{for(unsigned i=0;i<size;i++)p[le?i:size-i-1]=(val>>(8*i))&0xff;}
#define put_unaligned_le16(v,p) put_bytes(v,p,2,true)
#define put_unaligned_be16(v,p) put_bytes(v,p,2,false)
#define put_unaligned_le24(v,p) put_bytes(v,p,3,true)
#define put_unaligned_be24(v,p) put_bytes(v,p,3,false)
#define put_unaligned_le32(v,p) put_bytes(v,p,4,true)
#define put_unaligned_be32(v,p) put_bytes(v,p,4,false)
#define put_unaligned_le64(v,p) put_bytes(v,p,8,true)
#define put_unaligned_be64(v,p) put_bytes(v,p,8,false)
static int regmap_bulk_write(struct regmap *m,unsigned reg,const void *p,unsigned len)
{writes++;assert(reg+len<=sizeof(m->bytes));if(writes==fail_write_at)return -EIO;memcpy(m->bytes+reg,p,len);return 0;}
static int pm_runtime_resume_and_get(struct device *dev)
{if(resume_error)return resume_error;dev->power.usage_count++;return 0;}
static int rpm_drop_usage_count(struct device *dev);
static int pm_runtime_put(struct device *dev) {int ret=rpm_drop_usage_count(dev);return ret<0?ret:0;}
static int __v4l2_ctrl_modify_range(struct v4l2_ctrl *ctrl,int minimum,int maximum,int step,int def)
{range_updates++;assert(minimum<=maximum && def>=minimum && def<=maximum);ctrl->minimum=minimum;ctrl->maximum=maximum;ctrl->step=step;if(ctrl->val>maximum)ctrl->val=maximum;return 0;}
static int __v4l2_ctrl_s_ctrl(struct v4l2_ctrl *ctrl,int value) {ctrl->val=value;return 0;}
static int __v4l2_ctrl_handler_setup(struct v4l2_ctrl_handler *hdl) {(void)hdl;return setup_error;}
static int regulator_bulk_enable(unsigned n,struct regulator_bulk_data *supplies)
{assert(n==3);assert(!strcmp(supplies[0].supply,"dovdd") && !strcmp(supplies[1].supply,"avdd") && !strcmp(supplies[2].supply,"dvdd"));bulk_calls++;if(bulk_error)return bulk_error;power_refs++;return 0;}
static int regulator_bulk_disable(unsigned n,struct regulator_bulk_data *supplies)
{(void)supplies;assert(n==3 && power_refs);power_refs--;return 0;}
static int clk_prepare_enable(struct clk *clk) {clock_calls++;if(clock_error)return clock_error;assert(!clk->enabled);clk->enabled=true;return 0;}
static void clk_disable_unprepare(struct clk *clk) {assert(clk->enabled);clk->enabled=false;}
static int gpiod_set_value_cansleep(struct gpio_desc *g,int value) {g->value=value;return 0;}
static void usleep_range(unsigned low,unsigned high) {assert(low<=high);}

struct cci_reg_sequence {
	u32 reg;
	u64 val;
};

/*
 * Macros to define register address with the register width encoded
 * into the higher bits.
 */
#define CCI_REG_ADDR_MASK		GENMASK(15, 0)
#define CCI_REG_WIDTH_SHIFT		16
#define CCI_REG_WIDTH_MASK		GENMASK(19, 16)
/*
 * Private CCI register flags, for the use of drivers.
 */
#define CCI_REG_PRIVATE_SHIFT		28U
#define CCI_REG_PRIVATE_MASK		GENMASK(31U, CCI_REG_PRIVATE_SHIFT)

#define CCI_REG_WIDTH_BYTES(x)		FIELD_GET(CCI_REG_WIDTH_MASK, x)
#define CCI_REG_WIDTH(x)		(CCI_REG_WIDTH_BYTES(x) << 3)
#define CCI_REG_ADDR(x)			FIELD_GET(CCI_REG_ADDR_MASK, x)
#define CCI_REG_LE			BIT(20)

#define CCI_REG8(x)			((1 << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG16(x)			((2 << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG24(x)			((3 << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG32(x)			((4 << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG64(x)			((8 << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG16_LE(x)			(CCI_REG_LE | (2U << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG24_LE(x)			(CCI_REG_LE | (3U << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG32_LE(x)			(CCI_REG_LE | (4U << CCI_REG_WIDTH_SHIFT) | (x))
#define CCI_REG64_LE(x)			(CCI_REG_LE | (8U << CCI_REG_WIDTH_SHIFT) | (x))


#define IMX132_REG_CHIP_ID		CCI_REG16(0x0000)
#define IMX132_CHIP_ID			0x0132
#define IMX132_REG_MODE_SELECT		CCI_REG8(0x0100)
#define IMX132_MODE_STANDBY		0x00
#define IMX132_MODE_STREAMING		0x01
#define IMX132_REG_HOLD			CCI_REG8(0x0104)
#define IMX132_REG_EXPOSURE		CCI_REG16(0x0202)
#define IMX132_REG_ANALOG_GAIN		CCI_REG8(0x0205)
#define IMX132_REG_FRAME_LENGTH		CCI_REG16(0x0340)
#define IMX132_REG_TEST_PATTERN		CCI_REG16(0x0600)

#define IMX132_XCLK_FREQ		24000000
#define IMX132_LINK_FREQ		198000000ULL
#define IMX132_NUM_LANES		1
/* 1 lane x 396 Mbit/s / 10 bits per pixel */
#define IMX132_PIXEL_RATE		39600000

#define IMX132_WIDTH			1976
#define IMX132_HEIGHT			1200
#define IMX132_LINE_LENGTH		2248
#define IMX132_FRAME_LENGTH_DEF		1226
#define IMX132_FRAME_LENGTH_MAX		0xffff
#define IMX132_EXPOSURE_MARGIN		4
#define IMX132_EXPOSURE_MIN		1
#define IMX132_AGAIN_MIN		0
#define IMX132_AGAIN_MAX		224
#define IMX132_AGAIN_DEF		0

static const char * const imx132_supply_names[] = {
	"dovdd",	/* digital I/O, 1.8 V */
	"avdd",		/* analogue, 2.8 V */
	"dvdd",		/* digital core, 1.2 V */
};

static const s64 imx132_link_freqs[] = { IMX132_LINK_FREQ };

static const char * const imx132_test_pattern_menu[] = {
	"Disabled",
	"Solid Colour",
	"Colour Bars",
	"Fade to Grey Colour Bars",
	"PN9",
};

/*
 * 1976x1200 RAW10 on one lane, 24 MHz input. The PLL runs at
 * 24 MHz / 2 * 33 = 396 Mbit/s per lane; with one lane the pixel rate is
 * 396 / 10 = 39.6 Mpixel/s, about 14 frames/s at 2248x1226.
 */
static const struct cci_reg_sequence imx132_common_regs[] = {
	/* Global settings */
	{ CCI_REG8(0x3087), 0x53 },
	{ CCI_REG8(0x308b), 0x5a },
	{ CCI_REG8(0x3094), 0x11 },
	{ CCI_REG8(0x309d), 0xa4 },
	{ CCI_REG8(0x30aa), 0x01 },
	{ CCI_REG8(0x30c6), 0x00 },
	{ CCI_REG8(0x30c7), 0x00 },
	{ CCI_REG8(0x3118), 0x2f },
	{ CCI_REG8(0x312a), 0x00 },
	{ CCI_REG8(0x312b), 0x0b },
	{ CCI_REG8(0x312c), 0x0b },
	{ CCI_REG8(0x312d), 0x13 },
	/* PLL */
	{ CCI_REG8(0x0305), 0x02 },
	{ CCI_REG8(0x0307), 0x21 },
	{ CCI_REG8(0x30a4), 0x02 },	/* VT divider /1 for one lane */
	{ CCI_REG8(0x303c), 0x4b },
	/* Timing and readout */
	{ CCI_REG8(0x0101), 0x00 },
	{ CCI_REG8(0x0342), 0x08 },
	{ CCI_REG8(0x0343), 0xc8 },
	{ CCI_REG8(0x0344), 0x00 },
	{ CCI_REG8(0x0345), 0x00 },
	{ CCI_REG8(0x0346), 0x00 },
	{ CCI_REG8(0x0347), 0x00 },
	{ CCI_REG8(0x0348), 0x07 },
	{ CCI_REG8(0x0349), 0xb7 },
	{ CCI_REG8(0x034a), 0x04 },
	{ CCI_REG8(0x034b), 0xaf },
	{ CCI_REG8(0x0381), 0x01 },
	{ CCI_REG8(0x0383), 0x01 },
	{ CCI_REG8(0x0385), 0x01 },
	{ CCI_REG8(0x0387), 0x01 },
	{ CCI_REG8(0x303d), 0x10 },
	{ CCI_REG8(0x303e), 0x4a },
	{ CCI_REG8(0x3040), 0x08 },
	{ CCI_REG8(0x3041), 0x97 },
	{ CCI_REG8(0x3048), 0x00 },
	{ CCI_REG8(0x304c), 0x2f },
	{ CCI_REG8(0x304d), 0x02 },
	{ CCI_REG8(0x3064), 0x92 },
	{ CCI_REG8(0x306a), 0x10 },
	{ CCI_REG8(0x309b), 0x00 },
	{ CCI_REG8(0x309e), 0x41 },
	{ CCI_REG8(0x30a0), 0x10 },
	{ CCI_REG8(0x30a1), 0x0b },
	{ CCI_REG8(0x30b2), 0x00 },
	{ CCI_REG8(0x30d5), 0x00 },
	{ CCI_REG8(0x30d6), 0x00 },
	{ CCI_REG8(0x30d7), 0x00 },
	{ CCI_REG8(0x30d8), 0x00 },
	{ CCI_REG8(0x30d9), 0x00 },
	{ CCI_REG8(0x30da), 0x00 },
	{ CCI_REG8(0x30db), 0x00 },
	{ CCI_REG8(0x30dc), 0x00 },
	{ CCI_REG8(0x30dd), 0x00 },
	{ CCI_REG8(0x30de), 0x00 },
	{ CCI_REG8(0x3102), 0x0c },
	{ CCI_REG8(0x3103), 0x33 },
	{ CCI_REG8(0x3104), 0x30 },
	{ CCI_REG8(0x3105), 0x00 },
	{ CCI_REG8(0x3106), 0xca },
	{ CCI_REG8(0x3107), 0x00 },
	{ CCI_REG8(0x3108), 0x06 },
	{ CCI_REG8(0x3109), 0x04 },
	{ CCI_REG8(0x310a), 0x04 },
	{ CCI_REG8(0x315c), 0x3d },
	{ CCI_REG8(0x315d), 0x3c },
	{ CCI_REG8(0x316e), 0x3e },
	{ CCI_REG8(0x316f), 0x3d },
	{ CCI_REG8(0x3301), 0x01 },	/* one MIPI lane */
	{ CCI_REG8(0x3304), 0x07 },
	{ CCI_REG8(0x3305), 0x06 },
	{ CCI_REG8(0x3306), 0x19 },
	{ CCI_REG8(0x3307), 0x03 },
	{ CCI_REG8(0x3308), 0x0f },
	{ CCI_REG8(0x3309), 0x07 },
	{ CCI_REG8(0x330a), 0x0c },
	{ CCI_REG8(0x330b), 0x06 },
	{ CCI_REG8(0x330c), 0x0b },
	{ CCI_REG8(0x330d), 0x07 },
	{ CCI_REG8(0x330e), 0x03 },
	{ CCI_REG8(0x3318), 0x67 },
	{ CCI_REG8(0x3322), 0x09 },
	{ CCI_REG8(0x3342), 0x00 },
	{ CCI_REG8(0x3348), 0xe0 },
};

static const struct cci_reg_sequence imx132_mode_1976x1200[] = {
	{ CCI_REG16(0x034c), IMX132_WIDTH },
	{ CCI_REG16(0x034e), IMX132_HEIGHT },
};

struct imx132_mode {
	u32 width;
	u32 height;
	const struct cci_reg_sequence *regs;
	unsigned int num_regs;
};

static const struct imx132_mode imx132_modes[] = {
	{
		.width = IMX132_WIDTH,
		.height = IMX132_HEIGHT,
		.regs = imx132_mode_1976x1200,
		.num_regs = ARRAY_SIZE(imx132_mode_1976x1200),
	},
};

struct imx132 {
	struct device *dev;
	struct regmap *regmap;
	struct clk *xclk;
	struct gpio_desc *reset_gpio;
	struct regulator_bulk_data supplies[ARRAY_SIZE(imx132_supply_names)];

	struct v4l2_subdev sd;
	struct media_pad pad;

	struct v4l2_ctrl_handler ctrl_handler;
	struct v4l2_ctrl *vblank;
	struct v4l2_ctrl *exposure;

	/* Protected by the control handler lock, which is the state lock. */
	const struct imx132_mode *mode;
};


static int rpm_drop_usage_count(struct device *dev)
{
	int ret;

	ret = atomic_sub_return(1, &dev->power.usage_count);
	if (ret >= 0)
		return ret;

	/*
	 * Because rpm_resume() does not check the usage counter, it will resume
	 * the device even if the usage counter is 0 or negative, so it is
	 * sufficient to increment the usage counter here to reverse the change
	 * made above.
	 */
	atomic_inc(&dev->power.usage_count);
	dev_warn(dev, "Runtime PM usage count underflow!\n");
	return -EINVAL;
}
static int pm_runtime_get_conditional(struct device *dev, bool ign_usage_count)
{
	unsigned long flags;
	int retval;

	spin_lock_irqsave(&dev->power.lock, flags);
	if (dev->power.disable_depth > 0) {
		retval = -EINVAL;
	} else if (dev->power.runtime_status != RPM_ACTIVE) {
		retval = 0;
	} else if (ign_usage_count || (!dev->power.ignore_children &&
		   atomic_read(&dev->power.child_count) > 0)) {
		retval = 1;
		atomic_inc(&dev->power.usage_count);
	} else {
		retval = atomic_inc_not_zero(&dev->power.usage_count);
	}
	trace_rpm_usage(dev, 0);
	spin_unlock_irqrestore(&dev->power.lock, flags);

	return retval;
}
int pm_runtime_get_if_in_use(struct device *dev)
{
	return pm_runtime_get_conditional(dev, false);
}
int cci_write(struct regmap *map, u32 reg, u64 val, int *err)
{
	bool little_endian;
	unsigned int len;
	u8 buf[8];
	int ret;

	if (err && *err)
		return *err;

	little_endian = reg & CCI_REG_LE;
	len = CCI_REG_WIDTH_BYTES(reg);
	reg = CCI_REG_ADDR(reg);

	switch (len) {
	case 1:
		buf[0] = val;
		break;
	case 2:
		if (little_endian)
			put_unaligned_le16(val, buf);
		else
			put_unaligned_be16(val, buf);
		break;
	case 3:
		if (little_endian)
			put_unaligned_le24(val, buf);
		else
			put_unaligned_be24(val, buf);
		break;
	case 4:
		if (little_endian)
			put_unaligned_le32(val, buf);
		else
			put_unaligned_be32(val, buf);
		break;
	case 8:
		if (little_endian)
			put_unaligned_le64(val, buf);
		else
			put_unaligned_be64(val, buf);
		break;
	default:
		dev_err(regmap_get_device(map), "Error invalid reg-width %u for reg 0x%04x\n",
			len, reg);
		ret = -EINVAL;
		goto out;
	}

	ret = regmap_bulk_write(map, reg, buf, len);
	if (ret)
		dev_err(regmap_get_device(map), "Error writing reg 0x%04x: %d\n",
			reg, ret);

out:
	if (ret && err)
		*err = ret;

	return ret;
}
int cci_multi_reg_write(struct regmap *map, const struct cci_reg_sequence *regs,
			unsigned int num_regs, int *err)
{
	unsigned int i;
	int ret;

	for (i = 0; i < num_regs; i++) {
		ret = cci_write(map, regs[i].reg, regs[i].val, err);
		if (ret)
			return ret;
	}

	return 0;
}
#undef abs
#define __abs_choose_expr(x, type, other) __builtin_choose_expr(	\
	__builtin_types_compatible_p(typeof(x),   signed type) ||	\
	__builtin_types_compatible_p(typeof(x), unsigned type),		\
	({ signed type __x = (x); __x < 0 ? -__x : __x; }), other)
#define abs(x)	__abs_choose_expr(x, long long,				\
		__abs_choose_expr(x, long,				\
		__abs_choose_expr(x, int,				\
		__abs_choose_expr(x, short,				\
		__abs_choose_expr(x, char,				\
		__builtin_choose_expr(					\
			__builtin_types_compatible_p(typeof(x), char),	\
			(char)({ signed char __x = (x); __x<0?-__x:__x; }), \
			((void)0)))))))
const void *
__v4l2_find_nearest_size_conditional(const void *array, size_t array_size,
				     size_t entry_size, size_t width_offset,
				     size_t height_offset, s32 width,
				     s32 height,
				     bool (*func)(const void *array,
						  size_t index,
						  const void *context),
				     const void *context)
{
	u32 error, min_error = U32_MAX;
	const void *best = NULL;
	size_t i;

	if (!array)
		return NULL;

	for (i = 0; i < array_size; i++, array += entry_size) {
		const u32 *entry_width = array + width_offset;
		const u32 *entry_height = array + height_offset;

		if (func && !func(array, i, context))
			continue;

		error = abs(*entry_width - width) + abs(*entry_height - height);
		if (error > min_error)
			continue;

		min_error = error;
		best = array;
		if (!error)
			break;
	}

	return best;
}
#define v4l2_find_nearest_size_conditional(array, array_size, width_field, \
					   height_field, width, height, \
					   func, context) \
	({								\
		BUILD_BUG_ON(sizeof((array)->width_field) != sizeof(u32) || \
			     sizeof((array)->height_field) != sizeof(u32)); \
		(typeof(&(array)[0]))__v4l2_find_nearest_size_conditional( \
			(array), array_size, sizeof(*(array)),		\
			offsetof(typeof(*(array)), width_field),	\
			offsetof(typeof(*(array)), height_field),	\
			width, height, func, context);			\
	})
#define v4l2_find_nearest_size(array, array_size, width_field,		\
			       height_field, width, height)		\
	v4l2_find_nearest_size_conditional(array, array_size, width_field, \
					   height_field, width, height, NULL, \
					   NULL)
bool v4l2_subdev_is_streaming(struct v4l2_subdev *sd)
{
	struct v4l2_subdev_state *state;

	if (!v4l2_subdev_has_op(sd, pad, enable_streams))
		return sd->s_stream_enabled;

	if (!(sd->flags & V4L2_SUBDEV_FL_STREAMS))
		return !!sd->enabled_pads;

	state = v4l2_subdev_get_locked_active_state(sd);

	for (unsigned int i = 0; i < state->stream_configs.num_configs; ++i) {
		const struct v4l2_subdev_stream_config *cfg;

		cfg = &state->stream_configs.configs[i];

		if (cfg->enabled)
			return true;
	}

	return false;
}
static inline struct imx132 *to_imx132(struct v4l2_subdev *sd)
{
	return container_of(sd, struct imx132, sd);
}
static int imx132_update_exposure_range(struct imx132 *imx132, int vblank)
{
	int max = imx132->mode->height + vblank - IMX132_EXPOSURE_MARGIN;

	return __v4l2_ctrl_modify_range(imx132->exposure,
					imx132->exposure->minimum, max,
					imx132->exposure->step,
					min(imx132->exposure->val, max));
}
static int imx132_set_ctrl(struct v4l2_ctrl *ctrl)
{
	struct imx132 *imx132 = container_of(ctrl->handler, struct imx132,
					     ctrl_handler);
	int ret = 0;

	if (ctrl->id == V4L2_CID_VBLANK) {
		ret = imx132_update_exposure_range(imx132, ctrl->val);
		if (ret)
			return ret;
	}

	if (!pm_runtime_get_if_in_use(imx132->dev))
		return 0;

	switch (ctrl->id) {
	case V4L2_CID_EXPOSURE:
		cci_write(imx132->regmap, IMX132_REG_EXPOSURE, ctrl->val, &ret);
		break;
	case V4L2_CID_ANALOGUE_GAIN:
		cci_write(imx132->regmap, IMX132_REG_ANALOG_GAIN, ctrl->val, &ret);
		break;
	case V4L2_CID_VBLANK:
		cci_write(imx132->regmap, IMX132_REG_FRAME_LENGTH,
			  imx132->mode->height + ctrl->val, &ret);
		break;
	case V4L2_CID_TEST_PATTERN:
		cci_write(imx132->regmap, IMX132_REG_TEST_PATTERN, ctrl->val, &ret);
		break;
	default:
		ret = -EINVAL;
		break;
	}

	pm_runtime_put(imx132->dev);

	return ret;
}
static void imx132_fill_format(struct v4l2_mbus_framefmt *fmt,
			       const struct imx132_mode *mode)
{
	fmt->width = mode->width;
	fmt->height = mode->height;
	fmt->code = MEDIA_BUS_FMT_SRGGB10_1X10;
	fmt->field = V4L2_FIELD_NONE;
	fmt->colorspace = V4L2_COLORSPACE_RAW;
	fmt->ycbcr_enc = V4L2_YCBCR_ENC_601;
	fmt->quantization = V4L2_QUANTIZATION_FULL_RANGE;
	fmt->xfer_func = V4L2_XFER_FUNC_NONE;
}
static int imx132_set_format(struct v4l2_subdev *sd,
			     const struct v4l2_subdev_client_info *ci,
			     struct v4l2_subdev_state *state,
			     struct v4l2_subdev_format *fmt)
{
	struct imx132 *imx132 = to_imx132(sd);
	const struct imx132_mode *mode;
	int vblank, ret;

	if (fmt->which == V4L2_SUBDEV_FORMAT_ACTIVE &&
	    v4l2_subdev_is_streaming(sd))
		return -EBUSY;

	mode = v4l2_find_nearest_size(imx132_modes, ARRAY_SIZE(imx132_modes),
				      width, height, fmt->format.width,
				      fmt->format.height);
	imx132_fill_format(&fmt->format, mode);
	*v4l2_subdev_state_get_format(state, 0) = fmt->format;

	if (fmt->which != V4L2_SUBDEV_FORMAT_ACTIVE)
		return 0;

	imx132->mode = mode;
	vblank = IMX132_FRAME_LENGTH_DEF - mode->height;
	ret = __v4l2_ctrl_modify_range(imx132->vblank, vblank,
				       IMX132_FRAME_LENGTH_MAX - mode->height,
				       1, vblank);
	if (ret)
		return ret;

	ret = __v4l2_ctrl_s_ctrl(imx132->vblank, vblank);
	if (ret)
		return ret;

	/* The vblank value may be unchanged while the height changed. */
	return imx132_update_exposure_range(imx132, imx132->vblank->val);
}
static int imx132_enable_streams(struct v4l2_subdev *sd,
				 struct v4l2_subdev_state *state, u32 pad,
				 u64 streams_mask)
{
	struct imx132 *imx132 = to_imx132(sd);
	int ret;

	ret = pm_runtime_resume_and_get(imx132->dev);
	if (ret)
		return ret;

	ret = cci_multi_reg_write(imx132->regmap, imx132_common_regs,
				  ARRAY_SIZE(imx132_common_regs), NULL);
	if (ret)
		goto err_put;

	ret = cci_multi_reg_write(imx132->regmap, imx132->mode->regs,
				  imx132->mode->num_regs, NULL);
	if (ret)
		goto err_put;

	ret = __v4l2_ctrl_handler_setup(&imx132->ctrl_handler);
	if (ret)
		goto err_put;

	ret = cci_write(imx132->regmap, IMX132_REG_MODE_SELECT,
			IMX132_MODE_STREAMING, NULL);
	if (ret)
		goto err_put;

	return 0;

err_put:
	pm_runtime_put(imx132->dev);
	return ret;
}
static int imx132_disable_streams(struct v4l2_subdev *sd,
				  struct v4l2_subdev_state *state, u32 pad,
				  u64 streams_mask)
{
	struct imx132 *imx132 = to_imx132(sd);
	int ret;

	ret = cci_write(imx132->regmap, IMX132_REG_MODE_SELECT,
			IMX132_MODE_STANDBY, NULL);
	pm_runtime_put(imx132->dev);

	return ret;
}
static int imx132_power_on(struct device *dev)
{
	struct v4l2_subdev *sd = dev_get_drvdata(dev);
	struct imx132 *imx132 = to_imx132(sd);
	int ret;

	ret = regulator_bulk_enable(ARRAY_SIZE(imx132->supplies),
				    imx132->supplies);
	if (ret)
		return ret;

	ret = clk_prepare_enable(imx132->xclk);
	if (ret) {
		regulator_bulk_disable(ARRAY_SIZE(imx132->supplies),
				       imx132->supplies);
		return ret;
	}

	usleep_range(1000, 1100);
	gpiod_set_value_cansleep(imx132->reset_gpio, 0);
	/* Wait for the sensor to leave reset before the first access. */
	usleep_range(10000, 11000);

	return 0;
}
static int imx132_power_off(struct device *dev)
{
	struct v4l2_subdev *sd = dev_get_drvdata(dev);
	struct imx132 *imx132 = to_imx132(sd);

	gpiod_set_value_cansleep(imx132->reset_gpio, 1);
	clk_disable_unprepare(imx132->xclk);
	regulator_bulk_disable(ARRAY_SIZE(imx132->supplies), imx132->supplies);

	return 0;
}
static void v4l2_subdev_collect_streams(struct v4l2_subdev *sd,
					struct v4l2_subdev_state *state,
					u32 pad, u64 streams_mask,
					u64 *found_streams,
					u64 *enabled_streams)
{
	if (!(sd->flags & V4L2_SUBDEV_FL_STREAMS)) {
		*found_streams = BIT_ULL(0);
		*enabled_streams =
			(sd->enabled_pads & BIT_ULL(pad)) ? BIT_ULL(0) : 0;
		dev_dbg(sd->dev,
			"collect_streams: sub-device \"%s\" does not support streams\n",
			sd->entity.name);
		return;
	}

	*found_streams = 0;
	*enabled_streams = 0;

	for (unsigned int i = 0; i < state->stream_configs.num_configs; ++i) {
		const struct v4l2_subdev_stream_config *cfg =
			&state->stream_configs.configs[i];

		if (cfg->pad != pad || !(streams_mask & BIT_ULL(cfg->stream)))
			continue;

		*found_streams |= BIT_ULL(cfg->stream);
		if (cfg->enabled)
			*enabled_streams |= BIT_ULL(cfg->stream);
	}

	dev_dbg(sd->dev,
		"collect_streams: \"%s\":%u: found %#llx enabled %#llx\n",
		sd->entity.name, pad, *found_streams, *enabled_streams);
}
static void v4l2_subdev_set_streams_enabled(struct v4l2_subdev *sd,
					    struct v4l2_subdev_state *state,
					    u32 pad, u64 streams_mask,
					    bool enabled)
{
	if (!(sd->flags & V4L2_SUBDEV_FL_STREAMS)) {
		if (enabled)
			sd->enabled_pads |= BIT_ULL(pad);
		else
			sd->enabled_pads &= ~BIT_ULL(pad);
		return;
	}

	for (unsigned int i = 0; i < state->stream_configs.num_configs; ++i) {
		struct v4l2_subdev_stream_config *cfg =
			&state->stream_configs.configs[i];

		if (cfg->pad == pad && (streams_mask & BIT_ULL(cfg->stream)))
			cfg->enabled = enabled;
	}
}
int v4l2_subdev_enable_streams(struct v4l2_subdev *sd, u32 pad,
			       u64 streams_mask)
{
	struct device *dev = sd->entity.graph_obj.mdev->dev;
	struct v4l2_subdev_state *state;
	bool already_streaming;
	u64 enabled_streams;
	u64 found_streams;
	bool use_s_stream;
	int ret;

	dev_dbg(dev, "enable streams \"%s\":%u/%#llx\n", sd->entity.name, pad,
		streams_mask);

	/* A few basic sanity checks first. */
	if (pad >= sd->entity.num_pads)
		return -EINVAL;

	if (!(sd->entity.pads[pad].flags & MEDIA_PAD_FL_SOURCE))
		return -EOPNOTSUPP;

	/*
	 * We use a 64-bit bitmask for tracking enabled pads, so only subdevices
	 * with 64 pads or less can be supported.
	 */
	if (pad >= sizeof(sd->enabled_pads) * BITS_PER_BYTE)
		return -EOPNOTSUPP;

	if (!streams_mask)
		return 0;

	/* Fallback on .s_stream() if .enable_streams() isn't available. */
	use_s_stream = !v4l2_subdev_has_op(sd, pad, enable_streams);

	if (!use_s_stream)
		state = v4l2_subdev_lock_and_get_active_state(sd);
	else
		state = NULL;

	/*
	 * Verify that the requested streams exist and that they are not
	 * already enabled.
	 */

	v4l2_subdev_collect_streams(sd, state, pad, streams_mask,
				    &found_streams, &enabled_streams);

	if (found_streams != streams_mask) {
		dev_dbg(dev, "streams 0x%llx not found on %s:%u\n",
			streams_mask & ~found_streams, sd->entity.name, pad);
		ret = -EINVAL;
		goto done;
	}

	if (enabled_streams) {
		dev_dbg(dev, "streams 0x%llx already enabled on %s:%u\n",
			enabled_streams, sd->entity.name, pad);
		ret = -EALREADY;
		goto done;
	}

	already_streaming = v4l2_subdev_is_streaming(sd);

	if (!use_s_stream) {
		/* Call the .enable_streams() operation. */
		ret = v4l2_subdev_call(sd, pad, enable_streams, state, pad,
				       streams_mask);
	} else {
		/* Start streaming when the first pad is enabled. */
		if (!already_streaming)
			ret = v4l2_subdev_call(sd, video, s_stream, 1);
		else
			ret = 0;
	}

	if (ret) {
		dev_dbg(dev, "enable streams %u:%#llx failed: %d\n", pad,
			streams_mask, ret);
		goto done;
	}

	/* Mark the streams as enabled. */
	v4l2_subdev_set_streams_enabled(sd, state, pad, streams_mask, true);

	/*
	 * TODO: When all the drivers have been changed to use
	 * v4l2_subdev_enable_streams() and v4l2_subdev_disable_streams(),
	 * instead of calling .s_stream() operation directly, we can remove
	 * the privacy LED handling from call_s_stream() and do it here
	 * for all cases.
	 */
	if (!use_s_stream && !already_streaming)
		v4l2_subdev_enable_privacy_led(sd);

done:
	if (!use_s_stream)
		v4l2_subdev_unlock_state(state);

	return ret;
}
int v4l2_subdev_disable_streams(struct v4l2_subdev *sd, u32 pad,
				u64 streams_mask)
{
	struct device *dev = sd->entity.graph_obj.mdev->dev;
	struct v4l2_subdev_state *state;
	u64 enabled_streams;
	u64 found_streams;
	bool use_s_stream;
	int ret;

	dev_dbg(dev, "disable streams \"%s\":%u/%#llx\n", sd->entity.name, pad,
		streams_mask);

	/* A few basic sanity checks first. */
	if (pad >= sd->entity.num_pads)
		return -EINVAL;

	if (!(sd->entity.pads[pad].flags & MEDIA_PAD_FL_SOURCE))
		return -EOPNOTSUPP;

	/*
	 * We use a 64-bit bitmask for tracking enabled pads, so only subdevices
	 * with 64 pads or less can be supported.
	 */
	if (pad >= sizeof(sd->enabled_pads) * BITS_PER_BYTE)
		return -EOPNOTSUPP;

	if (!streams_mask)
		return 0;

	/* Fallback on .s_stream() if .disable_streams() isn't available. */
	use_s_stream = !v4l2_subdev_has_op(sd, pad, disable_streams);

	if (!use_s_stream)
		state = v4l2_subdev_lock_and_get_active_state(sd);
	else
		state = NULL;

	/*
	 * Verify that the requested streams exist and that they are not
	 * already disabled.
	 */

	v4l2_subdev_collect_streams(sd, state, pad, streams_mask,
				    &found_streams, &enabled_streams);

	if (found_streams != streams_mask) {
		dev_dbg(dev, "streams 0x%llx not found on %s:%u\n",
			streams_mask & ~found_streams, sd->entity.name, pad);
		ret = -EINVAL;
		goto done;
	}

	if (enabled_streams != streams_mask) {
		dev_dbg(dev, "streams 0x%llx already disabled on %s:%u\n",
			streams_mask & ~enabled_streams, sd->entity.name, pad);
		ret = -EALREADY;
		goto done;
	}

	if (!use_s_stream) {
		/* Call the .disable_streams() operation. */
		ret = v4l2_subdev_call(sd, pad, disable_streams, state, pad,
				       streams_mask);
	} else {
		/* Stop streaming when the last streams are disabled. */

		if (!(sd->enabled_pads & ~BIT_ULL(pad)))
			ret = v4l2_subdev_call(sd, video, s_stream, 0);
		else
			ret = 0;
	}

	if (ret) {
		dev_dbg(dev, "disable streams %u:%#llx failed: %d\n", pad,
			streams_mask, ret);
		goto done;
	}

	v4l2_subdev_set_streams_enabled(sd, state, pad, streams_mask, false);

done:
	if (!use_s_stream) {
		if (!v4l2_subdev_is_streaming(sd))
			v4l2_subdev_disable_privacy_led(sd);

		v4l2_subdev_unlock_state(state);
	}

	return ret;
}

static unsigned cases,broken,stop_broken,format_broken;
#define CHECK(c) do {cases++;if(!(c))broken++;} while(0)
static struct imx132 s;
static struct device device;
static struct regmap map;
static struct clk clock;
static struct gpio_desc gpio;
static struct v4l2_subdev_state active;
static struct media_device mdev;
static struct v4l2_ctrl exposure,vblank;
static void setup(unsigned mode)
{
 memset(&s,0,sizeof(s));memset(&device,0,sizeof(device));memset(&map,0,sizeof(map));
 memset(&clock,0,sizeof(clock));memset(&gpio,0,sizeof(gpio));memset(&active,0,sizeof(active));
 s.dev=&device;s.regmap=&map;s.xclk=&clock;s.reset_gpio=&gpio;s.mode=&imx132_modes[mode];
 for(unsigned i=0;i<ARRAY_SIZE(imx132_supply_names);i++)s.supplies[i].supply=imx132_supply_names[i];
 map.dev=&device;device.driver_data=&s.sd;device.power.runtime_status=RPM_ACTIVE;
 static const struct v4l2_subdev_pad_ops pads={.enable_streams=imx132_enable_streams,.disable_streams=imx132_disable_streams};
 static const struct v4l2_subdev_ops ops={.pad=&pads};
 s.sd.dev=&device;s.sd.ops=&ops;s.sd.active=&active;s.pad.flags=MEDIA_PAD_FL_SOURCE;
 mdev.dev=&device;s.sd.entity.graph_obj.mdev=&mdev;s.sd.entity.num_pads=1;s.sd.entity.pads=&s.pad;s.sd.entity.name="synthetic-sensor";
 exposure=(struct v4l2_ctrl){.id=V4L2_CID_EXPOSURE,.val=IMX132_FRAME_LENGTH_DEF-10,.minimum=1,.maximum=0xffff,.step=1,.handler=&s.ctrl_handler};
 vblank=(struct v4l2_ctrl){.id=V4L2_CID_VBLANK,.val=IMX132_FRAME_LENGTH_DEF-s.mode->height,.handler=&s.ctrl_handler};
 s.exposure=&exposure;s.vblank=&vblank;s.ctrl_handler.exposure=&exposure;s.ctrl_handler.vblank=&vblank;
 imx132_fill_format(&active.format,s.mode);
 writes=fail_write_at=underflows=0;resume_error=setup_error=bulk_error=clock_error=0;
 power_refs=bulk_calls=clock_calls=range_updates=0;
}
static unsigned reg16(unsigned address) {return ((unsigned)map.bytes[address]<<8)|map.bytes[address+1];}
int main(void)
{
 for(unsigned m=0;m<ARRAY_SIZE(imx132_modes);m++) {
  setup(m);
  for(unsigned cycle=0;cycle<10;cycle++) {
   CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==0 && device.power.usage_count==1 && s.sd.enabled_pads==1);
   CHECK(reg16(0x034c)==s.mode->width && reg16(0x034e)==s.mode->height && map.bytes[0x0100]==1);
   CHECK(v4l2_subdev_disable_streams(&s.sd,0,1)==0 && !device.power.usage_count && !s.sd.enabled_pads && !underflows);
  }
  unsigned write_count=ARRAY_SIZE(imx132_common_regs)+s.mode->num_regs+1;
  for(unsigned fail=1;fail<=write_count;fail++) {
   setup(m);fail_write_at=fail;
   CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==-EIO && !device.power.usage_count && !s.sd.enabled_pads && !underflows && writes==fail);
  }
  setup(m);resume_error=-EIO;CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==-EIO && !device.power.usage_count && !writes && !s.sd.enabled_pads);
  setup(m);setup_error=-ERANGE;CHECK(v4l2_subdev_enable_streams(&s.sd,0,1)==-ERANGE && !device.power.usage_count && !s.sd.enabled_pads);
  for(unsigned repeat=1;repeat<=3;repeat+=2) {
   setup(m);assert(v4l2_subdev_enable_streams(&s.sd,0,1)==0);bool ok=true;
   for(unsigned attempt=0;attempt<repeat;attempt++) {
    fail_write_at=writes+1;
    int ret=v4l2_subdev_disable_streams(&s.sd,0,1);
    ok &= ret==-EIO && device.power.usage_count==1 && s.sd.enabled_pads==1 && !underflows;
   }
   fail_write_at=0;
   ok &= v4l2_subdev_disable_streams(&s.sd,0,1)==0 && !device.power.usage_count && !s.sd.enabled_pads && !underflows;
   cases++;if(!ok){broken++;stop_broken++;}
  }
  setup(m);assert(v4l2_subdev_enable_streams(&s.sd,0,1)==0);
  struct v4l2_subdev_state attempt={0};
  struct v4l2_subdev_format fmt={.which=V4L2_SUBDEV_FORMAT_TRY,.format={.width=imx132_modes[0].width,.height=imx132_modes[0].height}};
  const struct imx132_mode *saved=s.mode;unsigned before=writes;
  CHECK(imx132_set_format(&s.sd,NULL,&attempt,&fmt)==0 && s.mode==saved && writes==before && device.power.usage_count==1);
  assert(v4l2_subdev_disable_streams(&s.sd,0,1)==0);
  if(ARRAY_SIZE(imx132_modes)>1) {
   setup(m);assert(v4l2_subdev_enable_streams(&s.sd,0,1)==0);
   unsigned next=(m+1)%ARRAY_SIZE(imx132_modes);struct v4l2_mbus_framefmt old=active.format;unsigned width=reg16(0x034c);
   fmt=(struct v4l2_subdev_format){.which=V4L2_SUBDEV_FORMAT_ACTIVE,.format={.width=imx132_modes[next].width,.height=imx132_modes[next].height}};
   before=writes;active.locked=true;
   int ret=imx132_set_format(&s.sd,NULL,&active,&fmt);active.locked=false;
   bool ok=ret==-EBUSY && s.mode==&imx132_modes[m] && !memcmp(&old,&active.format,sizeof(old)) && writes==before && reg16(0x034c)==width;
   cases++;if(!ok){broken++;format_broken++;}
   assert(v4l2_subdev_disable_streams(&s.sd,0,1)==0);
  }
  setup(m);struct v4l2_ctrl ctrl={.handler=&s.ctrl_handler};
  const unsigned ids[]={V4L2_CID_EXPOSURE,V4L2_CID_ANALOGUE_GAIN,V4L2_CID_VBLANK,V4L2_CID_TEST_PATTERN};
  const unsigned addresses[]={0x0202,0x0205,0x0340,0x0600};
  for(unsigned i=0;i<4;i++) {
   ctrl.id=ids[i];ctrl.val=i==2?100:17;int saved_count=device.power.usage_count;
   CHECK(imx132_set_ctrl(&ctrl)==0 && device.power.usage_count==saved_count);
   CHECK(!writes); /* Suspended/not-in-use controls only update the cache. */
   device.power.usage_count=1;
   CHECK(imx132_set_ctrl(&ctrl)==0 && device.power.usage_count==1 && !underflows);
   unsigned value=i==2?s.mode->height+100:17;
   CHECK((i==1?map.bytes[addresses[i]]:reg16(addresses[i]))==value);
   writes=0;device.power.usage_count=0;
  }
  setup(m);CHECK(imx132_power_on(&device)==0 && power_refs==1 && clock.enabled && gpio.value==0);
  CHECK(imx132_power_off(&device)==0 && !power_refs && !clock.enabled && gpio.value==1);
  setup(m);bulk_error=-EIO;CHECK(imx132_power_on(&device)==-EIO && !power_refs && !clock_calls);
  setup(m);clock_error=-EIO;CHECK(imx132_power_on(&device)==-EIO && !power_refs && !clock.enabled);
 }
 setup(0);CHECK(v4l2_subdev_enable_streams(&s.sd,1,1)==-EINVAL && !writes);
 CHECK(v4l2_subdev_enable_streams(&s.sd,0,2)==-EINVAL && !writes);
 CHECK(v4l2_subdev_enable_streams(&s.sd,0,0)==0 && !writes);
 CHECK(v4l2_subdev_disable_streams(&s.sd,0,1)==-EALREADY && !underflows);
 printf("cases=%u broken=%u stop=%u format=%u\n",cases,broken,stop_broken,format_broken);
 return broken?1:0;
}
/* End of extracted fixture. */
