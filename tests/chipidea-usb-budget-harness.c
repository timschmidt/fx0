// SPDX-License-Identifier: MIT
/* Exercise the extracted ChipIdea budget consumer with controlled work and supplier I/O. */
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CONFIG_PM_SLEEP 1
#define IS_REACHABLE(x) 1
#define container_of(p, t, m) ((t *)((char *)(p) - offsetof(t, m)))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define READ_ONCE(x) (x)
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%d: %s\n", __LINE__, #x); exit(1); } } while (0)
#define ERR_PTR(x) ((void *)(intptr_t)(x))
#define PTR_ERR(x) ((int)(intptr_t)(x))
#define IS_ERR(x) ((uintptr_t)(x) > (uintptr_t)-4096)
#define GFP_KERNEL 0
#define EPROBE_DEFER 517
#define ENOTSUPP 524
#define DL_FLAG_AUTOPROBE_CONSUMER 1
#define USB_DR_MODE_PERIPHERAL 2
#define POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT 1
#define POWER_SUPPLY_TYPE_USB 2
#define POWER_SUPPLY_TYPE_BATTERY 3
#define USB_REQ_SET_CONFIGURATION 9
#define USB_ENDPOINT_XFER_CONTROL 0
#define U8_MAX UINT8_MAX
#define le16_to_cpu(x) (x)
#define __releases(x)
#define __acquires(x)

typedef bool spinlock_t;
static unsigned locks;
#define spin_lock_init(lock) (*(lock) = false)
#define spin_lock_irqsave(lock, flags) do { CHECK(!*(lock)); *(lock) = true; locks++; flags = 0; } while (0)
#define spin_unlock_irqrestore(lock, flags) do { (void)flags; CHECK(*(lock)); *(lock) = false; locks--; } while (0)
static void spin_lock(spinlock_t *lock) { CHECK(!*lock); *lock = true; locks++; }
static void spin_unlock(spinlock_t *lock) { CHECK(*lock); *lock = false; locks--; }

struct work_struct {
    void (*run)(struct work_struct *);
    bool pending;
    bool running;
};
#define INIT_WORK(work, fn) ((work)->run = fn)

static void schedule_work(struct work_struct *work) { work->pending = true; }
static void flush_work(struct work_struct *work)
{
    CHECK(!locks && !work->running);
    while (work->pending) {
        work->pending = false;
        work->running = true;
        work->run(work);
        work->running = false;
    }
}
static void cancel_work_sync(struct work_struct *work)
{
    CHECK(!locks && !work->running);
    work->pending = false;
}

struct device {
    struct device *parent;
    struct { int status; } links;
    bool has_supply, role_switch;
};
struct fwnode_handle { struct device *device; };
enum { DL_STATE_CONSUMER_PROBE = 1, DL_DEV_DRIVER_BOUND = 2 };
struct device_link { int status; };
struct power_supply_desc { int type; const char *name; };
struct power_supply { struct device dev; const struct power_supply_desc *desc; };
union power_supply_propval { int intval; };
struct ci_platdata { int dr_mode; };
struct usb_gadget { unsigned unused; };
struct usb_ctrlrequest { uint8_t bRequestType, bRequest; uint16_t wValue, wIndex, wLength; };
struct usb_ep { unsigned unused; };
struct usb_request { unsigned length; void (*complete)(struct usb_ep *, struct usb_request *); };
struct list_head { struct ci_hw_req *item; };
struct ci_hw_req { struct usb_request req; struct list_head queue; };
struct ci_hw_ep {
    struct ci_hdrc *ci;
    spinlock_t *lock;
    struct { struct list_head queue; } qh;
    struct usb_ep ep;
    unsigned type;
};
struct ci_hdrc {
    struct ci_vbus_draw *vbus_draw;
    struct ci_platdata *platdata;
    struct device *dev;
    void *usb_phy;
    struct usb_gadget gadget;
    struct ci_hw_ep *ep0in;
};

#define list_for_each_entry_safe(pos, next, head, member) \
    for ((pos) = (head)->item, (next) = NULL; (pos); (pos) = (next))
static void list_del_init(struct list_head *node) { node->item = NULL; }
static int dequeue_result;
static int _hardware_dequeue(struct ci_hw_ep *ep, struct ci_hw_req *req)
{
    CHECK(*ep->lock && ep->qh.queue.item == req);
    return dequeue_result;
}
static void usb_gadget_giveback_request(struct usb_ep *ep, struct usb_request *req)
{
    CHECK(!locks && req->complete);
    req->complete(ep, req);
}

