/* Host fixture: extracted Linux RMI callbacks; low-level I/O is mocked. */
// SPDX-License-Identifier: GPL-2.0-only

// SPDX-License-Identifier: GPL-2.0-only
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
struct device { void *data; };
struct i2c_client { struct device dev; };
struct rmi_device { struct device dev; };
struct drm_panel_follower { int unused; };
struct gpio_desc { int asserted; };
struct rmi_i2c_xport {
    struct { struct rmi_device *rmi_dev; } xport;
    struct i2c_client *client;
    int supplies[2]; unsigned int startup_delay;
    struct gpio_desc *reset_gpio;
    struct drm_panel_follower panel_follower;
    bool is_panel_follower, powered;
};
static int refs, irq, violations, suspend_error, resume_error, enable_error;
static int suspend_calls, resume_calls, enables, disables;
static struct i2c_client *to_i2c_client(struct device *d) { return (void *)d; }
static struct rmi_i2c_xport *i2c_get_clientdata(struct i2c_client *c) { return c->dev.data; }
static void *dev_get_drvdata(struct device *d) { return d->data; }
#define dev_warn(dev, ...) ((void)(dev))
static int rmi_suspend_functions(struct rmi_device *d) {
    (void)d; ++suspend_calls; return suspend_error;
}
static int rmi_resume_functions(struct rmi_device *d) {
    (void)d; ++resume_calls; return resume_error;
}
static void rmi_disable_irq(struct rmi_device *d, bool wake) {
    (void)d; (void)wake; irq = 0;
}
static void rmi_enable_irq(struct rmi_device *d, bool wake) {
    (void)d; (void)wake; irq = 1; if (refs <= 0) ++violations;
}
static int regulator_bulk_disable(unsigned int n, int *s) {
    assert(n == 2 && s); ++disables; --refs; if (refs < 0) ++violations; return 0;
}
static int regulator_bulk_enable(unsigned int n, int *s) {
    assert(n == 2 && s); ++enables; if (enable_error) return enable_error;
    ++refs; return 0;
}
static void msleep(unsigned int delay) { assert(delay == 10); }
static void usleep_range(unsigned int low, unsigned int high) {
    assert(low == 10000 && high == 20000);
}
static void gpiod_set_value_cansleep(struct gpio_desc *g, int value) {
    assert(g); g->asserted = value;
}

int rmi_driver_suspend(struct rmi_device *rmi_dev, bool enable_wake)
{
	int retval;

	/*
	 * Transport driver will try to suspend RMI device even if physical
	 * driver did not bind to the RMI device, because transport device
	 * (I2C, SPI) is fully registered and operational. Exit early if
	 * there is no driver data attached to the RMI device.
	 */
	if (!dev_get_drvdata(&rmi_dev->dev))
		return 0;

	retval = rmi_suspend_functions(rmi_dev);
	if (retval)
		dev_warn(&rmi_dev->dev, "Failed to suspend functions: %d\n",
			retval);

	rmi_disable_irq(rmi_dev, enable_wake);
	return retval;
}

int rmi_driver_resume(struct rmi_device *rmi_dev, bool clear_wake)
{
	int retval;

	/* Skip if not fully bound to RMI driver */
	if (!dev_get_drvdata(&rmi_dev->dev))
		return 0;

	rmi_enable_irq(rmi_dev, clear_wake);

	retval = rmi_resume_functions(rmi_dev);
	if (retval)
		dev_warn(&rmi_dev->dev, "Failed to suspend functions: %d\n",
			retval);

	return retval;
}

static void rmi_i2c_regulator_bulk_disable(void *data)
{
	struct rmi_i2c_xport *rmi_i2c = data;

	if (!rmi_i2c->powered)
		return;

	if (rmi_i2c->reset_gpio)
		gpiod_set_value_cansleep(rmi_i2c->reset_gpio, 1);

	regulator_bulk_disable(ARRAY_SIZE(rmi_i2c->supplies),
			       rmi_i2c->supplies);
	rmi_i2c->powered = false;
}

static void rmi_i2c_release_reset(struct rmi_i2c_xport *rmi_i2c)
{
	if (rmi_i2c->reset_gpio) {
		usleep_range(10000, 20000);
		gpiod_set_value_cansleep(rmi_i2c->reset_gpio, 0);
	}

	msleep(rmi_i2c->startup_delay);
}

static int rmi_i2c_power_off(struct rmi_i2c_xport *rmi_i2c, bool enable_wake)
{
	int ret;

	if (!rmi_i2c->powered)
		return 0;

	ret = rmi_driver_suspend(rmi_i2c->xport.rmi_dev, enable_wake);
	if (ret)
		dev_warn(&rmi_i2c->client->dev,
			 "Failed to suspend device: %d\n", ret);

	if (rmi_i2c->reset_gpio)
		gpiod_set_value_cansleep(rmi_i2c->reset_gpio, 1);

	regulator_bulk_disable(ARRAY_SIZE(rmi_i2c->supplies),
			       rmi_i2c->supplies);
	rmi_i2c->powered = false;

	return ret;
}

