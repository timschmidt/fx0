// SPDX-License-Identifier: GPL-2.0-only
/* Fx0 BMS experiment: restore control settings; optional counter epoch reset. */
#include <linux/bitops.h>
#include <linux/debugfs.h>
#include <linux/delay.h>
#include <linux/iio/consumer.h>
#include <linux/iio/iio.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/regmap.h>
#include <linux/seq_file.h>

struct bms_config {
	u8 channel;
	u8 sense;
	u8 trim[2];
};

static bool apply;
module_param(apply, bool, 0);
static unsigned int trim_bank = 0x3600;
module_param(trim_bank, uint, 0);
static unsigned int mode;
module_param(mode, uint, 0);
static bool reset_epoch;
module_param(reset_epoch, bool, 0);
static struct platform_device *provider;
static struct regmap *bms_map;
static struct dentry *debug_dir;
static struct bms_config saved;
static int gain_raw, offset_raw;

/* BEGIN TESTED CONFIGURATION HELPERS */
static int bms_start_epoch(struct regmap *map)
{
	unsigned int before, after;
	int attempt, ret, release_ret = -EIO;

	ret = regmap_read(map, 0x4043, &before);
	if (ret)
		return ret;
	if (before & 0xc0)
		return -EBUSY;
	ret = regmap_write_bits(map, 0x4043, 0xc0, 0xc0);
	if (!ret)
		udelay(100);
	/* A failed assertion may still have stopped the counters. */
	for (attempt = 0; attempt < 2; attempt++) {
		release_ret = regmap_write_bits(map, 0x4043, 0xc0, 0);
		if (release_ret)
			continue;
		release_ret = regmap_read(map, 0x4043, &after);
		if (release_ret)
			continue;
		if (!(after & 0xc0))
			return ret;
		release_ret = -EIO;
	}
	return release_ret;
}

static int bms_read_config(struct regmap *map, struct bms_config *config)
{
	unsigned int value;
	u8 mirror[2];
	int ret;

	ret = regmap_read(map, 0x3848, &value);
	if (ret)
		return ret;
	config->channel = value;
	ret = regmap_read(map, 0x3849, &value);
	if (ret)
		return ret;
	config->sense = value;
	ret = regmap_bulk_read(map, 0x36f2, config->trim, 2);
	if (ret)
		return ret;
	ret = regmap_bulk_read(map, 0x38f2, mirror, 2);
	if (ret)
		return ret;
	return memcmp(mirror, config->trim, 2) ? -EIO : 0;
}

static int bms_write_trim(struct regmap *map, unsigned int bank, const u8 *trim)
{
	int i, ret;

	for (i = 0; i < 2; i++) {
		ret = regmap_write(map, bank + 0xd0, 0xa5);
		if (ret)
			return ret;
		ret = regmap_write(map, bank + 0xf2 + i, trim[i]);
		if (ret)
			return ret;
	}
	return 0;
}

static int bms_restore_config(struct regmap *map, const struct bms_config *before)
{
	struct bms_config after;
	int attempt, ret = -EIO;

	/* Restore through the original stock driver's primary trim address. */
	for (attempt = 0; attempt < 2; attempt++) {
		ret = bms_write_trim(map, 0x3600, before->trim);
		if (ret)
			continue;
		ret = regmap_update_bits(map, 0x3848, 0x07, before->channel);
		if (ret)
			continue;
		ret = regmap_update_bits(map, 0x3849, 0x03, before->sense);
		if (ret)
			continue;
		ret = bms_read_config(map, &after);
		if (ret)
			continue;
		if (!memcmp(&after, before, sizeof(after)))
			return 0;
		ret = -EIO;
	}
	return ret;
}

static int bms_apply_config(struct regmap *map, unsigned int bank, u16 offset,
			    bool sense, bool calibrate)
{
	struct bms_config after;
	u8 trim[2] = { offset >> 8, offset & 0xff };
	int ret;

	if (sense) {
		/* Open internal sense leads before selecting the external resistor. */
		ret = regmap_update_bits(map, 0x3849, 0x03, 0x02);
		if (ret)
			return ret;
		ret = regmap_update_bits(map, 0x3848, 0x07, 0x01);
		if (ret)
			return ret;
	}
	if (calibrate) {
		ret = bms_write_trim(map, bank, trim);
		if (ret)
			return ret;
	}
	ret = bms_read_config(map, &after);
	if (ret)
		return ret;
	if (sense && ((after.channel & 0x07) != 1 || (after.sense & 0x03) != 2))
		return -EIO;
	if (calibrate && memcmp(after.trim, trim, sizeof(trim)))
		return -EIO;
	return 0;
}
/* END TESTED CONFIGURATION HELPERS */

static int bms_read_reference(struct iio_dev *indio, int number, int *raw)
{
	struct iio_channel channel = { .indio_dev = indio };
	int i;

	for (i = 0; i < indio->num_channels; i++) {
		if (indio->channels[i].channel != number ||
		    indio->channels[i].type != IIO_VOLTAGE)
			continue;
		channel.channel = &indio->channels[i];
		return iio_read_channel_raw(&channel, raw);
	}
	return -ENODEV;
}

