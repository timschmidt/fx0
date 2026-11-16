/* SPDX-License-Identifier: GPL-2.0-only */
/* Exact regulator core/provider and RPM bodies with logical transport services. */
/* PREFIX */
/* ACTUAL_RPM_TYPES */
/* ACTUAL_RPM_DEFINES */
/* ACTUAL_RPM */
typedef int suspend_state_t;
#define PM_SUSPEND_ON 0
#define PM_SUSPEND_TO_IDLE 1
#define PM_SUSPEND_STANDBY 2
#define PM_SUSPEND_MEM 3
#define PM_SUSPEND_MAX 4
#define ENABLE_IN_SUSPEND 1
#define DISABLE_IN_SUSPEND 2
#define rdev_err(...) ((void)0)
#define rdev_warn(...) ((void)0)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
struct regulator_dev;
struct regulator_ops {
	int (*enable)(struct regulator_dev *);
	int (*disable)(struct regulator_dev *);
	int (*is_enabled)(struct regulator_dev *);
	int (*list_voltage)(struct regulator_dev *, unsigned);
	int (*get_voltage)(struct regulator_dev *);
	int (*set_voltage)(struct regulator_dev *, int, int, unsigned *);
	int (*set_load)(struct regulator_dev *, int);
	int (*set_suspend_voltage)(struct regulator_dev *, int);
	int (*set_suspend_enable)(struct regulator_dev *);
	int (*set_suspend_disable)(struct regulator_dev *);
	int (*set_suspend_mode)(struct regulator_dev *, unsigned);
};
struct regulator_desc { const struct regulator_ops *ops; };
struct regulator_state { int enabled, uV; unsigned mode; };
struct regulation_constraints {
	struct regulator_state state_standby, state_mem, state_disk;
};
struct regulator_dev {
	struct device dev;
	struct regulator_desc *desc;
	struct regulation_constraints *constraints;
	void *data;
	bool locked;
};
static void *rdev_get_drvdata(struct regulator_dev *rdev) { return rdev->data; }
static struct regulator_dev *dev_to_rdev(struct device *dev) { return dev->data; }
static void regulator_lock(struct regulator_dev *rdev) { CHECK(!rdev->locked); rdev->locked = true; }
static void regulator_unlock(struct regulator_dev *rdev) { CHECK(rdev->locked); rdev->locked = false; }
static int regulator_list_voltage_linear_range(struct regulator_dev *rdev, unsigned sel) { return 750000 + sel * 12500; }
static suspend_state_t pm_suspend_target_state;
/* ACTUAL_REG_TYPES */
static struct qcom_smd_rpm *smd_vreg_rpm;
/* ACTUAL_REG_DEFINES */
/* ACTUAL_REG */
/* ACTUAL_OPS */
/* ACTUAL_CORE */
enum { FAST, ALLOC, SEND, SILENT, STALE, NACK, BOUNDARY };
static unsigned cases, checks, failures, alloc_calls, wire_calls;
static unsigned fault_mode, fault_at, current_fault;
static struct qcom_rpm_reg *expected_vreg;
static int expected_uV, expected_enable;
static bool active_test;
static FILE *trace;
static u32 last_id;
#define EXPECT(x) do { ++checks; if (!(x)) { ++failures; \
	if (failures <= 12) fprintf(stderr, "check failed at %d: %s\n", __LINE__, #x); \
	} } while (0)
