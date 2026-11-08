// SPDX-License-Identifier: GPL-2.0-only
#include <linux/bitfield.h>
#include <linux/firmware/qcom/qcom_scm.h>
#include <linux/module.h>
#include <linux/of.h>

static int read_status = -ENODATA;
static int condition_matches = -1;
module_param(read_status, int, 0400);
module_param(condition_matches, int, 0400);
MODULE_PARM_DESC(read_status, "Result of the single legacy firmware read");
MODULE_PARM_DESC(condition_matches, "Expected conditional selector matched, or -1 on error");

static int __init fx0_cpr_fuse_probe_init(void)
{
	u64 row;

	if (!of_machine_is_compatible("lg,madai"))
		return -ENODEV;

	/* Compiled Madai CPR descriptor: row54, bits42..47, expected7, secure. */
	condition_matches = -1;
	read_status = qcom_scm_legacy_fuse_read(0xfc4b81b0, &row);
	if (!read_status)
		condition_matches = FIELD_GET(GENMASK_ULL(47, 42), row) == 7;

	pr_info("fx0-cpr-fuse: read_status=%d condition_matches=%d\n",
		read_status, condition_matches);
	return 0;
}

static void __exit fx0_cpr_fuse_probe_exit(void)
{
}

module_init(fx0_cpr_fuse_probe_init);
module_exit(fx0_cpr_fuse_probe_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Fx0 read-only pilot of the legacy CPR conditional fuse read");
