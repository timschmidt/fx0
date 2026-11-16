/* SPDX-License-Identifier: GPL-2.0-only */
/* Logical services; actual provider, regulator-core and CPR bodies are composed above. */
enum { FAST, ALLOC, SEND, SILENT, STALE, NACK, BOUNDARY };
static unsigned cases, checks, failures, alloc_calls, wire_calls;
static unsigned fault_mode, fault_at, current_fault;
static bool apply_uncertain;
static u32 last_id;
static struct rpm_reg_pair *expected_pair;
struct firmware_vote { bool enabled; int uV; u32 mA; };
static struct firmware_vote fw[2];
static unsigned states[32];
static unsigned apc_calls, event_count;
static int apc_voltage, apc_error;
static char events[64];
static bool reported[4096];
#define EXPECT(x) do { ++checks; if (!(x)) { ++failures; \
    CHECK(__LINE__ < 4096); \
    if (!reported[__LINE__]) fprintf(stderr, "check failed at %d: %s\n", __LINE__, #x); \
    reported[__LINE__] = true; \
    } } while (0)
static void event(char c) { CHECK(event_count < sizeof(events)); events[event_count++] = c; }
static void *kmalloc(size_t size, int flags)
{
    ++alloc_calls;
    current_fault = alloc_calls == fault_at ? fault_mode : FAST;
    if (current_fault == ALLOC) return NULL;
    ++allocated;
    return malloc(size);
}
static void put32(u8 *p, u32 value)
{
    for (unsigned i = 0; i < 4; ++i) p[i] = value >> (8 * i);
}
static void reply(struct qcom_smd_rpm *rpm, u32 id, bool nack)
{
    u32 words[16] = {0};
    u8 *data = (u8 *)words;
    size_t size = 20;
    put32(data, RPM_SERVICE_TYPE_REQUEST);
    put32(data + 8, RPM_MSG_TYPE_MSG_ID);
    put32(data + 12, 4);
    put32(data + 16, id);
    if (nack) {
        const char error[] = "resource does not exist";
        put32(data + 20, RPM_MSG_TYPE_ERR);
        put32(data + 24, sizeof(error));
        memcpy(data + 28, error, sizeof(error));
        size = 28 + ALIGN(sizeof(error), 4);
    }
    put32(data + 4, size - 8);
    struct rpmsg_device rpdev = {.dev.data = rpm};
    CHECK(qcom_smd_rpm_callback(&rpdev, data, size, NULL, 0) == 0);
}
static void complete(struct completion *c) { ++c->done; }
static int rpmsg_send(struct rpmsg_endpoint *ep, void *data, size_t size)
{
    u8 *p = data;
    EXPECT(expected_pair && expected_pair->lock.held);
    EXPECT(size >= 40 && size <= 64 && (size - 28) % 12 == 0);
    EXPECT(get_unaligned_le32(p) == RPM_SERVICE_TYPE_REQUEST);
    EXPECT(get_unaligned_le32(p + 4) == size - 8);
    last_id = get_unaligned_le32(p + 8);
    EXPECT(last_id != 0);
    unsigned state = get_unaligned_le32(p + 12);
    CHECK(state <= 1 && wire_calls < 32);
    states[wire_calls++] = state;
    event(state ? 'S' : 'M');
    EXPECT(get_unaligned_le32(p + 16) == QCOM_SMD_RPM_LDOA);
    EXPECT(get_unaligned_le32(p + 20) == 3);
    EXPECT(get_unaligned_le32(p + 24) == size - 28);
    EXPECT(ep->rpm->lock.held && !ep->rpm->ack_lock.held);
    struct firmware_vote proposed = fw[state];
    unsigned keys = 0;
    for (size_t off = 28; off < size; off += 12) {
        u32 key = get_unaligned_le32(p + off), value = get_unaligned_le32(p + off + 8);
        EXPECT(get_unaligned_le32(p + off + 4) == 4);
        if (key == RPM_KEY_SWEN) { EXPECT(!(keys & 1)); keys |= 1; proposed.enabled = value; }
        else if (key == RPM_KEY_UV) { EXPECT(!(keys & 2)); keys |= 2; proposed.uV = value; }
        else if (key == RPM_KEY_MA) { EXPECT(!(keys & 4)); keys |= 4; proposed.mA = value; }
        else EXPECT(!"known KVP key");
    }
    bool uncertain = current_fault == SILENT || current_fault == STALE || current_fault == BOUNDARY;
    if (current_fault == FAST || (uncertain && apply_uncertain)) fw[state] = proposed;
    if (current_fault == SEND) return -EIO;
    if (current_fault == FAST) reply(ep->rpm, last_id, false);
    if (current_fault == STALE) reply(ep->rpm, last_id + 1, false);
    if (current_fault == NACK) reply(ep->rpm, last_id, true);
    return 0;
}
static int wait_for_completion_timeout(struct completion *c, int timeout)
{
    CHECK(timeout == RPM_REQUEST_TIMEOUT);
    struct qcom_smd_rpm *rpm = container_of(c, struct qcom_smd_rpm, ack);
    if (current_fault == BOUNDARY) { reply(rpm, last_id, false); return 0; }
    if (current_fault == SILENT || current_fault == STALE) EXPECT(!c->done);
    if (c->done) { --c->done; return 1; }
    return 0;
}
static int regulator_set_voltage(struct regulator *reg, int min_uV, int max_uV)
{
    if (reg->apc) {
        event('A'); ++apc_calls;
        EXPECT(min_uV == max_uV);
        if (apc_error) return apc_error;
        EXPECT(fw[QCOM_SMD_RPM_ACTIVE_STATE].enabled);
        EXPECT(fw[QCOM_SMD_RPM_ACTIVE_STATE].uV >= min_uV);
        apc_voltage = min_uV;
        return 0;
    }
    struct regulator_voltage old = reg->voltage[PM_SUSPEND_ON];
    reg->voltage[PM_SUSPEND_ON] = (struct regulator_voltage){min_uV, max_uV};
    int low = min_uV, high = max_uV;
    int ret = regulator_check_consumers(reg->rdev, &low, &high, PM_SUSPEND_ON);
    if (!ret) ret = rpm_reg_set_voltage(reg->rdev, low, high, NULL);
    if (ret) reg->voltage[PM_SUSPEND_ON] = old;
    return ret;
}
static int regulator_sync_voltage(struct regulator *reg)
{
    int low = 750000, high = 1337500;
    int ret = regulator_check_consumers(reg->rdev, &low, &high, PM_SUSPEND_ON);
    if (!ret) ret = rpm_reg_set_voltage(reg->rdev, low, high, NULL);
    return ret;
}
static int regulator_enable(struct regulator *reg) { return rpm_reg_enable(reg->rdev); }
#define panic(...) CHECK(!"unexpected recovery panic")
/* ACTUAL_CPR */
struct fixture {
    struct rpm_reg_pair pair;
    struct qcom_rpm_reg vreg[2];
    struct regulator_dev rdev[2];
    struct regulator normal, ao, apc;
    struct qcom_smd_rpm rpm;
    struct rpmsg_endpoint ep;
};
static void clear_io(void)
{
    alloc_calls = wire_calls = 0;
    event_count = apc_calls = 0;
    fault_at = 0; fault_mode = FAST; apc_error = 0;
}
static void init(struct fixture *f, bool n_enabled, bool a_enabled, int nv, int av, bool initialized)
{
    memset(f, 0, sizeof(*f)); clear_io();
    f->ep.rpm = &f->rpm; f->rpm.rpm_channel = &f->ep;
    f->rpm.msg_id = UINT32_MAX; /* include wrap and stale nonzero replies */
    smd_vreg_rpm = &f->rpm; expected_pair = &f->pair;
    f->pair.sleep_initialized = initialized;
    for (unsigned i = 0; i < 2; ++i) {
        f->vreg[i].type = QCOM_SMD_RPM_LDOA; f->vreg[i].id = 3;
        f->vreg[i].pair = &f->pair; f->vreg[i].active_only = i;
        f->vreg[i].is_enabled = i ? a_enabled : n_enabled;
        f->vreg[i].uV = i ? av : nv;
        f->vreg[i].load = i ? 21000 : 12000;
        f->vreg[i].desc.ops = &rpm_smps_ldo_ops;
        f->rdev[i].data = &f->vreg[i]; f->rdev[i].desc = &f->vreg[i].desc;
        f->rdev[i].dev.data = &f->rdev[i];
        f->pair.votes[i] = (struct rpm_reg_vote){f->vreg[i].is_enabled, f->vreg[i].uV, f->vreg[i].load, true};
    }
    f->normal.rdev = &f->rdev[0]; f->ao.rdev = &f->rdev[1];
    f->normal.voltage[0] = (struct regulator_voltage){nv, nv};
    f->ao.voltage[0] = (struct regulator_voltage){av, 1337500};
    f->rdev[0].consumer_list = &f->normal; f->rdev[1].consumer_list = &f->ao;
    f->apc.apc = true;
    fw[0] = (struct firmware_vote){n_enabled || a_enabled, nv > av ? nv : av, 33};
    fw[1] = initialized ? (struct firmware_vote){n_enabled, nv, 12} : fw[0];
    apc_voltage = 900000;
}
static bool same_vote(struct rpm_reg_vote a, struct rpm_reg_vote b)
{
    return a.enabled == b.enabled && a.uV == b.uV && a.load == b.load && a.load_valid == b.load_valid;
}
static void healthy(struct fixture *f)
{
    EXPECT(!allocated && !f->rpm.waiting && !f->rpm.lock.held && !f->rpm.ack_lock.held && !f->pair.lock.held);
}
int main(void)
{
    const struct regulator_ops *other_ops[] = {&rpm_smps_ldo_ops_fixed, &rpm_switch_ops,
        &rpm_bob_ops, &rpm_mp5496_ops};
    for (unsigned i = 0; i < sizeof(other_ops) / sizeof(other_ops[0]); ++i)
        EXPECT(other_ops[i]->set_suspend_disable == rpm_reg_set_suspend_disable);
    const int errors[] = {0, -ENOMEM, -EIO, -ETIMEDOUT, -ETIMEDOUT, -ENXIO, -ETIMEDOUT};
    /* A disabled Pronto request still participates in the exact core function. */
    for (int floor = 750000; floor <= 1337500; floor += 12500)
    for (int refs = 0; refs <= 1; ++refs) {
        struct fixture f; init(&f, false, true, 1287500, floor, true);
        f.normal.enable_count = refs;
        f.normal.next = &f.ao;
        f.rdev[0].consumer_list = &f.normal;
        int low = floor, high = 1337500;
        EXPECT(regulator_check_consumers(&f.rdev[0], &low, &high, 0) == (floor > 1287500 ? -EINVAL : 0));
        EXPECT(high == 1287500);
        f.normal.next = NULL; low = floor; high = 1337500;
        EXPECT(regulator_check_consumers(&f.rdev[1], &low, &high, 0) == 0);
        EXPECT(low == floor && high == 1337500);
        EXPECT(rpm_reg_set_voltage(&f.rdev[1], low, high, NULL) == 0);
        EXPECT(fw[0].enabled && fw[0].uV == (floor > 1287500 ? floor : 1287500));
        EXPECT(fw[1].uV == 1287500 && !fw[1].enabled);
        ++cases; healthy(&f);
    }
    /* Exercise each actual callback, both firmware timeout outcomes and failures at each write. */
    for (unsigned ne = 0; ne < 2; ++ne)
    for (unsigned ae = 0; ae < 2; ++ae)
    for (unsigned si = 0; si < 2; ++si)
    for (unsigned actor = 0; actor < 2; ++actor)
    for (unsigned op = 0; op < 5; ++op)
    for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
    for (unsigned stage = 1; stage <= 3; ++stage)
    for (unsigned applied = 0; applied < 2; ++applied) {
        struct fixture f; init(&f, ne, ae, 1287500, 1337500, si);
        struct rpm_reg_vote old[2] = {f.pair.votes[0], f.pair.votes[1]};
        struct rpm_reg_vote desired[2] = {old[0], old[1]};
        if (op == 0) desired[actor].enabled = true;
        if (op == 1) desired[actor].enabled = false;
        if (op == 2) desired[actor].uV = 1300000;
        if (op == 3) desired[actor].load = 34000;
        if (op == 4) desired[actor].uV = 750000;
        bool cached = !desired[0].enabled && !desired[1].enabled && op > 1;
        unsigned required = cached ? 0 : !si ? 2 : actor ? 1 : 2;
        bool failed = mode != FAST && stage <= required;
        fault_mode = mode; fault_at = stage; apply_uncertain = applied;
        int ret;
        if (op == 0) ret = rpm_reg_enable(&f.rdev[actor]);
        else if (op == 1) ret = rpm_reg_disable(&f.rdev[actor]);
        else if (op == 3) ret = rpm_reg_set_load(&f.rdev[actor], 34000);
        else ret = rpm_reg_set_voltage(&f.rdev[actor], desired[actor].uV, 1337500, NULL);
        EXPECT(ret == (failed ? errors[mode] : 0));
        EXPECT(alloc_calls == (failed ? stage : required));
        EXPECT(wire_calls == alloc_calls - (unsigned)(failed && mode == ALLOC));
        if (failed) {
            EXPECT(same_vote(f.pair.votes[actor], old[actor]));
            EXPECT(f.vreg[actor].uV == old[actor].uV);
            EXPECT(f.vreg[actor].is_enabled == old[actor].enabled);
            EXPECT(f.vreg[actor].load == old[actor].load);
            EXPECT(!f.pair.sleep_initialized);
        } else {
            EXPECT(same_vote(f.pair.votes[actor], desired[actor]));
            if (!cached) {
                EXPECT(fw[0].enabled == (desired[0].enabled || desired[1].enabled));
                EXPECT(fw[0].uV == (desired[0].uV > desired[1].uV ? desired[0].uV : desired[1].uV));
                EXPECT(fw[0].mA == (desired[0].load + desired[1].load) / 1000);
                EXPECT(fw[1].enabled == desired[0].enabled);
                EXPECT(fw[1].uV == desired[0].uV);
                EXPECT(fw[1].mA == desired[0].load / 1000);
                EXPECT(f.pair.sleep_initialized);
            }
        }
        EXPECT(same_vote(f.pair.votes[!actor], old[!actor]));
        if (wire_calls) EXPECT(states[0] == (!si ? QCOM_SMD_RPM_SLEEP_STATE : QCOM_SMD_RPM_ACTIVE_STATE));
        if (si && actor) for (unsigned w = 0; w < wire_calls; ++w) EXPECT(states[w] == QCOM_SMD_RPM_ACTIVE_STATE);
        healthy(&f);
        /* Reassert the acknowledged cache; even an applied timeout must be repaired. */
        clear_io();
        EXPECT(rpm_reg_enable(&f.rdev[1]) == 0);
        EXPECT(fw[0].enabled && fw[0].uV >= f.pair.votes[1].uV);
        EXPECT(fw[1].enabled == f.pair.votes[0].enabled);
        EXPECT(fw[1].uV == f.pair.votes[0].uV);
        healthy(&f); ++cases;
    }
    /* Explicit normal sleep policy survives either active voter; AO hooks reject it. */
    for (unsigned actor = 0; actor < 2; ++actor)
    for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
    for (unsigned key = 0; key < 3; ++key) {
        struct fixture f; init(&f, true, true, 1287500, 1337500, true);
        fault_mode = mode; fault_at = 1;
        int ret = key == 0 ? rpm_reg_set_suspend_disable(&f.rdev[actor]) : key == 1 ?
            rpm_reg_set_suspend_enable(&f.rdev[actor]) : rpm_reg_set_suspend_voltage(&f.rdev[actor], 750000);
        EXPECT(ret == (actor ? -EOPNOTSUPP : errors[mode]));
        EXPECT(alloc_calls == (actor ? 0 : 1));
        EXPECT(f.pair.sleep_enable_valid == (!actor && !mode && key != 2));
        EXPECT(f.pair.sleep_voltage_valid == (!actor && !mode && key == 2));
        if (!actor && mode) {
            clear_io(); EXPECT(rpm_reg_enable(&f.rdev[1]) == 0);
            EXPECT(fw[1].enabled && fw[1].uV == 1287500);
        }
        healthy(&f); ++cases;
    }
    for (unsigned actor = 0; actor < 2; ++actor) {
        struct fixture f; init(&f, true, true, 1287500, 1337500, true);
        EXPECT(rpm_reg_set_suspend_disable(&f.rdev[0]) == 0);
        EXPECT(rpm_reg_set_suspend_voltage(&f.rdev[0], 750000) == 0);
        clear_io();
        EXPECT(rpm_reg_set_voltage(&f.rdev[actor], 1300000, 1337500, NULL) == 0);
        EXPECT(!fw[1].enabled && fw[1].uV == 750000);
        EXPECT(fw[0].enabled && fw[0].uV >= 1300000);
        healthy(&f); ++cases;
    }
    /* Large loads add without 32-bit wrap; no peer rdev is needed by the pair. */
    {
        struct fixture f; init(&f, true, true, 1287500, 1337500, true);
        f.vreg[0].load = UINT32_MAX; f.pair.votes[0].load = UINT32_MAX;
        f.vreg[1].load = 21000; f.pair.votes[1].load = 21000;
        EXPECT(rpm_reg_enable(&f.rdev[1]) == 0);
        EXPECT(fw[0].mA == UINT32_MAX / 1000);
        memset(&f.rdev[0], 0xa5, sizeof(f.rdev[0]));
        memset(&f.vreg[0], 0xa5, sizeof(f.vreg[0]));
        clear_io(); EXPECT(rpm_reg_set_voltage(&f.rdev[1], 1300000, 1337500, NULL) == 0);
        EXPECT(fw[0].uV == 1300000 && fw[1].uV == 1287500);
        healthy(&f); ++cases;
    }
    /* Actual CPR sequencing composed with the pair and actual consumer check. */
    for (unsigned down = 0; down < 2; ++down)
    for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
    for (unsigned applied = 0; applied < 2; ++applied)
    for (unsigned apc_fail = 0; apc_fail < 2; ++apc_fail) {
        struct fixture f; init(&f, false, true, 1287500, down ? 1337500 : 1287500, true);
        struct cpr_voltage rails = {.mx = &f.ao, .apc = &f.apc, .mx_min_uV = down ? 1337500 : 1287500,
            .mx_max_uV = 1337500, .mx_enabled = true};
        fault_mode = mode; fault_at = 1; apply_uncertain = applied;
        apc_error = apc_fail ? -EIO : 0;
        int target = down ? 900000 : 1337500;
        int ret = cpr_voltage_set(&rails, target, target);
        bool mx_fail = mode != FAST && !(down && apc_fail);
        EXPECT(ret == (!down && mx_fail ? errors[mode] : apc_fail ? -EIO : 0));
        EXPECT(apc_calls == (unsigned)(down || !mx_fail));
        if (event_count) EXPECT(events[0] == (down ? 'A' : mode == ALLOC ? 'S' : 'M'));
        if (mx_fail) {
            EXPECT(fw[0].uV >= (down ? 1337500 : 1287500));
            EXPECT(rails.mx_min_uV == (down ? 1337500 : 1287500));
        }
        EXPECT(rails.mx_lower_error == (down && !apc_fail && mode ? errors[mode] : 0));
        EXPECT(!fw[1].enabled && fw[1].uV == 1287500);
        healthy(&f); ++cases;
    }
    /* Initial CPU vote establishes normal sleep first; bootstrap retains one enable. */
    {
        struct fixture f; init(&f, false, false, 1287500, 0, false);
        f.pair.votes[1].uV = 0;
        struct cpr_voltage rails = {.mx = &f.ao, .apc = &f.apc, .mx_max_uV = 1337500};
        EXPECT(cpr_voltage_bootstrap(&rails, 1337500) == 0);
        EXPECT(rails.mx_enabled && rails.mx_min_uV == 1337500);
        EXPECT(wire_calls == 2 && states[0] == QCOM_SMD_RPM_SLEEP_STATE && states[1] == QCOM_SMD_RPM_ACTIVE_STATE);
        EXPECT(fw[0].enabled && fw[0].uV == 1337500 && !fw[1].enabled && fw[1].uV == 1287500);
        clear_io(); EXPECT(cpr_voltage_bootstrap(&rails, 1287500) == 0);
        EXPECT(!wire_calls && rails.mx_min_uV == 1337500);
        healthy(&f); ++cases;
    }
    printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
    return 0;
}
