// SPDX-License-Identifier: GPL-2.0-only
/* One-shot Fx0 identity diagnostic. No IMU scan/reset/configuration/DMP writes. */
#include <linux/delay.h>
#include <linux/firmware/qcom/qcom_scm.h>
#include <linux/gpio/consumer.h>
#include <linux/gpio/machine.h>
#include <linux/i2c-algo-bit.h>
#include <linux/io.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/of_address.h>
#include <linux/platform_device.h>
#include <linux/slab.h>

#define TLMM_BASE 0xfd510000
#define TLMM_SIZE 0x2000
#define GPIO_CTL(pin) (0x1000 + 0x10 * (pin))
#define GPIO_IO(pin) (GPIO_CTL(pin) + 4)
#define GPIO_OUTPUT BIT(1)

static bool capture;
module_param(capture, bool, 0400);
MODULE_PARM_DESC(capture, "Quiesce ADSP PAS1 and read only 0x68:WHO_AM_I three times");

static struct gpiod_lookup_table pins = {
	.dev_id = "fx0-imu-id",
	.table = {
		GPIO_LOOKUP("fd510000.pinctrl", 6, "sda", GPIO_OPEN_DRAIN),
		GPIO_LOOKUP("fd510000.pinctrl", 7, "scl", GPIO_OPEN_DRAIN),
		{},
	},
};

struct id_bus {
	struct gpio_desc *sda, *scl;
};

static void set_sda(void *data, int value)
{
	struct id_bus *bus = data;

	gpiod_set_value_cansleep(bus->sda, value);
}

static void set_scl(void *data, int value)
{
	struct id_bus *bus = data;

	gpiod_set_value_cansleep(bus->scl, value);
}

static int get_sda(void *data)
{
	struct id_bus *bus = data;

	return gpiod_get_value_cansleep(bus->sda);
}

static int get_scl(void *data)
{
	struct id_bus *bus = data;

	return gpiod_get_value_cansleep(bus->scl);
}

static int require_disabled_paths(void)
{
	struct device_node *adsp, *node;
	struct resource resource;
	unsigned int buses = 0;
	bool enabled;

	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;
	adsp = of_find_compatible_node(NULL, NULL, "qcom,msm8226-adsp-pil");
	if (!adsp)
		return -ENODEV;
	enabled = of_device_is_available(adsp);
	of_node_put(adsp);
	if (enabled)
		return -EBUSY;

	for_each_compatible_node(node, NULL, "qcom,i2c-qup-v2.1.1") {
		if (of_address_to_resource(node, 0, &resource))
			continue;
		if (resource.start != 0xf9924000)
			continue;
		buses++;
		if (of_device_is_available(node)) {
			of_node_put(node);
			return -EBUSY;
		}
	}
	return buses == 1 ? 0 : -ENODEV;
}

/* Fixed two-message register-pointer/read transaction; never an address scan. */
static int read_identity(struct i2c_adapter *adapter, u8 *identity)
{
	u8 reg = 0x75;
	struct i2c_msg messages[] = {
		{ .addr = 0x68, .len = 1, .buf = &reg },
		{ .addr = 0x68, .flags = I2C_M_RD, .len = 1, .buf = identity },
	};
	int ret;

	ret = i2c_transfer(adapter, messages, ARRAY_SIZE(messages));
	return ret == ARRAY_SIZE(messages) ? 0 : ret < 0 ? ret : -EIO;
}

static int read_identities(struct i2c_adapter *adapter)
{
	u8 identity;
	int i, ret;

	for (i = 0; i < 3; i++) {
		ret = read_identity(adapter, &identity);
		pr_info("fx0-imu-id: read%d ret=%d id=%02x\n",
			i, ret, ret ? 0 : identity);
		if (ret)
			return ret;
		if (identity != 0x74)
			return -ENODEV;
		usleep_range(1000, 2000);
	}
	return 0;
}

