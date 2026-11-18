/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

typedef uint32_t u32;
typedef uint64_t u64;
typedef int irqreturn_t;
typedef bool spinlock_t;
#define __iomem
#define __maybe_unused
#define BIT(bit) (1U << (bit))
#define QCOM_IOMMU_WRAPPER_CLK_SEL BIT(0)
#define ARRAY_SIZE(array) (sizeof(array) / sizeof((array)[0]))
#define IS_ERR(pointer) ((pointer) == &failed_map)
#define PTR_ERR(pointer) (-ENOMEM)
#define IS_IRIS2(core) ((core)->iris2)
#define IS_IRIS2_1(core) (false)
#define IS_AR50_LITE(core) (false)
#define HFI_COLOR_FORMAT_10_BIT_BASE BIT(16)
#define VIDC_SESSION_TYPE_ENC 0
#define VIDC_SESSION_TYPE_DEC 1
#define CLK_NUM 3
#define kbps_to_icc(kbps) (kbps)
#define max(a, b) ((a) > (b) ? (a) : (b))
#define dev_dbg(...) do { } while (0)
#define dev_err(...) do { } while (0)
#define WARN_ON(condition) (condition)
#define READ_ONCE(value) (value)
#define WRITE_ONCE(target, value) ((target) = (value))
#define IRQ_NONE 0
#define IRQ_HANDLED 1
#define ARM_SMMU_CB_FSR_FAULT BIT(1)
#define spin_lock_irqsave(lock, flags) do { \
	assert(!*(lock)); \
	*(lock) = true; \
	(flags) = 1; \
} while (0)
#define spin_unlock_irqrestore(lock, flags) do { \
	assert(*(lock) && (flags) == 1); \
	*(lock) = false; \
} while (0)
#define readl_poll_timeout(addr, val, condition, delay, timeout) \
	((val) = readl_relaxed(addr), (condition) ? 0 : -ETIMEDOUT)
#define list_for_each_entry(inst, entries, unused) \
	for (unsigned int i = 0; ((inst) = (*(entries))[i]); i++)

struct reg_val { u32 reg, value; };
struct bw_tbl { u32 mbs_per_sec, avg, peak, avg_10bit, peak_10bit; };
struct venus_resources {
	const struct reg_val *reg_tbl;
	unsigned int reg_tbl_size;
	const struct bw_tbl *bw_tbl_enc, *bw_tbl_dec;
	unsigned int bw_tbl_enc_size, bw_tbl_dec_size;
	bool split_reg_banks, bw_per_direction;
};
struct venus_inst { u32 session_type, dpb_fmt, load; };
struct venus_core {
	void *base, *vbif_base, *cpu_base, *cpu_cs_base, *cpu_ic_base;
	void *wrapper_base, *wrapper_version, *wrapper_tz_base, *aon_base;
	const struct venus_resources *res;
	struct venus_inst *instances[5];
	void *video_path;
	bool iris2;
};
struct venus_hfi_device { struct venus_core *core; };
struct platform_device { unsigned int fail_at, calls; };
struct iommu_fwspec { unsigned int num_ids, ids[2]; };
struct device {
	struct qcom_iommu_dev *data;
	void *pm_domain;
	struct iommu_fwspec *fwspec;
	struct device *parent;
};
struct qcom_iommu_cfg { bool ctx_restore, halt; };
struct qcom_iommu_ctx_state { u32 sctlr; };
struct qcom_iommu_ctx {
	void *domain, *base;
	bool secured_ctx;
	unsigned int asid;
	int irq;
	struct device *dev;
	struct qcom_iommu_ctx_state state;
};
struct qcom_iommu_dev {
	struct device *dev;
	u32 *wrapper_clk_sel;
	void *global_base;
	bool non_secure, ctx_online;
	spinlock_t ctx_lock;
	unsigned int max_asid, sec_id;
	int clks[CLK_NUM];
	const struct qcom_iommu_cfg *cfg;
	struct qcom_iommu_ctx *ctxs[2];
};
struct iommu_domain { struct qcom_iommu_domain *private; };
struct iommu_iotlb_gather { bool walk; };
struct io_pgtable_ops {
	size_t (*unmap_pages)(struct io_pgtable_ops *, unsigned long, size_t, size_t,
			      struct iommu_iotlb_gather *);
	void *cookie;
};
struct qcom_iommu_domain {
	struct qcom_iommu_dev *iommu;
	struct iommu_domain domain;
	struct io_pgtable_ops *pgtbl_ops;
	spinlock_t pgtbl_lock;
	u32 *asids;
	unsigned int num_asids;
};

