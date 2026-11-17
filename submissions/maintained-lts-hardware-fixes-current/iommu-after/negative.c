
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <assert.h>
#define __iomem
#define BIT(x) (1U << (x))
typedef uint32_t u32;
struct qcom_iommu_cfg { bool halt; };
struct qcom_iommu_dev { struct qcom_iommu_cfg *cfg; void *global_base; void *dev; };
static unsigned char registers[0x3000];
static unsigned reads, writes, polls, errors;
static bool timeout;
static u32 readl_relaxed(void *p) {
    assert(p == registers + 0x2000);
    u32 value;
    memcpy(&value, p, sizeof(value));
    reads++;
    return timeout ? value : value | BIT(3);
}
static void writel_relaxed(u32 value, void *p) {
    assert(p == registers + 0x2000);
    memcpy(p, &value, sizeof(value));
    writes++;
}
#define readl_poll_timeout(reg, val, cond, delay, limit) \
    (polls++, assert((delay) == 0 && (limit) == 100000), \
     (val = readl_relaxed(reg)), timeout ? -110 : ((cond) ? 0 : -110))
#define dev_err(dev, text) ((void)(dev), (void)(text), errors++)
#define QCOM_IOMMU_IMPL_DEF		0x2000
#define QCOM_IOMMU_MICRO_MMU_CTRL	(QCOM_IOMMU_IMPL_DEF + 0x000)
#define MICRO_MMU_CTRL_HALT_REQ		BIT(2)
#define MICRO_MMU_CTRL_IDLE		BIT(3)
static void qcom_iommu_halt(struct qcom_iommu_dev *qcom_iommu)
{
	void __iomem *reg = qcom_iommu->global_base + QCOM_IOMMU_MICRO_MMU_CTRL;
	u32 val;

	if (!qcom_iommu->cfg || !qcom_iommu->cfg->halt)
		return;

	writel_relaxed(readl_relaxed(reg) | MICRO_MMU_CTRL_HALT_REQ, reg);

	if (readl_poll_timeout(reg, val, val & MICRO_MMU_CTRL_IDLE, 0, 100000))
		dev_err(qcom_iommu->dev, "timeout waiting for micro-MMU halt\n");
}

static void qcom_iommu_unhalt(struct qcom_iommu_dev *qcom_iommu)
{
	void __iomem *reg = qcom_iommu->global_base + QCOM_IOMMU_MICRO_MMU_CTRL;

	if (!qcom_iommu->cfg || !qcom_iommu->cfg->halt)
		return;

	writel_relaxed(readl_relaxed(reg) & ~MICRO_MMU_CTRL_HALT_REQ, reg);
}
int main(int argc, char **argv) {
    struct qcom_iommu_dev dev = {0};
    if (argc == 2) {
        if (!strcmp(argv[1], "halt")) qcom_iommu_halt(&dev);
        else if (!strcmp(argv[1], "unhalt")) qcom_iommu_unhalt(&dev);
        else assert(0);
        return 0;
    }
    assert(argc == 1);
    qcom_iommu_halt(&dev);
    qcom_iommu_unhalt(&dev);
    assert(reads == 0 && writes == 0 && polls == 0 && errors == 0);
    struct qcom_iommu_cfg config = {0};
    dev.cfg = &config;
    qcom_iommu_halt(&dev);
    qcom_iommu_unhalt(&dev);
    assert(reads == 0 && writes == 0 && polls == 0 && errors == 0);
    config.halt = true;
    dev.global_base = registers;
    u32 value = 0x80;
    memcpy(registers + 0x2000, &value, sizeof(value));
    qcom_iommu_halt(&dev);
    memcpy(&value, registers + 0x2000, sizeof(value));
    assert((value & BIT(2)) && (value & 0x80));
    qcom_iommu_unhalt(&dev);
    memcpy(&value, registers + 0x2000, sizeof(value));
    assert(!(value & BIT(2)) && (value & 0x80));
    assert(writes == 2 && polls == 1 && errors == 0);
    timeout = true;
    qcom_iommu_halt(&dev);
    qcom_iommu_unhalt(&dev);
    memcpy(&value, registers + 0x2000, sizeof(value));
    assert(!(value & BIT(2)) && (value & 0x80));
    assert(writes == 4 && polls == 2 && errors == 1);
    puts("Four cases passed: absent cfg, disabled halt, enabled RMW, timeout diagnostic");
    return 0;
}
