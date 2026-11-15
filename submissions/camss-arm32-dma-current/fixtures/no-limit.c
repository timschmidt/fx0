// SPDX-License-Identifier: GPL-2.0-only
/*
 * Extracted Linux kernel code; original source notices:
 * platform.c: Copyright (c) 2002-3 Patrick Mochel
 *             Copyright (c) 2002-3 Open Source Development Labs
 * arch/arm/mm/dma-mapping.c: Copyright (C) 2000-2004 Russell King
 * camss-video.c: Copyright (c) 2013-2015, The Linux Foundation.
 *               All rights reserved.
 *               Copyright (C) 2015-2018 Linaro Ltd.
 * camss.c: Copyright (c) 2015, The Linux Foundation. All rights reserved.
 *          Copyright (C) 2015-2018 Linaro Ltd.
 * DMA parameter helpers from include/linux/dma-mapping.h (GPL-2.0).
 * See NOTICE and LICENSES/GPL-2.0.txt. Original full source files are
 * supplied under sources/ with their original SPDX tags and notices.
 */
/* BEGIN EXECUTED BODY */
static void setup_pdev_dma_masks(struct platform_device *pdev)
{
	pdev->dev.dma_parms = &pdev->dma_parms;

	if (!pdev->dev.coherent_dma_mask)
		pdev->dev.coherent_dma_mask = DMA_BIT_MASK(32);
	if (!pdev->dev.dma_mask) {
		pdev->platform_dma_mask = DMA_BIT_MASK(32);
		pdev->dev.dma_mask = &pdev->platform_dma_mask;
	}
}

static inline unsigned int dma_get_max_seg_size(struct device *dev)
{
	if (dev->dma_parms && dev->dma_parms->max_segment_size)
		return dev->dma_parms->max_segment_size;
	return SZ_64K;
}

static inline void dma_set_max_seg_size(struct device *dev, unsigned int size)
{
	if (WARN_ON_ONCE(!dev->dma_parms))
		return;
	dev->dma_parms->max_segment_size = size;
}

static int __map_sg_chunk(struct device *dev, struct scatterlist *sg,
			  size_t size, dma_addr_t *handle,
			  enum dma_data_direction dir, unsigned long attrs)
{
	struct dma_iommu_mapping *mapping = to_dma_iommu_mapping(dev);
	dma_addr_t iova, iova_base;
	int ret = 0;
	unsigned int count;
	struct scatterlist *s;
	int prot;

	size = PAGE_ALIGN(size);
	*handle = DMA_MAPPING_ERROR;

	iova_base = iova = __alloc_iova(mapping, size);
	if (iova == DMA_MAPPING_ERROR)
		return -ENOMEM;

	for (count = 0, s = sg; count < (size >> PAGE_SHIFT); s = sg_next(s)) {
		phys_addr_t phys = page_to_phys(sg_page(s));
		unsigned int len = PAGE_ALIGN(s->offset + s->length);

		if (!dev_dma_coherent(dev) && !(attrs & DMA_ATTR_SKIP_CPU_SYNC))
			arch_sync_dma_for_device(sg_phys(s), s->length, dir);

		prot = __dma_info_to_prot(dir, attrs);

		ret = iommu_map(mapping->domain, iova, phys, len, prot,
				GFP_KERNEL);
		if (ret < 0)
			goto fail;
		count += len >> PAGE_SHIFT;
		iova += len;
	}
	*handle = iova_base;

	return 0;
fail:
	iommu_unmap(mapping->domain, iova_base, count * PAGE_SIZE);
	__free_iova(mapping, iova_base, size);
	return ret;
}

