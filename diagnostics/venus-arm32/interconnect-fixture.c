// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
struct icc_node;
struct icc_provider {
	struct icc_node *nodes[4];
	int (*set)(struct icc_node *, struct icc_node *);
	int (*get_bw)(struct icc_node *, u32 *, u32 *);
	void (*pre_aggregate)(struct icc_node *);
	int (*aggregate)(struct icc_node *, u32, u32, u32, u32 *, u32 *);
};
struct icc_node {
	struct icc_provider *provider;
	void *data;
	int node_list;
	u32 init_avg, init_peak, avg_bw, peak_bw;
};
struct clk {
	unsigned long peer_rate, min_rate, effective_rate;
	unsigned int min_calls, direct_calls;
	long round_error;
	int min_error;
};
struct regmap { unsigned int max_register; };
struct regmap_config {
	int reg_bits, val_bits, reg_stride, max_register;
	bool fast_io;
};

#define QCOM_SMD_RPM_STATE_NUM 2
#define QCOM_SMD_RPM_ACTIVE_STATE 0
#define QCOM_SMD_RPM_SLEEP_STATE 1
#define BIT(n) (1U << (n))
#define RPM_ALWAYS_TAG (BIT(0) | BIT(1))
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(ptr, type, member) \
	((type *)((char *)(ptr) - offsetof(type, member)))
#define icc_units_to_bps(bw) ((bw) * 1000ULL)
#define dev_dbg(...) ((void)0)
#define pr_err(...) ((void)0)
#define WARN_ON(x) (x)
#define max(a, b) ((a) > (b) ? (a) : (b))
#define max_t(type, a, b) max((type)(a), (type)(b))
#define min_t(type, a, b) ((type)(a) < (type)(b) ? (type)(a) : (type)(b))
#define div_u64(value, divisor) ((value) / (divisor))
#define mutex_lock(lock) ((void)0)
#define mutex_unlock(lock) ((void)0)
#define list_for_each_entry(node, array, member) \
	for (unsigned int i = 0; i < ARRAY_SIZE(*(array)) && ((node) = (*(array))[i]); i++)
#define list_add_tail(item, array) do { \
	for (unsigned int i = 0; i < ARRAY_SIZE(*(array)); i++) { \
		if (!(*(array))[i]) { \
			(*(array))[i] = container_of(item, struct icc_node, node_list); \
			break; \
		} \
	} \
} while (0)

static struct {
	unsigned int reg, mask, value;
} writes[8];
static unsigned int nwrites, fail_write;
static struct {
	int state, type, id;
	u32 value;
} votes[24];
static unsigned int nvotes;
static u32 ddr_clock_rate[] = { INT_MAX, INT_MAX };
static unsigned int ddr_clock_writes;

static int regmap_update_bits(struct regmap *map, unsigned int reg,
			      unsigned int mask, unsigned int value)
{
	if (reg > map->max_register || nwrites == ARRAY_SIZE(writes))
		return -1;
	writes[nwrites++] = (typeof(writes[0])){ reg, mask, value };
	return nwrites == fail_write ? -5 : 0;
}

static int qcom_icc_rpm_smd_send(int state, int type, int id, u32 value)
{
	if (nvotes == ARRAY_SIZE(votes))
		return -1;
	votes[nvotes++] = (typeof(votes[0])){ state, type, id, value };
	return 0;
}

static const struct rpm_clk_resource bimc_clk __attribute__((unused));
static int qcom_icc_rpm_set_bus_rate(const struct rpm_clk_resource *clock, int state, u32 rate)
{
	ddr_clock_rate[state] = rate;
	ddr_clock_writes++;
	return 0;
}

static long clk_round_rate(struct clk *clk, unsigned long rate);
static int clk_set_min_rate(struct clk *clk, unsigned long rate);
static int clk_set_rate(struct clk *clk, unsigned long rate);

/* EXTRACTED KERNEL SOURCE */

static long clk_round_rate(struct clk *clk, unsigned long rate)
{
	if (clk->round_error)
		return clk->round_error;
	for (unsigned int i = 0; i < ARRAY_SIZE(hardware_rates); i++)
		if (rate <= hardware_rates[i])
			return hardware_rates[i];
	/* The MSM8226 clock selects the highest entry for excess requests. */
	return hardware_rates[ARRAY_SIZE(hardware_rates) - 1];
}

static int clk_set_min_rate(struct clk *clk, unsigned long rate)
{
	clk->min_calls++;
	if (clk->min_error)
		return clk->min_error;
	clk->min_rate = rate;
	clk->effective_rate = clk_round_rate(clk, max(clk->peer_rate, clk->min_rate));
	return 0;
}

