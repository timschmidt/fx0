
// SPDX-License-Identifier: GPL-2.0-only
/* Extracted portions retain the original QFPROM and NVMEM core copyrights:
 * Copyright (C) 2015 Srinivas Kandagatla <srinivas.kandagatla@linaro.org>
 * Copyright (C) 2013 Maxime Ripard <maxime.ripard@free-electrons.com>
 */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
typedef uint32_t u32;
typedef unsigned umode_t;
#define __iomem
#define GFP_KERNEL 0
#define IORESOURCE_MEM 0
#define NVMEM_DEVID_AUTO (-2)
#define BITS_PER_BYTE 8
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define DIV_ROUND_UP(a,b) (((a)+(b)-1)/(b))
#define IS_ALIGNED(a,b) (!((a)% (b)))
#define round_down(a,b) ((a)-((a)%(b)))
#define min(a,b) ((a)<(b)?(a):(b))
#define ERR_PTR(e) ((void *)(intptr_t)(e))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define IS_ERR(p) ((uintptr_t)(p)>(uintptr_t)-4096)
#define PTR_ERR_OR_ZERO(p) (IS_ERR(p)?PTR_ERR(p):0)
#define dev_err(...) ((void)0)
#define dev_err_probe(dev,err,...) ((void)(dev),(err))
#define guard(type) fake_guard
static void fake_guard(void *ptr) {(void)ptr;}
#define srcu_dereference(p,s) ((void)(s),(p))
#define rcu_dereference_raw(p) (p)
struct resource {size_t start,end;unsigned slot;};
struct device {const void *match;bool read_only;};
struct platform_device {struct device dev;struct resource regions[4];unsigned count;};
struct clk {int unused;};
struct regulator {int unused;};
struct file {int unused;};
struct kobject {struct device *dev;};
struct bin_attribute {void *private;};
struct nvmem_keepout {unsigned start,end;unsigned char value;};
struct nvmem_cell_info {unsigned offset,bit_offset,nbits,bytes;};
struct nvmem_device;
struct nvmem_config {
 const char *name;bool add_legacy_fixed_of_cells,read_only,root_only;
 unsigned stride,word_size;int id;size_t size;struct device *dev;void *priv;
 int (*reg_read)(void *,unsigned,void *,size_t);
 int (*reg_write)(void *,unsigned,void *,size_t);
 void (*fixup_dt_cell_info)(struct nvmem_device *,struct nvmem_cell_info *);
 const struct nvmem_keepout *keepout;unsigned nkeepout;
};
struct nvmem_operations {
 int (*reg_read)(void *,unsigned,void *,size_t);
 int (*reg_write)(void *,unsigned,void *,size_t);
};
struct nvmem_device {
 struct device dev;struct nvmem_operations *ops;unsigned srcu;
 unsigned stride,word_size;size_t size;bool root_only,read_only;
 void *priv,*wp_gpio;const struct nvmem_keepout *keepout;unsigned nkeepout;
};
static struct nvmem_device registered;
static struct nvmem_operations registered_ops;
static struct nvmem_config captured;
static bool raw_view;
static unsigned maps,clock_gets,regulator_gets,mmio_reads,bad_raw_reads,program_calls;
static unsigned pm_enables,pm_disables,registrations;
static int mapping_error,action_error,registration_error;
static u32 memory[4][2048];
static _Alignas(max_align_t) unsigned char allocation[4096];
static bool read_raw_data;
static struct device *kobj_to_dev(struct kobject *k) {return k->dev;}
#define to_nvmem_device(d) ((struct nvmem_device *)((char *)(d)-offsetof(struct nvmem_device,dev)))
static const void *device_get_match_data(struct device *dev) {return dev->match;}
static bool device_property_present(struct device *dev,const char *name)
{assert(!strcmp(name,"read-only"));return dev->read_only;}
static struct resource *platform_get_resource(struct platform_device *p,int type,unsigned index)
{assert(type==IORESOURCE_MEM);return index<p->count?&p->regions[index]:NULL;}
static size_t resource_size(struct resource *r) {return r->end-r->start+1;}
static void *devm_kzalloc(struct device *dev,size_t size,int flags)
{(void)dev;(void)flags;assert(size<=sizeof(allocation));memset(allocation,0,sizeof(allocation));return allocation;}
static void *devm_platform_get_and_ioremap_resource(struct platform_device *p,unsigned index,struct resource **res)
{*res=platform_get_resource(p,0,index);if(!*res)return ERR_PTR(-ENOENT);if(mapping_error)return ERR_PTR(mapping_error);maps++;return memory[index];}
static void *devm_ioremap_resource(struct device *dev,struct resource *res)
{(void)dev;maps++;return memory[res->slot];}
static void *devm_platform_ioremap_resource(struct platform_device *p,unsigned index)
{struct resource *r=platform_get_resource(p,0,index);return r?devm_ioremap_resource(&p->dev,r):ERR_PTR(-ENOENT);}
static bool readable(unsigned offset)
{return (offset>=0xb0 && offset<0xb8)||(offset>=0x450 && offset<0x460);}
static u32 readl(const void *ptr)
{
 uintptr_t address=(uintptr_t)ptr,base=(uintptr_t)memory;
 assert(address>=base && address+4<=base+sizeof(memory) && !(address%4));
 unsigned slot=(address-base)/sizeof(memory[0]);unsigned offset=(address-base)%sizeof(memory[0]);
 mmio_reads++;if(raw_view && (slot!=0 || !readable(offset)))bad_raw_reads++;
 u32 value;memcpy(&value,ptr,sizeof(value));return value;
}
static struct regulator *devm_regulator_get(struct device *dev,const char *name)
{(void)dev;assert(!strcmp(name,"vcc"));regulator_gets++;static struct regulator r;return &r;}
static struct clk *devm_clk_get_optional(struct device *dev,const char *name)
{(void)dev;assert(!strcmp(name,"core"));clock_gets++;static struct clk c;return &c;}
static void pm_runtime_enable(void *dev) {(void)dev;pm_enables++;}
static void pm_runtime_disable(void *dev) {(void)dev;pm_disables++;}
static int devm_add_action_or_reset(struct device *dev,void (*action)(void *),void *data)
{(void)dev;if(action_error)action(data);return action_error;}
static int qfprom_reg_write(void *priv,unsigned offset,void *val,size_t bytes)
{(void)priv;(void)offset;(void)val;(void)bytes;program_calls++;return -EIO;}
static int gpiod_set_value_cansleep(void *gpio,int value)
{(void)gpio;(void)value;program_calls++;return 0;}
static struct nvmem_device *devm_nvmem_register(struct device *,const struct nvmem_config *);

