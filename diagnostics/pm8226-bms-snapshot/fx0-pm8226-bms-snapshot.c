// SPDX-License-Identifier: GPL-2.0-only
/* Fx0 BMS1 output latching diagnostic; no counter reset or charger writes. */
#include <linux/bitops.h>
#include <linux/debugfs.h>
#include <linux/device.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/seq_file.h>
#include <linux/unaligned.h>

#define BMS_CC_DATA_CTL	0x4042
#define BMS_HOLD_OUTPUT	BIT(0)

struct bms_outputs {
	u8 cc[5];
	u8 shadow[5];
	u8 ocv[2];
	u8 vbat[2];
	u8 vsense[2];
};

static struct platform_device *provider;
static struct regmap *bms_map;
static struct dentry *debug_dir;
static DEFINE_MUTEX(snapshot_lock);

/* BEGIN TESTED SNAPSHOT HELPERS */
static s64 bms_decode_cc(const u8 *data)
{
	u64 raw = get_unaligned_le32(data) | ((u64)data[4] << 32);

	return sign_extend64(raw & GENMASK_ULL(35, 0), 35);
}

static int bms_read_outputs(struct regmap *map, struct bms_outputs *out)
{
	int ret;

	ret = regmap_bulk_read(map, 0x408a, out->cc, sizeof(out->cc));
	if (ret)
		return ret;
	ret = regmap_bulk_read(map, 0x40a8, out->shadow, sizeof(out->shadow));
	if (ret)
		return ret;
	ret = regmap_bulk_read(map, 0x4090, out->ocv, sizeof(out->ocv));
	if (ret)
		return ret;
	ret = regmap_bulk_read(map, 0x409e, out->vbat, sizeof(out->vbat));
	if (ret)
		return ret;
	return regmap_bulk_read(map, 0x4098, out->vsense, sizeof(out->vsense));
}

static int bms_restore_output(struct regmap *map, unsigned int before,
			      unsigned int *after)
{
	int attempt, ret = -EIO;

	/* Retry once if a transient bus failure obscures the release. */
	for (attempt = 0; attempt < 2; attempt++) {
		ret = regmap_update_bits(map, BMS_CC_DATA_CTL, BMS_HOLD_OUTPUT,
					 before & BMS_HOLD_OUTPUT);
		if (ret)
			continue;
		ret = regmap_read(map, BMS_CC_DATA_CTL, after);
		if (ret)
			continue;
		if (!((*after ^ before) & BMS_HOLD_OUTPUT))
			return 0;
		ret = -EIO;
	}
	return ret;
}

static int bms_take_snapshot(struct regmap *map, struct bms_outputs *out,
			     unsigned int *before, unsigned int *after)
{
	struct bms_outputs verify;
	unsigned int held;
	int ret, release_ret;

	ret = regmap_read(map, BMS_CC_DATA_CTL, before);
	if (ret)
		return ret;
	/* An existing hold belongs to somebody else; do not release it. */
	if (*before & BMS_HOLD_OUTPUT)
		return -EBUSY;
	ret = regmap_update_bits(map, BMS_CC_DATA_CTL, BMS_HOLD_OUTPUT,
				 BMS_HOLD_OUTPUT);
	if (ret)
		goto restore;
	ret = regmap_read(map, BMS_CC_DATA_CTL, &held);
	if (ret)
		goto restore;
	if (!(held & BMS_HOLD_OUTPUT)) {
		ret = -EIO;
		goto restore;
	}
	ret = bms_read_outputs(map, out);
	if (ret)
		goto restore;
	ret = bms_read_outputs(map, &verify);
	if (!ret && memcmp(out, &verify, sizeof(*out)))
		ret = -EIO;
restore:
	/* A write may have reached hardware even if the bus reports an error. */
	release_ret = bms_restore_output(map, *before, after);
	return release_ret ? release_ret : ret;
}
/* END TESTED SNAPSHOT HELPERS */