static void dev_err_ratelimited(struct device *dev, const char *format, ...) { }

static u32 vbif[0x400 / 4], cpu[0x20000 / 4], wrapper[0x4000 / 4];
static u32 combined[0x100000 / 4], clock_select, failed_map;
static u32 observed_avg, observed_peak;
static unsigned int reads, writes, enables, disables, restores, resets, presets, contexts;
static int clock_error, secure_error, clock_stuck;
static int pm_error, pm_gets, pm_puts, domain_initializations;
static unsigned int ctx_writes;
static u32 global_regs[0x3000 / 4], context_regs[0x1000 / 4];
#define micro_control global_regs[0x2000 / 4]
static u32 tlb_status, fsr;
static bool halt_timeout, runtime_active, mapping_present;
static unsigned int irq_syncs, irq_gets, irq_puts, faults, freed_tables, freed_objects;
static unsigned int ctx_reads;
static struct {
	struct qcom_iommu_ctx *ctx;
	unsigned int reg;
	u32 value;
} ctx_trace[32];

static void *devm_platform_ioremap_resource(struct platform_device *pdev, int index)
{
	assert(!index);
	return ++pdev->calls == pdev->fail_at ? &failed_map : combined;
}

static void *devm_platform_ioremap_resource_byname(struct platform_device *pdev, const char *name)
{
	if (++pdev->calls == pdev->fail_at)
		return &failed_map;
	if (!strcmp(name, "vbif"))
		return vbif;
	if (!strcmp(name, "cpu"))
		return cpu;
	if (!strcmp(name, "wrapper-version"))
		return &wrapper[0];
	assert(!strcmp(name, "wrapper"));
	return &wrapper[2];
}

static u32 load_per_instance(struct venus_inst *inst)
{
	return inst->load;
}

static u32 load_per_type(struct venus_core *core, u32 type)
{
	u32 load = 0;

	for (unsigned int i = 0; core->instances[i]; i++)
		if (core->instances[i]->session_type == type)
			load += core->instances[i]->load;
	return load;
}

static int icc_set_bw(void *path, u32 avg, u32 peak)
{
	assert(path);
	observed_avg = avg;
	observed_peak = peak;
	return 0;
}

static u32 readl(void *addr)
{
	assert(addr == &clock_select && enables > disables);
	reads++;
	return *(u32 *)addr;
}

static void writel(u32 value, void *addr)
{
	if (addr == &clock_select) {
		writes++;
		assert(enables > disables && !restores && !presets);
		if (clock_stuck)
			return;
	}
	*(u32 *)addr = value;
}

static u32 readl_relaxed(void *address)
{
	assert(enables > disables);
	if (address == &micro_control)
		return micro_control;
	return tlb_status;
}

static void writel_relaxed(u32 value, void *address)
{
	assert(address == &micro_control && enables > disables);
	micro_control = value & ~BIT(3);
	if ((value & BIT(2)) && !halt_timeout)
		micro_control |= BIT(3);
}

static struct qcom_iommu_dev *dev_get_drvdata(struct device *dev) { return dev->data; }

static int clk_bulk_prepare_enable(int n, int *clks)
{
	assert(n == CLK_NUM && clks);
	if (!clock_error)
		enables++;
	return clock_error;
}

static void clk_bulk_disable_unprepare(int n, int *clks)
{
	assert(n == CLK_NUM && clks);
	disables++;
}

