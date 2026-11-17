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
 struct iio_device_config config = {0};
 model_cache_config(&d, &config, &mask, stamp);
 model_cache_enable(&d, &config);
 assert(d.scan_bytes > 0);
#if !MODEL_CURRENT
 if (stamp) d.scan_timestamp_offset = d.scan_bytes - sizeof(int64_t);
#endif

	d.observer_offset = d.scan_timestamp_offset;
	return d;
}