static int fx0_bms_show(struct seq_file *seq, void *unused)
{
	struct bms_outputs data;
	unsigned int before = 0, after = 0;
	u64 started, finished;
	int ret;

	mutex_lock(&snapshot_lock);
	started = ktime_get_boottime_ns();
	ret = bms_take_snapshot(bms_map, &data, &before, &after);
	finished = ktime_get_boottime_ns();
	mutex_unlock(&snapshot_lock);
	if (ret)
		return ret;
	seq_printf(seq, "{\"boottime_ns\":%llu,\"capture_ns\":%llu,",
		   finished, finished - started);
	seq_printf(seq, "\"control_before\":%u,\"control_after\":%u,", before, after);
	seq_printf(seq, "\"cc_signed\":%lld,\"shadow_signed\":%lld,",
		   bms_decode_cc(data.cc), bms_decode_cc(data.shadow));
	seq_printf(seq, "\"ocv_raw\":%u,\"vbat_raw\":%u,\"vsense_signed\":%d}\n",
		   get_unaligned_le16(data.ocv), get_unaligned_le16(data.vbat),
		   (s16)get_unaligned_le16(data.vsense));
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(fx0_bms);

static int fx0_bms_control_show(struct seq_file *seq, void *unused)
{
	unsigned int control;
	int ret;

	mutex_lock(&snapshot_lock);
	ret = regmap_read(bms_map, BMS_CC_DATA_CTL, &control);
	mutex_unlock(&snapshot_lock);
	if (ret)
		return ret;
	seq_printf(seq, "%u\n", control);
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(fx0_bms_control);

static int fx0_bms_configuration_show(struct seq_file *seq, void *unused)
{
	static const struct {
		u16 address;
		u8 bytes;
	} windows[] = {
		{ 0x4040, 1 }, { 0x3848, 2 }, { 0x385b, 1 },
		{ 0x36f2, 4 }, { 0x38f2, 4 }, { 0x1249, 1 },
	};
	u8 data[4];
	int i, j, ret = 0;

	mutex_lock(&snapshot_lock);
	seq_putc(seq, '{');
	for (i = 0; i < ARRAY_SIZE(windows); i++) {
		ret = regmap_bulk_read(bms_map, windows[i].address, data,
				       windows[i].bytes);
		if (ret)
			break;
		seq_printf(seq, "%s\"0x%04x\":[", i ? "," : "", windows[i].address);
		for (j = 0; j < windows[i].bytes; j++)
			seq_printf(seq, "%s%u", j ? "," : "", data[j]);
		seq_putc(seq, ']');
	}
	seq_puts(seq, "}\n");
	mutex_unlock(&snapshot_lock);
	return ret;
}
DEFINE_SHOW_ATTRIBUTE(fx0_bms_configuration);

static int __init fx0_bms_snapshot_init(void)
{
	struct device_node *node;
	struct dentry *file;
	u8 identity[6];
	int ret;

	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;
	node = of_find_compatible_node(NULL, NULL, "qcom,pm8226-iadc");
	if (!node)
		return -ENODEV;
	provider = of_find_device_by_node(node);
	of_node_put(node);
	if (!provider)
		return -ENODEV;
	bms_map = dev_get_regmap(provider->dev.parent, NULL);
	if (!bms_map) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_bulk_read(bms_map, 0x4000, identity, sizeof(identity));
	if (ret)
		goto put;
	if (identity[4] != 0x0d || identity[5] != 0x01) {
		ret = -ENODEV;
		goto put;
	}
	debug_dir = debugfs_create_dir("fx0-bms-snapshot", NULL);
	if (IS_ERR(debug_dir)) {
		ret = PTR_ERR(debug_dir);
		goto put;
	}
	file = debugfs_create_file("snapshot", 0400, debug_dir, NULL,
				   &fx0_bms_fops);
	if (IS_ERR(file)) {
		ret = PTR_ERR(file);
		debugfs_remove_recursive(debug_dir);
		goto put;
	}
	file = debugfs_create_file("control", 0400, debug_dir, NULL,
				   &fx0_bms_control_fops);
	if (IS_ERR(file)) {
		ret = PTR_ERR(file);
		debugfs_remove_recursive(debug_dir);
		goto put;
	}
	file = debugfs_create_file("configuration", 0400, debug_dir, NULL,
				   &fx0_bms_configuration_fops);
	if (IS_ERR(file)) {
		ret = PTR_ERR(file);
		debugfs_remove_recursive(debug_dir);
		goto put;
	}
	return 0;
put:
	put_device(&provider->dev);
	return ret;
}

static void __exit fx0_bms_snapshot_exit(void)
{
	debugfs_remove_recursive(debug_dir);
	put_device(&provider->dev);
}

module_init(fx0_bms_snapshot_init);
module_exit(fx0_bms_snapshot_exit);
MODULE_DESCRIPTION("Fx0 PM8226 BMS1 latched output diagnostic");
MODULE_LICENSE("GPL");