static struct device controller, charger, other_charger;
static struct fwnode_handle reference = { &charger };
static struct device_link link;
static const struct power_supply_desc usb = { POWER_SUPPLY_TYPE_USB, "usb-input" };
static const struct power_supply_desc battery = { POWER_SUPPLY_TYPE_BATTERY, "battery" };
static struct power_supply supplies[] = {
    { .dev.parent = &other_charger, .desc = &usb },
    { .dev.parent = &charger, .desc = &battery },
    { .dev.parent = &charger, .desc = &usb },
    { .dev.parent = &charger, .desc = &usb },
};
static unsigned supply_count, references, device_references, node_references, warnings, legacy_ma;
static unsigned changes, programmed[64];
static int link_error, resolve_error, read_error, write_error, cleanup_error;
static void (*cleanup)(void *);
static void (*during_write)(void);
static void *cleanup_data, *allocation;

static bool device_property_present(struct device *dev, const char *name)
{
    CHECK(!strcmp(name, "power-supplies"));
    return dev->has_supply;
}
static bool device_property_read_bool(struct device *dev, const char *name)
{
    CHECK(!strcmp(name, "usb-role-switch"));
    return dev->role_switch;
}
static struct device *dev_fwnode(struct device *dev) { return dev; }
static struct fwnode_handle *fwnode_find_reference(struct device *dev, const char *name, int index)
{
    CHECK(dev == &controller && !strcmp(name, "power-supplies") && !index);
    if (resolve_error)
        return ERR_PTR(resolve_error);
    node_references++;
    return &reference;
}
static struct device *get_dev_from_fwnode(struct fwnode_handle *node)
{
    if (node->device)
        device_references++;
    return node->device;
}
static void fwnode_handle_put(struct fwnode_handle *node) { CHECK(node == &reference && node_references--); }
static void put_device(struct device *dev) { CHECK(dev == &charger && device_references--); }
static struct device_link *device_link_add(struct device *consumer, struct device *supplier, unsigned flags)
{
    CHECK(consumer == &controller && supplier == &charger && flags == DL_FLAG_AUTOPROBE_CONSUMER);
    return link_error ? NULL : &link;
}
static int power_supply_for_each_psy(void *data, int (*match)(struct power_supply *, void *))
{
    CHECK(link.status == DL_STATE_CONSUMER_PROBE && device_references == 1);
    for (unsigned i = 0; i < supply_count; i++) {
        int ret = match(&supplies[i], data);
        if (ret)
            return ret;
    }
    return 0;
}
static struct power_supply *power_supply_get_by_name(const char *name)
{
    CHECK(!strcmp(name, usb.name) && device_references == 1);
    references++;
    return &supplies[2];
}
static void power_supply_put(struct power_supply *psy) { CHECK(psy == &supplies[2] && references--); }
static int power_supply_get_property(struct power_supply *psy, int prop, union power_supply_propval *limit)
{
    CHECK(psy == &supplies[2] && prop == POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT && references);
    limit->intval = 100000;
    return read_error;
}
static int power_supply_set_property(struct power_supply *psy, int prop, const union power_supply_propval *limit)
{
    CHECK(!locks && references == 1 && psy == &supplies[2] && prop == POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT);
    CHECK(changes < sizeof(programmed) / sizeof(programmed[0]));
    programmed[changes++] = limit->intval;
    if (during_write) {
        void (*inject)(void) = during_write;
        during_write = NULL;
        inject();
    }
    return write_error;
}
#define dev_warn_ratelimited(dev, ...) do { CHECK((dev) == &controller); warnings++; } while (0)
static void *devm_kzalloc(struct device *dev, size_t size, int flags)
{
    CHECK(dev == &controller && flags == GFP_KERNEL && !allocation);
    allocation = calloc(1, size);
    return allocation;
}
static int devm_add_action_or_reset(struct device *dev, void (*release)(void *), void *data)
{
    CHECK(dev == &controller && !cleanup);
    if (cleanup_error)
        release(data);
    else {
        cleanup = release;
        cleanup_data = data;
    }
    return cleanup_error;
}
static int usb_phy_set_power(void *phy, unsigned ma)
{
    CHECK(phy == &controller);
    legacy_ma = ma;
    return -EIO;
}

#include "driver-functions.c"

static struct ci_platdata platdata;
static struct ci_hdrc ci = { .dev = &controller, .platdata = &platdata };
static spinlock_t ep_lock;
static struct ci_hw_ep ep0in = { .ci = &ci, .lock = &ep_lock, .type = USB_ENDPOINT_XFER_CONTROL };
static struct ci_hw_ep ep0out = { .ci = &ci, .lock = &ep_lock, .type = USB_ENDPOINT_XFER_CONTROL };
static const struct usb_ctrlrequest set_configuration = { .bRequest = USB_REQ_SET_CONFIGURATION, .wValue = 1 };
static unsigned cases;
#define PASS(x) do { CHECK(x); cases++; } while (0)
#define EVENT(name, value) ci_vbus_draw_event(&ci, CI_VBUS_DRAW_##name, value)

