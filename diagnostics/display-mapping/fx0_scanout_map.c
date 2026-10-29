// SPDX-License-Identifier: GPL-2.0-only
/* Read only the pinned diagnostic RGB buffer via its active IOMMU mapping. */
#include <linux/highmem.h>
#include <linux/io.h>
#include <linux/of_address.h>
#include <linux/pm_runtime.h>
#include <linux/iommu.h>
#include <linux/module.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>

static unsigned long iova;
module_param(iova, ulong, 0400);

static int __init scanout_init(void)
{
	static const unsigned int xs[] = { 0, 240, 480, 719 };
	static const unsigned int ys[] = { 0, 1, 1279 };
	struct platform_device *pdev;
	struct resource resource;
	void __iomem *pipe;
	struct device_node *node;
	struct iommu_domain *domain;
	unsigned int x, y, matches = 0;
	int ret = 0;

	if (!of_machine_is_compatible("lg,madai") || !iova ||
	    iova > 0xffffffffUL - 3768320 || (iova & ~PAGE_MASK))
		return -EINVAL;
	node = of_find_compatible_node(NULL, NULL, "qcom,msm8226-mdp5");
	if (!node)
		return -ENODEV;
	pdev = of_find_device_by_node(node);
	of_node_put(node);
	if (!pdev)
		return -ENODEV;
	domain = iommu_get_domain_for_dev(&pdev->dev);
	if (!domain) {
		ret = -ENODEV;
		goto put;
	}
	ret = of_address_to_resource(pdev->dev.of_node, 0, &resource);
	if (ret)
		goto put;
	if (resource.start != 0xfd900100 || resource_size(&resource) < 0x29b8) {
		ret = -ENODEV;
		goto put;
	}
	ret = pm_runtime_get_if_in_use(&pdev->dev);
	if (ret <= 0) {
		ret = ret < 0 ? ret : -EBUSY;
		goto put;
	}
	pipe = ioremap(resource.start + 0x2900, 0xb8);
	if (!pipe) {
		pm_runtime_put(&pdev->dev);
		ret = -ENOMEM;
		goto put;
	}
	{
		static const u32 offsets[] = { 0, 4, 8, 0xc, 0x10, 0x14,
			0x24, 0x30, 0x34, 0x38, 0x3c, 0x48, 0x70, 0xa4 };
		unsigned int n;

		for (n = 0; n < ARRAY_SIZE(offsets); n++)
			pr_info("Fx0 DMA0 offset=%02x value=%08x\n",
				offsets[n], readl(pipe + offsets[n]));
	}
	iounmap(pipe);
	pm_runtime_put(&pdev->dev);
	ret = 0;
	for (y = 0; y < ARRAY_SIZE(ys); y++) {
		for (x = 0; x < ARRAY_SIZE(xs); x++) {
			unsigned long address = iova + ys[y] * 2944 + xs[x] * 4;
			phys_addr_t physical = iommu_iova_to_phys(domain, address);
			u32 expected = xs[x] < 240 ? 0xffff0000 :
				       xs[x] < 480 ? 0xff00ff00 : 0xff0000ff;
			void *mapping;
			u32 value;

			if (!physical || !pfn_valid(PHYS_PFN(physical))) {
				ret = -EFAULT;
				goto put;
			}
			mapping = kmap_local_page(pfn_to_page(PHYS_PFN(physical)));
			value = READ_ONCE(*(u32 *)(mapping + offset_in_page(physical)));
			kunmap_local(mapping);
			matches += value == expected;
			pr_info("Fx0 scanout x=%u y=%u iova=%08lx phys=%pa value=%08x expected=%08x\n",
				xs[x], ys[y], address, &physical, value, expected);
		}
	}
	pr_info("Fx0 scanout software-map samples match=%u/%zu; no hardware translation/fetch proof\n",
		matches, ARRAY_SIZE(xs) * ARRAY_SIZE(ys));
put:
	put_device(&pdev->dev);
	return ret;
}
static void __exit scanout_exit(void) { }
module_init(scanout_init);
module_exit(scanout_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary read-only Fx0 diagnostic scanout map inspection");