static void *kmalloc(size_t size, int flags)
{
	(void)flags;
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
	++wire_calls;
	EXPECT(size >= 40 && size <= 64);
	EXPECT(get_unaligned_le32(p) == RPM_SERVICE_TYPE_REQUEST);
	EXPECT(get_unaligned_le32(p + 4) == size - 8);
	last_id = get_unaligned_le32(p + 8);
	EXPECT(last_id != 0);
	EXPECT(get_unaligned_le32(p + 12) == (active_test ? QCOM_SMD_RPM_ACTIVE_STATE : QCOM_SMD_RPM_SLEEP_STATE));
	EXPECT(get_unaligned_le32(p + 16) == expected_vreg->type);
	EXPECT(get_unaligned_le32(p + 20) == expected_vreg->id);
	EXPECT(get_unaligned_le32(p + 24) == size - 28);
	EXPECT(ep->rpm->lock.held && !ep->rpm->ack_lock.held);
	for (size_t offset = 28; offset + 12 <= size; offset += 12) {
		u32 key = get_unaligned_le32(p + offset);
		u32 value = get_unaligned_le32(p + offset + 8);
		EXPECT(get_unaligned_le32(p + offset + 4) == 4);
		if (active_test) {
			EXPECT(key == RPM_KEY_SWEN || key == RPM_KEY_UV || key == RPM_KEY_MA);
			EXPECT(value == (key == RPM_KEY_SWEN ? (u32)expected_vreg->is_enabled :
				key == RPM_KEY_UV ? (u32)expected_vreg->uV : expected_vreg->load / 1000));
		} else {
			EXPECT(size == 40);
			EXPECT(key == (alloc_calls == 1 ? RPM_KEY_SWEN : RPM_KEY_UV));
			EXPECT(value == (alloc_calls == 1 ? (u32)expected_enable : (u32)expected_uV));
		}
	}
	if (active_test) CHECK(fwrite(data, size, 1, trace) == 1);
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
static void init_vreg(struct qcom_rpm_reg *vreg, struct regulator_dev *rdev,
		      const struct regulator_ops *ops, unsigned resource)
{
	memset(vreg, 0, sizeof(*vreg));
	memset(rdev, 0, sizeof(*rdev));
	vreg->type = resource ? QCOM_SMD_RPM_SMPA : QCOM_SMD_RPM_LDOA;
	vreg->id = resource ? 4 : 3;
	vreg->desc.ops = ops;
	vreg->uV = 900000;
	vreg->is_enabled = 1;
	vreg->load = 12000;
	rdev->dev.data = rdev;
	rdev->data = vreg;
	rdev->desc = &vreg->desc;
	expected_vreg = vreg;
}
int main(int argc, char **argv)
{
	CHECK(argc == 2);
	trace = fopen(argv[1], "wb");
	CHECK(trace);
	const struct regulator_ops *tables[] = {&rpm_smps_ldo_ops, &rpm_smps_ldo_ops_fixed,
		&rpm_switch_ops, &rpm_bob_ops, &rpm_mp5496_ops};
	struct qcom_smd_rpm rpm = {0};
	struct rpmsg_endpoint ep = {.rpm = &rpm};
	rpm.rpm_channel = &ep;
	smd_vreg_rpm = &rpm;
	const int voltages[] = {0, 750000, 1337500};
	const int errors[] = {0, -ENOMEM, -EIO, -ETIMEDOUT, -ETIMEDOUT, -ENXIO, -ETIMEDOUT};
	for (unsigned table = 0; table < 5; ++table)
	for (int target = 0; target <= PM_SUSPEND_MAX; ++target)
	for (int enable = 0; enable <= DISABLE_IN_SUSPEND; ++enable)
	for (unsigned voltage = 0; voltage < 3; ++voltage)
	for (unsigned mode = FAST; mode <= BOUNDARY; ++mode)
	for (unsigned stage = 1; stage <= 2; ++stage)
	for (unsigned resource = 0; resource < 2; ++resource) {
		struct qcom_rpm_reg vreg;
		struct regulator_dev rdev;
		struct regulation_constraints constraints = {0};
		init_vreg(&vreg, &rdev, tables[table], resource);
		vreg.enabled_updated = target & 1;
		vreg.uv_updated = enable == ENABLE_IN_SUSPEND;
		vreg.load_updated = voltage == 1;
		struct qcom_rpm_reg before = vreg;
		struct regulator_state state = {.enabled = enable, .uV = voltages[voltage]};
		constraints.state_mem = constraints.state_standby = constraints.state_disk = state;
		rdev.constraints = &constraints;
		rpm.msg_id = resource ? UINT32_MAX : 0;
		alloc_calls = wire_calls = 0;
		fault_mode = mode; fault_at = stage; active_test = false;
		expected_uV = state.uV; expected_enable = enable == ENABLE_IN_SUSPEND;
		pm_suspend_target_state = target;
		unsigned required = target >= PM_SUSPEND_STANDBY && enable != 0 ? 1 + (unsigned)(table != 2 && voltage != 0) : 0;
		bool failed = mode != FAST && stage <= required;
		unsigned attempts = failed ? stage : required;
		int ret = regulator_suspend(&rdev.dev);
		++cases;
		EXPECT(ret == (failed ? errors[mode] : 0));
		EXPECT(alloc_calls == attempts);
		EXPECT(wire_calls == attempts - (unsigned)(failed && mode == ALLOC));
		EXPECT(!memcmp(&before, &vreg, sizeof(vreg)));
		EXPECT(!rdev.locked && !rpm.lock.held && !rpm.ack_lock.held);
		EXPECT(!rpm.waiting && !allocated);
	}
	active_test = true; fault_mode = FAST; fault_at = 0;
	for (unsigned table = 0; table < 5; ++table)
	for (unsigned resource = 0; resource < 2; ++resource) {
		struct qcom_rpm_reg vreg;
		struct regulator_dev rdev;
		init_vreg(&vreg, &rdev, tables[table], resource);
		vreg.is_enabled = 0; rpm.msg_id = 0; alloc_calls = wire_calls = 0;
		EXPECT(tables[table]->enable(&rdev) == 0);
		if (tables[table]->set_voltage) EXPECT(tables[table]->set_voltage(&rdev, 1337500, 1337500, NULL) == 0);
		if (tables[table]->set_load) EXPECT(tables[table]->set_load(&rdev, 34000) == 0);
		EXPECT(tables[table]->disable(&rdev) == 0);
		EXPECT(!vreg.is_enabled && !allocated && !rpm.lock.held);
		++cases;
	}
	CHECK(!fclose(trace));
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
	return 0;
}
