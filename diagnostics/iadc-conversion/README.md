# PM8226 current conversion regression

On the Fx0, the packaged IADC driver reports raw 40/36 with scale 0.001 mA.
Its own calibration log shows samples below the offset, but an unsigned
intermediate wraps their difference. A second error divides microvolts by
microohms without converting the resulting amps to the microamps expected by
that scale. Both errors also exist in the reviewed
[upstream driver](https://github.com/torvalds/linux/blob/master/drivers/iio/adc/qcom-spmi-iadc.c).
The correction is developed on
[integration/fx0-iadc](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-iadc).

Run this host-only fixture against the actual driver source:

```sh
python3 diagnostics/iadc-conversion/check.py /path/to/linux/drivers/iio/adc/qcom-spmi-iadc.c
```

Clang and its undefined-behavior sanitizer runtime are required by default;
`--cc` selects another compatible compiler. The fixture extracts the real
`iadc_read_raw` function and replaces only hardware/IIO plumbing. Thirteen
vectors on each channel cover zero, both directions, one-code differences,
a 10.8 mΩ resistor, synthetic wrap examples, subtraction extremes and int overflow.
The wrap examples use invented calibration inputs and an illustrative 9 mΩ
resistor or the driver's 10 mΩ default. Actual unit conversion traces and
calibration readings remain private. It checks the unchanged IIO scale. The original driver fails these regression
cases; the correction passes without sanitizer findings.

An isolated module build uses Alpine Clang 22.1.3, the running r3 configuration
with only automatic release suffix generation disabled, and an existing matching
symbol table. All 34 common imported CRCs match the packaged module; the new
`div64_s64` import matches the seed symbol table. W=1 compilation and patch-only
checkpatch pass. This is a diagnostic build, not a signed production package.

A brief RAM-only test replaces the unused IADC module, records negative sensed
current and matching conversion logs, then restores the original packaged
module. Its file hash remains unchanged. The unsigned external module sets
kernel taint 12288; the subsequent normal installed-r3 reboot returns to taint 0. No
charger thresholds, firmware or calibration storage are changed. The external
channel still uses its original 10 mΩ default. Board sense-resistor values,
direction relative to battery status, physical accuracy, fuel-gauge capacity
and charging policy remain separate qualification work.

The signed native r4 package subsequently boots from eMMC with kernel taint 0.
Twelve logged voltage calculations and six external-channel current calculations
match the conversion, with the full Sxmo session restored. See
[installed r4 evidence](../../evidence/2026-10-30-native-r4-installed-boot.json).
The charger still reports the pre-existing intermittent Overheat state.