static int clk_set_rate(struct clk *clk, unsigned long rate)
{
	clk->direct_calls++;
	clk->peer_rate = rate;
	clk->effective_rate = clk_round_rate(clk, rate);
	return 0;
}

static int check(bool ok, const char *message)
{
	if (ok)
		return 0;
	fprintf(stderr, "%s\n", message);
	return 1;
}

static int check_clock_requests(struct qcom_icc_node *video, struct qcom_icc_node *gateway,
				struct qcom_icc_node *bimc, struct qcom_icc_node *ebi)
{
	struct clk clock = { .peer_rate = 150000000, .effective_rate = 150000000 };
	struct qcom_icc_desc legacy = {};
	struct qcom_icc_provider ss = {
		.provider = {
			.set = qcom_icc_set, .get_bw = INITIAL_BW((&msm8226_mmss)),
			.pre_aggregate = qcom_icc_pre_bw_aggregate,
			.aggregate = qcom_icc_bw_aggregate,
		},
		.bus_clk = &clock, .set_bus_clk_rate = CLOCK_SETTER((&msm8226_mmss)),
	};
	struct qcom_icc_provider mem = {
		.provider = {
			.set = qcom_icc_set, .get_bw = INITIAL_BW((&msm8226_bimc)),
			.pre_aggregate = qcom_icc_pre_bw_aggregate,
			.aggregate = qcom_icc_bw_aggregate,
		},
		.bus_clk_desc = msm8226_bimc.bus_clk_desc,
		.keep_alive = msm8226_bimc.keep_alive,
	};
	struct icc_node video_node = { .data = video }, gateway_node = { .data = gateway };
	struct icc_node bimc_node = { .data = bimc }, ebi_node = { .data = ebi };
	int failures = 0;

	nvotes = 0;
	icc_node_add(&video_node, &ss.provider);
	icc_node_add(&gateway_node, &ss.provider);
	icc_node_add(&bimc_node, &mem.provider);
	icc_node_add(&ebi_node, &mem.provider);
	failures += check(!video_node.init_peak && !ebi_node.init_avg && !nvotes &&
			  !ddr_clock_writes && !clock.min_calls && !clock.direct_calls,
			  "probe changed existing clock or bandwidth votes");
	failures += check(CLOCK_SETTER((&legacy)) == clk_set_rate,
			  "legacy clock setter changed");

	video->sum_avg[0] = gateway->sum_avg[0] = ebi->sum_avg[0] = 866000;
	video->max_peak[0] = gateway->max_peak[0] = ebi->max_peak[0] = 953000;
	failures += check(!qcom_icc_set(&video_node, &gateway_node) &&
			  !clock.direct_calls && clock.min_rate == 59562000 &&
			  clock.effective_rate == 150000000,
			  "video vote overwrote the peer's higher rate");
	failures += check(!qcom_icc_set(&bimc_node, &ebi_node) && nvotes == 2 &&
			  votes[0].value == 866000000 && !votes[1].value &&
			  !ddr_clock_writes && ddr_clock_rate[0] == INT_MAX &&
			  ddr_clock_rate[1] == INT_MAX,
			  "video vote replaced the DDR clock handoff");

	clock.peer_rate = 19200000;
	failures += check(!qcom_icc_set(&video_node, &gateway_node) &&
			  clock.effective_rate == 75000000,
			  "video minimum did not select the required AXI rate");
	video->sum_avg[0] = gateway->sum_avg[0] = ebi->sum_avg[0] = 0;
	video->max_peak[0] = gateway->max_peak[0] = ebi->max_peak[0] = 0;
	failures += check(!qcom_icc_set(&video_node, &gateway_node) && !clock.min_rate &&
			  !clock.direct_calls && clock.peer_rate == 19200000,
			  "idle handling did not release only the video minimum");
	failures += check(!qcom_icc_set(&bimc_node, &ebi_node) && nvotes == 4 &&
			  !votes[2].value && !votes[3].value && !ddr_clock_writes,
			  "idle handling moved the DDR clock vote");

	failures += check(msm8226_set_mmss_rate(&clock, 266666667) == -ERANGE &&
			  !clock.min_rate, "excess MMSS minimum was admitted");
	clock.round_error = -EINVAL;
	failures += check(msm8226_set_mmss_rate(&clock, 20000000) == -EINVAL &&
			  !clock.min_rate, "clock rounding error was lost");
	clock.round_error = 0;
	clock.min_error = -EBUSY;
	failures += check(msm8226_set_mmss_rate(&clock, 20000000) == -EBUSY &&
			  !clock.min_rate, "clock reservation error was lost");
	return failures;
}

