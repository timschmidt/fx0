// SPDX-License-Identifier: GPL-2.0-only
/* Bounded PM8226 BMS1 observation; no register writes or driver binding. */
#include <linux/device.h>
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>

struct bms_window {
	unsigned int reg;
	unsigned int bytes;
};

static const struct bms_window windows[] = {
	{ 0x1010, 1 }, /* Charger real-time status */
	{ 0x1209, 1 }, /* Battery-temperature comparator status */
	{ 0x1210, 1 }, /* Battery-interface status, including BATFET */
	{ 0x4008, 1 }, /* BMS1_STATUS1 */
	{ 0x4040, 1 }, /* BMS1_MODE_CTL */
	{ 0x4042, 1 }, /* BMS1_CC_DATA_CTL */
	{ 0x4043, 1 }, /* BMS1_CC_CLEAR_CTL: readback alone is not pulse proof */
	{ 0x4044, 1 }, /* BMS1_TOL_CTL */
	{ 0x4048, 5 }, /* OCV use limits and control */
	{ 0x405a, 1 }, /* S1 sample delay */
	{ 0x4061, 1 }, /* S2 sample averaging */
	{ 0x4080, 4 }, /* OCV/VSENSE for resistance */
	{ 0x408a, 5 }, /* CC: not held, not an atomic observation */
	{ 0x4090, 2 }, /* Last good OCV */
	{ 0x4094, 2 }, /* VSENSE at power-on */
	{ 0x4098, 2 }, /* Average VSENSE */
	{ 0x409e, 2 }, /* Average VBAT */
	{ 0x40a8, 5 }, /* Shadow CC: also not atomic */
	{ 0x3800, 6 }, /* BMS IADC companion identity */
	{ 0x3848, 2 }, /* BMS IADC channel and sense selection */
	{ 0x385b, 1 }, /* BMS IADC averaging enable */
};

static int __init fx0_bms_readonly_init(void)
{
	struct device_node *node;
	struct platform_device *pdev;
	struct regmap *map;
	u8 data[6];
	int i, ret;

	node = of_find_compatible_node(NULL, NULL, "qcom,pm8226-iadc");
	if (!node)
		return -ENODEV;
	pdev = of_find_device_by_node(node);
	of_node_put(node);
	if (!pdev)
		return -ENODEV;
	map = dev_get_regmap(pdev->dev.parent, NULL);
	if (!map) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_bulk_read(map, 0x4000, data, sizeof(data));
	if (ret)
		goto put;
	/* This is the non-VM BMS1 peripheral, not the PM8916 VM BMS. */
	if (data[4] != 0x0d || data[5] != 0x01) {
		ret = -ENODEV;
		goto put;
	}
	pr_info("fx0-bms-readonly: 4000 %*ph\n", (int)sizeof(data), data);
	for (i = 0; i < ARRAY_SIZE(windows); i++) {
		ret = regmap_bulk_read(map, windows[i].reg, data,
				       windows[i].bytes);
		if (ret)
			goto put;
		pr_info("fx0-bms-readonly: %04x %*ph\n", windows[i].reg,
			(int)windows[i].bytes, data);
	}
put:
	put_device(&pdev->dev);
	return ret;
}

static void __exit fx0_bms_readonly_exit(void)
{
}

module_init(fx0_bms_readonly_init);
module_exit(fx0_bms_readonly_exit);
MODULE_DESCRIPTION("Bounded read-only Fx0 PM8226 BMS1 observation");
MODULE_LICENSE("GPL");
