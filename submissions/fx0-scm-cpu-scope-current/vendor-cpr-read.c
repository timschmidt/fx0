// SPDX-License-Identifier: GPL-2.0-only
/*
 * Copyright (c) 2013-2014, The Linux Foundation. All rights reserved.
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 2 and
 * only version 2 as published by the Free Software Foundation.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 */
/* Source excerpt from 03aba4427a7666d57b5ae06d375e259ea337f351 arch/arm/mach-msm/cpr-regulator.c */
static u64 cpr_read_efuse_row(struct cpr_regulator *cpr_vreg, u32 row_num,
				bool use_tz_api)
{
	int rc;
	u64 efuse_bits;
	struct cpr_read_req {
		u32 row_address;
		int addr_type;
	} req;

	struct cpr_read_rsp {
		u32 row_data[2];
		u32 status;
	} rsp;

	if (!use_tz_api) {
		efuse_bits = readll_relaxed(cpr_vreg->efuse_base
			+ row_num * BYTES_PER_FUSE_ROW);
		return efuse_bits;
	}

	req.row_address = cpr_vreg->efuse_addr + row_num * BYTES_PER_FUSE_ROW;
	req.addr_type = 0;
	efuse_bits = 0;

	rc = scm_call(SCM_SVC_FUSE, SCM_FUSE_READ,
			&req, sizeof(req), &rsp, sizeof(rsp));

	if (rc) {
		pr_err("read row %d failed, err code = %d", row_num, rc);
	} else {
		efuse_bits = ((u64)(rsp.row_data[1]) << 32) +
				(u64)rsp.row_data[0];
	}

	return efuse_bits;
}
