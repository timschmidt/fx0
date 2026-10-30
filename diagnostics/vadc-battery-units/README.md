# Battery voltage units and consumer precision

The new VBAT_SNS and BAT_THERM processed interfaces use standard IIO millivolts.
Absolute calibration internally produces microvolts, so the callback returns
`IIO_VAL_FRACTIONAL` with denominator 1000. Ratiometric calibration already
produces millivolts. `iio_read_channel_processed_scale(channel, &value, 1000)`
recovers the original microvolt precision for a power-supply consumer.
Legacy processed channels and all raw interfaces retain their existing units.

Run the actual VADC callback and IIO consumer multiplication tests:

```sh
python3 diagnostics/vadc-battery-units/check.py /path/to/linux
```

The fixture replaces conversion/calibration hardware plumbing, while compiling
the real callback and `iio_multiply_value`. Its 84 cases cover both battery
channels, absolute/ratiometric calibration, fractional precision, legacy
channels, raw reads and error propagation under ASan/UBSan. The pre-fix driver
fails. W=1 ARM compilation and RAM-only sysfs reads also pass; firmware consumer
lookup and physical voltage accuracy remain separate tests.
