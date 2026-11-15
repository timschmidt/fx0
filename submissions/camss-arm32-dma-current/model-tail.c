// SPDX-License-Identifier: GPL-2.0-only
static unsigned int checks, failures;
static void check(bool ok, const char *label)
{
	checks++;
	if (!ok) { failures++; printf("FAIL %s\n", label); }
}
static struct scatterlist sg[5000];
static struct page pages[5000];
static struct platform_device pdev;
static struct camss camss;
static struct camss_video video;
static struct vb2_queue queue;
static struct camss_buffer buffer;
static struct sg_table table;
static void reset(size_t required)
{
	memset(&pdev, 0, sizeof(pdev));
	memset(&video, 0, sizeof(video));
	memset(&buffer, 0, sizeof(buffer));
	memset(sg, 0, sizeof(sg));
	setup_pdev_dma_masks(&pdev);
	apply_probe_statement(&pdev.dev);
	camss.dev = &pdev.dev;
	video.camss = &camss;
	video.active_fmt.fmt.pix_mp.num_planes = 1;
	video.active_fmt.fmt.pix_mp.plane_fmt[0].sizeimage = required;
	queue.priv = &video;
	buffer.vb.vb2_buf.vb2_queue = &queue;
	buffer.vb.vb2_buf.desc[0] = &table;
	buffer.vb.vb2_buf.size[0] = required;
	table = (struct sg_table){ .sgl = sg };
	next_iova = 0x10000000;
	allocations = maps = frees = unmaps = removals = fail_alloc = fail_map = 0;
}
static unsigned int page_list(size_t bytes)
{
	unsigned int count = PAGE_ALIGN(bytes) >> PAGE_SHIFT;
	assert(count < 5000);
	for (unsigned int i = 0; i < count; i++) {
		pages[i].phys = 0x100000 + i * 2 * PAGE_SIZE;
		sg[i].page = &pages[i];
		sg[i].length = PAGE_SIZE;
		sg[i].next = i + 1 < count ? &sg[i + 1] : NULL;
	}
	table.orig_nents = count;
	return count;
}
static void imported(unsigned int n, const dma_addr_t *addresses, const unsigned int *lengths)
{
	table.nents = table.orig_nents = n;
	for (unsigned int i = 0; i < n; i++) {
		sg[i].dma_address = addresses[i];
		sg[i].dma_length = lengths[i];
		sg[i].next = i + 1 < n ? &sg[i + 1] : NULL;
	}
}
int main(void)
{
	struct platform_device parameter_probe = {0};
	setup_pdev_dma_masks(&parameter_probe);
	check(dma_get_max_seg_size(&parameter_probe.dev) == SZ_64K,
	      "real DMA getter defaults to 64KiB on platform device");
	dma_set_max_seg_size(&parameter_probe.dev, UINT_MAX);
	check(dma_get_max_seg_size(&parameter_probe.dev) == UINT_MAX,
	      "real DMA setter updates platform parameters");
	const size_t sizes[] = {4096, 65536, 69632, 1976*1200*2,
		3280*2464*2, 1640*1232*2, 720*1280*3/2};
	reset(4096);
	check(pdev.dev.dma_parms == &pdev.dma_parms &&
	      *pdev.dev.dma_mask == UINT32_MAX && pdev.dev.coherent_dma_mask == UINT32_MAX,
	      "real platform defaults install DMA parameters and 32-bit masks");
	check(dma_get_max_seg_size(&pdev.dev) == UINT_MAX, "probe removes default 64KiB segment limit");
	for (unsigned int i = 0; i < sizeof(sizes)/sizeof(sizes[0]); i++) {
		reset(sizes[i]);
		unsigned int n = page_list(sizes[i]);
		int mapped = arm_iommu_map_sg(&pdev.dev, sg, n, DMA_FROM_DEVICE, 0);
		check(mapped > 0, "real ARM mapper maps synthetic frame pages");
		table.nents = mapped > 0 ? (unsigned int)mapped : 0;
		check(mapped == 1 && sg[0].dma_length >= sizes[i] &&
		      video_buf_init(&buffer.vb.vb2_buf) == 0 &&
		      buffer.addr[0] == sg[0].dma_address, "normal frame remains usable as one linear DMA range");
		check(video_buf_prepare(&buffer.vb.vb2_buf) == 0 &&
		      buffer.vb.vb2_buf.payload[0] == sizes[i], "real preparation preserves image payload");
	}
	const dma_addr_t adjacent[] = {0x10000000, 0x10010000, 0x10020000};
	const dma_addr_t gapped[] = {0x10000000, 0x10011000, 0x10022000};
	const dma_addr_t overlapping[] = {0x10000000, 0x1000f000, 0x10020000};
	const unsigned int lengths[] = {65536, 65536, 65536};
	for (unsigned int count = 1; count <= 3; count++) {
		reset(count * 65536);
		imported(count, adjacent, lengths);
		check(video_buf_init(&buffer.vb.vb2_buf) == 0 && buffer.addr[0] == adjacent[0],
		      "one or several adjacent imported DMA segments accepted");
		if (count > 1) {
			imported(count, gapped, lengths);
			check(video_buf_init(&buffer.vb.vb2_buf) == -EFAULT, "gapped imported DMA segments rejected");
			imported(count, overlapping, lengths);
			check(video_buf_init(&buffer.vb.vb2_buf) == -EFAULT, "overlapping imported DMA segments rejected");
		}
	}
	reset(65536);
	imported(3, gapped, lengths);
	buffer.vb.vb2_buf.size[0] = 3 * 65536;
	check(video_buf_init(&buffer.vb.vb2_buf) == 0, "unused imported buffer tail need not be contiguous");
	reset(65537);
	imported(1, adjacent, lengths);
	check(video_buf_init(&buffer.vb.vb2_buf) == -EFAULT, "insufficient contiguous prefix rejected");
	reset(4096);
	buffer.vb.vb2_buf.desc[0] = NULL;
	check(video_buf_init(&buffer.vb.vb2_buf) == -EFAULT, "missing VB2 descriptor rejected");
	for (unsigned int mode = 0; mode < 2; mode++) {
		reset(8192);
		page_list(8192);
		if (mode) { sg[1].offset = 128; sg[1].length -= 128; }
		else sg[0].length -= 128;
		video.active_fmt.fmt.pix_mp.plane_fmt[0].sizeimage = 8192 - 128;
		int mapped = arm_iommu_map_sg(&pdev.dev, sg, 2, DMA_FROM_DEVICE, 0);
		table.nents = mapped > 0 ? (unsigned int)mapped : 0;
		check(mapped == 2 && video_buf_init(&buffer.vb.vb2_buf) == -EFAULT,
		      "ARM mapper offset or partial-page forced gaps rejected despite large segment limit");
	}
	struct scatterlist other = {.dma_address = 0x20000000, .dma_length = 65536};
	struct sg_table other_table = {.sgl = &other, .nents = 1, .orig_nents = 1};
	reset(65536);
	imported(1, adjacent, lengths);
	video.active_fmt.fmt.pix_mp.num_planes = 2;
	video.active_fmt.fmt.pix_mp.plane_fmt[1].sizeimage = 65536;
	buffer.vb.vb2_buf.desc[1] = &other_table;
	buffer.vb.vb2_buf.size[1] = 65536;
	check(video_buf_init(&buffer.vb.vb2_buf) == 0 && buffer.addr[1] == other.dma_address,
	      "separate memory planes need not be adjacent to each other");
	other.dma_length--;
	check(video_buf_init(&buffer.vb.vb2_buf) == -EFAULT, "each separate memory plane checked");
	const unsigned int nv[] = {V4L2_PIX_FMT_NV12, V4L2_PIX_FMT_NV21, V4L2_PIX_FMT_NV16, V4L2_PIX_FMT_NV61};
	for (unsigned int i = 0; i < 4; i++) {
		reset(65536);
		imported(1, adjacent, lengths);
		video.active_fmt.fmt.pix_mp.pixelformat = nv[i];
		video.active_fmt.fmt.pix_mp.plane_fmt[0].bytesperline = 256;
		video.active_fmt.fmt.pix_mp.height = 128;
		check(video_buf_init(&buffer.vb.vb2_buf) == 0 && buffer.addr[1] == adjacent[0]+32768,
		      "single-plane NV chroma address derivation preserved");
	}
	reset(8192);
	page_list(8192);
	fail_alloc = 1;
	check(arm_iommu_map_sg(&pdev.dev, sg, 2, DMA_FROM_DEVICE, 0) == -ENOMEM && maps == 0,
	      "real mapper propagates first allocation failure");
	reset(8192);
	page_list(8192);
	fail_map = 2;
	check(arm_iommu_map_sg(&pdev.dev, sg, 2, DMA_FROM_DEVICE, 0) == -EINVAL && frees == 1 && unmaps == 1,
	      "real mapper cleans partial mapping on IOMMU failure");
	reset(4096);
	buffer.vb.vb2_buf.size[0]--;
	check(video_buf_prepare(&buffer.vb.vb2_buf) == -EINVAL, "real preparation rejects undersized plane");
	printf("{\"checks\":%u,\"failures\":%u}\n", checks, failures);
	return failures ? 1 : 0;
}
