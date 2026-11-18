/* SPDX-License-Identifier: GPL-2.0-only */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#define CONFIG_ARM_DMA_USE_IOMMU 1
#define PAGE_SHIFT 12
#define DMA_BIT_MASK(bits) ((UINT64_C(1) << (bits)) - 1)
#define min(x, y) ((x) < (y) ? (x) : (y))
#define min_t(type, x, y) min((type)(x), (type)(y))
#define VENUS_NP_RESERVE_IOVA_START 0
#define VENUS_NP_RESERVE_IOVA_SIZE 0x25800000

typedef uint64_t u64;

struct iommu_domain { int id; };
struct dma_map_ops { int id; };
struct dma_iommu_mapping {
	struct iommu_domain *domain;
	uint32_t base;
	uint32_t bits;
	uint32_t extensions;
};
struct device {
	struct dma_iommu_mapping *mapping;
	const struct dma_map_ops *ops;
	struct iommu_domain *domain;
	u64 bus_dma_limit;
};
struct venus_resources { u64 dma_mask; };
struct venus_core {
	struct device *dev;
	struct venus_resources *res;
};
struct dma_iova_state { u64 bytes; };

static const struct dma_map_ops iommu_ops = {1};
static unsigned int frees;

static struct dma_iommu_mapping *to_dma_iommu_mapping(struct device *dev)
{
	return dev->mapping;
}

static const struct dma_map_ops *get_dma_ops(struct device *dev)
{
	return dev->ops;
}

static struct iommu_domain *iommu_get_domain_for_dev(struct device *dev)
{
	return dev->domain;
}

static int dev_err_probe(struct device *dev, int error, const char *description)
{
	assert(dev && *description);
	return error;
}

static u64 dma_iova_size(struct dma_iova_state *state)
{
	return state->bytes;
}

static void dma_iova_free(struct device *dev, struct dma_iova_state *state)
{
	assert(dev && state->bytes);
	frees++;
}

/* kernel helpers */

#define CHECK(condition) do { assert(condition); checks++; } while (0)

int main(void)
{
	struct iommu_domain active = {1}, other = {2};
	const struct dma_map_ops direct = {2};
	struct dma_iommu_mapping mapping = {&active, 0x40000000, 32768, 8};
	struct device dev = {&mapping, &iommu_ops, &active, 0};
	struct venus_resources res = {0x7fffffff};
	struct venus_core core = {&dev, &res};
	struct dma_iova_state states[] = {{4096}, {8192}, {0}};
	unsigned int checks = 0;

	CHECK(venus_reserve_iova_region(&core) == 0);
	CHECK(dev.bus_dma_limit == 0);
	dev.bus_dma_limit = 0x7fffffff;
	CHECK(venus_reserve_iova_region(&core) == 0);
	dev.bus_dma_limit--;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	dev.bus_dma_limit = UINT64_C(1) << 40;
	res.dma_mask--;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	res.dma_mask++;
	mapping.base = 0x257ff000;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	mapping.base += 4096;
	CHECK(venus_reserve_iova_region(&core) == 0);
	mapping.base = 0x40000000;
	mapping.extensions++;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	mapping.extensions = 0;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	mapping.extensions = 8;
	dev.mapping = NULL;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	dev.mapping = &mapping;
	dev.ops = &direct;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	dev.ops = NULL;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	dev.ops = &iommu_ops;
	dev.domain = &other;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	dev.domain = NULL;
	mapping.domain = NULL;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	dev.domain = mapping.domain = &active;
	res.dma_mask = 0x257fffff;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	res.dma_mask = UINT64_MAX;
	mapping.base = 0xc0000000;
	CHECK(venus_reserve_iova_region(&core) == 0);
	mapping.base += 4096;
	CHECK(venus_reserve_iova_region(&core) == -EOPNOTSUPP);
	CHECK(!arm_iommu_dma_aperture_within(&dev, 0, UINT64_C(1) << 40));
	CHECK(!arm_iommu_dma_aperture_within(&dev, 0, 0x20000000));
	CHECK(!arm_iommu_dma_aperture_within(&dev, 0x80000000, 0x80000000));
	CHECK(dev.bus_dma_limit == (UINT64_C(1) << 40));
	venus_unreserve_iova_region(&dev, NULL);
	CHECK(frees == 0);
	venus_unreserve_iova_region(&dev, states);
	CHECK(frees == 2);
	printf("{\"passed\":true,\"checks\":%u}\n", checks);
	return 0;
}
