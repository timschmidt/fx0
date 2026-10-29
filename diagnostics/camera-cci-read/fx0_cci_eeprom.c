// SPDX-License-Identifier: GPL-2.0-only
/* Temporary native CCI read test; no EEPROM model/capacity binding implied. */
#include <linux/debugfs.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>
#include <linux/slab.h>

static bool capture;
module_param(capture, bool, 0400);
static unsigned int read_bytes = 0xa00;
module_param(read_bytes, uint, 0400);
static u8 calibration[0x10000];
static struct debugfs_blob_wrapper blob = {
	.data = calibration,
};
static struct dentry *directory;

static int __init cci_eeprom_init(void)
{
	struct device_node *cci, *bus;
	struct i2c_adapter *adapter;
	struct i2c_client *client;
	struct regulator *supply;
	bool powered = false;
	unsigned int offset;
	int ret, disable_ret;

	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;
	if (read_bytes != 0xa00 && read_bytes != sizeof(calibration))
		return -EINVAL;
	cci = of_find_compatible_node(NULL, NULL, "qcom,msm8226-cci");
	if (!cci)
		return -ENODEV;
	if (!of_device_is_available(cci)) {
		of_node_put(cci);
		return -ENODEV;
	}
	bus = of_get_child_by_name(cci, "i2c-bus");
	of_node_put(cci);
	if (!bus)
		return -ENODEV;
	adapter = of_get_i2c_adapter_by_node(bus);
	of_node_put(bus);
	if (!adapter)
		return -EPROBE_DEFER;
	if (!i2c_check_functionality(adapter, I2C_FUNC_I2C)) {
		ret = -EOPNOTSUPP;
		goto put_adapter;
	}
	/* This diagnostic uses the board regulator's exact, unique name. */
	supply = regulator_get_optional(NULL, "cam_io_1v8");
	if (IS_ERR(supply)) {
		ret = PTR_ERR(supply);
		goto put_adapter;
	}
	if (regulator_get_voltage(supply) != 1800000) {
		ret = -EINVAL;
		goto put_supply;
	}
	ret = regulator_is_enabled(supply);
	if (ret) {
		ret = ret < 0 ? ret : -EBUSY;
		goto put_supply;
	}
	client = i2c_new_dummy_device(adapter, 0x50);
	if (IS_ERR(client)) {
		ret = PTR_ERR(client);
		goto put_supply;
	}
	pr_info("Fx0 native EEPROM preflight: adapter=%d supply=1800000 disabled capture=%d\n",
		adapter->nr, capture);
	if (!capture) {
		ret = 0;
		goto remove_client;
	}
	ret = regulator_enable(supply);
	if (ret)
		goto remove_client;
	powered = true;
	msleep(20);
	/* Eight-byte reads fit the native CCI v1 twelve-byte read limit. */
	for (offset = 0; offset < read_bytes; offset += 8) {
		u8 address[] = { offset >> 8, offset & 0xff };
		struct i2c_msg messages[] = {
			{ .addr = client->addr, .len = 2, .buf = address },
			{ .addr = client->addr, .flags = I2C_M_RD, .len = 8,
			  .buf = calibration + offset },
		};

		ret = i2c_transfer(adapter, messages, ARRAY_SIZE(messages));
		if (ret != ARRAY_SIZE(messages)) {
			pr_err("Fx0 native EEPROM read failed at %04x: %d\n", offset, ret);
			ret = ret < 0 ? ret : -EIO;
			goto remove_client;
		}
	}
	ret = 0;
	pr_info("Fx0 native EEPROM read %u bytes; no data programming\n", read_bytes);
remove_client:
	i2c_unregister_device(client);
	if (powered) {
		disable_ret = regulator_disable(supply);
		if (disable_ret) {
			pr_err("Fx0 native EEPROM supply disable failed: %d\n", disable_ret);
			if (!ret)
				ret = disable_ret;
		}
	}
put_supply:
	regulator_put(supply);
put_adapter:
	i2c_put_adapter(adapter);
	if (ret)
		return ret;
	if (capture) {
		blob.size = read_bytes;
		directory = debugfs_create_dir("fx0-native-camera-calibration", NULL);
		if (IS_ERR_OR_NULL(directory))
			return directory ? PTR_ERR(directory) : -ENOMEM;
		if (IS_ERR_OR_NULL(debugfs_create_blob("readout", 0400, directory, &blob))) {
			debugfs_remove_recursive(directory);
			return -ENOMEM;
		}
	}
	return 0;
}

static void __exit cci_eeprom_exit(void)
{
	debugfs_remove_recursive(directory);
	memzero_explicit(calibration, sizeof(calibration));
}
module_init(cci_eeprom_init);
module_exit(cci_eeprom_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary Fx0 native CCI camera EEPROM read diagnostic");
