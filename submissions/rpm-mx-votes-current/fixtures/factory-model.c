/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical OF/devres/registration services for the exact provider factory. */
#define ENODEV 19
#define QCOM_SMD_RPM_VSA 0x00617376
#define THIS_MODULE NULL
#define REGULATOR_VOLTAGE 1
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((intptr_t)(p))
struct device_node { const char *name; bool available; int refs; struct device_node *child, *next; };
struct platform_device { struct device dev; };
struct regulator_config { struct device *dev; struct device_node *of_node; void *driver_data; };
static const struct regulator_desc pm8226_hfsmps = {.ops = &rpm_smps_ldo_ops};
static const struct regulator_desc pm8226_ftsmps = {.ops = &rpm_smps_ldo_ops};
static const struct regulator_desc pm8226_nldo = {.ops = &rpm_smps_ldo_ops};
static const struct regulator_desc pm8226_pldo = {.ops = &rpm_smps_ldo_ops};
static const struct regulator_desc pm8226_switch = {.ops = &rpm_switch_ops};
/* ACTUAL_CATALOGUE */
static const struct rpm_regulator_data other_pmic[] = {{.name = "l3", .type = QCOM_SMD_RPM_LDOA,
    .id = 3, .desc = &pm8226_nldo, .supply = "test"}, {}};
struct devres_entry { void *ptr; size_t size; bool rdev; };
static struct devres_entry arena[16];
static unsigned arena_count, factory_allocs, factory_registers, fail_allocate, fail_register;
static bool registration_callbacks;
static struct regulator_dev *registered[8];
static unsigned live_count;
static void mutex_init(struct mutex *m) { m->held = 0; }
static int dev_err_probe(struct device *dev, int error, const char *fmt) { return error; }
static const void *of_device_get_match_data(struct device *dev) { return dev->match_data; }
static bool of_node_name_eq(struct device_node *node, const char *name) { return !strcmp(node->name, name); }
static struct device_node *of_get_available_child_by_name(const struct device_node *node, const char *name)
{
    for (struct device_node *p = node->child; p; p = p->next)
        if (p->available && !strcmp(p->name, name)) { ++p->refs; return p; }
    return NULL;
}
static void of_node_put(struct device_node *node) { if (node) { EXPECT(node->refs > 0); --node->refs; } }
static void node_cleanup(struct device_node **node) { of_node_put(*node); }
static struct device_node *next_child(struct device_node *parent, struct device_node *old)
{
    struct device_node *p = old ? old->next : parent->child;
    of_node_put(old);
    while (p && !p->available) p = p->next;
    if (p) ++p->refs;
    return p;
}
#define for_each_available_child_of_node_scoped(parent, node) \
    for (struct device_node *node __attribute__((cleanup(node_cleanup))) = next_child(parent, NULL); \
        node; node = next_child(parent, node))
