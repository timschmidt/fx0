// SPDX-License-Identifier: GPL-2.0-only
/* Bounded ARMv7s privileged-read ATOS query; never changes translation tables. */
#include <linux/io.h>
#include <linux/iopoll.h>
#include <linux/iommu.h>
#include <linux/module.h>
#include <linux/of_address.h>
#include <linux/of_platform.h>
#include <linux/platform_device.h>
#include <linux/pm_runtime.h>

static unsigned long iova;
module_param(iova, ulong, 0400);
static int __init query_init(void)
{
	static const unsigned long offsets[] = { 0, 4096, 3768320 - 4096 };
	struct device_node *node;
	struct platform_device *mdp, *iommu;
	struct iommu_domain *domain;
	struct resource resource;
	void __iomem *cb;
	unsigned int n, matches = 0;
	int ret;

	if (!of_machine_is_compatible("lg,madai") || !iova ||
	    iova > 0xffffffffUL - 3768320 || (iova & ~PAGE_MASK))
		return -EINVAL;
	node = of_find_compatible_node(NULL, NULL, "qcom,msm8226-mdp5");
	mdp = node ? of_find_device_by_node(node) : NULL;
	of_node_put(node);
	if (!mdp)
		return -ENODEV;
	domain = iommu_get_domain_for_dev(&mdp->dev);
	if (!domain) {
		ret = -ENODEV;
		goto put_mdp;
	}
	node = of_find_compatible_node(NULL, NULL, "qcom,msm8226-mdp-iommu");
	iommu = node ? of_find_device_by_node(node) : NULL;
	of_node_put(node);
	if (!iommu) {
		ret = -ENODEV;
		goto put_mdp;
	}
	ret = pm_runtime_get_if_in_use(&iommu->dev);
	if (ret <= 0) {
		ret = ret < 0 ? ret : -EBUSY;
		goto put_iommu;
	}
	node = of_find_node_by_path("/soc/iommu@fd928000/iommu-ctx@0");
	ret = node ? of_address_to_resource(node, 0, &resource) : -ENODEV;
	of_node_put(node);
	if (ret)
		goto put_pm;
	if (resource.start != 0xfd930000 || resource_size(&resource) != 0x1000) {
		ret = -ENODEV;
		goto put_pm;
	}
	cb = ioremap(resource.start, resource_size(&resource));
	if (!cb) {
		ret = -ENOMEM;
		goto put_pm;
	}
	if (!(readl(cb) & 1)) {
		ret = -EBUSY;
		goto unmap;
	}
	for (n = 0; n < ARRAY_SIZE(offsets); n++) {
		unsigned long address = iova + offsets[n];
		phys_addr_t software = iommu_iova_to_phys(domain, address);
		u32 active, par_low, par_high;
		u64 hardware;

		if (!software) {
			ret = -EFAULT;
			break;
		}
		/* ARM32 short descriptors use the 32-bit ATS1PR access. */
		writel(address, cb + 0x800);
		ret = readl_poll_timeout_atomic(cb + 0x8f0, active,
					      !(active & 1), 5, 1000);
		if (ret) {
			pr_err("Fx0 ATOS timeout: iova=%08lx status=%08x\n", address, active);
			break;
		}
		par_low = readl(cb + 0x50);
		par_high = readl(cb + 0x54);
		hardware = ((u64)par_high << 32 | par_low) & GENMASK_ULL(39, 12);
		matches += !(par_low & 1) && hardware == software;
		pr_info("Fx0 ATOS iova=%08lx software=%pa PAR=%08x%08x match=%d\n",
			address, &software, par_high, par_low,
			!(par_low & 1) && hardware == software);
	}
	pr_info("Fx0 ATOS hardware translations match=%u/%zu; not pixel/fetch proof\n",
		matches, ARRAY_SIZE(offsets));
unmap:
	iounmap(cb);
put_pm:
	pm_runtime_put(&iommu->dev);
put_iommu:
	put_device(&iommu->dev);
put_mdp:
	put_device(&mdp->dev);
	return ret;
}
static void __exit query_exit(void) { }
module_init(query_init);
module_exit(query_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Temporary bounded Fx0 active-display IOMMU ATOS query");
