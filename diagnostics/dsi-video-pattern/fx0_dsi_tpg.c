// SPDX-License-Identifier: GPL-2.0-only
/*
 * Temporary test based on mdss_dsi_video_test_pattern() in LG's madai kernel.
 * Copyright (c) 2012-2014, The Linux Foundation. All rights reserved.
 * Copyright (c) 2026 Timothy Schmidt
 */
#include <linux/delay.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/pm_runtime.h>
#include <linux/workqueue.h>
#include <drm/drm_mipi_dsi.h>

/* Physical offsets include the MSM8226 host's four-byte register shift. */
#define HOST_CTRL 0x004
#define TPG_CTRL 0x15c
#define TPG_VALUE 0x164
#define TPG_TRIGGER 0x180
#define TPG_VIDEO_FIXED 0x21

static bool apply;
module_param(apply, bool, 0400);
static unsigned int color = 0xff0000;
module_param(color, uint, 0400);
static unsigned int seconds = 60;
module_param(seconds, uint, 0400);
static struct mipi_dsi_device *panel;
static struct device *host_device;
static struct module *host_module;
static void __iomem *registers;
static u32 saved_control, saved_value;
static unsigned long deadline;
static bool held, enabled;
static struct delayed_work tick;

static void restore(void)
{
	if (enabled) {
		writel(saved_control, registers + TPG_CTRL);
		writel(saved_value, registers + TPG_VALUE);
		readl(registers + TPG_CTRL);
		enabled = false;
		pr_info("Fx0 DSI TPG restored previous generator registers\n");
	}
	if (held) {
		pm_runtime_put(host_device);
		held = false;
	}
}

static void trigger(struct work_struct *work)
{
	if (time_after_eq(jiffies, deadline) ||
	    (readl(registers + HOST_CTRL) & 3) != 3) {
		restore();
		return;
	}
	writel(1, registers + TPG_TRIGGER);
	schedule_delayed_work(&tick, msecs_to_jiffies(20));
}

static int __init tpg_init(void)
{
	struct resource resource;
	struct device_node *node;
	u32 version, control;
	int ret;

	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;
	if (!seconds || seconds > 120 || color > 0xffffff)
		return -EINVAL;
	node = of_find_compatible_node(NULL, NULL, "lg,fx0-panel");
	if (!node)
		return -ENODEV;
	panel = of_find_mipi_dsi_device_by_node(node);
	of_node_put(node);
	if (!panel)
		return -ENODEV;
	host_device = panel->host->dev;
	device_lock(host_device);
	if (!host_device->driver || !try_module_get(host_device->driver->owner)) {
		device_unlock(host_device);
		ret = -ENODEV;
		goto put_panel;
	}
	host_module = host_device->driver->owner;
	device_unlock(host_device);
	ret = of_address_to_resource(host_device->of_node, 0, &resource);
	if (ret)
		goto put_host_module;
	if (resource.start != 0xfd922800 || resource_size(&resource) < 0x184) {
		ret = -ENODEV;
		goto put_host_module;
	}
	/* Refuse to wake inactive hardware or run before an active video mode. */
	ret = pm_runtime_get_if_in_use(host_device);
	if (ret <= 0) {
		ret = ret < 0 ? ret : -EBUSY;
		goto put_host_module;
	}
	held = true;
	registers = ioremap(resource.start, 0x184);
	if (!registers) {
		ret = -ENOMEM;
		goto release;
	}
	version = readl(registers);
	control = readl(registers + HOST_CTRL);
	if (version != 0x10000002 || (control & 3) != 3) {
		ret = -EBUSY;
		goto release;
	}
	saved_control = readl(registers + TPG_CTRL);
	saved_value = readl(registers + TPG_VALUE);
	if (saved_control) {
		ret = -EBUSY;
		goto release;
	}
	pr_info("Fx0 DSI TPG preflight: version=%08x host=%08x generator=%08x apply=%d\n",
		version, control, saved_control, apply);
	INIT_DELAYED_WORK(&tick, trigger);
	if (apply) {
		writel(color, registers + TPG_VALUE);
		writel(TPG_VIDEO_FIXED, registers + TPG_CTRL);
		readl(registers + TPG_CTRL);
		enabled = true;
		deadline = jiffies + seconds * HZ;
		schedule_delayed_work(&tick, 0);
		pr_info("Fx0 DSI TPG active: color=%06x timeout=%u seconds\n",
			color, seconds);
	}
	return 0;
release:
	restore();
	if (registers)
		iounmap(registers);
put_host_module:
	module_put(host_module);
put_panel:
	put_device(&panel->dev);
	panel = NULL;
	return ret;
}

static void __exit tpg_exit(void)
{
	cancel_delayed_work_sync(&tick);
	restore();
	iounmap(registers);
	module_put(host_module);
	put_device(&panel->dev);
}
module_init(tpg_init);
module_exit(tpg_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary guarded Fx0 DSI video pattern isolation test");
