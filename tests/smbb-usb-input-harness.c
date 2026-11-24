// SPDX-License-Identifier: MIT
/* Instrumented SPMI fixture for extracted SMBB USB input callbacks. */
#include <errno.h>
#include <pthread.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define BIT(n) (1U << (n))
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%d: %s\n", __LINE__, #x); exit(1); } } while (0)
#define dev_dbg(...) ((void)0)
#define dev_warn(...) ((void)0)
#define dev_err(...) ((void)0)
#include "driver-definitions.h"

struct device_node { bool pm8226; };
struct device { struct device_node *of_node; };
struct mutex { pthread_mutex_t lock; };
struct operation { unsigned offset; unsigned value; bool write; };
struct regmap {
    unsigned registers[0x400];
    struct operation log[32];
    unsigned operations, fail_at, fail_from, drop_offset;
    bool fail_after_write;
};
struct smbb_charger {
    unsigned addr;
    struct device *dev;
    struct regmap *regmap;
    struct mutex charge_lock, statlock;
    bool usb_input_control;
    bool usb_budget_managed;
    unsigned long status;
    unsigned attr[_ATTR_CNT];
};
struct power_supply { struct smbb_charger *data; };
enum power_supply_property {
    POWER_SUPPLY_PROP_ONLINE, POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,
    POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT, POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT_MAX,
};
union power_supply_propval { int intval; };
static struct smbb_charger *power_supply_get_drvdata(struct power_supply *psy) { return psy->data; }
static void mutex_lock(struct mutex *m) { CHECK(!pthread_mutex_lock(&m->lock)); }
static void mutex_unlock(struct mutex *m) { CHECK(!pthread_mutex_unlock(&m->lock)); }
static bool of_device_is_compatible(struct device_node *node, const char *name)
{
    CHECK(!strcmp(name, "qcom,pm8226-charger"));
    return node->pm8226;
}
static unsigned register_offset(unsigned address)
{
    CHECK(address >= 0x1000);
    unsigned offset = address - 0x1000;
    CHECK(offset == SMBB_USB_TYPE || offset == SMBB_USB_SUBTYPE || offset == SMBB_USB_IMAX ||
          offset == SMBB_USB_SUSPEND || offset == SMBB_BAT_PRES_STATUS);
    return offset;
}
static bool trace(struct regmap *map, unsigned offset, unsigned value, bool write)
{
    CHECK(map->operations < sizeof(map->log) / sizeof(map->log[0]));
    map->log[map->operations++] = (struct operation){ offset, value, write };
    return map->operations == map->fail_at || (map->fail_from && map->operations >= map->fail_from);
}
static int regmap_read(struct regmap *map, unsigned address, unsigned *value)
{
    unsigned offset = register_offset(address);
    if (trace(map, offset, map->registers[offset], false))
        return -EREMOTEIO;
    *value = map->registers[offset];
    return 0;
}
static int regmap_write(struct regmap *map, unsigned address, unsigned value)
{
    unsigned offset = register_offset(address);
    CHECK(offset == SMBB_USB_IMAX || offset == SMBB_USB_SUSPEND);
    CHECK(value < 256);
    bool fail = trace(map, offset, value, true);
    if ((!fail || map->fail_after_write) && offset != map->drop_offset)
        map->registers[offset] = value;
    return fail ? -EREMOTEIO : 0;
}
static int regmap_write_bits(struct regmap *map, unsigned address, unsigned mask, unsigned value)
{
    unsigned old;
    int ret = regmap_read(map, address, &old);
    if (ret)
        return ret;
    return regmap_write(map, address, (old & ~mask) | (value & mask));
}
#include "driver-functions.c"

static struct regmap map;
static struct device_node node;
static struct device dev = { .of_node = &node };
static struct smbb_charger charger = {
    .addr = 0x1000, .dev = &dev, .regmap = &map,
    .charge_lock = { PTHREAD_MUTEX_INITIALIZER }, .statlock = { PTHREAD_MUTEX_INITIALIZER },
};
static struct power_supply psy = { .data = &charger };
static unsigned cases;
#define PASS(x) do { CHECK(x); cases++; } while (0)