static int qcom_iommu_reset_ns(struct qcom_iommu_dev *iommu)
{
	assert(iommu->non_secure);
	resets++;
	return 0;
}

static int qcom_scm_restore_sec_cfg(unsigned int instance, unsigned int context)
{
	assert(!instance && !context && !(clock_select & BIT(0)));
	restores++;
	return secure_error;
}

static void qcom_iommu_bfb_setup(struct qcom_iommu_dev *iommu)
{
	assert(!iommu->wrapper_clk_sel || !(clock_select & BIT(0)));
	presets++;
}

static void qcom_iommu_program_ctx(struct qcom_iommu_dev *iommu, struct qcom_iommu_ctx *ctx)
{
	assert(presets && ctx == iommu->ctxs[0]);
	contexts++;
}

static void qcom_iommu_write_ctx(struct qcom_iommu_dev *iommu, struct qcom_iommu_ctx *ctx,
				const struct qcom_iommu_ctx_state *state)
{
	assert(iommu->ctx_lock && micro_control == (BIT(2) | BIT(3)));
	assert(state == &ctx->state && !tlb_status);
	qcom_iommu_program_ctx(iommu, ctx);
}

static struct qcom_iommu_dev *dev_iommu_priv_get(struct device *dev) { return dev->data; }
static struct iommu_fwspec *dev_iommu_fwspec_get(struct device *dev) { return dev->fwspec; }

static struct qcom_iommu_domain *to_qcom_iommu_domain(struct iommu_domain *domain)
{
	return domain->private;
}

static struct qcom_iommu_ctx *to_ctx(struct qcom_iommu_domain *domain, unsigned int asid)
{
	assert(asid < ARRAY_SIZE(domain->iommu->ctxs));
	return domain->iommu->ctxs[asid];
}

static void iommu_writel(struct qcom_iommu_ctx *ctx, unsigned int reg, u32 value)
{
	assert(enables > disables && ctx_writes < ARRAY_SIZE(ctx_trace));
	ctx_trace[ctx_writes++] = (typeof(ctx_trace[0])) { ctx, reg, value };
}

static u32 iommu_readl(struct qcom_iommu_ctx *ctx, unsigned int reg)
{
	assert(ctx && enables > disables);
	ctx_reads++;
	return fsr;
}

static u64 iommu_readq(struct qcom_iommu_ctx *ctx, unsigned int reg)
{
	return iommu_readl(ctx, reg);
}

static int report_iommu_fault(struct iommu_domain *domain, struct device *dev, u64 addr, int flags)
{
	assert(domain && dev);
	faults++;
	return 0;
}

static int pm_runtime_resume_and_get(struct device *dev)
{
	assert(dev);
	pm_gets++;
	return pm_error;
}

static int pm_runtime_get_sync(struct device *dev)
{
	return pm_runtime_resume_and_get(dev);
}

static void pm_runtime_put_sync(struct device *dev)
{
	assert(dev);
	pm_puts++;
}

static int pm_runtime_get_if_active(struct device *dev)
{
	assert(dev);
	irq_gets++;
	return runtime_active;
}

static void pm_runtime_put(struct device *dev)
{
	assert(dev && runtime_active);
	irq_puts++;
}

static void synchronize_irq(int irq)
{
	assert(irq == 42);
	irq_syncs++;
}

static void kfree(void *address)
{
	if (address)
		freed_objects++;
}

static void qcom_iommu_tlb_inv_context(void *cookie);

static void free_io_pgtable_ops(struct io_pgtable_ops *ops)
{
	assert(ops && irq_syncs > freed_tables);
	qcom_iommu_tlb_inv_context(ops->cookie);
	freed_tables++;
}

static int qcom_iommu_init_domain(struct iommu_domain *domain, struct qcom_iommu_dev *iommu,
				  struct device *dev)
{
	assert(dev && !pm_error && pm_gets > pm_puts);
	domain_initializations++;
	domain->private->iommu = iommu;
	return 0;
}

/* insert actual kernel code */