#define QFPROM_VERSION_OFFSET 0x0
#define QFPROM_MAJOR_VERSION_SHIFT 28
#define QFPROM_MAJOR_VERSION_MASK GENMASK(31, QFPROM_MAJOR_VERSION_SHIFT)
#define QFPROM_MINOR_VERSION_SHIFT 16
#define QFPROM_MINOR_VERSION_MASK GENMASK(27, QFPROM_MINOR_VERSION_SHIFT)
#define GENMASK(h,l) ((~0U << (l)) & (~0U >> (31-(h))))
struct qfprom_soc_data {
	u32 accel_value;
	u32 qfprom_blow_timer_value;
	u32 qfprom_blow_set_freq;
	int qfprom_blow_uV;
};

/**
 * struct qfprom_priv - structure holding qfprom attributes
 *
 * @qfpraw:       iomapped memory space for qfprom-efuse raw address space.
 * @qfpconf:      iomapped memory space for qfprom-efuse configuration address
 *                space.
 * @qfpcorrected: primary read window: corrected normally, raw for the
 *                standalone read-only view.
 * @qfpsecurity:  iomapped memory space for qfprom security control space.
 * @dev:          qfprom device structure.
 * @secclk:       Clock supply.
 * @vcc:          Regulator supply.
 * @soc_data:     Data that for things that varies from SoC to SoC.
 */
struct qfprom_priv {
	void __iomem *qfpraw;
	void __iomem *qfpconf;
	void __iomem *qfpcorrected;
	void __iomem *qfpsecurity;
	struct device *dev;
	struct clk *secclk;
	struct regulator *vcc;
	const struct qfprom_soc_data *soc_data;
};

/**
 * struct qfprom_touched_values - saved values to restore after blowing
 *
 * @clk_rate: The rate the clock was at before blowing.
 * @accel_val: The value of the accel reg before blowing.
 * @timer_val: The value of the timer before blowing.
 */
struct qfprom_touched_values {
	unsigned long clk_rate;
	u32 accel_val;
	u32 timer_val;
};