static void reset(bool suspended)
{
    memset(&map, 0, sizeof(map));
    node.pm8226 = true;
    map.registers[SMBB_USB_TYPE] = 2;
    map.registers[SMBB_USB_SUBTYPE] = 0x34;
    map.registers[SMBB_USB_IMAX] = 5;
    map.registers[SMBB_USB_SUSPEND] = suspended ? 0xa1 : 0xa0;
    map.registers[SMBB_BAT_PRES_STATUS] = PRES_STATUS_BAT_PRES;
    charger.usb_input_control = true;
    charger.usb_budget_managed = false;
    charger.attr[ATTR_USBIN_IMAX] = 500000;
}
static int set(enum power_supply_property property, int value)
{
    union power_supply_propval request = { .intval = value };
    return smbb_usbin_set_property(&psy, property, &request);
}
static int get(enum power_supply_property property, int *value)
{
    union power_supply_propval result = { .intval = *value };
    int ret = smbb_usbin_get_property(&psy, property, &result);
    *value = result.intval;
    return ret;
}
static unsigned writes(unsigned offset)
{
    unsigned count = 0;
    for (unsigned i = 0; i < map.operations; i++)
        count += map.log[i].write && map.log[i].offset == offset;
    return count;
}

int main(void)
{
    const enum power_supply_property input = POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT;
    const enum power_supply_property legacy = POWER_SUPPLY_PROP_CHARGE_CONTROL_LIMIT;
    int value = -1;

    reset(false);
    PASS(smbb_usb_input_supported(&charger) && map.operations == 2);
    reset(false);
    node.pm8226 = false;
    PASS(!smbb_usb_input_supported(&charger) && !map.operations);
    reset(false);
    map.registers[SMBB_USB_SUBTYPE] = 4;
    PASS(!smbb_usb_input_supported(&charger) && map.operations == 2);
    reset(false);
    map.registers[SMBB_USB_TYPE] = 1;
    PASS(!smbb_usb_input_supported(&charger));
    for (unsigned failure = 1; failure <= 2; failure++) {
        reset(false);
        map.fail_at = failure;
        PASS(!smbb_usb_input_supported(&charger));
    }

    reset(false);
    PASS(smbb_usbin_writable_property(&psy, input) == 1);
    PASS(!get(input, &value) && value == 500000);
    map.registers[SMBB_USB_IMAX] = 0xff;
    PASS(get(input, &value) == -EIO && value == 500000);
    map.registers[SMBB_USB_SUSPEND] = 0xa1;
    PASS(!get(input, &value) && value == 0);
    PASS(!get(legacy, &value) && value == 500000);
    for (unsigned failure = 1; failure <= 2; failure++) {
        reset(false);
        map.fail_at = failure;
        value = -1;
        PASS(get(input, &value) == -EREMOTEIO && value == -1);
    }
    reset(false);
    charger.usb_input_control = false;
    PASS(smbb_usbin_writable_property(&psy, input) == 0);
    PASS(set(input, 0) == -EOPNOTSUPP && !map.operations);
    PASS(get(input, &value) == -EOPNOTSUPP && !map.operations);
    PASS(!set(legacy, 200000) && map.registers[SMBB_USB_IMAX] == 2 && !writes(SMBB_USB_SUSPEND));

    reset(false);
    PASS(!set(input, 0) && map.registers[SMBB_USB_SUSPEND] == 0xa1 && !writes(SMBB_USB_IMAX));
    reset(false);
    map.registers[SMBB_BAT_PRES_STATUS] = 0;
    PASS(set(input, 0) == -ENODEV && !writes(SMBB_USB_SUSPEND));
    reset(true);
    PASS(!set(legacy, 150000) && map.registers[SMBB_USB_SUSPEND] == 0xa1 && !writes(SMBB_USB_SUSPEND));
    PASS(set(legacy, 0) == -EINVAL && !writes(SMBB_USB_SUSPEND));
    reset(true);
    PASS(!set(input, 399999) && map.registers[SMBB_USB_IMAX] == 3 && map.registers[SMBB_USB_SUSPEND] == 0xa0);
    PASS(map.operations == 5 && map.log[0].offset == SMBB_USB_IMAX && map.log[0].write &&
         map.log[1].offset == SMBB_USB_IMAX && !map.log[1].write &&
         map.log[3].offset == SMBB_USB_SUSPEND && map.log[3].write);
    PASS(!get(input, &value) && value == 300000);

    int invalid[] = { -1, 1, 2000, 99999, 2500001 };
    for (unsigned i = 0; i < sizeof(invalid) / sizeof(invalid[0]); i++) {
        reset(false);
        PASS(set(input, invalid[i]) == -EINVAL && !map.operations);
    }
    for (unsigned failure = 1; failure <= 5; failure++) {
        for (unsigned after = 0; after <= 1; after++) {
            reset(false);
            map.fail_at = failure;
            map.fail_after_write = after;
            PASS(set(input, 100000) == -EREMOTEIO && map.registers[SMBB_USB_SUSPEND] == 0xa1);
        }
    }
    for (unsigned failure = 1; failure <= 4; failure++) {
        reset(false);
        map.fail_at = failure;
        PASS(set(input, 0) == -EREMOTEIO);
    }
    reset(false);
    map.drop_offset = SMBB_USB_IMAX;
    PASS(set(input, 100000) == -EIO && map.registers[SMBB_USB_SUSPEND] == 0xa1);
    reset(true);
    map.drop_offset = SMBB_USB_SUSPEND;
    PASS(set(input, 100000) == -EIO && map.registers[SMBB_USB_SUSPEND] == 0xa1);
    reset(false);
    map.drop_offset = SMBB_USB_SUSPEND;
    PASS(set(input, 0) == -EIO && map.registers[SMBB_USB_SUSPEND] == 0xa0);
    reset(false);
    map.fail_from = 1;
    PASS(set(input, 100000) == -EREMOTEIO && map.registers[SMBB_USB_SUSPEND] == 0xa0);
    reset(false);
    map.fail_at = 1;
    map.registers[SMBB_BAT_PRES_STATUS] = 0;
    PASS(set(input, 100000) == -EREMOTEIO && !writes(SMBB_USB_SUSPEND));
#ifdef HAVE_USB_BUDGET_MANAGED
    reset(false);
    charger.usb_budget_managed = true;
    PASS(!smbb_usbin_writable_property(&psy, input));
    PASS(!smbb_usbin_writable_property(&psy, legacy));
    PASS(set(legacy, 200000) == -EBUSY && !map.operations);
    PASS(!set(input, 500000) && map.registers[SMBB_USB_IMAX] == 5);
    PASS(!set(input, 0) && map.registers[SMBB_USB_SUSPEND] == 0xa1);
    PASS(!get(input, &value) && value == 0);
    PASS(!set(input, 500000) && map.registers[SMBB_USB_SUSPEND] == 0xa0);

    reset(false);
    charger.usb_budget_managed = true;
    map.registers[SMBB_BAT_PRES_STATUS] = 0;
    PASS(set(input, 0) == -ENODEV && map.registers[SMBB_USB_IMAX] == 0 &&
         map.registers[SMBB_USB_SUSPEND] == 0xa0);
    PASS(!get(input, &value) && value == 100000);

    reset(true);
    charger.usb_budget_managed = true;
    map.registers[SMBB_BAT_PRES_STATUS] = 0;
    PASS(set(input, 0) == -ENODEV && map.registers[SMBB_USB_IMAX] == 0 &&
         map.registers[SMBB_USB_SUSPEND] == 0xa0);

    reset(false);
    charger.usb_budget_managed = true;
    map.registers[SMBB_BAT_PRES_STATUS] = 0;
    map.fail_at = 2;
    PASS(set(input, 0) == -EREMOTEIO && map.registers[SMBB_USB_IMAX] == 5 &&
         !writes(SMBB_USB_SUSPEND));
#endif
    printf("USB_INPUT_CASES %u\n", cases);
    return 0;
}
