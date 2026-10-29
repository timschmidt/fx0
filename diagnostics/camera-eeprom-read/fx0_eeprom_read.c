// SPDX-License-Identifier: GPL-2.0-only
/* Temporary GPIO read diagnostic; not a replacement for native CCI/NVMEM. */
#include <linux/module.h>
#include <linux/platform_device.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/i2c-algo-bit.h>
#include <linux/debugfs.h>
#include <linux/delay.h>
#include <linux/of.h>

static bool capture;
module_param(capture, bool, 0400);
static unsigned int read_bytes = 0xa00;
module_param(read_bytes, uint, 0400);
static u8 calibration[0x10000];
static struct debugfs_blob_wrapper blob = {
	.data = calibration,
	.size = sizeof(calibration),
};
static struct dentry *directory;
static struct gpiod_lookup_table pins = {
	.dev_id = "fx0-eeprom-diagnostic",
	.table = {
		GPIO_LOOKUP("fd510000.pinctrl", 29, "sda", GPIO_OPEN_DRAIN),
		GPIO_LOOKUP("fd510000.pinctrl", 30, "scl", GPIO_OPEN_DRAIN),
		GPIO_LOOKUP("fd510000.pinctrl", 64, "power", GPIO_ACTIVE_HIGH),
		{},
	},
};
struct read_bus {
	struct gpio_desc *sda, *scl;
};
static void set_sda(void *data, int value)
{
	struct read_bus *bus = data;
	gpiod_set_value_cansleep(bus->sda, value);
}
static void set_scl(void *data, int value)
{
	struct read_bus *bus = data;
	gpiod_set_value_cansleep(bus->scl, value);
}
static int get_sda(void *data)
{
	struct read_bus *bus = data;
	return gpiod_get_value_cansleep(bus->sda);
}
static int get_scl(void *data)
{
	struct read_bus *bus = data;
	return gpiod_get_value_cansleep(bus->scl);
}