int main(void)
{
	struct qcom_icc_node *video = msm8226_mmss.nodes[MSM8226_MMSS_MASTER_VIDEO_P0];
	struct qcom_icc_node *mmss = msm8226_mmss.nodes[MSM8226_MMSS_SLAVE_BIMC];
	struct qcom_icc_node *bimc = msm8226_bimc.nodes[MSM8226_BIMC_MASTER_MMSS];
	struct qcom_icc_node *ebi = msm8226_bimc.nodes[MSM8226_BIMC_SLAVE_EBI_CH0];
	struct qcom_icc_desc legacy = {};
	struct regmap map = { .max_register = msm8226_mmss.regmap_cfg->max_register };
	struct qcom_icc_provider qp = {
		.regmap = &map,
		.qos_offset = msm8226_mmss.qos_offset,
		.noc_qos_stride = DEFAULT_STRIDE((&msm8226_mmss)),
	};
	struct icc_node node = { .provider = &qp.provider, .data = video };
	u64 bandwidth[] = { 866000, 129000 };
	int failures = 0;

	failures += check(video->num_links == 1 && video->links[0] == mmss->id &&
			  mmss->num_links == 1 && mmss->links[0] == bimc->id &&
			  bimc->num_links == 1 && bimc->links[0] == ebi->id &&
			  !ebi->num_links, "incorrect route");
	failures += check(video->buswidth == 16 && mmss->buswidth == 16 &&
			  bimc->buswidth == 8 && ebi->buswidth == 8,
			  "incorrect clock topology");
	failures += check(!qcom_icc_set_noc_qos(&node) && nwrites == 1 &&
			  writes[0].reg == 0x320c && writes[0].mask == 3 &&
			  writes[0].value == 2, "incorrect MSM8226 mode write");

	video->qos.qos_mode = NOC_QOS_MODE_FIXED;
	video->qos.areq_prio = 2;
	video->qos.prio_level = 1;
	nwrites = 0;
	failures += check(!qcom_icc_set_noc_qos(&node) && nwrites == 3 &&
			  writes[0].reg == 0x3208 && writes[0].mask == 0xc &&
			  writes[0].value == 8 && writes[1].reg == 0x3208 &&
			  writes[1].mask == 3 && writes[1].value == 1 &&
			  writes[2].reg == 0x320c && writes[2].value == 0,
			  "incorrect MSM8226 priority sequence");
	nwrites = 0;
	fail_write = 1;
	failures += check(qcom_icc_set_noc_qos(&node) == -5 && nwrites == 1,
			  "priority failure not propagated");
	fail_write = 0;
	nwrites = 0;
	video->qos.qos_port = -1;
	failures += check(!qcom_icc_set_noc_qos(&node) && !nwrites,
			  "negative port was programmed");

	video->qos.qos_mode = NOC_QOS_MODE_BYPASS;
	video->qos.qos_port = 4;
	map.max_register = 0xffff;
	qp.noc_qos_stride = DEFAULT_STRIDE((&legacy));
	failures += check(!qcom_icc_set_noc_qos(&node) && nwrites == 1 &&
			  writes[0].reg == 0x700c, "legacy mode stride changed");

	nwrites = 0;
	map.max_register = msm8226_bimc.regmap_cfg->max_register;
	qp.qos_offset = msm8226_bimc.qos_offset;
	node.data = bimc;
	failures += check(!qcom_icc_set_bimc_qos(&node) && nwrites == 1 &&
			  writes[0].reg == 0x10300 && writes[0].mask == 1 &&
			  writes[0].value == 0, "incorrect BIMC bypass write");
	failures += check(!qcom_icc_rpm_set(video, bandwidth) &&
			  !qcom_icc_rpm_set(mmss, bandwidth) &&
			  !qcom_icc_rpm_set(bimc, bandwidth) && !nvotes,
			  "AP-owned node emitted an RPM vote");
	failures += check(!qcom_icc_rpm_set(ebi, bandwidth) && nvotes == 2 &&
			  votes[0].state == 0 && votes[1].state == 1 &&
			  votes[0].type == RPM_BUS_SLAVE_REQ &&
			  votes[1].type == RPM_BUS_SLAVE_REQ &&
			  !votes[0].id && !votes[1].id &&
			  votes[0].value == 866000000 && votes[1].value == 129000000,
			  "incorrect EBI RPM vote");
	failures += check_clock_requests(video, mmss, bimc, ebi);
	if (failures)
		return 1;
	puts("19 checks passed");
	return 0;
}