static void *arena_alloc(size_t size, bool rdev)
{
    CHECK(arena_count < 16);
    void *p = calloc(1, size); CHECK(p);
    arena[arena_count++] = (struct devres_entry){p, size, rdev};
    return p;
}
static void *devm_allocate(struct device *dev, size_t size)
{
    if (++factory_allocs == fail_allocate) return NULL;
    return arena_alloc(size, false);
}
#define devm_kzalloc_obj(dev, object) devm_allocate(dev, sizeof(object))
#define GFP_KERNEL 0
static void *devm_kzalloc(struct device *dev, size_t size, int flags) { return devm_allocate(dev, size); }
static struct regulator_dev *devm_regulator_register(struct device *dev,
    struct regulator_desc *desc, struct regulator_config *config)
{
    if (++factory_registers == fail_register) return ERR_PTR(-EIO);
    CHECK(live_count < 8);
    struct regulator_dev *rdev = arena_alloc(sizeof(*rdev), true);
    rdev->data = config->driver_data; rdev->desc = desc; rdev->dev.data = rdev;
    registered[live_count++] = rdev;
    struct qcom_rpm_reg *vreg = rdev_get_drvdata(rdev);
    EXPECT(!strcmp(vreg->desc.name, config->of_node->name));
    EXPECT(!strcmp(vreg->desc.of_match, config->of_node->name));
    EXPECT(vreg->dev == dev && config->dev == dev);
    if (registration_callbacks && vreg->pair) {
        EXPECT(arena[0].ptr == vreg->pair && arena[0].size == sizeof(*vreg->pair));
        expected_pair = vreg->pair;
        EXPECT(rpm_reg_set_voltage(rdev, vreg->active_only ? 1337500 : 1287500, 1337500, NULL) == 0);
        EXPECT(rpm_reg_enable(rdev) == 0);
    }
    return rdev;
}
/* ACTUAL_PROBE */
static void release_arena(void)
{
    while (arena_count) {
        struct devres_entry *e = &arena[--arena_count];
        if (e->rdev) {
            for (unsigned i = 0; i < live_count; ++i) if (registered[i] == e->ptr) registered[i] = NULL;
        }
        free(e->ptr);
        /* Remaining registered consumers may still vote during reverse devres release. */
        for (unsigned i = 0; i < live_count; ++i) if (registered[i]) {
            struct qcom_rpm_reg *vreg = rdev_get_drvdata(registered[i]);
            if (registration_callbacks && vreg->pair) {
                expected_pair = vreg->pair; clear_io();
                EXPECT(rpm_reg_set_voltage(registered[i], 1300000, 1337500, NULL) == 0);
                EXPECT(fw[0].enabled && fw[0].uV >= 1300000);
            }
        }
    }
    live_count = 0; expected_pair = NULL;
}
static void factory_tests(void)
{
    for (unsigned order = 0; order < 2; ++order)
    for (unsigned scenario = 0; scenario < 7; ++scenario)
    for (unsigned alloc_fail = 0; alloc_fail <= 3; ++alloc_fail)
    for (unsigned reg_fail = 0; reg_fail <= 2; ++reg_fail) {
        struct qcom_smd_rpm rpm = {0};
        struct rpmsg_endpoint ep = {.rpm = &rpm}; rpm.rpm_channel = &ep;
        struct device parent = {.data = &rpm};
        struct device_node normal = {.name = "l3", .available = scenario != 2};
        struct device_node ao = {.name = "l3-ao", .available = scenario != 1};
        struct device_node node = {.child = order ? &ao : &normal};
        if (order) ao.next = &normal; else normal.next = &ao;
        if (scenario == 3) { node.child = &ao; ao.next = NULL; }
        struct platform_device pdev = {.dev = {.parent = &parent, .of_node = &node,
            .match_data = scenario == 4 ? other_pmic : rpm_pm8226_regulators}};
        if (scenario == 5) parent.data = NULL;
        if (scenario == 6) pdev.dev.match_data = NULL;
        smd_vreg_rpm = NULL; clear_io();
        memset(fw, 0, sizeof(fw));
        factory_allocs = factory_registers = arena_count = live_count = 0;
        fail_allocate = alloc_fail; fail_register = reg_fail;
        registration_callbacks = scenario == 0;
        int ret = rpm_reg_probe(&pdev);
        if (scenario == 2 || scenario == 3 || scenario == 4) EXPECT(ret == -EINVAL);
        else if (scenario == 5 || scenario == 6) EXPECT(ret == -ENODEV);
        else {
            unsigned allocs_needed = scenario == 1 ? 1 : 3;
            unsigned regs_needed = scenario == 1 ? 1 : 2;
            bool alloc_reached = alloc_fail && alloc_fail <= allocs_needed;
            bool reg_reached = reg_fail && reg_fail <= regs_needed;
            /* Pair allocation comes before either vreg, then registration interleaves. */
            int expected = 0;
            if (scenario == 1) {
                if (alloc_reached) expected = -ENOMEM; else if (reg_reached) expected = -EIO;
            } else {
                if (alloc_reached && (!reg_reached || alloc_fail <= reg_fail + 1)) expected = -ENOMEM;
                else if (reg_reached) expected = -EIO;
            }
            EXPECT(ret == expected);
            for (unsigned i = 0; i < live_count; ++i) {
                struct qcom_rpm_reg *vreg = rdev_get_drvdata(registered[i]);
                EXPECT((vreg->pair != NULL) == (scenario == 0));
                EXPECT(vreg->active_only == !strcmp(vreg->desc.name, "l3-ao"));
            }
            if (!ret && scenario == 0) {
                EXPECT(live_count == 2);
                struct qcom_rpm_reg *first = rdev_get_drvdata(registered[0]);
                struct qcom_rpm_reg *second = rdev_get_drvdata(registered[1]);
                EXPECT(first->pair == second->pair);
                EXPECT(fw[0].enabled && fw[0].uV == 1337500);
                EXPECT(fw[1].enabled && fw[1].uV == 1287500);
            }
        }
        release_arena();
        EXPECT(normal.refs == 0 && ao.refs == 0);
        EXPECT(!allocated && !rpm.waiting && !rpm.lock.held);
        ++cases;
    }
    smd_vreg_rpm = NULL;
}