static int bms_status_show(struct seq_file *seq, void *unused)
{
	struct bms_config now;
	unsigned int clear;
	int ret;

	ret = bms_read_config(bms_map, &now);
	if (ret)
		return ret;
	ret = regmap_read(bms_map, 0x4043, &clear);
	if (ret)
		return ret;
	seq_printf(seq, "{\"mode\":%u,\"trim_bank\":%u,\"reset_epoch\":%s,\"counter_clear\":%u,",
		   mode, trim_bank, reset_epoch ? "true" : "false", clear);
	seq_printf(seq, "\"gain_raw\":%d,\"offset_raw\":%d,", gain_raw, offset_raw);
	seq_printf(seq, "\"channel\":%u,\"sense\":%u,\"trim_changed\":%s,",
		   now.channel & 7, now.sense & 3,
		   memcmp(now.trim, saved.trim, 2) ? "true" : "false");
	seq_printf(seq, "\"trim_matches_reference\":%s}\n",
		   now.trim[0] == offset_raw >> 8 &&
		   now.trim[1] == (offset_raw & 0xff) ? "true" : "false");
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(bms_status);

static int __init fx0_bms_configure_init(void)
{
	struct device_node *node;
	struct device *iio_device;
	struct dentry *file;
	unsigned int hold;
	u8 identity[6];
	int ret, restore_ret;

	if (!apply || mode > 2 || (trim_bank != 0x3600 && trim_bank != 0x3800) ||
	    (reset_epoch && (mode || trim_bank != 0x3600)) ||
	    !of_machine_is_compatible("lg,madai"))
		return -EINVAL;
	node = of_find_compatible_node(NULL, NULL, "qcom,pm8226-iadc");
	if (!node)
		return -ENODEV;
	provider = of_find_device_by_node(node);
	iio_device = bus_find_device_by_fwnode(&iio_bus_type, of_fwnode_handle(node));
	of_node_put(node);
	if (!provider || !iio_device) {
		ret = -ENODEV;
		goto put;
	}
	bms_map = dev_get_regmap(provider->dev.parent, NULL);
	if (!bms_map) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_bulk_read(bms_map, 0x3800, identity, sizeof(identity));
	if (ret)
		goto put;
	if (identity[1] != 4 || identity[4] != 8 || identity[5] != 5) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_bulk_read(bms_map, 0x4000, identity, sizeof(identity));
	if (ret)
		goto put;
	if (identity[4] != 0x0d || identity[5] != 1) {
		ret = -ENODEV;
		goto put;
	}
	ret = regmap_read(bms_map, 0x4042, &hold);
	if (ret)
		goto put;
	if (hold & BIT(0)) {
		ret = -EBUSY;
		goto put;
	}
	ret = bms_read_reference(dev_to_iio_dev(iio_device), 3, &gain_raw);
	if (ret < 0)
		goto put;
	ret = bms_read_reference(dev_to_iio_dev(iio_device), 5, &offset_raw);
	if (ret < 0)
		goto put;
	if (offset_raw < 0 || gain_raw > U16_MAX || gain_raw <= offset_raw) {
		ret = -ERANGE;
		goto put;
	}
	ret = bms_read_config(bms_map, &saved);
	if (ret)
		goto put;
	ret = bms_apply_config(bms_map, trim_bank, offset_raw, mode != 2, mode != 1);
	if (ret)
		goto restore;
	if (reset_epoch) {
		ret = bms_start_epoch(bms_map);
		if (ret)
			goto restore;
	}
	debug_dir = debugfs_create_dir("fx0-bms-configure", NULL);
	if (IS_ERR(debug_dir)) {
		ret = PTR_ERR(debug_dir);
		goto restore;
	}
	file = debugfs_create_file("status", 0400, debug_dir, NULL, &bms_status_fops);
	if (IS_ERR(file)) {
		ret = PTR_ERR(file);
		debugfs_remove_recursive(debug_dir);
		goto restore;
	}
	put_device(iio_device);
	return 0;
restore:
	restore_ret = bms_restore_config(bms_map, &saved);
	if (restore_ret) {
		pr_err("Fx0 BMS experiment could not restore configuration: %d\n",
		       restore_ret);
		ret = restore_ret;
	}
put:
	put_device(iio_device);
	if (provider)
		put_device(&provider->dev);
	return ret;
}

static void __exit fx0_bms_configure_exit(void)
{
	int ret;

	debugfs_remove_recursive(debug_dir);
	ret = bms_restore_config(bms_map, &saved);
	if (ret)
		pr_err("Fx0 BMS experiment could not restore configuration: %d\n", ret);
	put_device(&provider->dev);
}

module_init(fx0_bms_configure_init);
module_exit(fx0_bms_configure_exit);
MODULE_DESCRIPTION("Fx0 BMS external-sense and volatile-trim experiment");
MODULE_LICENSE("GPL");
