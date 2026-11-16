// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic regmap/work services; the driver functions are extracted unchanged. */
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
#define GENMASK(h, l) (((1U << ((h) + 1)) - 1) & ~((1U << (l)) - 1))
#define min(a, b) ((a) < (b) ? (a) : (b))
#define mult_frac(x, n, d) (((x) / (d)) * (n) + ((x) % (d)) * (n) / (d))
#define container_of(p, type, member) ((type *)((char *)(p) - offsetof(type, member)))
struct input_dev {};
struct work_struct { int unused; };
struct regmap { unsigned values[0x10000], calls, fail; };
static bool fail(struct regmap *m) { return ++m->calls == m->fail; }
static int regmap_read(struct regmap *m, unsigned addr, unsigned *value)
{
	assert(addr < 0x10000);
	if (fail(m)) return -EIO;
	*value = m->values[addr]; return 0;
}
static int regmap_write(struct regmap *m, unsigned addr, unsigned value)
{
	assert(addr < 0x10000 && value <= 255);
	if (fail(m)) return -EIO;
	m->values[addr] = value; return 0;
}
static int regmap_update_bits(struct regmap *m, unsigned addr, unsigned mask, unsigned value)
{
	assert(addr < 0x10000 && mask <= 255);
	if (fail(m)) return -EIO;
	m->values[addr] = (m->values[addr] & ~mask) | (value & mask); return 0;
}
#define regmap_write_bits regmap_update_bits
