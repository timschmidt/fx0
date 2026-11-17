/* SPDX-License-Identifier: GPL-2.0-only */
/* Explicitly synthetic consumer counts and a single managed cleanup action. */
static struct regulator *sleep_consumer;
static int sleep_get_error, action_error;
static void (*cleanup_action)(void *);
static void *cleanup_data;
static unsigned managed_gets, managed_puts, disable_calls;
static struct regulator *devm_regulator_get(struct device *dev, const char *id)
{
    if (strcmp(id, "vdd-mx-sleep")) return boot_devm_regulator_get(dev, id);
    ++managed_gets;
    CHECK(dev->of_node->sleep_supply);
    return sleep_get_error ? ERR_PTR(sleep_get_error) : sleep_consumer;
}
static int regulator_disable(struct regulator *reg)
{
    CHECK(reg == sleep_consumer && reg->enable_count == 1);
    ++disable_calls;
    int ret = rpm_reg_disable(reg->rdev);
    if (!ret) --reg->enable_count;
    return ret;
}
static int devm_add_action_or_reset(struct device *dev, void (*action)(void *), void *data)
{
    CHECK(!cleanup_action);
    if (action_error) { action(data); return action_error; }
    cleanup_action = action; cleanup_data = data;
    return 0;
}
/* ACTUAL_SLEEP_CLIENT */
static void managed_release(void)
{
    if (cleanup_action) {
        void (*action)(void *) = cleanup_action;
        cleanup_action = NULL;
        action(cleanup_data);
    }
    CHECK(!sleep_consumer->enable_count);
    ++managed_puts;
}
static void reset_client(struct regulator *consumer)
{
    sleep_consumer = consumer;
    cleanup_action = NULL; cleanup_data = NULL;
    managed_gets = managed_puts = disable_calls = 0;
    sleep_get_error = action_error = 0;
    fault_span = 0;
}
