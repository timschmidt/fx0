static unsigned cases, checks, failures;
static const char *label;
#define CHECK(c) do { checks++; if (!(c)) { failures++; \
	if (failures < 20) printf("FAIL %s at %d: %s\n", label, __LINE__, #c); } } while (0)
static const struct pm8xxx_regs *variants[] = {&pm8058_regs, &pm8916_regs, &pmi632_regs};
static struct pm8xxx_vib init(struct regmap *map, unsigned variant, unsigned base, unsigned initial)
{
	const struct pm8xxx_regs *r = variants[variant];
	struct pm8xxx_vib v = {.regmap = map, .regs = r,
		.enable_addr = base + r->enable_offset,
		.drv_addr = base + r->drv_offset, .drv2_addr = base + r->drv2_offset};
	map->values[v.drv_addr] = initial & ~r->drv_mask;
	if (r->drv2_mask) map->values[v.drv2_addr] = 0xa0;
	if (r->enable_mask) map->values[v.enable_addr] = 0x55;
	v.reg_vib_drv = map->values[v.drv_addr];
	return v;
}
static void speeds(unsigned variant, unsigned base, unsigned initial, bool descending)
{
	struct regmap *m = calloc(1, sizeof(*m)); assert(m);
	struct pm8xxx_vib v = init(m, variant, base, initial);
	const struct pm8xxx_regs *r = v.regs;
	unsigned low = variant == 2 ? 1504 : 1200, high = variant == 2 ? 3544 : 3100;
	unsigned step = variant == 2 ? 8 : 100;
	for (unsigned n = 0; n < 256; n++) {
		unsigned speed = descending ? 255 - n : n;
		unsigned millivolts = low + (high - low + step) * speed / 255;
		if (millivolts > high) millivolts = high;
		unsigned code = r->drv_in_step ? millivolts / step : millivolts;
		v.speed = speed; label = "full-voltage-register-fields"; cases++;
		pm8xxx_work_handler(&v.work);
		CHECK(v.active == (speed != 0));
		CHECK(v.level == (int)code);
		unsigned lower = m->values[v.drv_addr];
		CHECK((lower & ~r->drv_mask) == (initial & ~r->drv_mask));
		CHECK((lower & r->drv_mask) == (speed ? ((code << r->drv_shift) & r->drv_mask) : 0));
		if (r->drv2_mask) {
			unsigned upper = m->values[v.drv2_addr];
			CHECK((upper & ~r->drv2_mask) == 0xa0);
			CHECK((upper & r->drv2_mask) == (speed ? ((code >> r->drv2_shift) & r->drv2_mask) : 0));
			unsigned combined = (lower & r->drv_mask) | ((upper & r->drv2_mask) << r->drv2_shift);
			CHECK(combined == (speed ? code : 0));
		}
		if (r->enable_mask) {
			CHECK((m->values[v.enable_addr] & ~r->enable_mask) == 0x55);
			CHECK(!!(m->values[v.enable_addr] & r->enable_mask) == !!speed);
		}
		if (variant < 2 && speed) {
			unsigned observed = (lower & r->drv_mask) >> r->drv_shift;
			CHECK(observed >= 12 && observed <= 31);
			if (speed == 153) CHECK(observed == 24);
		}
	}
	free(m);
}
static void errors(unsigned variant)
{
	const struct pm8xxx_regs *r = variants[variant];
	unsigned operations = 1 + !!r->drv2_mask + !!r->enable_mask;
	for (unsigned nth = 1; nth <= operations; nth++) for (unsigned enabled = 0; enabled < 2; enabled++) {
		struct regmap *m = calloc(1, sizeof(*m)); assert(m);
		struct pm8xxx_vib v = init(m, variant, 0xc000, 0xa5);
		v.level = variant == 2 ? 2400 : 2400; m->fail = nth;
		label = "register-error-propagation"; cases++;
		CHECK(pm8xxx_vib_set(&v, enabled) == -EIO);
		CHECK(m->calls == nth);
		CHECK((m->values[v.drv_addr] & ~r->drv_mask) == (0xa5U & ~r->drv_mask));
		if (nth == 1) CHECK(v.reg_vib_drv == (0xa5U & ~r->drv_mask));
		if (r->enable_mask) CHECK(m->values[v.enable_addr] == 0x55);
		free(m);
	}
	struct regmap *m = calloc(1, sizeof(*m)); assert(m);
	struct pm8xxx_vib v = init(m, variant, 0xc000, 0xa5);
	v.speed = 255; v.level = 17; m->fail = 1;
	label = "worker-read-error-no-write"; cases++;
	pm8xxx_work_handler(&v.work);
	CHECK(m->calls == 1); CHECK(v.level == 17); CHECK(!v.active);
	free(m);
}
int main(void)
{
	for (unsigned variant = 0; variant < 3; variant++) {
		for (unsigned base = 0; base < 2; base++) for (unsigned pattern = 0; pattern < 4; pattern++)
			for (unsigned direction = 0; direction < 2; direction++)
				speeds(variant, base ? 0xc000 : 0, pattern * 0x55, direction);
		errors(variant);
	}
	printf("{\"cases\":%u,\"checks\":%u,\"failures\":%u}\n", cases, checks, failures);
	return failures != 0;
}