static void reset(void)
{
    CHECK(!references && !device_references && !node_references);
    CHECK(!cleanup && !during_write);
    free(allocation);
    allocation = NULL;
    ci.vbus_draw = NULL;
    ci.usb_phy = NULL;
    ci.ep0in = &ep0in;
    controller.has_supply = true;
    controller.role_switch = false;
    platdata.dr_mode = USB_DR_MODE_PERIPHERAL;
    charger.links.status = DL_DEV_DRIVER_BOUND;
    reference.device = &charger;
    link.status = DL_STATE_CONSUMER_PROBE;
    supply_count = 3;
    changes = warnings = legacy_ma = 0;
    link_error = resolve_error = read_error = write_error = cleanup_error = 0;
}

static void applied(unsigned expected)
{
    unsigned prior = changes;
    flush_work(&ci.vbus_draw->work);
    PASS(changes == prior + 1 && programmed[prior] == expected);
}

static void disconnect_during_write(void)
{
    EVENT(VBUS, 0);
}

static int complete(struct ci_hw_ep *ep, unsigned length, int result)
{
    struct ci_hw_req request = { .req.length = length };
    ep->qh.queue.item = &request;
    dequeue_result = result;
    spin_lock(ep->lock);
    int ret = isr_tr_complete_low(ep);
    spin_unlock(ep->lock);
    ep->qh.queue.item = NULL;
    return ret;
}