/**
 * struct qfprom_soc_compatible_data - Data matched against the SoC
 * compatible string.
 *
 * @keepout: Array of keepout regions for this SoC.
 * @nkeepout: Number of elements in the keepout array.
 * @raw_read_only: Standalone raw view without programming access.
 */
struct qfprom_soc_compatible_data {
	const struct nvmem_keepout *keepout;
	unsigned int nkeepout;
	bool raw_read_only;
};

/* Only the documented CPU/PVS and primary/redundant CPR rows are readable. */
static const struct nvmem_keepout msm8926_raw_keepout[] = {
	{ .start = 0, .end = 0xb0 },
	{ .start = 0xb8, .end = 0x450 },
	{ .start = 0x460, .end = 0x1000 },
};

static const struct qfprom_soc_compatible_data msm8926_raw_qfprom = {
	.keepout = msm8926_raw_keepout,
	.nkeepout = ARRAY_SIZE(msm8926_raw_keepout),
	.raw_read_only = true,
};

static const struct nvmem_keepout sc7180_qfprom_keepout[] = {
	{.start = 0x128, .end = 0x148},
	{.start = 0x220, .end = 0x228}
};

static const struct qfprom_soc_compatible_data sc7180_qfprom = {
	.keepout = sc7180_qfprom_keepout,
	.nkeepout = ARRAY_SIZE(sc7180_qfprom_keepout)
};

static const struct nvmem_keepout sc7280_qfprom_keepout[] = {
	{.start = 0x128, .end = 0x148},
	{.start = 0x238, .end = 0x248}
};

static const struct qfprom_soc_compatible_data sc7280_qfprom = {
	.keepout = sc7280_qfprom_keepout,
	.nkeepout = ARRAY_SIZE(sc7280_qfprom_keepout)
};


static int qfprom_reg_read(void *context,
			unsigned int reg, void *_val, size_t bytes)
{
	struct qfprom_priv *priv = context;
	u32 *val = _val;
	void __iomem *base = priv->qfpcorrected;
	int words = DIV_ROUND_UP(bytes, sizeof(u32));
	int i;

	if (read_raw_data && priv->qfpraw)
		base = priv->qfpraw;

	for (i = 0; i < words; i++)
		*val++ = readl(base + reg + i * sizeof(u32));

	return 0;
}
static void qfprom_fixup_dt_cell_info(struct nvmem_device *nvmem,
				      struct nvmem_cell_info *cell)
{
	unsigned int byte_offset = cell->offset % sizeof(u32);

	cell->bit_offset += byte_offset * BITS_PER_BYTE;
	cell->offset -= byte_offset;
	if (byte_offset && !cell->nbits)
		cell->nbits = cell->bytes * BITS_PER_BYTE;
}
static void qfprom_runtime_disable(void *data)
{
	pm_runtime_disable(data);
}
static const struct qfprom_soc_data qfprom_7_8_data = {
	.accel_value = 0xD10,
	.qfprom_blow_timer_value = 25,
	.qfprom_blow_set_freq = 4800000,
	.qfprom_blow_uV = 1800000,
};

static const struct qfprom_soc_data qfprom_7_15_data = {
	.accel_value = 0xD08,
	.qfprom_blow_timer_value = 24,
	.qfprom_blow_set_freq = 4800000,
	.qfprom_blow_uV = 1900000,
};


