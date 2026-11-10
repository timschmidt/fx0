// SPDX-License-Identifier: MIT
/* Framing fixture. The checker appends functions from pinned lk2nd source. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "%d: %s\n", __LINE__, #x); exit(1); } } while (0)
#define STACKBUF_DMA_ALIGN(name, size) unsigned char name[size]
#define MAX_RSP_SIZE 64
#define STATE_COMMAND 1
#define STATE_ERROR 3
#define INFO 0
#define CACHE_LINE 32
#define ROUNDUP(x, y) (((x) + (y) - 1) & ~((y) - 1))
#define PA(x) (x)
#define dprintf(...) ((void)0)
typedef uintptr_t addr_t;
struct udc_request {
    void *buf;
    unsigned length;
    void (*complete)(struct udc_request *, unsigned, int);
};
static struct udc_request request, *req = &request;
static unsigned fastboot_state, download_size, download_max;
static void *download_base;
static int txn_done, txn_status;
static int out_endpoint, in_endpoint;
static void *out = &out_endpoint, *in = &in_endpoint;
static unsigned char payload[8 * 1024 * 1024];
static unsigned length, frames, okay;
static unsigned count[2], bytes[2], max_descriptors[2];
static char expected_frame[16];

static void event_signal(int *event, int value)
{
    (void)value;
    CHECK(!*event);
    *event = 1;
}

static void event_wait(int *event)
{
    CHECK(*event);
    *event = 0;
}

static void arch_invalidate_cache_range(addr_t address, unsigned length)
{
    (void)address;
    (void)length;
}

static int udc_request_queue(void *endpoint, struct udc_request *r)
{
    unsigned direction = endpoint == in;
    CHECK((endpoint == in || endpoint == out) && r == req);
    if (direction && r->buf != payload + bytes[1]) {
        CHECK(r->length == strlen(expected_frame));
        CHECK(!memcmp(r->buf, expected_frame, r->length));
        frames++;
    } else {
        CHECK(bytes[direction] < length && r->buf == payload + bytes[direction]);
        unsigned remaining = length - bytes[direction];
        unsigned expected = remaining > MAX_USBFS_BULK_SIZE ? MAX_USBFS_BULK_SIZE : remaining;
        CHECK(r->length == expected);
        unsigned descriptors = (r->length + MAX_TD_XFER_SIZE - 1) / MAX_TD_XFER_SIZE;
        if (descriptors > max_descriptors[direction])
            max_descriptors[direction] = descriptors;
        bytes[direction] += r->length;
        count[direction]++;
    }
    r->complete(r, r->length, 0);
    return 0;
}

static void fastboot_okay(const char *message)
{
    CHECK(!*message);
    okay++;
}

static void fastboot_fail(const char *message)
{
    (void)message;
    CHECK(0);
}

static struct {
    int (*usb_write)(void *, unsigned);
    int (*usb_read)(void *, unsigned);
} usb_if;
