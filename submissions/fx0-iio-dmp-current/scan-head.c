// SPDX-License-Identifier: GPL-2.0-only
/* Synthetic IIO object/resolver/sink services for the actual core helpers. */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#ifndef BIT
#define BIT(n) (1U << (n))
#endif
#ifndef ARRAY_SIZE
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#endif
#define ALIGN(x, a) (((x) + (a) - 1) & ~((a) - 1))
#define max(a, b) ((a) > (b) ? (a) : (b))
#define IS_ERR(p) ((uintptr_t)(p) >= (uintptr_t)-4095)
#define PTR_ERR(p) ((int)(intptr_t)(p))
#define ACCESS_PRIVATE(p, m) ((p)->m)
#define unlikely(c) (c)
#ifndef dev_err
#define dev_err(...) ((void)0)
#endif
#define roundup_pow_of_two(n) (1UL << (sizeof(unsigned long) * 8 - __builtin_clzl((n) - 1)))
#define for_each_set_bit(i, p, n) for ((i) = 0; (i) < (int)(n); (i)++) if (*(p) & (1UL << (i)))
enum { IIO_TEMP, IIO_ANGL_VEL, IIO_ACCEL, IIO_ACTIVITY, IIO_ROT, IIO_TIMESTAMP };
enum { IIO_MOD_X, IIO_MOD_Y, IIO_MOD_Z, IIO_MOD_X_OR_Y_OR_Z, IIO_MOD_STILL, IIO_MOD_QUATERNION };
enum { IIO_CHAN_INFO_RAW, IIO_CHAN_INFO_OFFSET, IIO_CHAN_INFO_SCALE, IIO_CHAN_INFO_CALIBBIAS, IIO_CHAN_INFO_SAMP_FREQ };
enum { IIO_BE, IIO_CPU };
struct iio_scan_type { char sign; unsigned realbits, storagebits, shift, repeat, endianness; };
struct iio_chan_spec {
	int type, modified, channel, channel2, scan_index;
	unsigned info_mask_separate, info_mask_shared_by_type, num_event_specs;
	const void *ext_info, *event_spec;
	struct iio_scan_type scan_type;
};
struct inv_mpu6050_state;
struct iio_dev {
	struct inv_mpu6050_state *st;
	const struct iio_chan_spec *channels;
	int num_channels;
	unsigned masklength, scan_index_timestamp, scan_bytes, scan_timestamp_offset;
	unsigned observer_offset;
	bool scan_timestamp;
	int samples;
	int32_t q[4]; int64_t timestamp;
	unsigned char record[32];
};
#define iio_dev_opaque iio_dev
#define to_iio_dev_opaque(p) (p)
#define iio_get_masklength(p) ((p)->masklength)
#define iio_priv(d) ((d)->st)
static const int inv_ext_info[] = {0}, inv_wom_events[] = {0}, inv_smd_events[] = {0};
static const struct iio_scan_type *iio_get_current_scan_type(struct iio_dev *dev,
	const struct iio_chan_spec *ch)
{ (void)dev; assert(ch); return &ch->scan_type; }
static int iio_push_to_buffers(struct iio_dev *d, const void *p)
{
	assert(d->scan_bytes <= sizeof(d->record));
	memcpy(d->record, p, d->scan_bytes);
	memcpy(d->q, p, sizeof(d->q));
	if (d->scan_timestamp) memcpy(&d->timestamp, (const char *)p + d->observer_offset, 8);
	d->samples++;
	return 0;
}