static int rmi_i2c_power_on(struct rmi_i2c_xport *rmi_i2c, bool clear_wake)
{
	int ret;

	if (rmi_i2c->powered)
		return 0;

	ret = regulator_bulk_enable(ARRAY_SIZE(rmi_i2c->supplies),
				    rmi_i2c->supplies);
	if (ret)
		return ret;

	rmi_i2c->powered = true;
	rmi_i2c_release_reset(rmi_i2c);

	ret = rmi_driver_resume(rmi_i2c->xport.rmi_dev, clear_wake);
	if (ret)
		dev_warn(&rmi_i2c->client->dev,
			 "Failed to resume device: %d\n", ret);

	return ret;
}

static int rmi_i2c_panel_prepared(struct drm_panel_follower *follower)
{
	struct rmi_i2c_xport *rmi_i2c =
		container_of(follower, struct rmi_i2c_xport, panel_follower);

	return rmi_i2c_power_on(rmi_i2c, false);
}

static int rmi_i2c_panel_unpreparing(struct drm_panel_follower *follower)
{
	struct rmi_i2c_xport *rmi_i2c =
		container_of(follower, struct rmi_i2c_xport, panel_follower);

	rmi_i2c_power_off(rmi_i2c, false);

	return 0;
}

static int rmi_i2c_suspend(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);

	/* The followed panel powers the device down and up */
	if (rmi_i2c->is_panel_follower)
		return 0;

	rmi_i2c_power_off(rmi_i2c, true);

	/* Resume must restore power even if putting the device to sleep failed. */
	return 0;
}

static int rmi_i2c_resume(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);

	if (rmi_i2c->is_panel_follower)
		return 0;

	return rmi_i2c_power_on(rmi_i2c, true);
}

static int rmi_i2c_runtime_suspend(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);

	if (rmi_i2c->is_panel_follower)
		return 0;

	rmi_i2c_power_off(rmi_i2c, false);

	return 0;
}

static int rmi_i2c_runtime_resume(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);
	int ret;

	if (rmi_i2c->is_panel_follower)
		return 0;

	ret = rmi_i2c_power_on(rmi_i2c, false);
	if (!rmi_i2c->powered)
		return ret;

	/* Preserve the existing warning-only handling of function-resume errors. */
	return 0;
}

int main(void) {
    const struct { const char *steps; bool follower; } schedules[] = {
        {"psPc", true}, {"pSPc", true}, {"sdDSc", false}, {"sc", false},
        {"sSc", false}, {"pdDPc", true}, {"pPPppPc", true}, {"dDc", false},
    };
    int cases = 0, broken = 0;
    for (int reset = 0; reset <= 1; ++reset)
    for (int error = 0; error <= 1; ++error)
    for (unsigned int k = 0; k < ARRAY_SIZE(schedules); ++k) {
        struct rmi_device rmi = { .dev.data = &rmi };
        struct gpio_desc gpio = {0};
        struct i2c_client client;
        struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .client = &client,
            .startup_delay = 10, .reset_gpio = reset ? &gpio : NULL,
            .powered = true, .is_panel_follower = schedules[k].follower };
        client.dev.data = &x;
        refs = irq = 1; violations = 0; suspend_error = error ? -110 : 0;
        resume_error = enable_error = 0;
        suspend_calls = resume_calls = enables = disables = 0;
        for (const char *step = schedules[k].steps; *step; ++step) {
            switch (*step) {
            case 'p': rmi_i2c_panel_unpreparing(&x.panel_follower); break;
            case 'P': rmi_i2c_panel_prepared(&x.panel_follower); break;
            case 's': rmi_i2c_runtime_suspend(&client.dev); break;
            case 'S': rmi_i2c_runtime_resume(&client.dev); break;
            case 'd': rmi_i2c_suspend(&client.dev); break;
            case 'D': rmi_i2c_resume(&client.dev); break;
            case 'c': rmi_i2c_regulator_bulk_disable(&x); break;
            default: assert(false);
            }
        }
        bool bad = violations || refs || x.powered || (reset && !gpio.asserted);
        broken += bad; ++cases;
        printf("schedule=%s reset=%d sleep_error=%d broken=%d refs=%d violations=%d\n",
               schedules[k].steps, reset, suspend_error, bad, refs, violations);
    }
    /* Failed enable must leave the vote absent, allowing a later retry. */
    struct rmi_device rmi = { .dev.data = &rmi };
    struct i2c_client client;
    struct gpio_desc gpio = { .asserted = 1 };
    struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .client = &client,
        .startup_delay = 10, .reset_gpio = &gpio };
    client.dev.data = &x;
    refs = irq = violations = 0; suspend_error = resume_error = 0; enable_error = -5;
    assert(rmi_i2c_power_on(&x, false) == -5 && !x.powered && refs == 0 && gpio.asserted);
    enable_error = 0;
    assert(rmi_i2c_power_on(&x, false) == 0 && x.powered && refs == 1 && !gpio.asserted);
    rmi_i2c_regulator_bulk_disable(&x);
    assert(refs == 0 && !x.powered && gpio.asserted && !violations);
    ++cases;
    /* Function-resume failure is visible; a complete power cycle can retry. */
    resume_error = -110;
    assert(rmi_i2c_power_on(&x, false) == -110 && x.powered && refs == 1);
    rmi_i2c_power_off(&x, false); resume_error = 0;
    assert(rmi_i2c_power_on(&x, false) == 0 && refs == 1);
    rmi_i2c_regulator_bulk_disable(&x);
    assert(refs == 0 && !violations);
    ++cases;
    printf("cases=%d broken=%d\n", cases, broken);
    return broken ? 1 : 0;
}
