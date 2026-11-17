// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic resource, firmware-property, ULPI and notifier services. */
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint8_t u8;
#define BIT(n) (1U << (n))
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define ERR_PTR(n) ((void *)(intptr_t)(n))
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define PTR_ERR_OR_ZERO(p) (IS_ERR(p) ? PTR_ERR(p) : 0)
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define GFP_KERNEL 0
#define EPROBE_DEFER 517
#define __counted_by(n)
#define struct_size(p, m, n) (sizeof(*(p)) + sizeof((p)->m[0]) * (n))
#define fallthrough __attribute__((fallthrough))
#define THIS_MODULE NULL
#define EXTCON_USB 1
#include "ulpi-regs.h"
struct device { void *of_node, *data; };
struct ulpi { struct device dev; };
struct phy { void *data; };
enum phy_mode { PHY_MODE_INVALID, PHY_MODE_USB_HOST, PHY_MODE_USB_DEVICE, PHY_MODE_USB_OTG };
struct clk { bool enabled; unsigned id; };
struct regulator { bool enabled; unsigned id; };
struct reset_control {};
struct extcon_dev {};
struct notifier_block { int (*notifier_call)(struct notifier_block *, unsigned long, void *); };
struct phy_provider {};
struct phy_ops {
	int (*power_on)(struct phy *), (*power_off)(struct phy *);
	int (*set_mode)(struct phy *, enum phy_mode, int);
	void *owner;
};
static struct {
	u8 bytes[128]; int length, read_error;
	void *allocation, *separate_allocation; size_t allocation_size;
	struct phy phy; struct clk clocks[2]; struct regulator regulators[2];
	struct reset_control reset; struct extcon_dev extcon; struct phy_provider provider;
	bool has_reset, has_extcon, notifier;
	int reset_get_error, extcon_get_error, probe_fault;
	unsigned probe_calls, power_calls, power_fault, writes, reset_calls;
	struct { unsigned addr, value; } trace[256];
} model;
static bool probe_fail(unsigned stage) { model.probe_calls++; return model.probe_fault == (int)stage; }
static bool power_fail(void) { return ++model.power_calls == model.power_fault; }
static void *phy_get_drvdata(struct phy *p) { return p->data; }
static void phy_set_drvdata(struct phy *p, void *data) { p->data = data; }
static void ulpi_set_drvdata(struct ulpi *p, void *data) { p->dev.data = data; }
static int of_property_count_u8_elems(void *node, const char *name)
{ (void)node; assert(!strcmp(name, "qcom,init-seq")); return model.length; }
static int of_property_read_u8_array(void *node, const char *name, u8 *data, size_t n)
{
	(void)node; assert(!strcmp(name, "qcom,init-seq"));
	if (model.read_error) return model.read_error;
	assert(n <= sizeof(model.bytes)); memcpy(data, model.bytes, n); return 0;
}
static void *devm_kzalloc(struct device *dev, size_t n, int flags)
{
	(void)dev; (void)flags;
	if (probe_fail(1)) return NULL;
	assert(!model.allocation); model.allocation_size = n;
	return model.allocation = calloc(1, n);
}
static __attribute__((unused)) void *devm_kmalloc_array(struct device *dev, size_t count, size_t size, int flags)
{
 (void)dev; (void)flags;
 if (probe_fail(8)) return NULL;
 assert(!model.separate_allocation && size && count <= SIZE_MAX / size);
 return model.separate_allocation = malloc(count * size ? count * size : 1);
}
static struct clk *devm_clk_get(struct device *dev, const char *name)
{
	(void)dev; unsigned id = !strcmp(name, "ref") ? 0 : 1;
	return probe_fail(2 + id) ? ERR_PTR(-EIO) : &model.clocks[id];
}
static struct regulator *devm_regulator_get(struct device *dev, const char *name)
{
	(void)dev; unsigned id = !strcmp(name, "v1p8") ? 0 : 1;
	return probe_fail(4 + id) ? ERR_PTR(-EIO) : &model.regulators[id];
}
static struct reset_control *devm_reset_control_get(struct device *dev, const char *name)
{
	(void)dev; assert(!strcmp(name, "por"));
	if (model.reset_get_error) return ERR_PTR(model.reset_get_error);
	return model.has_reset ? &model.reset : ERR_PTR(-ENOENT);
}
static struct phy *devm_phy_create(struct device *dev, void *node, const struct phy_ops *ops)
{
	(void)dev; (void)node; assert(ops->power_on && ops->power_off && ops->set_mode);
	return probe_fail(6) ? ERR_PTR(-EIO) : &model.phy;
}
static struct extcon_dev *extcon_get_edev_by_phandle(struct device *dev, unsigned id)
{
	(void)dev; assert(id == 0);
	if (model.extcon_get_error) return ERR_PTR(model.extcon_get_error);
	return model.has_extcon ? &model.extcon : ERR_PTR(-ENODEV);
}
static struct phy_provider *devm_of_phy_provider_register(struct device *dev, void *xlate)
{ (void)dev; (void)xlate; return probe_fail(7) ? ERR_PTR(-EIO) : &model.provider; }
#define of_phy_simple_xlate NULL
static int clk_prepare_enable(struct clk *c)
{ if (power_fail()) return -EIO; assert(!c->enabled); c->enabled = true; return 0; }
static void clk_disable_unprepare(struct clk *c) { assert(c->enabled); c->enabled = false; }
static int regulator_set_load(struct regulator *r, unsigned load)
{ (void)r; assert(load == 50000); return power_fail() ? -EIO : 0; }
static int regulator_enable(struct regulator *r)
{ if (power_fail()) return -EIO; assert(!r->enabled); r->enabled = true; return 0; }
static int regulator_set_voltage_triplet(struct regulator *r, unsigned min, unsigned target, unsigned max)
{ (void)r; assert(min == 3050000 && target == 3300000 && max == 3300000); return power_fail() ? -EIO : 0; }
static int regulator_disable(struct regulator *r) { assert(r->enabled); r->enabled = false; return 0; }
static int ulpi_write(struct ulpi *u, unsigned addr, unsigned value)
{
	assert(u && model.writes < 256);
	if (power_fail()) return -EIO;
	model.trace[model.writes].addr = addr; model.trace[model.writes++].value = value; return 0;
}
static int reset_control_reset(struct reset_control *r)
{ assert(r); model.reset_calls++; return power_fail() ? -EIO : 0; }
static int extcon_get_state(struct extcon_dev *e, unsigned id)
{ assert(e && id == EXTCON_USB); return 1; }
static int extcon_register_notifier(struct extcon_dev *e, unsigned id, struct notifier_block *n)
{
	assert(e && id == EXTCON_USB && n->notifier_call);
	if (power_fail()) return -EIO;
	model.notifier = true; return 0;
}
static void extcon_unregister_notifier(struct extcon_dev *e, unsigned id, struct notifier_block *n)
{ assert(e && id == EXTCON_USB && n->notifier_call && model.notifier); model.notifier = false; }
