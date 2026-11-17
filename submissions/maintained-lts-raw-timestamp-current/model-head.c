/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Synthetic time inputs only; no I/O, kernel service or device execution. */
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef uint32_t u32;
typedef uint64_t u64;
typedef int64_t s64;
#define ARRAY_SIZE(x) (sizeof(x) / sizeof((x)[0]))
#define NSEC_PER_MSEC 1000000LL
static inline s64 div_s64(s64 dividend, int32_t divisor)
{
	return dividend / divisor;
}
static inline u64 div_u64(u64 dividend, u32 divisor)
{
	return dividend / divisor;
}
#define min(a, b) ((a) < (b) ? (a) : (b))
#define clamp(x, lo, hi) ((x) < (lo) ? (lo) : ((x) > (hi) ? (hi) : (x)))
#define EXPORT_SYMBOL_NS_GPL(...)
#define MODULE_AUTHOR(...)
#define MODULE_DESCRIPTION(...)
#define MODULE_LICENSE(...)
static unsigned long cases, checks, failures;
static unsigned long group_failures[8];
static unsigned int group;
#define CHECK(c) do { checks++; if (!(c)) { failures++; group_failures[group]++; } } while (0)

