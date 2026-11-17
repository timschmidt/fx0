#define VIB_MAX_LEVEL_mV(vib)	((vib)->regs->drv2_mask ? 3544 : 3100)
#define VIB_MIN_LEVEL_mV(vib)	((vib)->regs->drv2_mask ? 1504 : 1200)
#define VIB_PER_STEP_mV(vib)	((vib)->regs->drv2_mask ? 8 : 100)
#define VIB_MAX_LEVELS(vib) \
	(VIB_MAX_LEVEL_mV(vib) - VIB_MIN_LEVEL_mV(vib) + VIB_PER_STEP_mV(vib))

#define MAX_FF_SPEED		0xff

struct pm8xxx_regs {
	unsigned int enable_offset;
	unsigned int enable_mask;

	unsigned int drv_offset;
	unsigned int drv_mask;
	unsigned int drv_shift;
	unsigned int drv2_offset;
	unsigned int drv2_mask;
	unsigned int drv2_shift;
	unsigned int drv_en_manual_mask;
	bool	     drv_in_step;
};

static const struct pm8xxx_regs pm8058_regs = {
	.drv_offset = 0,
	.drv_mask = GENMASK(7, 3),
	.drv_shift = 3,
	.drv_en_manual_mask = 0xfc,
	.drv_in_step = true,
};

static struct pm8xxx_regs pm8916_regs = {
	.enable_offset = 0x46,
	.enable_mask = BIT(7),
	.drv_offset = 0x41,
	.drv_mask = GENMASK(4, 0),
	.drv_shift = 0,
	.drv_en_manual_mask = 0,
	.drv_in_step = true,
};

static struct pm8xxx_regs pmi632_regs = {
	.enable_offset = 0x46,
	.enable_mask = BIT(7),
	.drv_offset = 0x40,
	.drv_mask = GENMASK(7, 0),
	.drv_shift = 0,
	.drv2_offset = 0x41,
	.drv2_mask = GENMASK(3, 0),
	.drv2_shift = 8,
	.drv_en_manual_mask = 0,
	.drv_in_step = false,
};

struct pm8xxx_vib {
	struct input_dev *vib_input_dev;
	struct work_struct work;
	struct regmap *regmap;
	const struct pm8xxx_regs *regs;
	unsigned int enable_addr;
	unsigned int drv_addr;
	unsigned int drv2_addr;
	int speed;
	int level;
	bool active;
	u8  reg_vib_drv;
};
static int pm8xxx_vib_set(struct pm8xxx_vib *vib, bool on)
{
	int rc;
	unsigned int val = vib->reg_vib_drv;
	const struct pm8xxx_regs *regs = vib->regs;

	if (regs->drv_in_step)
		vib->level /= VIB_PER_STEP_mV(vib);

	if (on)
		val = (val & ~regs->drv_mask) |
		      ((vib->level << regs->drv_shift) & regs->drv_mask);
	else
		val &= ~regs->drv_mask;

	rc = regmap_write(vib->regmap, vib->drv_addr, val);
	if (rc < 0)
		return rc;

	vib->reg_vib_drv = val;

	if (regs->drv2_mask) {
		val = vib->level >> regs->drv2_shift;
		rc = regmap_write_bits(vib->regmap, vib->drv2_addr,
				regs->drv2_mask, on ? val : 0);
		if (rc < 0)
			return rc;
	}

	if (regs->enable_mask)
		rc = regmap_update_bits(vib->regmap, vib->enable_addr,
					regs->enable_mask, on ? regs->enable_mask : 0);

	return rc;
}
static void pm8xxx_work_handler(struct work_struct *work)
{
	struct pm8xxx_vib *vib = container_of(work, struct pm8xxx_vib, work);
	unsigned int val;
	int rc;

	rc = regmap_read(vib->regmap, vib->drv_addr, &val);
	if (rc < 0)
		return;

	/*
	 * pmic vibrator supports voltage ranges from MIN_LEVEL to MAX_LEVEL, so
	 * scale the level to fit into these ranges.
	 */
	if (vib->speed) {
		vib->active = true;
		vib->level = VIB_MIN_LEVEL_mV(vib);
		vib->level += mult_frac(VIB_MAX_LEVELS(vib), vib->speed, MAX_FF_SPEED);
	} else {
		vib->active = false;
		vib->level = VIB_MIN_LEVEL_mV(vib);
	}

	vib->level = min(vib->level, VIB_MAX_LEVEL_mV(vib));

	pm8xxx_vib_set(vib, vib->active);
}
