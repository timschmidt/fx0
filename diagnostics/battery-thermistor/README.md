# Fx0 battery temperature

**Do not promote this integration yet.** The native comparator window produces
HOT at a stock-reported 31.6°C, reproduced on the original kernel with the same
tighter settings. Restoring stock's wider window clears HOT. Stock also supplies
LG software temperature policy; native needs its own complete policy/fault/PM
handling before widening the hardware range. Measurement conversion and supplier
lifetime pass, but charging integration remains incomplete. See
[stock-window evidence](../../evidence/2026-10-30-stock-BTC-window.json).

The experimental
[temperature branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-battery-temperature)
adds the generic ADC thermal binding's optional zero-cell IIO output and a
separate GPL-2.0-only Fx0 battery include. The include preserves the LG table's
attribution and describes the original pack. It supplies temperature measurements;
it does not choose a capacity profile or relax charging limits.

The chain is VADC thermistor channel 48, in standard IIO millivolts, through
`generic-adc-thermal` to thermal/IIO milliCelsius and BMS `temp` in deciCelsius.
The lookup data come from the LG charging-temperature branch of
[`qpnp-adc-common.c` at 03aba4427](https://github.com/peremen/android-kernel-lg-madai/blob/03aba4427a7666d57b5ae06d375e259ea337f351/drivers/hwmon/qpnp-adc-common.c).
Its temperature entries are multiplied by 100 to convert deciCelsius to
milliCelsius; voltage entries remain millivolts. The generic driver already
exports the processed temperature channel; the binding addition makes that
consumer reference valid. The installed r4 package is unchanged.

Run the host check against the experimental Linux tree and pinned vendor tree:

```sh
python3 diagnostics/battery-thermistor/check.py "$LINUX_TREE" "$VENDOR_TREE"
```

It verifies all 83 data points and units, then compiles the actual generic-driver
interpolation function and kernel `mult_frac` macro. It compares 1,803 inputs to a
fractional oracle under ASan/UBSan, covering table endpoints, negative temperature,
every integer millivolt from 0 through 1,800, extreme inputs and passthrough.

RAM testing uses the original signed r4 kernel/initramfs, a new board DTB, and
unsigned candidate IADC/VADC/BMS modules plus the unmodified generic thermal
module. A packaged implementation will need `CONFIG_GENERIC_ADC_THERMAL=m` and
normal module delivery. The first RAM test confirms matching temperatures, then
stops because its automatic consumer-rebind expectation was too strong. The
second uses the same image and explicitly reprobes the BMS after rebinding the
temperature supplier; all three cycles pass. No automatic rebind is claimed.
Removing the supplier first removes the BMS consumer and cancels its work.

Generic interpolation clamps out-of-table voltages to the endpoint temperatures.
That behavior is covered by the host check; it does not distinguish an electrical
open/short from an extreme temperature. Sensor-fault discrimination, independent
accuracy, software charging policy/hysteresis and suspend/wake protection remain
required. The thermal zone has no automatic charging policy. Hardware comparator
limits remain conservative. See [runtime evidence](../../evidence/2026-10-30-battery-temperature.json).