static int __nvmem_reg_read(struct nvmem_device *nvmem, unsigned int offset,
			    void *val, size_t bytes)
{
	struct nvmem_operations *ops;

	guard(srcu)(&nvmem->srcu);
	ops = srcu_dereference(nvmem->ops, &nvmem->srcu);
	if (!ops)
		return -ENODEV;

	if (!ops->reg_read)
		return -EOPNOTSUPP;

	return ops->reg_read(nvmem->priv, offset, val, bytes);
}
static int __nvmem_reg_write(struct nvmem_device *nvmem, unsigned int offset,
			     void *val, size_t bytes)
{
	struct nvmem_operations *ops;
	int ret, wr_ok;

	guard(srcu)(&nvmem->srcu);
	ops = srcu_dereference(nvmem->ops, &nvmem->srcu);
	if (!ops)
		return -ENODEV;

	if (!ops->reg_write)
		return -EOPNOTSUPP;

	ret = gpiod_set_value_cansleep(nvmem->wp_gpio, 0);
	if (ret)
		return ret;

	wr_ok = ops->reg_write(nvmem->priv, offset, val, bytes);

	ret = gpiod_set_value_cansleep(nvmem->wp_gpio, 1);
	if (ret)
		return ret;

	return wr_ok;
}
static int nvmem_access_with_keepouts(struct nvmem_device *nvmem,
				      unsigned int offset, void *val,
				      size_t bytes, int write)
{

	unsigned int end = offset + bytes;
	unsigned int kend, ksize;
	const struct nvmem_keepout *keepout = nvmem->keepout;
	const struct nvmem_keepout *keepoutend = keepout + nvmem->nkeepout;
	int rc;

	/*
	 * Skip all keepouts before the range being accessed.
	 * Keepouts are sorted.
	 */
	while ((keepout < keepoutend) && (keepout->end <= offset))
		keepout++;

	while ((offset < end) && (keepout < keepoutend)) {
		/* Access the valid portion before the keepout. */
		if (offset < keepout->start) {
			kend = min(end, keepout->start);
			ksize = kend - offset;
			if (write)
				rc = __nvmem_reg_write(nvmem, offset, val, ksize);
			else
				rc = __nvmem_reg_read(nvmem, offset, val, ksize);

			if (rc)
				return rc;

			offset += ksize;
			val += ksize;
		}

		/*
		 * Now we're aligned to the start of this keepout zone. Go
		 * through it.
		 */
		kend = min(end, keepout->end);
		ksize = kend - offset;
		if (!write)
			memset(val, keepout->value, ksize);

		val += ksize;
		offset += ksize;
		keepout++;
	}

	/*
	 * If we ran out of keepouts but there's still stuff to do, send it
	 * down directly
	 */
	if (offset < end) {
		ksize = end - offset;
		if (write)
			return __nvmem_reg_write(nvmem, offset, val, ksize);
		else
			return __nvmem_reg_read(nvmem, offset, val, ksize);
	}

	return 0;
}
static int nvmem_reg_read(struct nvmem_device *nvmem, unsigned int offset,
			  void *val, size_t bytes)
{
	if (!nvmem->nkeepout)
		return __nvmem_reg_read(nvmem, offset, val, bytes);

	return nvmem_access_with_keepouts(nvmem, offset, val, bytes, false);
}
static int nvmem_reg_write(struct nvmem_device *nvmem, unsigned int offset,
			   void *val, size_t bytes)
{
	if (!nvmem->nkeepout)
		return __nvmem_reg_write(nvmem, offset, val, bytes);

	return nvmem_access_with_keepouts(nvmem, offset, val, bytes, true);
}
static ssize_t bin_attr_nvmem_read(struct file *filp, struct kobject *kobj,
				   const struct bin_attribute *attr, char *buf,
				   loff_t pos, size_t count)
{
	struct device *dev;
	struct nvmem_device *nvmem;
	int rc;

	if (attr->private)
		dev = attr->private;
	else
		dev = kobj_to_dev(kobj);
	nvmem = to_nvmem_device(dev);

	if (!IS_ALIGNED(pos, nvmem->stride))
		return -EINVAL;

	if (count < nvmem->word_size)
		return -EINVAL;

	count = round_down(count, nvmem->word_size);

	rc = nvmem_reg_read(nvmem, pos, buf, count);
	if (rc) {
		if (rc == -EOPNOTSUPP)
			return -EPERM;
		return rc;
	}

	return count;
}
static ssize_t bin_attr_nvmem_write(struct file *filp, struct kobject *kobj,
				    const struct bin_attribute *attr, char *buf,
				    loff_t pos, size_t count)
{
	struct device *dev;
	struct nvmem_device *nvmem;
	int rc;

	if (attr->private)
		dev = attr->private;
	else
		dev = kobj_to_dev(kobj);
	nvmem = to_nvmem_device(dev);

	if (!IS_ALIGNED(pos, nvmem->stride))
		return -EINVAL;

	if (count < nvmem->word_size)
		return -EINVAL;

	count = round_down(count, nvmem->word_size);

	if (nvmem->read_only)
		return -EPERM;

	rc = nvmem_reg_write(nvmem, pos, buf, count);
	if (rc) {
		if (rc == -EOPNOTSUPP)
			return -EPERM;
		return rc;
	}

	return count;
}
static umode_t nvmem_bin_attr_get_umode(struct nvmem_device *nvmem)
{
	struct nvmem_operations *ops = rcu_dereference_raw(nvmem->ops);

	umode_t mode = 0400;

	if (!nvmem->root_only)
		mode |= 0044;

	if (!nvmem->read_only)
		mode |= 0200;

	if (!ops->reg_write)
		mode &= ~0200;

	if (!ops->reg_read)
		mode &= ~0444;

	return mode;
}
static int nvmem_validate_keepouts(struct nvmem_device *nvmem)
{
	unsigned int cur = 0;
	const struct nvmem_keepout *keepout = nvmem->keepout;
	const struct nvmem_keepout *keepoutend = keepout + nvmem->nkeepout;

	while (keepout < keepoutend) {
		/* Ensure keepouts are sorted and don't overlap. */
		if (keepout->start < cur) {
			dev_err(&nvmem->dev,
				"Keepout regions aren't sorted or overlap.\n");

			return -ERANGE;
		}

		if (keepout->end < keepout->start) {
			dev_err(&nvmem->dev,
				"Invalid keepout region.\n");

			return -EINVAL;
		}

		/*
		 * Validate keepouts (and holes between) don't violate
		 * word_size constraints.
		 */
		if ((keepout->end - keepout->start < nvmem->word_size) ||
		    ((keepout->start != cur) &&
		     (keepout->start - cur < nvmem->word_size))) {

			dev_err(&nvmem->dev,
				"Keepout regions violate word_size constraints.\n");

			return -ERANGE;
		}

		/* Validate keepouts don't violate stride (alignment). */
		if (!IS_ALIGNED(keepout->start, nvmem->stride) ||
		    !IS_ALIGNED(keepout->end, nvmem->stride)) {

			dev_err(&nvmem->dev,
				"Keepout regions violate stride.\n");

			return -EINVAL;
		}

		cur = keepout->end;
		keepout++;
	}

	return 0;
}
int nvmem_device_read(struct nvmem_device *nvmem,
		      unsigned int offset,
		      size_t bytes, void *buf)
{
	int rc;

	if (!nvmem)
		return -EINVAL;

	rc = nvmem_reg_read(nvmem, offset, buf, bytes);

	if (rc)
		return rc;

	return bytes;
}
int nvmem_device_write(struct nvmem_device *nvmem,
		       unsigned int offset,
		       size_t bytes, void *buf)
{
	int rc;

	if (!nvmem)
		return -EINVAL;

	rc = nvmem_reg_write(nvmem, offset, buf, bytes);

	if (rc)
		return rc;


	return bytes;
}
static struct nvmem_device *devm_nvmem_register(struct device *dev,const struct nvmem_config *config) {
 (void)dev;captured=*config;if(registration_error)return ERR_PTR(registration_error);
 struct nvmem_device *nvmem=&registered;struct nvmem_operations *ops=&registered_ops;nvmem->ops=ops;
	ops->reg_read = config->reg_read;
	ops->reg_write = config->reg_write;
	nvmem->stride = config->stride ?: 1;
	nvmem->word_size = config->word_size ?: 1;
	nvmem->size = config->size;
	nvmem->root_only = config->root_only;
	nvmem->priv = config->priv;
	nvmem->keepout = config->keepout;
	nvmem->nkeepout = config->nkeepout;
	nvmem->read_only = device_property_present(config->dev, "read-only") ||
			   config->read_only || !ops->reg_write;
 int ret=nvmem_validate_keepouts(nvmem);if(ret)return ERR_PTR(ret);registrations++;return nvmem;
}
static int qfprom_probe(struct platform_device *pdev)
{
	struct nvmem_config econfig = {
		.name = "qfprom",
		.add_legacy_fixed_of_cells = true,
		.stride = 4,
		.word_size = 4,
		.id = NVMEM_DEVID_AUTO,
		.reg_read = qfprom_reg_read,
		.fixup_dt_cell_info = qfprom_fixup_dt_cell_info,
	};
	struct device *dev = &pdev->dev;
	struct resource *res;
	struct nvmem_device *nvmem;
	const struct qfprom_soc_compatible_data *soc_data;
	struct qfprom_priv *priv;
	int ret;

	soc_data = device_get_match_data(dev);
	if (soc_data && soc_data->raw_read_only) {
		/* A raw reader must never enter the programming-resource path. */
		if (platform_get_resource(pdev, IORESOURCE_MEM, 1))
			return dev_err_probe(dev, -EINVAL,
					     "read-only raw view requires one region\n");
		econfig.name = "qfprom-raw";
		econfig.read_only = true;
		econfig.root_only = true;
	}

	priv = devm_kzalloc(dev, sizeof(*priv), GFP_KERNEL);
	if (!priv)
		return -ENOMEM;

	/* Region zero is corrected, except for the standalone read-only raw view. */
	priv->qfpcorrected = devm_platform_get_and_ioremap_resource(pdev, 0, &res);
	if (IS_ERR(priv->qfpcorrected))
		return PTR_ERR(priv->qfpcorrected);

	econfig.size = resource_size(res);
	econfig.dev = dev;
	econfig.priv = priv;

	priv->dev = dev;
	if (soc_data) {
		econfig.keepout = soc_data->keepout;
		econfig.nkeepout = soc_data->nkeepout;
	}

	/*
	 * If more than one region is provided then the OS has the ability
	 * to write.
	 */
	res = platform_get_resource(pdev, IORESOURCE_MEM, 1);
	if (res) {
		u32 version;
		int major_version, minor_version;

		priv->qfpraw = devm_ioremap_resource(dev, res);
		if (IS_ERR(priv->qfpraw))
			return PTR_ERR(priv->qfpraw);
		priv->qfpconf = devm_platform_ioremap_resource(pdev, 2);
		if (IS_ERR(priv->qfpconf))
			return PTR_ERR(priv->qfpconf);
		priv->qfpsecurity = devm_platform_ioremap_resource(pdev, 3);
		if (IS_ERR(priv->qfpsecurity))
			return PTR_ERR(priv->qfpsecurity);

		version = readl(priv->qfpsecurity + QFPROM_VERSION_OFFSET);
		major_version = (version & QFPROM_MAJOR_VERSION_MASK) >>
				QFPROM_MAJOR_VERSION_SHIFT;
		minor_version = (version & QFPROM_MINOR_VERSION_MASK) >>
				QFPROM_MINOR_VERSION_SHIFT;

		if (major_version == 7 && minor_version == 8)
			priv->soc_data = &qfprom_7_8_data;
		else if (major_version == 7 && minor_version == 15)
			priv->soc_data = &qfprom_7_15_data;

		priv->vcc = devm_regulator_get(&pdev->dev, "vcc");
		if (IS_ERR(priv->vcc))
			return PTR_ERR(priv->vcc);

		priv->secclk = devm_clk_get_optional(dev, "core");
		if (IS_ERR(priv->secclk))
			return dev_err_probe(dev, PTR_ERR(priv->secclk), "Error getting clock\n");

		/* Only enable writing if we have SoC data and a valid clock */
		if (priv->soc_data && priv->secclk)
			econfig.reg_write = qfprom_reg_write;
	}

	pm_runtime_enable(dev);
	ret = devm_add_action_or_reset(dev, qfprom_runtime_disable, dev);
	if (ret)
		return ret;

	nvmem = devm_nvmem_register(dev, &econfig);

	return PTR_ERR_OR_ZERO(nvmem);
}

