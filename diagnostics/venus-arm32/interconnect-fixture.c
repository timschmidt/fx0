// SPDX-License-Identifier: GPL-2.0-only
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>

typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
struct icc_provider { int unused; };
struct icc_node { struct icc_provider *provider; void *data; };
struct regmap { unsigned int max_register; };
struct regmap_config {
	int reg_bits, val_bits, reg_stride, max_register;
	bool fast_io;
};

#define QCOM_SMD_RPM_STATE_NUM 2
#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))
#define container_of(ptr, type, member) \
	((type *)((char *)(ptr) - offsetof(type, member)))
#define icc_units_to_bps(bw) ((bw) * 1000ULL)
#define dev_dbg(...) ((void)0)
#define pr_err(...) ((void)0)

static struct {
	unsigned int reg, mask, value;
} writes[8];
static unsigned int nwrites, fail_write;
static struct {
	int state, type, id;
	u32 value;
} votes[4];
static unsigned int nvotes;

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

static const struct rpm_clk_resource bimc_clk;

/* EXTRACTED KERNEL SOURCE */

static int check(bool ok, const char *message)
{
	if (ok)
		return 0;
	fprintf(stderr, "%s\n", message);
	return 1;
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
			  bimc->buswidth == 8 && ebi->buswidth == 8 &&
			  msm8226_bimc.bus_clk_desc == &bimc_clk &&
			  msm8226_bimc.keep_alive, "incorrect clock topology");
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
	if (failures)
		return 1;
	puts("nine checks passed");
	return 0;
}