static int __init imu_id_init(void)
{
	struct platform_device *pdev = NULL;
	struct id_bus bus = {};
	struct i2c_algo_bit_data algorithm = {
		.data = &bus,
		.setsda = set_sda,
		.setscl = set_scl,
		.getsda = get_sda,
		.getscl = get_scl,
		.udelay = 10,
		.timeout = HZ / 10,
	};
	struct i2c_adapter *adapter = NULL;
	void __iomem *tlmm;
	u32 control[2], output[2];
	bool lookup = false, added = false;
	int ret, i;

	ret = require_disabled_paths();
	if (ret)
		return ret;
	tlmm = ioremap(TLMM_BASE, TLMM_SIZE);
	if (!tlmm)
		return -ENOMEM;
	for (i = 0; i < 2; i++) {
		control[i] = readl(tlmm + GPIO_CTL(6 + i));
		output[i] = readl(tlmm + GPIO_IO(6 + i));
		pr_info("fx0-imu-id: pin%d ctl=%08x io=%08x\n",
			6 + i, control[i], output[i]);
	}
	if (!capture) {
		pr_info("fx0-imu-id: read-only preflight; no PAS or GPIO operation\n");
		ret = 0;
		goto unmap;
	}

	/* Disabled DT alone does not prove a warm-booted DSP has stopped. */
	ret = qcom_scm_pas_shutdown(1);
	pr_info("fx0-imu-id: ADSP PAS1 shutdown returned %d\n", ret);
	if (ret)
		goto unmap;
	adapter = kzalloc(sizeof(*adapter), GFP_KERNEL);
	if (!adapter) {
		ret = -ENOMEM;
		goto unmap;
	}
	gpiod_add_lookup_table(&pins);
	lookup = true;
	pdev = platform_device_register_simple("fx0-imu-id", -1, NULL, 0);
	if (IS_ERR(pdev)) {
		ret = PTR_ERR(pdev);
		pdev = NULL;
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
	if (gpiod_is_active_low(bus.sda) || gpiod_is_active_low(bus.scl) ||
	    gpiod_cansleep(bus.sda) || gpiod_cansleep(bus.scl)) {
		ret = -EINVAL;
		goto cleanup;
	}
	ret = gpiod_direction_input(bus.sda);
	if (ret)
		goto cleanup;
	ret = gpiod_direction_input(bus.scl);
	if (ret)
		goto cleanup;
	if (get_sda(&bus) != 1 || get_scl(&bus) != 1) {
		ret = -EBUSY;
		pr_err("fx0-imu-id: lines not idle-high; no clocking attempted\n");
		goto cleanup;
	}
	ret = gpiod_direction_output(bus.sda, 1);
	if (ret)
		goto cleanup;
	ret = gpiod_direction_output(bus.scl, 1);
	if (ret)
		goto cleanup;
	adapter->owner = THIS_MODULE;
	adapter->algo_data = &algorithm;
	adapter->dev.parent = &pdev->dev;
	strscpy(adapter->name, "Fx0 fixed IMU identity read", sizeof(adapter->name));
	ret = i2c_bit_add_bus(adapter);
	if (ret)
		goto cleanup;
	added = true;
	ret = read_identities(adapter);

cleanup:
	if (added)
		i2c_del_adapter(adapter);
	if (bus.scl) {
		gpiod_direction_input(bus.scl);
		gpiod_put(bus.scl);
	}
	if (bus.sda) {
		gpiod_direction_input(bus.sda);
		gpiod_put(bus.sda);
	}
	if (pdev)
		platform_device_unregister(pdev);
	if (lookup)
		gpiod_remove_lookup_table(&pins);
	/* Restore only pins acquired by this diagnostic; never touch another owner. */
	if (bus.sda) {
		writel(output[0] & GPIO_OUTPUT, tlmm + GPIO_IO(6));
		writel(control[0], tlmm + GPIO_CTL(6));
	}
	if (bus.scl) {
		writel(output[1] & GPIO_OUTPUT, tlmm + GPIO_IO(7));
		writel(control[1], tlmm + GPIO_CTL(7));
	}
	for (i = 0; i < 2; i++) {
		if (readl(tlmm + GPIO_CTL(6 + i)) != control[i] ||
		    (readl(tlmm + GPIO_IO(6 + i)) & GPIO_OUTPUT) !=
		    (output[i] & GPIO_OUTPUT)) {
			pr_err("fx0-imu-id: pin%d restoration mismatch\n", 6 + i);
			ret = -EIO;
		}
	}
	kfree(adapter);
	pr_info("fx0-imu-id: fixed-read result=%d; restoration checked; reboot required after PAS shutdown\n",
		ret);
unmap:
	iounmap(tlmm);
	return ret;
}

static void __exit imu_id_exit(void)
{
}

module_init(imu_id_init);
module_exit(imu_id_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Guarded Fx0 fixed-register IMU identity diagnostic");