static int __init eeprom_init(void)
{
	struct platform_device *pdev;
	struct device_node *cci;
	struct gpio_desc *power = NULL;
	struct read_bus bus = {};
	struct i2c_algo_bit_data algorithm = {
		.data = &bus,
		.setsda = set_sda,
		.setscl = set_scl,
		.getsda = get_sda,
		.getscl = get_scl,
		.udelay = 10,
		.timeout = HZ,
	};
	struct i2c_adapter *adapter;
	bool active = false, power_changed = false, added = false;
	unsigned int offset;
	int ret;

	if (read_bytes != 0xa00 && read_bytes != 0x10000)
		return -EINVAL;
	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;
	cci = of_find_compatible_node(NULL, NULL, "qcom,msm8226-cci");
	if (!cci)
		return -ENODEV;
	ret = of_device_is_available(cci);
	of_node_put(cci);
	if (ret)
		return -EBUSY;
	adapter = kzalloc(sizeof(*adapter), GFP_KERNEL);
	if (!adapter)
		return -ENOMEM;
	gpiod_add_lookup_table(&pins);
	pdev = platform_device_register_simple("fx0-eeprom-diagnostic", -1, NULL, 0);
	if (IS_ERR(pdev)) {
		ret = PTR_ERR(pdev);
		goto lookup;
	}
	power = gpiod_get(&pdev->dev, "power", GPIOD_ASIS);
	if (IS_ERR(power)) {
		ret = PTR_ERR(power);
		power = NULL;
		goto cleanup;
	}
	bus.sda = gpiod_get(&pdev->dev, "sda", GPIOD_ASIS);
	if (IS_ERR(bus.sda)) {
		ret = PTR_ERR(bus.sda);
		bus.sda = NULL;
		goto cleanup;
	}
	bus.scl = gpiod_get(&pdev->dev, "scl", GPIOD_ASIS);
	if (IS_ERR(bus.scl)) {
		ret = PTR_ERR(bus.scl);
		bus.scl = NULL;
		goto cleanup;
	}
	if (gpiod_is_active_low(power) || gpiod_is_active_low(bus.sda) ||
	    gpiod_is_active_low(bus.scl) || gpiod_cansleep(power) ||
	    gpiod_cansleep(bus.sda) || gpiod_cansleep(bus.scl) ||
	    gpiod_get_direction(power) != 1 || gpiod_get_value_cansleep(power) != 0 ||
	    gpiod_get_direction(bus.sda) != 1 || gpiod_get_direction(bus.scl) != 1) {
		ret = -EBUSY;
		goto cleanup;
	}
	pr_info("Fx0 EEPROM preflight: GPIO64 input-low; GPIO29/30 inputs; capture=%d\n", capture);
	ret = 0;
	if (!capture)
		goto cleanup;
	active = true;
	ret = gpiod_direction_output(bus.sda, 1);
	if (ret)
		goto cleanup;
	ret = gpiod_direction_output(bus.scl, 1);
	if (ret)
		goto cleanup;
	power_changed = true;
	ret = gpiod_direction_output(power, 1);
	if (ret)
		goto cleanup;
	msleep(20);
	pr_info("Fx0 EEPROM powered: SDA=%d SCL=%d\n", get_sda(&bus), get_scl(&bus));
	if (get_sda(&bus) != 1 || get_scl(&bus) != 1) {
		ret = -EIO;
		goto cleanup;
	}
	adapter->owner = THIS_MODULE;
	adapter->algo_data = &algorithm;
	adapter->dev.parent = &pdev->dev;
	strscpy(adapter->name, "Fx0 read-only EEPROM diagnostic", sizeof(adapter->name));
	ret = i2c_bit_add_bus(adapter);
	if (ret)
		goto cleanup;
	added = true;
	for (offset = 0; offset < read_bytes; offset += 32) {
		u8 address[] = { offset >> 8, offset & 0xff };
		struct i2c_msg messages[] = {
			{ .addr = 0x50, .len = 2, .buf = address },
			{ .addr = 0x50, .flags = I2C_M_RD, .len = 32,
			  .buf = calibration + offset },
		};
		/* Address-pointer write plus repeated-start read; no data programming. */
		ret = i2c_transfer(adapter, messages, ARRAY_SIZE(messages));
		if (ret != ARRAY_SIZE(messages)) {
			pr_err("Fx0 EEPROM read failed at %04x: %d\n", offset, ret);
			ret = ret < 0 ? ret : -EIO;
			goto cleanup;
		}
	}
	ret = 0;
	pr_info("Fx0 EEPROM captured %u bytes; no programming transaction issued\n", read_bytes);
cleanup:
	if (added)
		i2c_del_adapter(adapter);
	if (active) {
		if (bus.sda)
			gpiod_direction_input(bus.sda);
		if (bus.scl)
			gpiod_direction_input(bus.scl);
	}
	if (power_changed) {
		gpiod_direction_output(power, 0);
		msleep(10);
		gpiod_direction_input(power);
	}
	if (bus.scl)
		gpiod_put(bus.scl);
	if (bus.sda)
		gpiod_put(bus.sda);
	if (power)
		gpiod_put(power);
	platform_device_unregister(pdev);
lookup:
	gpiod_remove_lookup_table(&pins);
	kfree(adapter);
	if (ret)
		return ret;
	if (capture) {
		blob.size = read_bytes;
		directory = debugfs_create_dir("fx0-camera-calibration", NULL);
		if (IS_ERR_OR_NULL(directory))
			return directory ? PTR_ERR(directory) : -ENOMEM;
		if (IS_ERR_OR_NULL(debugfs_create_blob("readout", 0400, directory, &blob))) {
			debugfs_remove_recursive(directory);
			return -ENOMEM;
		}
	}
	return 0;
}
static void __exit eeprom_exit(void)
{
	debugfs_remove_recursive(directory);
	memzero_explicit(calibration, sizeof(calibration));
}
module_init(eeprom_init);
module_exit(eeprom_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary Fx0 independent camera EEPROM read diagnostic");
