// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic core, IOVA allocation and VB2 descriptor services, not hardware. */
#include <assert.h>
#include <errno.h>
#include <inttypes.h>
#include <limits.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <linux/videodev2.h>

typedef uint64_t dma_addr_t;
typedef uint64_t phys_addr_t;
typedef uint64_t u64;
#define PAGE_SHIFT 12
#define PAGE_SIZE (1UL << PAGE_SHIFT)
#define PAGE_MASK (~(PAGE_SIZE - 1))
#define PAGE_ALIGN(n) (((n) + PAGE_SIZE - 1) & PAGE_MASK)
#define SZ_64K 65536U
#define DMA_MAPPING_ERROR UINT64_MAX
#define DMA_BIT_MASK(n) ((1ULL << (n)) - 1)
#define DMA_ATTR_SKIP_CPU_SYNC 1
#define GFP_KERNEL 0
#define WARN_ON_ONCE(x) (!!(x))
#define container_of(p, t, member) ((t *)((char *)(p) - offsetof(t, member)))
enum dma_data_direction { DMA_FROM_DEVICE };
struct device_dma_parameters { unsigned int max_segment_size; };
struct device {
	bool dma_coherent;
	struct device_dma_parameters *dma_parms;
	u64 coherent_dma_mask, *dma_mask;
};
struct platform_device {
	struct device dev;
	struct device_dma_parameters dma_parms;
	u64 platform_dma_mask;
};
struct page { phys_addr_t phys; };
struct scatterlist {
	struct page *page;
	unsigned int offset, length, dma_length;
	dma_addr_t dma_address;
	struct scatterlist *next;
};
struct sg_table { struct scatterlist *sgl; unsigned int nents, orig_nents; };
#define sg_dma_address(s) ((s)->dma_address)
#define sg_dma_len(s) ((s)->dma_length)
#define sg_next(s) ((s)->next)
#define sg_page(s) ((s)->page)
#define page_to_phys(p) ((p)->phys)
#define sg_phys(s) (page_to_phys(sg_page(s)) + (s)->offset)
#define for_each_sg(sglist, sg, nr, i) \
	for ((i) = 0, (sg) = (sglist); (i) < (nr); (i)++, (sg) = sg_next(sg))
#define for_each_sgtable_dma_sg(sgt, sg, i) \
	for_each_sg((sgt)->sgl, sg, (sgt)->nents, i)
struct dma_iommu_mapping { void *domain; };
static struct dma_iommu_mapping synthetic_mapping;
#define to_dma_iommu_mapping(dev) ((void)(dev), &synthetic_mapping)
#define dev_dma_coherent(dev) ((void)(dev), true)
#define __dma_page_cpu_to_dev(p, o, n, d) ((void)(p), (void)(o), (void)(n), (void)(d))
#define arch_sync_dma_for_device(p, n, d) ((void)(p), (void)(n), (void)(d))
#define __dma_info_to_prot(d, a) ((void)(d), (void)(a), 0)
static dma_addr_t next_iova, allocation_base;
static size_t allocation_size;
static unsigned int allocations, maps, frees, unmaps, removals;
static unsigned int fail_alloc, fail_map;
static dma_addr_t __alloc_iova(struct dma_iommu_mapping *m, size_t size)
{
	(void)m;
	if (++allocations == fail_alloc)
		return DMA_MAPPING_ERROR;
	allocation_base = next_iova;
	allocation_size = size;
	next_iova += size + PAGE_SIZE; /* Legal gap between separate chunks. */
	return allocation_base;
}
static void __free_iova(struct dma_iommu_mapping *m, dma_addr_t a, size_t n)
{
	(void)m; (void)a; (void)n; frees++;
}
static int iommu_map(void *d, dma_addr_t a, phys_addr_t p, size_t n, int prot, int gfp)
{
	(void)d; (void)p; (void)prot; (void)gfp;
	assert(a >= allocation_base && a + n <= allocation_base + allocation_size);
	return ++maps == fail_map ? -EIO : 0;
}
static size_t iommu_unmap(void *d, dma_addr_t a, size_t n)
{
	(void)d; (void)a; unmaps++; return n;
}
static void __iommu_remove_mapping(struct device *d, dma_addr_t a, size_t n)
{
	(void)d; (void)a; (void)n; removals++;
}
struct camss { struct device *dev; };
struct camss_video {
	struct camss *camss;
	struct v4l2_format active_fmt;
};
struct vb2_queue { struct camss_video *priv; };
struct vb2_buffer {
	struct vb2_queue *vb2_queue;
	struct sg_table *desc[3];
	size_t size[3], payload[3];
};
struct vb2_v4l2_buffer { struct vb2_buffer vb2_buf; unsigned int field; };
struct camss_buffer { struct vb2_v4l2_buffer vb; dma_addr_t addr[3]; };
#define to_vb2_v4l2_buffer(v) container_of(v, struct vb2_v4l2_buffer, vb2_buf)
#define vb2_get_drv_priv(q) ((q)->priv)
#define vb2_dma_sg_plane_desc(v, i) ((v)->desc[i])
#define vb2_plane_size(v, i) ((v)->size[i])
#define vb2_set_plane_payload(v, i, n) ((v)->payload[i] = (n))
#define dev_err_ratelimited(d, fmt, ...) ((void)(d))
