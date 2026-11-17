// SPDX-License-Identifier: GPL-2.0-only
static unsigned int checks, failures, cases;
static void check(bool ok, const char *label)
{
	checks++;
	if (!ok) { if (failures < 8) printf("FAIL %s\n", label); failures++; }
}
static void reset_registers(void)
{
	memset(phy_regs, 0x6a, sizeof(phy_regs));
	memset(reg_regs, 0x5a, sizeof(reg_regs));
	ntrace = 0;
}
int main(void)
{
	struct platform_device pdev = {0};
	struct msm_dsi_phy_clk_request request = {0};
	for (unsigned int quirks = 0; quirks < 4; quirks++)
	for (unsigned int ldo = 0; ldo < 2; ldo++)
	for (unsigned int id = 0; id < 2; id++)
	for (unsigned int usecase = 0; usecase < 3; usecase++)
	for (unsigned int error = 0; error < 2; error++)
	for (unsigned int zero = 0; zero < 2; zero++) {
		struct msm_dsi_phy_cfg cfg = {.quirks = quirks};
		struct msm_dsi_phy phy = {.base = phy_regs, .reg_base = reg_regs,
			.pdev = &pdev, .cfg = &cfg, .regulator_ldo_mode = ldo,
			.id = id, .usecase = usecase};
		timing_failure = error;
		large_zero = zero;
		reset_registers();
		int old = baseline_dsi_28nm_phy_enable(&phy, &request);
		if (!old) dsi_28nm_phy_disable(&phy);
		struct write reference[256];
		unsigned int count = ntrace;
		memcpy(reference, trace, sizeof(reference));
		reset_registers();
		int result = dsi_28nm_phy_enable(&phy, &request);
		if (!result) dsi_28nm_phy_disable(&phy);
		cases++;
		check(result == old && result == (error ? -EINVAL : 0), "timing status propagation preserved");
		check(ntrace == count, "complete MMIO and barrier trace length preserved");
		if (error) {
			check(!ntrace, "timing failure performs no PHY or regulator writes");
			continue;
		}
		bool other_writes_same = true;
		unsigned int lanes = 0;
		for (unsigned int i = 0; i < count; i++) {
			bool lane = false;
			for (unsigned int j = 0; j < 4; j++)
				if (reference[i].offset == REG_DSI_28nm_PHY_LN_CFG_4(j)) {
					u32 expected = cfg.quirks & DSI_PHY_28NM_QUIRK_PHY_8226 ? vendor_lane_cfg4[j] : reference[i].value;
					check(trace[i].offset == reference[i].offset && trace[i].value == expected,
					      "lane CFG4 matches selected vendor bytes only for MSM8226 quirk");
					lane = true; lanes++;
				}
			if (!lane && (trace[i].offset != reference[i].offset || trace[i].value != reference[i].value)) other_writes_same = false;
		}
		check(lanes == 4 && other_writes_same, "all other PHY, timing, regulator and clock-lane writes unchanged");
		check(phy_regs[REG_DSI_28nm_PHY_CTRL_0/4] == 0 &&
		      reg_regs[REG_DSI_28nm_PHY_REGULATOR_CAL_PWR_CFG/4] == 0 &&
		      trace[ntrace-1].offset == 0xffffffff, "disable keeps control, regulator and barrier sequence");
	}
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
	return failures ? 1 : 0;
}