static unsigned cases,broken;
#define CHECK(c) do {cases++;if(!(c))broken++;} while(0)
static void setup(struct platform_device *p,bool raw,unsigned regions,size_t size)
{
 memset(p,0,sizeof(*p));memset(&registered,0,sizeof(registered));memset(&captured,0,sizeof(captured));
 memset(&registered_ops,0,sizeof(registered_ops));raw_view=raw;p->count=regions;
 p->dev.match=raw?&msm8926_raw_qfprom:&sc7180_qfprom;
 for(unsigned i=0;i<4;i++)p->regions[i]=(struct resource){.start=0,.end=size-1,.slot=i};
 for(unsigned i=0;i<4;i++)for(unsigned j=0;j<2048;j++)memory[i][j]=0xa5b70000U+i*0x10000U+j;
 memory[3][0]=0x70080000;
 maps=clock_gets=regulator_gets=mmio_reads=bad_raw_reads=program_calls=0;
 pm_enables=pm_disables=registrations=0;mapping_error=action_error=registration_error=0;read_raw_data=false;
}
static void check_bytes(const unsigned char *buf,unsigned offset,unsigned count)
{
 bool same=true;
 for(unsigned i=0;i<count;i++) {
  const unsigned char *raw=(const unsigned char *)memory[0];
  unsigned char expected=readable(offset+i)?raw[offset+i]:0;
  if(buf[i]!=expected)same=false;
 }
 CHECK(same && !bad_raw_reads && !program_calls);
}
int main(void)
{
 struct platform_device p;unsigned char buf[0x2000];struct bin_attribute attr={0};
 for(unsigned raw_parameter=0;raw_parameter<2;raw_parameter++) {
  setup(&p,true,1,0x1000);p.dev.read_only=raw_parameter;
  CHECK(qfprom_probe(&p)==0 && registrations==1 && maps==1 && !clock_gets && !regulator_gets && !mmio_reads);
  CHECK(captured.read_only && captured.root_only && !captured.reg_write && !strcmp(captured.name,"qfprom-raw"));
  CHECK(registered.read_only && registered.root_only && nvmem_bin_attr_get_umode(&registered)==0400);
  read_raw_data=raw_parameter;struct kobject kobj={.dev=&registered.dev};
  const unsigned sizes[]={4,8,16,64};
  for(unsigned offset=0;offset<0x1000;offset+=4)for(unsigned s=0;s<4;s++) {
   unsigned count=sizes[s];if(offset+count>0x1000)continue;
   memset(buf,0xcc,sizeof(buf));
   ssize_t rc=bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,offset,count);
   CHECK(rc==count);check_bytes(buf,offset,count);
  }
  mmio_reads=bad_raw_reads=0;memset(buf,0xcc,sizeof(buf));
  CHECK(nvmem_device_read(&registered,0,0x1000,buf)==0x1000);
  check_bytes(buf,0,0x1000);CHECK(mmio_reads==6);
  for(unsigned offset=0;offset<0x1000;offset+=4)
   CHECK(bin_attr_nvmem_write(NULL,&kobj,&attr,(char *)buf,offset,4)==-EPERM && !program_calls);
  CHECK(bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,1,4)==-EINVAL);
  CHECK(bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,0xb0,3)==-EINVAL);
  CHECK(bin_attr_nvmem_read(NULL,&kobj,&attr,(char *)buf,0xb0,7)==4);
  CHECK(nvmem_device_write(&registered,0xb0,4,buf)==-EOPNOTSUPP && !program_calls);
  registered.ops=NULL;CHECK(nvmem_device_read(&registered,0xb0,4,buf)==-ENODEV);
 }
 for(unsigned regions=2;regions<=4;regions+=2) {
  setup(&p,true,regions,0x1000);
  CHECK(qfprom_probe(&p)==-EINVAL && !maps && !registrations && !clock_gets && !regulator_gets);
 }
 setup(&p,true,0,0x1000);CHECK(qfprom_probe(&p)==-ENOENT && !registrations);
 setup(&p,true,1,0x2000);
 int ret=qfprom_probe(&p);
 /* Keepouts end at 0x1000; a wider registered view must be rejected. */
 CHECK(ret==-EINVAL && !registrations && !clock_gets && !regulator_gets);
 if(!ret) {
  unsigned before=bad_raw_reads;ret=nvmem_device_read(&registered,0x1000,4,buf);
  assert(ret==4 && bad_raw_reads==before+1); /* Demonstrates the earlier over-wide view. */
 }
 for(unsigned profile=0;profile<2;profile++) {
  setup(&p,false,profile?4:1,0x1000);CHECK(qfprom_probe(&p)==0 && registrations==1);
  CHECK(captured.reg_write==(profile?qfprom_reg_write:NULL));
  CHECK(clock_gets==profile && regulator_gets==profile && mmio_reads==profile && !program_calls);
  CHECK(!captured.root_only && !captured.read_only && registered.read_only==!profile);
 }
 setup(&p,true,1,0x1000);mapping_error=-EIO;CHECK(qfprom_probe(&p)==-EIO && !registrations);
 setup(&p,true,1,0x1000);action_error=-ENOMEM;CHECK(qfprom_probe(&p)==-ENOMEM && !registrations && pm_disables==1);
 setup(&p,true,1,0x1000);registration_error=-EIO;CHECK(qfprom_probe(&p)==-EIO);
 printf("cases=%u broken=%u\n",cases,broken);return broken?1:0;
}
