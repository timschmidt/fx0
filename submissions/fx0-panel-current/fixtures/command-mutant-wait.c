/*
 * Extracted Linux panel/core fixture. GPL-2.0-only combined work.
 * See NOTICE and LICENSE.GPL-2.0 for original notices and licensing.
 */
// SPDX-License-Identifier: GPL-2.0-or-later
/*
 * Copyright (C) 2013, NVIDIA Corporation.  All rights reserved.
 * Copyright (C) 2016 Laurent Pinchart <laurent.pinchart@ideasonboard.com>
 * Copyright (C) 2017 Broadcom
 */
// SPDX-License-Identifier: GPL-2.0-or-later
//
// core.c  --  Voltage/Current Regulator framework.
//
// Copyright 2007, 2008 Wolfson Microelectronics PLC.
// Copyright 2008 SlimLogic Ltd.
//
// Author: Liam Girdwood <lrg@slimlogic.co.uk>
/*
 * MIPI DSI Bus
 *
 * Copyright (C) 2012-2013, Samsung Electronics, Co., Ltd.
 * Andrzej Hajda <a.hajda@samsung.com>
 *
 * Permission is hereby granted, free of charge, to any person obtaining a
 * copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sub license, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice (including the
 * next paragraph) shall be included in all copies or substantial portions
 * of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL
 * THE COPYRIGHT HOLDERS, AUTHORS AND/OR ITS SUPPLIERS BE LIABLE FOR ANY CLAIM,
 * DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
 * OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE
 * USE OR OTHER DEALINGS IN THE SOFTWARE.
 */
/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * MIPI DSI Bus
 *
 * Copyright (C) 2012-2013, Samsung Electronics, Co., Ltd.
 * Andrzej Hajda <a.hajda@samsung.com>
 */
/* SPDX-License-Identifier: GPL-2.0-only */
/*
 * Defines for Mobile Industry Processor Interface (MIPI(R))
 * Display Working Group standards: DSI, DCS, DBI, DPI
 *
 * Copyright (C) 2010 Guennadi Liakhovetski <g.liakhovetski@gmx.de>
 * Copyright (C) 2006 Nokia Corporation
 * Author: Imre Deak <imre.deak@nokia.com>
 */
// SPDX-License-Identifier: GPL-2.0-only
/*
 * LG Fx0 JDI in-cell panel, production board revisions.
 * Initialization data and power sequencing derived from the LG madai kernel.
 * Copyright (c) 2013, Code Aurora Forum. All rights reserved.
 * Copyright (c) 2012-2014, The Linux Foundation. All rights reserved.
 * Copyright (c) 2026 Timothy Schmidt
 */

// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
typedef unsigned char u8;
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define MIPI_DSI_MODE_LPM 1
#define dev_err(dev,...) ((void)(dev))
struct device {int unused;};
struct drm_panel {int unused;};
struct mipi_dsi_device {struct device dev;unsigned long mode_flags;};
struct mipi_dsi_multi_context {struct mipi_dsi_device *dsi;int accum_err;};
struct lg_fx0 {struct drm_panel panel;struct mipi_dsi_device *dsi;};
static unsigned attempted, fail_at;
static ssize_t transfer(struct mipi_dsi_device *dsi,char family,const void *data,size_t len)
{
 assert(!!(dsi->mode_flags & MIPI_DSI_MODE_LPM)==(family!='X'));
 printf("%c ",family=='X'?'D':family);
 const u8 *p=data;for(size_t i=0;i<len;i++)printf("%02x",p[i]);puts("");
 attempted++;return attempted==fail_at?-EIO:(ssize_t)len;
}
static ssize_t mipi_dsi_generic_write(struct mipi_dsi_device *dsi,const void *p,size_t n)
{return transfer(dsi,'G',p,n);}
static ssize_t mipi_dsi_dcs_write_buffer(struct mipi_dsi_device *dsi,const void *p,size_t n)
{return transfer(dsi,'D',p,n);}
static ssize_t mipi_dsi_dcs_write(struct mipi_dsi_device *dsi,u8 cmd,const void *p,size_t n)
{assert(!n && !p);return transfer(dsi,(dsi->mode_flags & MIPI_DSI_MODE_LPM)?'D':'X',&cmd,1);}
static void msleep(unsigned delay) {printf("W %u\n",delay);}