static size_t remove_fixture_mapping(struct io_pgtable_ops *ops, unsigned long iova,
				     size_t pgsize, size_t pgcount,
				     struct iommu_iotlb_gather *gather)
{
	struct qcom_iommu_domain *domain = ops->cookie;

	assert(mapping_present && domain->pgtbl_lock && pgcount == 1 && pgsize == 0x1000);
	mapping_present = false;
	if (gather->walk)
		qcom_iommu_tlb_flush_walk(iova, pgsize, pgsize, domain);
	else
		qcom_iommu_tlb_add_page(gather, iova, pgsize, domain);
	return pgsize;
}

static void reset_resume_trace(void)
{
	clock_select = 1;
	restores = presets = contexts = ctx_reads = ctx_writes = 0;
}

static void check_offline_venus(void)
{
	struct qcom_iommu_cfg cfg = { .ctx_restore = true, .halt = true };
	struct qcom_iommu_dev iommu = {
		.cfg = &cfg, .global_base = global_regs, .wrapper_clk_sel = &clock_select,
	};
	struct device dev = { .data = &iommu, .pm_domain = &iommu };
	struct device cb = { .parent = &dev };
	struct qcom_iommu_ctx ctx = { .dev = &cb, .irq = 42, .base = context_regs };
	u32 asids[] = { 0 };
	struct qcom_iommu_domain domain = { .iommu = &iommu, .asids = asids, .num_asids = 1 };
	struct io_pgtable_ops ops = { .cookie = &domain, .unmap_pages = remove_fixture_mapping };
	struct iommu_iotlb_gather gather = { 0 };
	int saved_gets = pm_gets, saved_puts = pm_puts;

	iommu.dev = &dev;
	iommu.ctxs[0] = &ctx;
	domain.domain.private = &domain;
	domain.pgtbl_ops = &ops;
	ctx.domain = &domain.domain;
	enables = disables = 0;
	reset_resume_trace();
	assert(!qcom_iommu_resume(&dev) && iommu.ctx_online && contexts == 1);
	assert(ctx_writes == 3 && ctx_trace[0].reg == ARM_SMMU_CB_SCTLR &&
	       ctx_trace[1].reg == ARM_SMMU_CB_S1_TLBIASID &&
	       ctx_trace[2].reg == ARM_SMMU_CB_TLBSYNC && !micro_control);

	ctx_writes = 0;
	qcom_iommu_flush_iotlb_all(&domain.domain);
	assert(ctx_writes == 2 && ctx_trace[0].reg == ARM_SMMU_CB_S1_TLBIASID &&
	       ctx_trace[1].reg == ARM_SMMU_CB_TLBSYNC);
	ctx_writes = 0;
	qcom_iommu_iotlb_sync(&domain.domain, &gather);
	assert(ctx_writes == 1 && ctx_trace[0].reg == ARM_SMMU_CB_TLBSYNC);

	ctx_writes = 0;
	mapping_present = true;
	assert(qcom_iommu_unmap(&domain.domain, 0x40000000, 4096, 1, &gather) == 4096);
	assert(!mapping_present && ctx_writes == 1 &&
	       ctx_trace[0].reg == ARM_SMMU_CB_S1_TLBIVAL);
	ctx_writes = 0;
	halt_timeout = true;
	assert(qcom_iommu_suspend(&dev) == -ETIMEDOUT);
	assert(iommu.ctx_online && enables > disables && !ctx_writes);
	halt_timeout = false;
	assert(!qcom_iommu_suspend(&dev) && !iommu.ctx_online && enables == disables);
	assert(ctx_writes == 3 && ctx_trace[0].reg == ARM_SMMU_CB_SCTLR &&
	       ctx_trace[1].reg == ARM_SMMU_CB_S1_TLBIASID);

	reset_resume_trace();
	clock_error = -EACCES;
	assert(qcom_iommu_resume(&dev) == -EIO && !iommu.ctx_online && enables == disables);
	clock_error = 0;
	secure_error = -EACCES;
	assert(qcom_iommu_resume(&dev) == -EIO && !iommu.ctx_online && enables == disables);
	secure_error = 0;
	reset_resume_trace();
	halt_timeout = true;
	assert(qcom_iommu_resume(&dev) == -ETIMEDOUT && !iommu.ctx_online && !ctx_writes);
	assert(enables == disables && !contexts && !micro_control);
	halt_timeout = false;
	reset_resume_trace();
	tlb_status = 1;
	assert(qcom_iommu_resume(&dev) == -ETIMEDOUT && !iommu.ctx_online && ctx_writes == 3);
	assert(enables == disables && !contexts && !micro_control);
	tlb_status = 0;

	ctx_writes = 0;
	mapping_present = true;
	gather.walk = true;
	assert(qcom_iommu_unmap(&domain.domain, 0x40000000, 4096, 1, &gather) == 4096);
	assert(!mapping_present && !ctx_writes);
	qcom_iommu_flush_iotlb_all(&domain.domain);
	qcom_iommu_iotlb_sync(&domain.domain, &gather);
	assert(!ctx_writes && pm_gets == saved_gets && pm_puts == saved_puts);
	assert(qcom_iommu_fault(42, &ctx) == IRQ_NONE && !ctx_reads && !irq_puts);

	reset_resume_trace();
	assert(!qcom_iommu_resume(&dev) && iommu.ctx_online && contexts == 1);
	assert(ctx_trace[1].reg == ARM_SMMU_CB_S1_TLBIASID &&
	       ctx_trace[2].reg == ARM_SMMU_CB_TLBSYNC);
	runtime_active = true;
	fsr = ARM_SMMU_CB_FSR_FAULT;
	assert(qcom_iommu_fault(42, &ctx) == IRQ_HANDLED && faults == 1 && irq_puts == 1);
	runtime_active = false;
	assert(!qcom_iommu_suspend(&dev) && !iommu.ctx_online);

	ctx_writes = 0;
	qcom_iommu_domain_free(&domain.domain);
	assert(!ctx.domain && !ctx_writes && irq_syncs == 1 && freed_tables == 1 &&
	       freed_objects == 2 && pm_gets == saved_gets && pm_puts == saved_puts);
	reset_resume_trace();
	assert(!qcom_iommu_resume(&dev) && iommu.ctx_online && !contexts && ctx_writes == 3);
	assert(ctx_trace[1].reg == ARM_SMMU_CB_S1_TLBIASID &&
	       ctx_trace[2].reg == ARM_SMMU_CB_TLBSYNC);
	assert(!iommu.ctx_lock && !domain.pgtbl_lock && irq_gets == 2);

	ctx.domain = &domain.domain;
	ctx_reads = ctx_writes = 0;
	qcom_iommu_domain_free(&domain.domain);
	assert(!ctx.domain && ctx_reads == 1 && ctx_writes == 3 && irq_syncs == 2 &&
	       freed_tables == 2 && freed_objects == 4);
	assert(ctx_trace[0].reg == ARM_SMMU_CB_SCTLR &&
	       ctx_trace[1].reg == ARM_SMMU_CB_S1_TLBIASID &&
	       ctx_trace[2].reg == ARM_SMMU_CB_TLBSYNC);
}

