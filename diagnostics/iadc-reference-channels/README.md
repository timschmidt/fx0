# IADC calibration-reference regression

The native BMS needs the 17.857 mV gain reference and both zero-current reference
codes through IIO. The development patch exposes hardware channels 3, 5 and 6 as
raw voltage channels while preserving current channels 0 and 1. Firmware lookup
must translate hardware channel numbers to array indices because the channel
list is noncontiguous.

Run against the patched driver:

```sh
python3 diagnostics/iadc-reference-channels/check.py \
    /path/to/linux/drivers/iio/adc/qcom-spmi-iadc.c
python3 diagnostics/iadc-conversion/check.py \
    /path/to/linux/drivers/iio/adc/qcom-spmi-iadc.c
```

The first fixture extracts the actual translation and read functions, sharing
minimal IIO/hardware stubs with the current-conversion fixture. Its 23 cases cover
raw code endpoints, rejection of reference scale requests, all five hardware
channel mappings, invalid channel numbers, oversized IDs and invalid cell counts.
It runs with address and undefined-behavior sanitizers. The second fixture retains
the signed-current and unit regression.

Three RAM-only hardware sample sets return all three reference codes, with gain
above both zero references and both current interfaces usable. The original
packaged module is restored afterward. The physical test covers sysfs conversion;
firmware consumer routing remains a separate test. Per-unit reference codes stay
private. These are calibration inputs, not calibrated battery-current results.

Source commits, module hashes and test limits are recorded in
[ADC evidence](../../evidence/2026-10-30-battery-adc-references.json).
