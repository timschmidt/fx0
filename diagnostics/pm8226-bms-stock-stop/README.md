# Stock charge-only transition diagnostic

Run only under the original Fx0 kernel/QCDT booted into the diagnostic RAM
initramfs. A host supervisor must verify the selected unit, image digest and
automatic return timer, retain private captures, and return to the installed
system even when this script fails. This is not a stock restoration rehearsal.

`collect.sh` checks that no disk filesystems are mounted, the battery is present,
Charging/Good and within the guarded temperature range, and charging is enabled
without forced-battery mode. It uses the stock factory `bms/charge` API to stop
charging for about 26 seconds, then restore it. The selected API calls
`chg_status_set()` in the vendor charger driver. Its disabled path changes
charge enable and the factory EOC flag. The ordinary `charging_enabled` setter
also forces battery operation and is unsuitable for this comparison.

The script verifies charge-enable and forced-battery bits before/after the API,
samples supplies and selected registers, and restores attribute permissions and
debugfs selectors. Its exit trap attempts re-enabling only while the battery
sensor guards pass. A guard failure deliberately leaves charging disabled and
requires inspection. Voltage, current and thermal limits are not changed.
The stock kernel itself initializes volatile gauge state during RAM boot.

Optional `collect.sh --debug` enables existing dynamic-debug callsites in a
small set of BMS/calibration functions. Original print flags are saved in RAM
and restored at exit. Sample markers go into the kernel log; capture `dmesg`
privately before returning. Missing debug support aborts before charging changes.
Do not enable all SPMI/ADC debug messages: those paths are much hotter.

Raw output includes unit calibration and must remain private. Export the
allowlisted measurements with:

```sh
python3 diagnostics/pm8226-bms-stock-stop/summarize.py PRIVATE_CAPTURE
```

The export contains current, voltage, temperature, status, relative counters,
control bits and a trim-change boolean; it never includes raw calibration bytes.
Stock supply current is negative while charging, while the manual stock IADC
interface is positive. Registers are read sequentially without a joint latch;
do not interpret them as one atomic hardware state. Stock counter getters also
have stateful behavior, including a reset at a reported Full transition. Neither
stock/native agreement nor this test replaces external current measurement.

The pinned source reference is
[`03aba4427a7666d57b5ae06d375e259ea337f351`](https://github.com/peremen/android-kernel-lg-madai/commit/03aba4427a7666d57b5ae06d375e259ea337f351).
See `drivers/power/power_supply_sysfs.c`, `qpnp-charger.c`, `qpnp-bms.c` and
`drivers/hwmon/qpnp-adc-current.c`. The stock binary's exact source correspondence
has not been established; use runtime observations to qualify source inferences.
