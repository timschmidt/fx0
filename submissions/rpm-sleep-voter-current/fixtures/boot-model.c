/* SPDX-License-Identifier: GPL-2.0-only */
static struct qcom_rpm_reg *voter(struct regulator_dev *rdev) { return rdev_get_drvdata(rdev); }
static void setup_boot(struct platform_device *pdev, struct device *parent, struct device_node *node,
    struct device_node *normal, struct device_node *ao, struct qcom_smd_rpm *rpm,
    struct rpmsg_endpoint *ep, bool order, int apc)
{
    *rpm = (struct qcom_smd_rpm){0}; *ep = (struct rpmsg_endpoint){.rpm = rpm}; rpm->rpm_channel = ep;
    *parent = (struct device){.data = rpm};
    *normal = (struct device_node){.name = "l3", .available = true, .min_uV = 750000, .max_uV = 1337500};
    *ao = (struct device_node){.name = "l3-ao", .available = true, .min_uV = 750000, .max_uV = 1337500};
    *node = (struct device_node){.child = order ? ao : normal, .boot_apc = true};
    if (order) ao->next = normal; else normal->next = ao;
    *pdev = (struct platform_device){.dev = {.parent = parent, .of_node = node, .match_data = rpm_pm8226_regulators}};
    smd_vreg_rpm = NULL; expected_pair = NULL; clear_io();
    arena_count = live_count = factory_allocs = factory_registers = 0;
    fail_allocate = fail_register = 0; registration_callbacks = false; machine_registration = true;
    boot_get_calls = boot_read_calls = 0; boot_get_error = 0; boot_read_uV = apc;
    apc_voltage = apc; boot_safety = apc > 0 && apc <= 1337500;
    fw[0] = (struct firmware_vote){true, apc, 0}; fw[1] = (struct firmware_vote){false, 0, 0};
}
static void end_boot(struct device_node *normal, struct device_node *ao)
{
    release_arena(); EXPECT(!normal->refs && !ao->refs);
    EXPECT(!allocated); boot_safety = machine_registration = false;
}
static void get_voters(struct regulator_dev **normal, struct regulator_dev **ao)
{
    CHECK(live_count == 2);
    *normal = voter(registered[0])->active_only ? registered[1] : registered[0];
    *ao = voter(registered[0])->active_only ? registered[0] : registered[1];
}
int main(void)
{
    const struct regulator_ops *ops[] = {&rpm_smps_ldo_ops_fixed, &rpm_switch_ops,
        &rpm_bob_ops, &rpm_mp5496_ops};
    for (unsigned i = 0; i < sizeof(ops) / sizeof(ops[0]); ++i)
        EXPECT(ops[i]->set_suspend_disable == rpm_reg_set_suspend_disable);
    /* The previous factory and coexistence tests run as a separate base suite. */
    const int errors[] = {0, -ENOMEM, -EIO, -ETIMEDOUT, -ETIMEDOUT, -ENXIO, -ETIMEDOUT};
    /* Real machine voltage constraints run before either consumer is admitted. */
    for (unsigned order = 0; order < 2; ++order)
    for (int boot = 900000; boot <= 1335000; boot += 5000) {
        struct platform_device pdev; struct device parent; struct device_node node, n, a;
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_boot(&pdev, &parent, &node, &n, &a, &rpm, &ep, order, boot);
        EXPECT(rpm_reg_probe(&pdev) == 0);
        EXPECT(boot_get_calls == 1 && boot_read_calls == 1);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500);
        struct regulator_dev *normal, *ao; get_voters(&normal, &ao);
        EXPECT(!rpm_reg_is_enabled(normal) && !rpm_reg_is_enabled(ao));
        /* Pronto may start and finish before CPR probes, or CPR may keep deferring. */
        clear_io(); EXPECT(rpm_reg_set_voltage(normal, 1287500, 1287500, NULL) == 0);
        EXPECT(rpm_reg_enable(normal) == 0);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500);
        EXPECT(rpm_reg_disable(normal) == 0);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500);
        EXPECT(boot_read_calls == 1); /* no nested APC regulator read in callbacks */
        /* An enabled request below inherited APC cannot release the boot hold. */
        clear_io(); EXPECT(rpm_reg_enable(ao) == 0);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500);
        EXPECT(rpm_reg_disable(ao) == 0);
        if (boot % 12500) {
            clear_io(); EXPECT(rpm_reg_set_voltage(ao, boot / 12500 * 12500, 1337500, NULL) == 0);
            EXPECT(rpm_reg_enable(ao) == 0);
            EXPECT(fw[0].enabled && fw[0].uV == 1337500);
            EXPECT(rpm_reg_disable(ao) == 0);
        }
        int covering = ((boot + 12499) / 12500) * 12500;
        struct cpr_voltage rails;
        clear_io(); EXPECT(boot_cpu_attach(ao, covering, &rails) == 0);
        EXPECT(rails.mx_enabled && rails.mx_min_uV == covering);
        EXPECT(fw[0].uV == (covering > 1287500 ? covering : 1287500));
        /* The temporary maximum must not become a permanent CPU scaling cap. */
        clear_io(); EXPECT(cpr_voltage_set(&rails, 900000, 900000) == 0);
        EXPECT(fw[0].uV == 1287500 && fw[0].enabled);
        EXPECT(apc_voltage == 900000 && rails.mx_min_uV == 900000);
        EXPECT(boot_read_calls == 1);
        EXPECT(!fw[1].enabled && fw[1].uV == 1287500);
        end_boot(&n, &a); ++cases;
    }
    /* The real CPU attach callback rechecks APC before a stale plan can hand off. */
    for (unsigned order = 0; order < 2; ++order) {
        struct platform_device pdev; struct device parent; struct device_node node, n, a;
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_boot(&pdev, &parent, &node, &n, &a, &rpm, &ep, order, 1000000);
        EXPECT(rpm_reg_probe(&pdev) == 0);
        struct regulator_dev *normal, *ao; get_voters(&normal, &ao);
        apc_voltage = 1300000;
        struct cpr_voltage rails;
        clear_io(); EXPECT(boot_cpu_attach(ao, 1200000, &rails) == -ERANGE);
        EXPECT(!wire_calls && !rails.mx_enabled);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500);
        clear_io(); EXPECT(boot_cpu_attach(ao, 1325000, &rails) == 0);
        EXPECT(fw[0].enabled && fw[0].uV == 1325000);
        end_boot(&n, &a); ++cases;
    }
    /* A failed handoff keeps the boot hold, including when a timeout was applied. */
    for (unsigned order = 0; order < 2; ++order)
    for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct platform_device pdev; struct device parent; struct device_node node, n, a;
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_boot(&pdev, &parent, &node, &n, &a, &rpm, &ep, order, 1310000);
        EXPECT(rpm_reg_probe(&pdev) == 0);
        struct regulator_dev *normal, *ao; get_voters(&normal, &ao);
        EXPECT(rpm_reg_set_voltage(ao, 1325000, 1337500, NULL) == 0);
        clear_io(); fault_mode = mode; fault_at = 1; apply_uncertain = applied;
        EXPECT(rpm_reg_enable(ao) == errors[mode]);
        if (mode) {
            EXPECT(!rpm_reg_is_enabled(ao));
            clear_io(); EXPECT(rpm_reg_enable(normal) == 0);
            EXPECT(fw[0].enabled && fw[0].uV == 1337500);
            EXPECT(rpm_reg_enable(ao) == 0);
        }
        EXPECT(fw[0].enabled && fw[0].uV == 1325000);
        EXPECT(boot_read_calls == 1);
        end_boot(&n, &a); ++cases;
    }
    /* Every failed registration stage must leave inherited APC covered. */
    for (unsigned order = 0; order < 2; ++order)
    for (unsigned mode = ALLOC; mode <= BOUNDARY; ++mode)
    for (unsigned stage = 1; stage <= 4; ++stage)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct platform_device pdev; struct device parent; struct device_node node, n, a;
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_boot(&pdev, &parent, &node, &n, &a, &rpm, &ep, order, 1310000);
        fault_mode = mode; fault_at = stage; apply_uncertain = applied;
        int ret = rpm_reg_probe(&pdev);
        /* SLEEP+ACTIVE for the first voter, ACTIVE+[normal SLEEP] for the second. */
        unsigned required = order ? 4 : 3;
        EXPECT(ret == (stage <= required ? errors[mode] : 0));
        EXPECT(fw[0].enabled && fw[0].uV >= 1310000);
        EXPECT(boot_read_calls == 1);
        end_boot(&n, &a); ++cases;
    }
    /* Invalid/missing APC or malformed policy must fail before any publication/RPC. */
    const int readings[] = {-EPROBE_DEFER, -EIO, 0, 1337501, 1350000, INT_MAX};
    for (unsigned scenario = 0; scenario < 15; ++scenario) {
        struct platform_device pdev; struct device parent; struct device_node node, n, a;
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_boot(&pdev, &parent, &node, &n, &a, &rpm, &ep, false, 1100000);
        if (scenario < 6) boot_read_uV = readings[scenario];
        if (scenario == 6) boot_get_error = -EPROBE_DEFER;
        if (scenario == 7) a.boot_on = true;
        if (scenario == 8) a.always_on = true;
        if (scenario == 9) a.max_uV = 2000000;
        if (scenario == 10) a.max_uV = 1335000;
        if (scenario == 11) a.min_uV = 1500000;
        if (scenario == 12) a.min_uV = 0;
        if (scenario == 13) a.available = false;
        if (scenario == 14) pdev.dev.match_data = other_pmic;
        int ret = rpm_reg_probe(&pdev);
        EXPECT(ret < 0);
        EXPECT(!live_count && !factory_registers && !wire_calls);
        end_boot(&n, &a); ++cases;
    }
    printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
    return 0;
}