int main(void)
{
	struct venus_resources res = {
		.reg_tbl = msm8226_reg_preset, .reg_tbl_size = ARRAY_SIZE(msm8226_reg_preset),
		.bw_tbl_enc = msm8226_bw_enc, .bw_tbl_enc_size = ARRAY_SIZE(msm8226_bw_enc),
		.bw_tbl_dec = msm8226_bw_dec, .bw_tbl_dec_size = ARRAY_SIZE(msm8226_bw_dec),
		.split_reg_banks = true, .bw_per_direction = true,
	};
	struct venus_core venus = { .res = &res, .video_path = &res };
	struct venus_hfi_device hfi = { &venus };
	struct platform_device pdev = { 0 };
	struct venus_inst enc_a = { VIDC_SESSION_TYPE_ENC, 0, 20000 };
	struct venus_inst enc_b = { VIDC_SESSION_TYPE_ENC, 0, 16001 };
	struct venus_inst dec = { VIDC_SESSION_TYPE_DEC, 0, 110400 };
	struct qcom_iommu_cfg cfg = { .ctx_restore = true, .halt = true };
	struct qcom_iommu_ctx ns = { .domain = &cfg, .base = context_regs };
	struct qcom_iommu_ctx sec = { .domain = &cfg, .secured_ctx = true, .asid = 1 };
	struct iommu_fwspec fwspec = { 2, { 1, 0 } };
	struct qcom_iommu_dev iommu = { .wrapper_clk_sel = &clock_select, .cfg = &cfg,
				       .global_base = global_regs,
				       .max_asid = 1, .ctxs = { &ns, &sec } };
	struct device dev = { &iommu, &iommu, &fwspec };
	struct qcom_iommu_domain qcom_domain = { .asids = fwspec.ids, .num_asids = 2 };
	struct iommu_domain domain = { &qcom_domain };
	struct iommu_domain identity = { 0 };
	u32 avg, peak;

	assert(!venus_map_registers(&pdev, &venus) && pdev.calls == 4);
	assert(venus.cpu_cs_base == cpu + 0x12000 / 4 && venus.cpu_ic_base == cpu + 0x1f000 / 4);
	assert(venus_wrapper_addr(&venus, 0) == &wrapper[0]);
	assert(venus_wrapper_addr(&venus, 0xc) == &wrapper[3]);
	assert(venus_wrapper_addr(&venus, 0x3000) == &wrapper[0x3000 / 4]);
	wrapper[1] = 0xa5a5a5a5;
	wrapper[0] = 0x5a5a5a5a;
	venus_set_registers(&hfi);
	assert(wrapper[1] == 0xa5a5a5a5 && wrapper[0] == 0x5a5a5a5a);
	for (unsigned int i = 0; i < ARRAY_SIZE(msm8226_reg_preset); i++) {
		u32 offset = msm8226_reg_preset[i].reg;
		u32 *word = offset >= WRAPPER_BASE ? &wrapper[(offset - WRAPPER_BASE) / 4] :
			    &vbif[(offset - VBIF_BASE) / 4];

		assert(*word == msm8226_reg_preset[i].value);
	}

	for (unsigned int i = 1; i <= 4; i++) {
		pdev = (struct platform_device) { .fail_at = i };
		assert(venus_map_registers(&pdev, &venus) == -ENOMEM && pdev.calls == i);
	}

	venus = (struct venus_core) { .res = &res, .video_path = &res };
	pdev = (struct platform_device) { 0 };
	res.split_reg_banks = false;
	assert(!venus_map_registers(&pdev, &venus) && pdev.calls == 1);
	assert(venus_wrapper_addr(&venus, 0xc) == combined + (WRAPPER_BASE + 0xc) / 4);
	venus.iris2 = true;
	assert(!venus_map_registers(&pdev, &venus));
	assert(venus_wrapper_addr(&venus, 0xc) == combined + (WRAPPER_BASE_V6 + 0xc) / 4);
	assert(venus.wrapper_tz_base == combined + WRAPPER_TZ_BASE_V6 / 4);

	mbs_to_bw(&res, VIDC_SESSION_TYPE_ENC, false, 0, &avg, &peak);
	assert(!avg && !peak);
	mbs_to_bw(&res, VIDC_SESSION_TYPE_ENC, false, 36000, &avg, &peak);
	assert(avg == 129000 && peak == 142000);
	mbs_to_bw(&res, VIDC_SESSION_TYPE_ENC, false, 36001, &avg, &peak);
	assert(avg == 384000 && peak == 422000);
	mbs_to_bw(&res, VIDC_SESSION_TYPE_DEC, false, 110401, &avg, &peak);
	assert(avg == 505000 && peak == 657000);
	venus.instances[0] = &enc_a;
	venus.instances[1] = &enc_b;
	venus.instances[2] = &dec;
	assert(!load_scale_bw(&venus) && observed_avg == 652000 && observed_peak == 422000);
	res.bw_per_direction = false;
	assert(!load_scale_bw(&venus) && observed_avg == 526000 && observed_peak == 632000);

	clock_select = 0x4141;
	clock_error = -EBUSY;
	assert(qcom_iommu_resume(&dev) == -EBUSY && !reads && !writes);
	clock_error = 0;
	clock_stuck = 1;
	assert(qcom_iommu_resume(&dev) == -EIO && enables == disables && !restores && !presets);
	clock_stuck = 0;
	secure_error = -EINVAL;
	assert(qcom_iommu_resume(&dev) == -EINVAL && enables == disables && !presets);
	clock_select = 0x4141;
	secure_error = 0;
	reads = writes = restores = 0;
	assert(!qcom_iommu_resume(&dev));
	assert(reads == 2 && writes == 1 && clock_select == 0x4140);
	assert(restores == 1 && presets == 1 && contexts == 1);
	iommu.wrapper_clk_sel = NULL;
	iommu.non_secure = true;
	reads = writes = 0;
	assert(!qcom_iommu_resume(&dev));
	assert(!reads && !writes && resets == 1 && contexts == 2);
	iommu.dev = &dev;
	pm_error = -EIO;
	assert(qcom_iommu_attach_dev(&domain, &dev, NULL) == -EIO);
	assert(pm_gets == 1 && !pm_puts && !domain_initializations);
	pm_error = 0;
	assert(!qcom_iommu_attach_dev(&domain, &dev, NULL));
	assert(pm_gets == 2 && pm_puts == 1 && domain_initializations == 1);

	for (unsigned int leaf = 0; leaf < 2; leaf++) {
		unsigned int reg = leaf ? ARM_SMMU_CB_S1_TLBIVAL : ARM_SMMU_CB_S1_TLBIVA;

		ctx_writes = 0;
		qcom_iommu_tlb_inv_range_nosync(0x40123789, 0x3000, 0x1000, leaf, &qcom_domain);
		assert(ctx_writes == 6);
		for (unsigned int idx = 0; idx < ctx_writes; idx++) {
			struct qcom_iommu_ctx *bank = idx < 3 ? &sec : &ns;

			assert(ctx_trace[idx].ctx == bank && ctx_trace[idx].reg == reg);
			assert(ctx_trace[idx].value == (0x40123000 + idx % 3 * 0x1000 + bank->asid));
		}
	}

	ctx_writes = 0;
	assert(!qcom_iommu_identity_attach(&identity, &dev, NULL));
	assert(!qcom_iommu_identity_attach(&identity, &dev, &identity));
	assert(pm_gets == 2 && pm_puts == 1 && !ctx_writes);
	pm_error = -EIO;
	assert(qcom_iommu_identity_attach(&identity, &dev, &domain) == -EIO);
	assert(pm_gets == 3 && pm_puts == 1 && !ctx_writes && ns.domain && sec.domain);
	pm_error = 0;
	assert(!qcom_iommu_identity_attach(&identity, &dev, &domain));
	assert(pm_gets == 4 && pm_puts == 2 && ctx_writes == 2 && !ns.domain && !sec.domain);
	assert(ctx_trace[0].ctx == &sec && ctx_trace[1].ctx == &ns);
	assert(ctx_trace[0].reg == ARM_SMMU_CB_SCTLR && !ctx_trace[0].value);
	assert(ctx_trace[1].reg == ARM_SMMU_CB_SCTLR && !ctx_trace[1].value);

	check_offline_venus();
	puts("{\"passed\":true,\"preset_writes\":10,\"failed_map_slots\":4,"
	     "\"bandwidth_boundary_and_aggregation_cases\":6,\"clock_resume_cases\":5,"
	     "\"attach_PM_cases\":2,\"identity_PM_cases\":4,\"range_invalidation_writes\":12,"
	     "\"offline_venus_lifecycle\":true,\"offline_fault_paths\":4}");
	return 0;
}
