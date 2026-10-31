// SPDX-License-Identifier: GPL-2.0-only
/*
 * Fx0 diagnostic: ask the ADSP core service for its state and service API
 * versions through q6core, and log the answers. Sends only version/state
 * queries; registers no audio devices.
 */
#include <linux/module.h>
#include <linux/printk.h>
#include <dt-bindings/soc/qcom,apr.h>
#include "q6core.h"

static int __init fx0_q6probe_init(void)
{
	struct q6core_svc_api_info info;
	int svc, ret;

	pr_info("fx0_q6probe: adsp ready: %d\n", q6core_is_adsp_ready());

	for (svc = APR_SVC_ADSP_CORE; svc < APR_SVC_MAX; svc++) {
		info.api_version = 0;
		info.api_branch_version = 0;
		ret = q6core_get_svc_api_info(svc, &info);
		pr_info("fx0_q6probe: svc 0x%02x ret %d api %u branch %u\n",
			svc, ret, info.api_version, info.api_branch_version);
	}
	return 0;
}

static void __exit fx0_q6probe_exit(void)
{
}

module_init(fx0_q6probe_init);
module_exit(fx0_q6probe_exit);
MODULE_DESCRIPTION("Fx0 ADSP q6core version probe");
MODULE_LICENSE("GPL");
