static struct iio_dev model_iio_device(struct inv_mpu6050_state *state,
	unsigned long mask, bool stamp)
{
	struct iio_dev d = {.st = state, .channels = inv_mpu6515_channels,
		.num_channels = ARRAY_SIZE(inv_mpu6515_channels), .scan_timestamp = stamp};
	for (int i = 0; i < d.num_channels; i++) {
		const struct iio_chan_spec *ch = &d.channels[i];
		if (ch->scan_index >= 0 && (unsigned)ch->scan_index >= d.masklength)
			d.masklength = ch->scan_index + 1;
		if (ch->type == IIO_TIMESTAMP) d.scan_index_timestamp = ch->scan_index;
	}
#if MODEL_CURRENT
	assert(iio_compute_scan_bytes(&d, &mask, stamp, &d.scan_bytes, &d.scan_timestamp_offset) == 0);
#else
	int bytes = iio_compute_scan_bytes(&d, &mask, stamp);
	assert(bytes > 0); d.scan_bytes = bytes;
	if (stamp) d.scan_timestamp_offset = d.scan_bytes - sizeof(int64_t);
#endif
	d.observer_offset = d.scan_timestamp_offset;
	return d;
}
