/* SPDX-License-Identifier: GPL-2.0-only */
static const int fault_errors[] = {0, -ENOMEM, -EIO, -ETIMEDOUT, -ETIMEDOUT, -ENXIO, -ETIMEDOUT};
static void init_three(struct fixture *f)
{
    init(f, true, true, 1287500, 900000, true);
    f->pair.has_sleep_only = true;
    f->pair.boot_min_uV = 900000;
    f->pair.boot_max_uV = 1337500;
    f->vreg[2] = (struct qcom_rpm_reg){.type = QCOM_SMD_RPM_LDOA, .id = 3,
        .pair = &f->pair, .sleep_only = true, .is_enabled = true, .uV = 1337500,
        .load = 17000, .desc.ops = &rpm_smps_ldo_ops};
    f->rdev[2] = (struct regulator_dev){.data = &f->vreg[2], .desc = &f->vreg[2].desc};
    f->rdev[2].dev.data = &f->rdev[2];
    f->pair.votes[2] = (struct rpm_reg_vote){true, 1337500, 17000, true};
    f->so = (struct regulator){.rdev = &f->rdev[2], .enable_count = 1};
    f->so.voltage[0] = (struct regulator_voltage){1337500, 1337500};
    f->rdev[2].consumer_list = &f->so;
    fw[1] = (struct firmware_vote){true, 1337500, 29};
    boot_safety = sleep_safety = true;
    fault_span = 0;
}
static void setup_sleep(struct platform_device *pdev, struct device *parent,
    struct device_node *bank, struct device_node nodes[3], struct qcom_smd_rpm *rpm,
    struct rpmsg_endpoint *ep, unsigned order, int apc)
{
    static const unsigned permutations[6][3] = {{0,1,2},{0,2,1},{1,0,2},{1,2,0},{2,0,1},{2,1,0}};
    setup_boot(pdev, parent, bank, &nodes[0], &nodes[1], rpm, ep, false, apc);
    nodes[2] = (struct device_node){.name = "l3-so", .available = true,
        .min_uV = 750000, .max_uV = 1337500};
    for (unsigned i = 0; i < 3; ++i)
        nodes[permutations[order][i]].next = i == 2 ? NULL : &nodes[permutations[order][i+1]];
    bank->child = &nodes[permutations[order][0]];
    sleep_safety = true; fault_span = 0;
}
static void end_sleep(struct device_node nodes[3])
{
    release_arena();
    for (unsigned i = 0; i < 3; ++i) EXPECT(!nodes[i].refs);
    EXPECT(!allocated);
    boot_safety = sleep_safety = machine_registration = false;
}
static struct regulator_dev *find_voter(const char *name)
{
    for (unsigned i = 0; i < live_count; ++i)
        if (!strcmp(registered[i]->desc->name, name)) return registered[i];
    CHECK(!"missing registered voter"); return NULL;
}
int main(void)
{
    const struct regulator_ops *ops[] = {&rpm_smps_ldo_ops_fixed, &rpm_switch_ops,
        &rpm_bob_ops, &rpm_mp5496_ops};
    for (unsigned i = 0; i < sizeof(ops) / sizeof(ops[0]); ++i)
        EXPECT(ops[i]->set_suspend_disable == rpm_reg_set_suspend_disable);
    /* Every publication order and inherited APC grid point; independent handoffs. */
    for (unsigned order = 0; order < 6; ++order)
    for (int apc = 900000; apc <= 1335000; apc += 5000) {
        struct platform_device pdev; struct device parent; struct device_node bank, nodes[3];
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_sleep(&pdev, &parent, &bank, nodes, &rpm, &ep, order, apc);
        EXPECT(rpm_reg_probe(&pdev) == 0 && live_count == 3);
        struct regulator_dev *normal = find_voter("l3"), *ao = find_voter("l3-ao"), *so = find_voter("l3-so");
        struct rpm_reg_pair *pair = voter(so)->pair;
        EXPECT(pair->has_sleep_only && pair->boot_sleep_uV == 1337500 && pair->boot_uV == 1337500);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500 && fw[1].enabled && fw[1].uV == 1337500);
        clear_io(); EXPECT(rpm_reg_set_voltage(so, 1337500, 1337500, NULL) == 0);
        EXPECT(rpm_reg_enable(so) == 0);
        for (unsigned i = 0; i < wire_calls; ++i) EXPECT(states[i] == QCOM_SMD_RPM_SLEEP_STATE);
        EXPECT(pair->boot_sleep_uV == 0 && pair->boot_uV == 1337500);
        struct cpr_voltage rails;
        clear_io(); EXPECT(boot_cpu_attach(ao, 1337500, &rails) == 0);
        EXPECT(pair->boot_uV == 0 && fw[1].uV == 1337500);
        clear_io(); EXPECT(cpr_voltage_set(&rails, 900000, 900000) == 0);
        EXPECT(fw[0].uV == 900000 && fw[1].uV == 1337500);
        EXPECT(rpm_reg_set_suspend_disable(normal) == 0);
        EXPECT(rpm_reg_set_suspend_voltage(normal, 750000) == 0);
        EXPECT(fw[1].enabled && fw[1].uV == 1337500);
        EXPECT(rpm_reg_disable(so) == 0 && pair->boot_sleep_uV == 1337500);
        EXPECT(fw[1].enabled && fw[1].uV == 1337500);
        end_sleep(nodes); ++cases;
    }
    /* SO only changes SLEEP; AO only changes ACTIVE after SLEEP initialization. */
    for (unsigned actor = 0; actor < 3; ++actor)
    for (int uv = 750000; uv <= 1337500; uv += 12500) {
        struct fixture f; init_three(&f);
        if (actor == 2) sleep_safety = false; /* Prepared low floor is not permission to enter SLEEP. */
        struct firmware_vote before_active = fw[0], before_sleep = fw[1];
        EXPECT(rpm_reg_set_voltage(&f.rdev[actor], uv, 1337500, NULL) == 0);
        int wanted_active = actor == 0 ? (uv > 900000 ? uv : 900000) : actor == 1 ? (uv > 1287500 ? uv : 1287500) : 1287500;
        int wanted_sleep = actor == 2 ? (uv > 1287500 ? uv : 1287500) : 1337500;
        EXPECT(fw[0].uV == wanted_active && fw[1].uV == wanted_sleep);
        if (actor == 2) { EXPECT(wire_calls == 1 && states[0] == 1); EXPECT(fw[0].uV == before_active.uV); }
        if (actor == 1) { EXPECT(wire_calls == 1 && states[0] == 0); EXPECT(fw[1].uV == before_sleep.uV); }
        EXPECT(rpm_reg_set_suspend_disable(&f.rdev[2]) == -EOPNOTSUPP);
        EXPECT(rpm_reg_set_suspend_voltage(&f.rdev[1], 750000) == -EOPNOTSUPP);
        healthy(&f); ++cases;
    }
    /* All error classes, applied/unapplied timeout, all three voters, all packet stages. */
    for (unsigned actor = 0; actor < 3; ++actor)
    for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied)
    for (unsigned initialized = 0; initialized < 2; ++initialized)
    for (unsigned stage = 1; stage <= 3; ++stage) {
        struct fixture f; init_three(&f); f.pair.sleep_initialized = initialized;
        unsigned needed = actor == 2 ? 1 : (!initialized || actor == 0 ? 2 : 1);
        struct rpm_reg_vote previous = f.pair.votes[actor];
        clear_io(); fault_mode = mode; fault_at = stage; apply_uncertain = applied;
        int ret = rpm_reg_set_load(&f.rdev[actor], 27000);
        EXPECT(ret == (stage <= needed ? fault_errors[mode] : 0));
        if (ret) { EXPECT(same_vote(f.pair.votes[actor], previous)); EXPECT(!f.pair.sleep_initialized); }
        clear_io(); EXPECT(rpm_reg_set_load(&f.rdev[actor], 27000) == 0);
        EXPECT(fw[0].enabled && fw[0].uV == 1287500 && fw[1].enabled && fw[1].uV == 1337500);
        EXPECT(fw[0].mA == (actor == 0 ? 48 : actor == 1 ? 39 : 33));
        EXPECT(fw[1].mA == (actor == 0 ? 44 : actor == 2 ? 39 : 29));
        healthy(&f); ++cases;
    }
    /* Actual class suspend: enable update persists when the later voltage update fails. */
    for (unsigned mode = ALLOC; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct fixture f; init_three(&f);
        struct regulation_constraints policy = {.state_mem = {.enabled = DISABLE_IN_SUSPEND, .uV = 750000}};
        f.rdev[0].constraints = &policy; pm_suspend_target_state = PM_SUSPEND_MEM;
        clear_io(); fault_mode = mode; fault_at = 2; apply_uncertain = applied;
        EXPECT(regulator_suspend(&f.rdev[0].dev) == fault_errors[mode]);
        EXPECT(f.pair.sleep_enable_valid && !f.pair.sleep_enabled && !f.pair.sleep_voltage_valid);
        EXPECT(fw[1].enabled && fw[1].uV == 1337500);
        /* Failed devices are not marked suspended by PM core: no resume is required here. */
        clear_io(); EXPECT(rpm_reg_set_voltage(&f.rdev[1], 950000, 1337500, NULL) == 0);
        EXPECT(fw[1].enabled && fw[1].uV == 1337500);
        EXPECT(regulator_suspend(&f.rdev[0].dev) == 0);
        EXPECT(!f.pair.sleep_enabled && f.pair.sleep_uV == 750000 && fw[1].uV == 1337500);
        clear_io(); EXPECT(regulator_resume(&f.rdev[0].dev) == 0);
        EXPECT(!wire_calls && !f.pair.sleep_enabled && f.pair.sleep_uV == 750000);
        healthy(&f); ++cases;
    }
    /* Bindings cannot be trusted at runtime: reject malformed SO policy before RPC. */
    for (unsigned order = 0; order < 6; ++order)
    for (unsigned scenario = 1; scenario <= 15; ++scenario) {
        struct platform_device pdev; struct device parent; struct device_node bank, nodes[3];
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_sleep(&pdev, &parent, &bank, nodes, &rpm, &ep, order, 1100000);
        if (scenario == 1) nodes[0].available = false;
        if (scenario == 2) pdev.dev.match_data = other_pmic;
        if (scenario == 3) nodes[2].min_uV = 0;
        if (scenario == 4) nodes[2].max_uV = 0;
        if (scenario == 5) nodes[2].min_uV = 1350000;
        if (scenario == 6) nodes[2].max_uV = 1325000;
        if (scenario == 7) nodes[2].max_uV = 1550000;
        if (scenario == 8) nodes[2].min_uV = 751000;
        if (scenario == 9) nodes[2].max_uV = 1337000;
        if (scenario == 10) nodes[2].boot_on = true;
        if (scenario == 11) nodes[2].always_on = true;
        if (scenario == 12) nodes[1].available = false;
        if (scenario == 13) boot_get_error = -EPROBE_DEFER;
        if (scenario == 14) boot_read_uV = 0;
        if (scenario == 15) boot_read_uV = 1350000;
        int ret = rpm_reg_probe(&pdev);
        EXPECT(ret == (scenario == 13 ? -EPROBE_DEFER : scenario == 15 ? -ERANGE : -EINVAL));
        EXPECT(!wire_calls && !live_count && !factory_registers);
        end_sleep(nodes); ++cases;
    }
    /* Allocation and registration failures at every devres lifetime boundary. */
    for (unsigned order = 0; order < 6; ++order)
    for (unsigned alloc_fail = 0; alloc_fail <= 4; ++alloc_fail)
    for (unsigned reg_fail = 0; reg_fail <= 3; ++reg_fail) {
        struct platform_device pdev; struct device parent; struct device_node bank, nodes[3];
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_sleep(&pdev, &parent, &bank, nodes, &rpm, &ep, order, 1100000);
        fail_allocate = alloc_fail; fail_register = reg_fail;
        int wanted = alloc_fail && (!reg_fail || alloc_fail <= reg_fail + 1) ? -ENOMEM : reg_fail ? -EIO : 0;
        EXPECT(rpm_reg_probe(&pdev) == wanted);
        EXPECT(fw[0].enabled && fw[0].uV >= apc_voltage);
        end_sleep(nodes); ++cases;
    }
    /* Registration's actual voltage constraints can fail at any correlated write. */
    for (unsigned order = 0; order < 6; ++order)
    for (unsigned mode = ALLOC; mode <= BOUNDARY; ++mode)
    for (unsigned stage = 1; stage <= 6; ++stage)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct platform_device pdev; struct device parent; struct device_node bank, nodes[3];
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_sleep(&pdev, &parent, &bank, nodes, &rpm, &ep, order, 1100000);
        fault_mode = mode; fault_at = stage; apply_uncertain = applied;
        unsigned needed = order == 2 || order == 3 ? 5 : 4;
        EXPECT(rpm_reg_probe(&pdev) == (stage <= needed ? fault_errors[mode] : 0));
        EXPECT(fw[0].enabled && fw[0].uV >= apc_voltage);
        end_sleep(nodes); ++cases;
    }
    /* SO works without AO for non-CPU consumers when no APC boot guard is requested. */
    for (unsigned order = 0; order < 6; ++order) {
        struct platform_device pdev; struct device parent; struct device_node bank, nodes[3];
        struct qcom_smd_rpm rpm; struct rpmsg_endpoint ep;
        setup_sleep(&pdev, &parent, &bank, nodes, &rpm, &ep, order, 1100000);
        nodes[1].available = false; bank.boot_apc = false; boot_safety = sleep_safety = false;
        EXPECT(rpm_reg_probe(&pdev) == 0 && live_count == 2);
        EXPECT(!boot_get_calls && !boot_read_calls);
        struct regulator_dev *so = find_voter("l3-so");
        clear_io(); EXPECT(rpm_reg_set_voltage(so, 1000000, 1337500, NULL) == 0);
        EXPECT(rpm_reg_enable(so) == 0);
        for (unsigned i = 0; i < wire_calls; ++i) EXPECT(states[i] == 1);
        EXPECT(fw[0].enabled && fw[0].uV == 1100000 && fw[1].enabled && fw[1].uV == 1000000);
        end_sleep(nodes); ++cases;
    }
    /* Two cleanup failures are explicitly fatal; model the policy without a kernel panic. */
    for (unsigned mode = ALLOC; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied) {
        static struct fixture f; init_three(&f); reset_client(&f.so);
        clear_io(); fault_mode = mode; fault_at = 1; fault_span = 2; apply_uncertain = applied;
        expect_fatal = true; fatal_calls = 0;
        if (!setjmp(fatal_target)) {
            cpr_sleep_vote_disable(&f.so);
            EXPECT(!"persistent disable failure must stop");
        }
        expect_fatal = false;
        EXPECT(fatal_calls == 1 && disable_calls == 2 && f.so.enable_count == 1);
        EXPECT(f.pair.boot_sleep_uV == 1337500);
        clear_io(); fault_span = 0;
        EXPECT(regulator_disable(&f.so) == 0);
        EXPECT(fw[1].enabled && fw[1].uV == 1337500);
        healthy(&f); ++cases;
    }
    /* Overflow saturates the summed load; disabled cached voltage still participates. */
    for (unsigned actor = 0; actor < 3; ++actor) {
        struct fixture f; init_three(&f);
        f.vreg[0].load = UINT32_MAX; f.pair.votes[0].load = UINT32_MAX;
        EXPECT(rpm_reg_set_load(&f.rdev[actor], 21000) == 0);
        if (actor != 0) EXPECT(fw[actor == 1 ? 0 : 1].mA == UINT32_MAX / 1000);
        EXPECT(rpm_reg_disable(&f.rdev[0]) == 0);
        EXPECT(fw[0].uV == 1287500 && fw[0].enabled);
        healthy(&f); ++cases;
    }
    /* A high AO request must never contaminate a deliberately prepared SLEEP floor. */
    for (int uv = 750000; uv <= 1337500; uv += 12500) {
        struct fixture f; init_three(&f); sleep_safety = false;
        f.vreg[0].uV = 750000; f.pair.votes[0].uV = 750000;
        f.vreg[1].uV = 1337500; f.pair.votes[1].uV = 1337500;
        fw[0].uV = 1337500;
        EXPECT(rpm_reg_set_voltage(&f.rdev[2], uv, 1337500, NULL) == 0);
        EXPECT(fw[1].uV == uv && fw[0].uV == 1337500);
        EXPECT(rpm_reg_set_suspend_voltage(&f.rdev[0], 750000) == 0);
        EXPECT(fw[1].uV == uv);
        healthy(&f); ++cases;
    }
    /* The real CPR helper balances its vote before managed put, including probe failure. */
    for (unsigned scenario = 0; scenario < 9; ++scenario)
    for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct fixture f; init_three(&f);
        f.vreg[2].is_enabled = false; f.pair.votes[2].enabled = false; f.so.enable_count = 0;
        f.pair.boot_sleep_uV = 1337500;
        reset_client(&f.so);
        struct device_node node = {.sleep_supply = scenario != 1};
        struct device dev = {.of_node = &node}; struct regulator *out = (void *)1;
        int max_uv = scenario == 2 ? 0 : 1337500;
        if (scenario == 3) sleep_get_error = -EPROBE_DEFER;
        if (scenario == 4) action_error = -ENOMEM;
        if (scenario == 5 || scenario == 6) { fault_mode = mode; fault_at = scenario == 5 ? 1 : 2; apply_uncertain = applied; }
        int ret = cpr_sleep_vote_init(&dev, max_uv, &out);
        int wanted = scenario == 2 ? -EINVAL : scenario == 3 ? -EPROBE_DEFER : scenario == 4 ? -ENOMEM :
            (scenario == 5 || scenario == 6) ? fault_errors[mode] : 0;
        EXPECT(ret == wanted);
        if (ret || scenario == 1) {
            EXPECT(!out && !f.so.enable_count && !cleanup_action);
            EXPECT(f.pair.boot_sleep_uV == 1337500);
        } else {
            EXPECT(out == &f.so && f.so.enable_count == 1 && cleanup_action);
            EXPECT(f.pair.boot_sleep_uV == 0);
            clear_io();
            if (scenario == 7 || scenario == 8) { fault_mode = mode; fault_at = 1; apply_uncertain = applied; }
            managed_release();
            EXPECT(disable_calls == ((scenario == 7 || scenario == 8) && mode ? 2 : 1));
            EXPECT(managed_puts == 1 && !f.so.enable_count);
            EXPECT(f.pair.boot_sleep_uV == 1337500);
        }
        EXPECT(fw[1].enabled && fw[1].uV == 1337500);
        healthy(&f); ++cases;
    }
    /* A failed SO disable must retain its rearmed ceiling even after a normal write. */
    for (unsigned mode = ALLOC; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct fixture f; init_three(&f);
        EXPECT(rpm_reg_set_voltage(&f.rdev[2], 1000000, 1337500, NULL) == 0);
        clear_io(); fault_mode = mode; fault_at = 1; apply_uncertain = applied;
        EXPECT(rpm_reg_disable(&f.rdev[2]) == fault_errors[mode]);
        EXPECT(f.pair.boot_sleep_uV == 1337500 && f.pair.votes[2].enabled);
        clear_io(); EXPECT(rpm_reg_set_suspend_voltage(&f.rdev[0], 750000) == 0);
        EXPECT(fw[1].enabled && fw[1].uV == 1337500 && f.pair.boot_sleep_uV == 1337500);
        healthy(&f); ++cases;
    }
    printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
    return 0;
}