int main(void)
{
    reset();
    controller.has_supply = false;
    PASS(!ci_vbus_draw_init(&ci) && !ci.vbus_draw);
    PASS(ci_udc_vbus_draw(&ci.gadget, 500) == -ENOTSUPP && !changes);
    ci.usb_phy = &controller;
    PASS(ci_udc_vbus_draw(&ci.gadget, 300) == -EIO && legacy_ma == 300 && !changes);

    reset();
    ci.usb_phy = &controller;
    PASS(ci_vbus_draw_init(&ci) == -EINVAL);
    ci.usb_phy = NULL;
    platdata.dr_mode = 1;
    PASS(ci_vbus_draw_init(&ci) == -EINVAL);
    platdata.dr_mode = USB_DR_MODE_PERIPHERAL;
    controller.role_switch = true;
    PASS(ci_vbus_draw_init(&ci) == -EINVAL);
    controller.role_switch = false;
    resolve_error = -EINVAL;
    PASS(ci_vbus_draw_init(&ci) == -EINVAL);
    resolve_error = 0;
    reference.device = NULL;
    PASS(ci_vbus_draw_init(&ci) == -EPROBE_DEFER);
    reference.device = &charger;
    link_error = 1;
    PASS(ci_vbus_draw_init(&ci) == -EPROBE_DEFER && !device_references);
    link_error = 0;
    link.status = 0;
    PASS(ci_vbus_draw_init(&ci) == -EPROBE_DEFER && !device_references);
    link.status = DL_STATE_CONSUMER_PROBE;
    charger.links.status = 0;
    PASS(ci_vbus_draw_init(&ci) == -EPROBE_DEFER && !references);
    charger.links.status = DL_DEV_DRIVER_BOUND;
    supply_count = 2;
    PASS(ci_vbus_draw_init(&ci) == -ENODEV && !references);
    supply_count = 4;
    PASS(ci_vbus_draw_init(&ci) == -EINVAL && !references);
    supply_count = 3;
    read_error = -EIO;
    PASS(ci_vbus_draw_init(&ci) == -EIO && !references && !changes);
    reset();
    cleanup_error = -ENOMEM;
    PASS(ci_vbus_draw_init(&ci) == -ENOMEM && !references && !ci.vbus_draw &&
         changes == 1 && programmed[0] == 100000);

    reset();
    PASS(!ci_vbus_draw_init(&ci) && references == 1 && !device_references && !node_references);
    EVENT(REQUEST, 500);
    PASS(!ci.vbus_draw->work.pending);
    EVENT(VBUS, 1);
    applied(100000);
    EVENT(PULLUP, 1);
    EVENT(REQUEST, 500);
    applied(100000);
    PASS(!ci_vbus_draw_config_begin(&ci, &set_configuration));
    PASS(ci_vbus_draw_configuring(&ci));
    PASS(!ci_udc_vbus_draw(&ci.gadget, 500));
    applied(100000);
    PASS(!ci.vbus_draw->work.pending && ci.vbus_draw->requested_ma == 100);
    PASS(!complete(&ep0out, 0, 0) && ci_vbus_draw_configuring(&ci));
    PASS(complete(&ep0in, 4, 4) == 4 && ci_vbus_draw_configuring(&ci));
    PASS(!complete(&ep0in, 0, -EBUSY) && ci_vbus_draw_configuring(&ci));
    PASS(!complete(&ep0in, 0, 0));
    applied(500000);
    PASS(!ci_vbus_draw_configuring(&ci));
    EVENT(VBUS, 1);
    PASS(!ci.vbus_draw->work.pending && ci.vbus_draw->configured);

    EVENT(BUS_SUSPEND, 1);
    EVENT(REQUEST, 2);
    applied(0);
    EVENT(BUS_SUSPEND, 0);
    applied(500000);
    EVENT(REQUEST, 800);
    applied(500000);
    EVENT(REQUEST, 2);
    applied(0);
    EVENT(REQUEST, 300);
    applied(300000);

    struct usb_ctrlrequest invalid = set_configuration;
    invalid.wLength = 1;
    PASS(ci_vbus_draw_config_begin(&ci, &invalid) == -EINVAL && !ci_vbus_draw_configuring(&ci));
    invalid.wLength = 0;
    invalid.wIndex = 1;
    PASS(ci_vbus_draw_config_begin(&ci, &invalid) == -EINVAL && !ci_vbus_draw_configuring(&ci));
    invalid.wIndex = 0;
    invalid.wValue = 256;
    PASS(ci_vbus_draw_config_begin(&ci, &invalid) == -EINVAL && !ci_vbus_draw_configuring(&ci));

    PASS(!ci_vbus_draw_config_begin(&ci, &set_configuration));
    EVENT(REQUEST, 500);
    PASS(complete(&ep0in, 0, -EPIPE) == -EPIPE && !ci_vbus_draw_configuring(&ci));
    PASS(!complete(&ep0in, 0, 0));
    applied(100000);

    EVENT(CONFIG_BEGIN, 2);
    EVENT(REQUEST, 400);
    EVENT(CONFIG_CANCEL, 0);
    EVENT(CONFIG_COMPLETE, 0);
    applied(100000);
    EVENT(REQUEST, 400);
    applied(100000);
    EVENT(CONFIG_BEGIN, 1);
    EVENT(REQUEST, 350);
    EVENT(CONFIG_COMPLETE, 0);
    applied(350000);
    EVENT(CONFIG_BEGIN, 0);
    EVENT(REQUEST, 500);
    EVENT(CONFIG_COMPLETE, 0);
    applied(100000);

    EVENT(CONFIG_BEGIN, 1);
    EVENT(REQUEST, 500);
    EVENT(RESET, 0);
    EVENT(CONFIG_COMPLETE, 0);
    applied(100000);
    EVENT(CONFIG_BEGIN, 1);
    EVENT(REQUEST, 500);
    EVENT(CONFIG_COMPLETE, 0);
    EVENT(PULLUP, 0);
    EVENT(REQUEST, 0);
    applied(100000);
    EVENT(PULLUP, 1);
    applied(100000);

    EVENT(CONFIG_BEGIN, 1);
    EVENT(REQUEST, 500);
    EVENT(CONFIG_COMPLETE, 0);
    EVENT(BUS_SUSPEND, 1);
    unsigned prior = changes;
    ci_vbus_draw_pause(&ci, true);
    PASS(changes == prior + 1 && programmed[prior] == 0);
    EVENT(BUS_SUSPEND, 0);
    PASS(!ci.vbus_draw->work.pending);
    ci_vbus_draw_pause(&ci, false);
    applied(500000);

    EVENT(REQUEST, 400);
    during_write = disconnect_during_write;
    prior = changes;
    flush_work(&ci.vbus_draw->work);
    PASS(changes == prior + 2 && programmed[prior] == 400000 && programmed[prior + 1] == 100000);
    EVENT(REQUEST, 500);
    PASS(!ci.vbus_draw->work.pending);
    EVENT(VBUS, 1);
    write_error = -EREMOTEIO;
    applied(100000);
    PASS(warnings == 1);
    write_error = 0;
    EVENT(RESET, 0);
    applied(100000);

    EVENT(CONFIG_BEGIN, 1);
    EVENT(REQUEST, 500);
    EVENT(CONFIG_COMPLETE, 0);
    prior = changes;
    cleanup(cleanup_data);
    cleanup = NULL;
    PASS(changes == prior + 1 && programmed[prior] == 100000 &&
         !references && !ci.vbus_draw->work.pending);
    reset();
    printf("USB_BUDGET_CASES %u\n", cases);
    return 0;
}
