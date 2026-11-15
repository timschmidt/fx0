/* Host fixture: extracted Linux RMI callbacks; low-level I/O is mocked. */
// SPDX-License-Identifier: GPL-2.0-only

#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
struct device { void *data; struct { bool is_suspended; } power; };
struct rmi_device { struct device dev; };
struct rmi_i2c_xport {
    struct { struct rmi_device *rmi_dev; } xport;
    int supplies[2];
    unsigned int startup_delay;
};
struct i2c_client { struct device dev; };
static int suspend_error, resume_error, enable_error;
static int rails, irq, off_calls, on_calls, suspend_calls, resume_calls, sleeps;
static int warnings, wake_off, wake_on;
static struct i2c_client *to_i2c_client(struct device *dev) { return (void *)dev; }
static struct rmi_i2c_xport *i2c_get_clientdata(struct i2c_client *c) { return c->dev.data; }
static void *dev_get_drvdata(struct device *dev) { return dev->data; }
#define dev_warn(dev, ...) ((void)(dev), (void)++warnings)
static int rmi_suspend_functions(struct rmi_device *dev) {
    (void)dev; ++suspend_calls; return suspend_error;
}
static int rmi_resume_functions(struct rmi_device *dev) {
    (void)dev; ++resume_calls; return resume_error;
}
static void rmi_disable_irq(struct rmi_device *dev, bool wake) {
    (void)dev; irq = 0; wake_off += wake;
}
static void rmi_enable_irq(struct rmi_device *dev, bool wake) {
    (void)dev; irq = 1; wake_on += wake;
}
static int regulator_bulk_disable(unsigned int n, int *supplies) {
    assert(n == 2 && supplies); assert(rails == 1); rails = 0; ++off_calls; return 0;
}
static int regulator_bulk_enable(unsigned int n, int *supplies) {
    assert(n == 2 && supplies); ++on_calls;
    if (enable_error) return enable_error;
    assert(rails == 0); rails = 1; return 0;
}
static void msleep(unsigned int delay) { assert(delay == 10); ++sleeps; }

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

static int rmi_i2c_suspend(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);
	int ret;

	ret = rmi_driver_suspend(rmi_i2c->xport.rmi_dev, true);
	if (ret)
		dev_warn(dev, "Failed to suspend device: %d\n", ret);

	regulator_bulk_disable(ARRAY_SIZE(rmi_i2c->supplies),
			       rmi_i2c->supplies);

	/* Resume must restore power even if putting the device to sleep failed. */
	return 0;
}

static int rmi_i2c_resume(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);
	int ret;

	ret = regulator_bulk_enable(ARRAY_SIZE(rmi_i2c->supplies),
				    rmi_i2c->supplies);
	if (ret)
		return ret;

	msleep(rmi_i2c->startup_delay);

	ret = rmi_driver_resume(rmi_i2c->xport.rmi_dev, true);
	if (ret)
		dev_warn(dev, "Failed to resume device: %d\n", ret);

	return ret;
}

static int rmi_i2c_runtime_suspend(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);
	int ret;

	ret = rmi_driver_suspend(rmi_i2c->xport.rmi_dev, false);
	if (ret)
		dev_warn(dev, "Failed to resume device: %d\n", ret);

	regulator_bulk_disable(ARRAY_SIZE(rmi_i2c->supplies),
			       rmi_i2c->supplies);

	return 0;
}

static int rmi_i2c_runtime_resume(struct device *dev)
{
	struct i2c_client *client = to_i2c_client(dev);
	struct rmi_i2c_xport *rmi_i2c = i2c_get_clientdata(client);
	int ret;

	ret = regulator_bulk_enable(ARRAY_SIZE(rmi_i2c->supplies),
				    rmi_i2c->supplies);
	if (ret)
		return ret;

	msleep(rmi_i2c->startup_delay);

	ret = rmi_driver_resume(rmi_i2c->xport.rmi_dev, false);
	if (ret)
		dev_warn(dev, "Failed to resume device: %d\n", ret);

	return 0;
}

static int pm_cycle(struct device *dev) {
    int error = rmi_i2c_suspend(dev);
	if (!error) {
		dev->power.is_suspended = true;
	}
    /* Model the ordinary resume and aborted-suspend unwind decision alike. */
	if (!dev->power.is_suspended)
		goto Complete;
    dev->power.is_suspended = false;
    return rmi_i2c_resume(dev);
Complete:
    return error;
}
int main(void) {
    const int errors[] = {0, -5, -110, -19, -22};
    int cases = 0, stranded = 0;
    for (int bound = 0; bound <= 1; ++bound)
    for (unsigned int e = 0; e < ARRAY_SIZE(errors); ++e)
    for (int runtime = 0; runtime <= 1; ++runtime) {
        struct rmi_device rmi = { .dev.data = bound ? &rmi : NULL };
        struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .startup_delay = 10 };
        struct i2c_client client = { .dev.data = &x };
        suspend_error = errors[e]; resume_error = enable_error = 0;
        rails = irq = 1; off_calls = on_calls = suspend_calls = resume_calls = sleeps = 0;
        warnings = wake_off = wake_on = 0;
        int ret;
        if (runtime) {
            ret = rmi_i2c_runtime_suspend(&client.dev);
            assert(ret == 0 && rails == 0);
            ret = rmi_i2c_runtime_resume(&client.dev);
        } else {
            ret = pm_cycle(&client.dev);
        }
        bool bad = rails != 1 || irq != 1 || ret != 0;
        if (bad) ++stranded;
        assert(off_calls == 1);
        assert(suspend_calls == bound);
        if (bad) {
            assert(bound && errors[e] && !runtime);
            assert(rails == 0 && irq == 0 && on_calls == 0 && resume_calls == 0);
        } else {
            assert(on_calls == 1 && sleeps == 1 && resume_calls == bound);
            assert(wake_off == (bound && !runtime) && wake_on == (bound && !runtime));
        }
        printf("bound=%d suspend_error=%d runtime=%d stranded=%d\n",
               bound, errors[e], runtime, bad);
        ++cases;
    }
    /* Existing system resume propagates regulator and function errors. */
    for (int which = 0; which < 2; ++which) {
        struct rmi_device rmi = { .dev.data = &rmi };
        struct rmi_i2c_xport x = { .xport.rmi_dev = &rmi, .startup_delay = 10 };
        struct i2c_client client = { .dev.data = &x };
        rails = irq = 0; on_calls = resume_calls = sleeps = 0;
        enable_error = which == 0 ? -5 : 0;
        resume_error = which == 1 ? -110 : 0;
        int ret = rmi_i2c_resume(&client.dev);
        assert(ret == (which == 0 ? -5 : -110));
        assert(rails == which && resume_calls == which && sleeps == which);
        ++cases;
    }
    printf("cases=%d stranded=%d\n", cases, stranded);
    return stranded ? 1 : 0;
}