static int arm_iommu_map_sg(struct device *dev, struct scatterlist *sg,
		int nents, enum dma_data_direction dir, unsigned long attrs)
{
	struct scatterlist *s = sg, *dma = sg, *start = sg;
	int i, count = 0, ret;
	unsigned int offset = s->offset;
	unsigned int size = s->offset + s->length;
	unsigned int max = dma_get_max_seg_size(dev);

	for (i = 1; i < nents; i++) {
		s = sg_next(s);

		s->dma_length = 0;

		if (s->offset || (size & ~PAGE_MASK) || size + s->length > max) {
			ret = __map_sg_chunk(dev, start, size,
					     &dma->dma_address, dir, attrs);
			if (ret < 0)
				goto bad_mapping;

			dma->dma_address += offset;
			dma->dma_length = size - offset;

			size = offset = s->offset;
			start = s;
			dma = sg_next(dma);
			count += 1;
		}
		size += s->length;
	}
	ret = __map_sg_chunk(dev, start, size, &dma->dma_address, dir, attrs);
	if (ret < 0)
		goto bad_mapping;

	dma->dma_address += offset;
	dma->dma_length = size - offset;

	return count+1;

bad_mapping:
	for_each_sg(sg, s, count, i)
		__iommu_remove_mapping(dev, sg_dma_address(s), sg_dma_len(s));
	if (ret == -ENOMEM)
		return ret;
	return -EINVAL;
}

static void apply_probe_statement(struct device *dev)
{
	(void)dev;
}

static int video_buf_init(struct vb2_buffer *vb)
{
	struct vb2_v4l2_buffer *vbuf = to_vb2_v4l2_buffer(vb);
	struct camss_video *video = vb2_get_drv_priv(vb->vb2_queue);
	struct camss_buffer *buffer = container_of(vbuf, struct camss_buffer,
						   vb);
	const struct v4l2_pix_format_mplane *format =
						&video->active_fmt.fmt.pix_mp;
	struct sg_table *sgt;
	struct scatterlist *s;
	dma_addr_t expected;
	unsigned long size;
	unsigned int i, j;

	for (i = 0; i < format->num_planes; i++) {
		sgt = vb2_dma_sg_plane_desc(vb, i);
		if (!sgt)
			return -EFAULT;

		/* Adjacent DMA segments may cover one linear image plane. */
		expected = sg_dma_address(sgt->sgl);
		size = 0;
		for_each_sgtable_dma_sg(sgt, s, j) {
			if (sg_dma_address(s) != expected)
				break;
			size += sg_dma_len(s);
			if (size >= format->plane_fmt[i].sizeimage)
				break;
			expected += sg_dma_len(s);
		}
		if (size < format->plane_fmt[i].sizeimage) {
			dev_err_ratelimited(video->camss->dev,
					    "Buffer plane %u is not contiguous\n",
					    i);
			return -EFAULT;
		}

		buffer->addr[i] = sg_dma_address(sgt->sgl);
	}

	if (format->pixelformat == V4L2_PIX_FMT_NV12 ||
			format->pixelformat == V4L2_PIX_FMT_NV21 ||
			format->pixelformat == V4L2_PIX_FMT_NV16 ||
			format->pixelformat == V4L2_PIX_FMT_NV61)
		buffer->addr[1] = buffer->addr[0] +
				format->plane_fmt[0].bytesperline *
				format->height;

	return 0;
}

static int video_buf_prepare(struct vb2_buffer *vb)
{
	struct vb2_v4l2_buffer *vbuf = to_vb2_v4l2_buffer(vb);
	struct camss_video *video = vb2_get_drv_priv(vb->vb2_queue);
	const struct v4l2_pix_format_mplane *format =
						&video->active_fmt.fmt.pix_mp;
	unsigned int i;

	for (i = 0; i < format->num_planes; i++) {
		if (format->plane_fmt[i].sizeimage > vb2_plane_size(vb, i))
			return -EINVAL;

		vb2_set_plane_payload(vb, i, format->plane_fmt[i].sizeimage);
	}

	vbuf->field = V4L2_FIELD_NONE;

	return 0;
}
/* END EXECUTED BODY */
