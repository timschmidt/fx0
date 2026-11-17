static unsigned cases, checks, failures;
static const char *label;
#define CHECK(c) do { checks++; if (!(c)) { failures++; \
	if (failures < 20) printf("FAIL %s line %d: %s\n", label, __LINE__, #c); } } while (0)
static void initialize(unsigned pairs, unsigned pattern, bool reset, bool extcon)
{
	assert(!model.allocation && !model.separate_allocation); memset(&model, 0, sizeof(model));
	model.length = pairs * 2; model.has_reset = reset; model.has_extcon = extcon;
	for (unsigned i = 0; i < pairs; i++) {
		model.bytes[i * 2] = (u8)(i + 1);
		model.bytes[i * 2 + 1] = (u8)(0x40 + i);
	}
	if (pairs && pattern == 1) model.bytes[0] = 0;
	if (pairs && pattern == 2) model.bytes[(pairs / 2) * 2] = 0;
	if (pairs && pattern == 3) model.bytes[(pairs - 1) * 2] = 0;
}
static void release(void) { free(model.allocation); free(model.separate_allocation); model.allocation = model.separate_allocation = NULL; }
static void off(void)
{
	CHECK(!model.clocks[0].enabled && !model.clocks[1].enabled);
	CHECK(!model.regulators[0].enabled && !model.regulators[1].enabled);
	CHECK(!model.notifier);
}
static void sequence(unsigned pairs, unsigned pattern, bool reset, bool extcon)
{
	initialize(pairs, pattern, reset, extcon);
	label = "probe-power-sequence-off-repeat"; cases++;
	struct ulpi ulpi = {0}; int ret = qcom_usb_hs_phy_probe(&ulpi);
	CHECK(ret == 0); if (ret) { release(); return; }
	struct qcom_usb_hs_phy *uphy = model.phy.data;
	CHECK(uphy == model.allocation && ulpi.dev.data == uphy && uphy->ulpi == &ulpi);
#if HAS_COUNT
	CHECK(uphy->num_init_seq == pairs);
	CHECK(model.allocation_size == sizeof(*uphy) + (HAS_FLEX ? pairs * sizeof(struct ulpi_seq) : 0));
#endif
	for (unsigned cycle = 0; cycle < 2; cycle++) {
		model.writes = model.power_calls = model.reset_calls = 0;
		CHECK(qcom_usb_hs_phy_power_on(&model.phy) == 0);
		CHECK(model.clocks[0].enabled && model.clocks[1].enabled);
		CHECK(model.regulators[0].enabled && model.regulators[1].enabled);
		CHECK(model.writes == pairs + extcon);
		for (unsigned i = 0; i < pairs; i++) {
			CHECK(model.trace[i].addr == ULPI_EXT_VENDOR_SPECIFIC + model.bytes[i * 2]);
			CHECK(model.trace[i].value == model.bytes[i * 2 + 1]);
		}
		CHECK(model.reset_calls == (unsigned)reset);
		CHECK(model.notifier == extcon);
		CHECK(qcom_usb_hs_phy_power_off(&model.phy) == 0); off();
	}
	release();
}
static void power_errors(unsigned pairs, bool reset)
{
	for (unsigned nth = 1; nth <= 7 + pairs + reset; nth++) {
		initialize(pairs, 0, reset, false);
		label = "power-resource-and-init-write-error-unwind"; cases++;
		struct ulpi ulpi = {0}; assert(qcom_usb_hs_phy_probe(&ulpi) == 0);
		model.power_fault = nth;
		int ret = qcom_usb_hs_phy_power_on(&model.phy);
		CHECK(ret == -EIO); CHECK(model.power_calls == nth);
		if (!ret) qcom_usb_hs_phy_power_off(&model.phy);
		off(); release();
	}
}
static void probe_errors(void)
{
	for (unsigned size = 1; size < 64; size += 2) {
		initialize(0, 0, false, false); model.length = size;
		/* A malformed size must be rejected before even a failing data read. */
		model.read_error = -EIO; label = "odd-length-validation-precedes-data-access"; cases++;
		struct ulpi ulpi = {0}; CHECK(qcom_usb_hs_phy_probe(&ulpi) == -EINVAL);
		CHECK(model.probe_calls == (HAS_FLEX ? 0U : 1U)); CHECK((model.allocation == NULL) == (bool)HAS_FLEX); release();
	}
	for (unsigned stage = 1; stage <= 7; stage++) {
		initialize(3, 1, false, false); model.probe_fault = stage;
		label = "probe-resource-error"; cases++; struct ulpi ulpi = {0};
		CHECK(qcom_usb_hs_phy_probe(&ulpi) == (stage == 1 ? -ENOMEM : -EIO));
		off(); release();
	}
#if HAS_SEPARATE_INIT_ALLOC
 initialize(3, 1, false, false); model.probe_fault = 8;
 label = "legacy-separate-array-allocation-failure"; cases++;
 struct ulpi separate_ulpi = {0}; CHECK(qcom_usb_hs_phy_probe(&separate_ulpi) == -ENOMEM);
 off(); release();
#endif
	for (unsigned kind = 0; kind < 4; kind++) {
		initialize(3, 1, false, false);
		if (kind == 0) model.read_error = -EIO;
		if (kind == 1) model.reset_get_error = -EPROBE_DEFER;
		if (kind == 2) model.extcon_get_error = -EPROBE_DEFER;
		if (kind == 3) model.extcon_get_error = -EIO;
		label = "probe-property-and-defer-error"; cases++; struct ulpi ulpi = {0};
		CHECK(qcom_usb_hs_phy_probe(&ulpi) == ((kind == 1 || kind == 2) ? -EPROBE_DEFER : -EIO));
		off(); release();
	}
	initialize(0, 0, false, false); model.length = -ENOENT; model.read_error = -EINVAL;
	label = "absent-optional-sequence"; cases++; struct ulpi ulpi = {0};
	CHECK(qcom_usb_hs_phy_probe(&ulpi) == 0);
	CHECK(qcom_usb_hs_phy_power_on(&model.phy) == 0); CHECK(model.writes == 0);
	CHECK(qcom_usb_hs_phy_power_off(&model.phy) == 0); off(); release();
}
static void soc_sequences(void)
{
	for (unsigned i = 0; i < sizeof(soc_fixtures) / sizeof(soc_fixtures[0]); i++) {
		const struct soc_fixture *s = &soc_fixtures[i];
		initialize(0, 0, false, false); model.length = s->size;
		memcpy(model.bytes, s->bytes, s->size);
		label = "pinned-SoC-sequence"; cases++; struct ulpi ulpi = {0};
		CHECK(qcom_usb_hs_phy_probe(&ulpi) == 0);
		CHECK(qcom_usb_hs_phy_power_on(&model.phy) == 0);
		CHECK(model.writes == s->size / 2);
		for (unsigned j = 0; j < s->size / 2; j++) {
			CHECK(model.trace[j].addr == ULPI_EXT_VENDOR_SPECIFIC + s->bytes[j * 2]);
			CHECK(model.trace[j].value == s->bytes[j * 2 + 1]);
		}
		CHECK(qcom_usb_hs_phy_power_off(&model.phy) == 0); off(); release();
	}
}
int main(void)
{
	for (unsigned pairs = 0; pairs <= 32; pairs++) for (unsigned pattern = 0; pattern < 4; pattern++)
		for (unsigned reset = 0; reset < 2; reset++) for (unsigned extcon = 0; extcon < 2; extcon++)
			sequence(pairs, pattern, reset, extcon);
	for (unsigned reset = 0; reset < 2; reset++) for (unsigned pairs = 0; pairs <= 8; pairs++)
		power_errors(pairs, reset);
	probe_errors();
	soc_sequences();
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
	return failures != 0;
}
