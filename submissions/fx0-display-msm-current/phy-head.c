// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic MMIO/timing services for actual DSI PHY source functions. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "dsi_phy_28nm.xml.h"
typedef uint32_t u32;
#define BIT(n) (1U << (n))
#define __iomem
#define DBG(...) do {} while (0)
#define DRM_DEV_ERROR(d, ...) ((void)(d))
enum { DSI_0, DSI_1 };
enum { MSM_DSI_PHY_STANDALONE, MSM_DSI_PHY_MASTER, MSM_DSI_PHY_SLAVE };
struct device { int unused; };
struct platform_device { struct device dev; };
struct msm_dsi_phy_cfg { unsigned long quirks; };
struct msm_dsi_dphy_timing {
	u32 clk_zero, clk_trail, clk_prepare, hs_exit, hs_zero, hs_prepare;
	u32 hs_trail, hs_rqst, ta_go, ta_sure, ta_get;
};
struct msm_dsi_phy_clk_request { unsigned long bitclk_rate, escclk_rate; };
struct msm_dsi_phy {
	void *base, *reg_base;
	struct platform_device *pdev;
	const struct msm_dsi_phy_cfg *cfg;
	struct msm_dsi_dphy_timing timing;
	bool regulator_ldo_mode;
	unsigned int id, usecase;
};
struct write { u32 offset, value; };
static u32 phy_regs[1024], reg_regs[1024];
static struct write trace[256];
static unsigned int ntrace;
static bool timing_failure, large_zero;
static int msm_dsi_dphy_timing_calc(struct msm_dsi_dphy_timing *t,
	struct msm_dsi_phy_clk_request *request)
{
	(void)request;
	*t = (struct msm_dsi_dphy_timing){large_zero ? 0x102 : 0x22, 3, 4,
		5, 6, 7, 8, 9, 2, 1, 3};
	return timing_failure ? -EINVAL : 0;
}
static void writel(u32 value, void *address)
{
	uintptr_t a = (uintptr_t)address;
	u32 offset;
	if (a >= (uintptr_t)phy_regs && a + 4 <= (uintptr_t)(phy_regs + 1024))
		offset = a - (uintptr_t)phy_regs;
	else {
		assert(a >= (uintptr_t)reg_regs && a + 4 <= (uintptr_t)(reg_regs + 1024));
		offset = 0x1000 + a - (uintptr_t)reg_regs;
	}
	assert(ntrace < 256);
	trace[ntrace++] = (struct write){offset, value};
	memcpy(address, &value, 4);
}
static u32 readl(void *address)
{
	u32 value;
	memcpy(&value, address, 4);
	return value;
}
#define wmb() do { assert(ntrace < 256); trace[ntrace++] = (struct write){0xffffffff, 0}; } while (0)
