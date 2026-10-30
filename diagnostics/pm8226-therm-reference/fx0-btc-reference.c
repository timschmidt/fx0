// SPDX-License-Identifier: GPL-2.0-only
/* Fx0-only observation and bounded stock thermistor-reference mode comparison. */
#include <linux/debugfs.h>
#include <linux/device.h>
#include <linux/err.h>
#include <linux/errno.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/seq_file.h>

#define BAT_THERM_REF 0x124a
#define BAT_THERM_REF_MASK 0xc0

static bool force_on;
module_param(force_on, bool, 0400);
MODULE_PARM_DESC(force_on, "Force stock awake reference mode; restore original mode on unload");

static struct platform_device *iadc;
static struct regmap *map;
static struct dentry *directory;
static unsigned int original;
static bool changed;

static int set_reference(unsigned int mode)
{
	unsigned int value;
	int ret;

	if (mode & ~BAT_THERM_REF_MASK)
		return -EINVAL;
	ret = regmap_update_bits(map, BAT_THERM_REF, BAT_THERM_REF_MASK, mode);
	if (ret)
		return ret;
	ret = regmap_read(map, BAT_THERM_REF, &value);
	if (ret)
		return ret;
	return (value & BAT_THERM_REF_MASK) == mode ? 0 : -EIO;
}

static int restore_reference(void)
{
	int ret = 0, attempt;

	if (!changed)
		return 0;
	for (attempt = 0; attempt < 2; attempt++) {
		ret = set_reference(original & BAT_THERM_REF_MASK);
		if (!ret) {
			changed = false;
			return 0;
		}
	}
	return ret;
}

static int fx0_btc_show(struct seq_file *seq, void *unused)
{
	static const unsigned int registers[] = {
		0x1010, 0x1049, 0x1209, 0x1210, 0x1249, BAT_THERM_REF,
		0x3140, 0x3146, 0x3148, 0x3150, 0x3151, 0x315a, 0x315b,
	};
	unsigned int value;
	int i, ret;

	seq_printf(seq, "original_reference_mode %02x\n", original & BAT_THERM_REF_MASK);
	seq_printf(seq, "force_on %u\n", force_on);
	for (i = 0; i < ARRAY_SIZE(registers); i++) {
		ret = regmap_read(map, registers[i], &value);
		if (ret)
			return ret;
		seq_printf(seq, "%04x %02x\n", registers[i], value);
	}
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(fx0_btc);

static int __init fx0_btc_init(void)
{
	struct device_node *node;
	struct dentry *file;
	u8 identity[6];
	int ret, rollback;

	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;
	node = of_find_compatible_node(NULL, NULL, "qcom,pm8226-iadc");
	if (!node)
		return -ENODEV;
	iadc = of_find_device_by_node(node);
	of_node_put(node);
	if (!iadc)
		return -ENODEV;
	map = dev_get_regmap(iadc->dev.parent, NULL);
	if (!map) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_bulk_read(map, 0x4000, identity, sizeof(identity));
	if (ret)
		goto put;
	if (identity[4] != 0x0d || identity[5] != 1) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_read(map, BAT_THERM_REF, &original);
	if (ret)
		goto put;
	if (force_on) {
		/* Restore even when an I/O failure follows an effective write. */
		changed = true;
		ret = set_reference(BAT_THERM_REF_MASK);
		if (ret)
			goto restore;
	}
	directory = debugfs_create_dir("fx0-btc-reference", NULL);
	if (IS_ERR_OR_NULL(directory)) {
		ret = directory ? PTR_ERR(directory) : -ENOMEM;
		goto restore;
	}
	file = debugfs_create_file("registers", 0400, directory, NULL, &fx0_btc_fops);
	if (IS_ERR_OR_NULL(file)) {
		ret = file ? PTR_ERR(file) : -ENOMEM;
		debugfs_remove_recursive(directory);
		goto restore;
	}
	return 0;
restore:
	rollback = restore_reference();
	if (rollback) {
		pr_err("fx0-btc-reference: reference rollback failed: %d\n", rollback);
		ret = rollback;
	}
put:
	put_device(&iadc->dev);
	return ret;
}

static void __exit fx0_btc_exit(void)
{
	int ret;

	debugfs_remove_recursive(directory);
	ret = restore_reference();
	if (ret)
		pr_err("fx0-btc-reference: reference restoration failed: %d\n", ret);
	put_device(&iadc->dev);
}

module_init(fx0_btc_init);
module_exit(fx0_btc_exit);
MODULE_DESCRIPTION("Fx0 stock battery-thermistor reference comparison");
MODULE_LICENSE("GPL");