#define MIPI_DCS_ENTER_SLEEP_MODE 0x10
#define MIPI_DCS_EXIT_SLEEP_MODE 0x11
#define MIPI_DCS_SET_DISPLAY_OFF 0x28
#define MIPI_DCS_SET_DISPLAY_ON 0x29
#define mipi_dsi_generic_write_seq_multi(ctx, seq...)                \
	do {                                                         \
		static const u8 d[] = { seq };                       \
		mipi_dsi_generic_write_multi(ctx, d, ARRAY_SIZE(d)); \
	} while (0)
#define mipi_dsi_dcs_write_seq_multi(ctx, cmd, seq...)                  \
	do {                                                            \
		static const u8 d[] = { cmd, seq };                     \
		mipi_dsi_dcs_write_buffer_multi(ctx, d, ARRAY_SIZE(d)); \
	} while (0)
#define mipi_dsi_msleep(ctx, delay)	\
	do {				\
		if (!(ctx)->accum_err)	\
			msleep(delay);	\
	} while (0)
int mipi_dsi_dcs_enter_sleep_mode(struct mipi_dsi_device *dsi)
{
	ssize_t err;

	err = mipi_dsi_dcs_write(dsi, MIPI_DCS_ENTER_SLEEP_MODE, NULL, 0);
	if (err < 0)
		return err;

	return 0;
}
int mipi_dsi_dcs_exit_sleep_mode(struct mipi_dsi_device *dsi)
{
	ssize_t err;

	err = mipi_dsi_dcs_write(dsi, MIPI_DCS_EXIT_SLEEP_MODE, NULL, 0);
	if (err < 0)
		return err;

	return 0;
}
int mipi_dsi_dcs_set_display_off(struct mipi_dsi_device *dsi)
{
	ssize_t err;

	err = mipi_dsi_dcs_write(dsi, MIPI_DCS_SET_DISPLAY_OFF, NULL, 0);
	if (err < 0)
		return err;

	return 0;
}
int mipi_dsi_dcs_set_display_on(struct mipi_dsi_device *dsi)
{
	ssize_t err;

	err = mipi_dsi_dcs_write(dsi, MIPI_DCS_SET_DISPLAY_ON, NULL, 0);
	if (err < 0)
		return err;

	return 0;
}
void mipi_dsi_generic_write_multi(struct mipi_dsi_multi_context *ctx,
				  const void *payload, size_t size)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	struct device *dev = &dsi->dev;
	ssize_t ret;

	if (ctx->accum_err)
		return;

	ret = mipi_dsi_generic_write(dsi, payload, size);
	if (ret < 0) {
		ctx->accum_err = ret;
		dev_err(dev, "sending generic data %*ph failed: %d\n",
			(int)size, payload, ctx->accum_err);
	}
}
void mipi_dsi_dcs_write_buffer_multi(struct mipi_dsi_multi_context *ctx,
				     const void *data, size_t len)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	struct device *dev = &dsi->dev;
	ssize_t ret;

	if (ctx->accum_err)
		return;

	ret = mipi_dsi_dcs_write_buffer(dsi, data, len);
	if (ret < 0) {
		ctx->accum_err = ret;
		dev_err(dev, "sending dcs data %*ph failed: %d\n",
			(int)len, data, ctx->accum_err);
	}
}
void mipi_dsi_dcs_enter_sleep_mode_multi(struct mipi_dsi_multi_context *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	struct device *dev = &dsi->dev;
	ssize_t ret;

	if (ctx->accum_err)
		return;

	ret = mipi_dsi_dcs_enter_sleep_mode(dsi);
	if (ret < 0) {
		ctx->accum_err = ret;
		dev_err(dev, "sending DCS ENTER_SLEEP_MODE failed: %d\n",
			ctx->accum_err);
	}
}
void mipi_dsi_dcs_exit_sleep_mode_multi(struct mipi_dsi_multi_context *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	struct device *dev = &dsi->dev;
	ssize_t ret;

	if (ctx->accum_err)
		return;

	ret = mipi_dsi_dcs_exit_sleep_mode(dsi);
	if (ret < 0) {
		ctx->accum_err = ret;
		dev_err(dev, "sending DCS EXIT_SLEEP_MODE failed: %d\n",
			ctx->accum_err);
	}
}
void mipi_dsi_dcs_set_display_off_multi(struct mipi_dsi_multi_context *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	struct device *dev = &dsi->dev;
	ssize_t ret;

	if (ctx->accum_err)
		return;

	ret = mipi_dsi_dcs_set_display_off(dsi);
	if (ret < 0) {
		ctx->accum_err = ret;
		dev_err(dev, "sending DCS SET_DISPLAY_OFF failed: %d\n",
			ctx->accum_err);
	}
}
void mipi_dsi_dcs_set_display_on_multi(struct mipi_dsi_multi_context *ctx)
{
	struct mipi_dsi_device *dsi = ctx->dsi;
	struct device *dev = &dsi->dev;
	ssize_t ret;

	if (ctx->accum_err)
		return;

	ret = mipi_dsi_dcs_set_display_on(dsi);
	if (ret < 0) {
		ctx->accum_err = ret;
		dev_err(dev, "sending DCS SET_DISPLAY_ON failed: %d\n",
			ctx->accum_err);
	}
}
static struct lg_fx0 *to_lg_fx0(struct drm_panel *p) {return container_of(p,struct lg_fx0,panel);}
static int lg_fx0_on(struct lg_fx0 *priv)
{
	struct mipi_dsi_multi_context ctx = { .dsi = priv->dsi };

	priv->dsi->mode_flags |= MIPI_DSI_MODE_LPM;

	/* Production revisions use the stock touch-countermeasure sequence. */
	mipi_dsi_dcs_write_seq_multi(&ctx, 0x51, 0xff);
	mipi_dsi_dcs_write_seq_multi(&ctx, 0x53, 0x0c);
	mipi_dsi_dcs_write_seq_multi(&ctx, 0x55, 0x00);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xb0, 0x04);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xec, 0x29, 0x00, 0x2c, 0x2b, 0x01, 0x00, 0x00, 0x00,
					 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x07,
					 0x09, 0x00);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xee, 0x1c, 0x02, 0x02, 0x03, 0x00, 0x10, 0x00, 0x02,
					 0x00, 0x00, 0x00, 0x00, 0x00, 0x03);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xc1, 0x40, 0x61, 0x01);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xc7, 0x00, 0x0a, 0x16, 0x20, 0x2c, 0x39, 0x43, 0x52,
					 0x36, 0x3e, 0x4b, 0x58, 0x5a, 0x5f, 0x67, 0x00, 0x0a,
					 0x16, 0x20, 0x2c, 0x39, 0x43, 0x52, 0x36, 0x3e, 0x4b,
					 0x58, 0x5a, 0x5f, 0x67);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xc8, 0x00, 0x00, 0x00, 0x00, 0x00, 0xfc, 0x00, 0x00,
					 0x00, 0x00, 0x00, 0xfc, 0x00, 0x00, 0x00, 0x00, 0x00,
					 0xfc, 0x00);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xd6, 0x01);
	mipi_dsi_dcs_write_seq_multi(&ctx, 0x36, 0x00);
	mipi_dsi_generic_write_seq_multi(&ctx, 0xca, 0x01, 0x70, 0x9a, 0x95, 0xa2, 0x98, 0x95, 0x8f,
					 0x3f, 0x3f, 0x80, 0x80, 0x08, 0x80, 0x08, 0x3f, 0x08,
					 0x90, 0x0c, 0x0c, 0x0a, 0x06, 0x04, 0x04, 0x00, 0xc8,
					 0x10, 0x10, 0x3f, 0x3f, 0x3f, 0x3f);
	/* The production firmware sends display-on before sleep-out. */
	mipi_dsi_dcs_set_display_on_multi(&ctx);
	mipi_dsi_dcs_exit_sleep_mode_multi(&ctx);
	mipi_dsi_msleep(&ctx, 119);

	return ctx.accum_err;
}
static int lg_fx0_disable(struct drm_panel *panel)
{
	struct lg_fx0 *priv = to_lg_fx0(panel);
	struct mipi_dsi_multi_context ctx = { .dsi = priv->dsi };

	priv->dsi->mode_flags &= ~MIPI_DSI_MODE_LPM;

	mipi_dsi_dcs_set_display_off_multi(&ctx);
	mipi_dsi_msleep(&ctx, 20);
	mipi_dsi_dcs_enter_sleep_mode_multi(&ctx);
	mipi_dsi_msleep(&ctx, 80);

	return ctx.accum_err;
}
int main(int argc,char **argv) {
 assert(argc==3);bool off=atoi(argv[1]);fail_at=atoi(argv[2]);
 struct mipi_dsi_device dsi={.mode_flags=off?MIPI_DSI_MODE_LPM:0};
 struct lg_fx0 p={.dsi=&dsi};
 int ret=off?lg_fx0_disable(&p.panel):lg_fx0_on(&p);
 assert(!!(dsi.mode_flags & MIPI_DSI_MODE_LPM)==!off);
 printf("R %d\n",ret);return 0;
}

/* End of extracted fixture. */
