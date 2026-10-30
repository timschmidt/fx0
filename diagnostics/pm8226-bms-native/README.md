# Native PM8226 BMS regression checks

These tests extract functions from the experimental Linux driver rather than
maintaining a second conversion implementation. They run on the host and do not
access the phone. Install Clang and run against the pinned Linux candidate:

```sh
python3 diagnostics/pm8226-bms-native/check_math.py "$LINUX_TREE/drivers/power/supply/qcom_pm8226_bms.c"
python3 diagnostics/pm8226-bms-native/check_io.py "$LINUX_TREE/drivers/power/supply/qcom_pm8226_bms.c"
python3 diagnostics/iadc-calibration/check.py "$LINUX_TREE/drivers/iio/adc/qcom-spmi-iadc.c"
python3 diagnostics/iadc-reference-channels/check.py "$LINUX_TREE/drivers/iio/adc/qcom-spmi-iadc.c"
```

At candidate `35743f1984fc7b9863224856dca0aa148e832be5`, the checks pass
20,033 math cases, 70 BMS I/O fault cases, 34 provider calibration/rollback cases
and 27 IADC reference/cache cases under AddressSanitizer/UndefinedBehaviorSanitizer.
The math oracle uses Python fractions and includes counter wrap, direction
changes, fractional retention, frequent reads and overflow. The I/O model covers
hold ownership/release, torn output, bus faults, sense rollback and forced command
deassertion when clear-command readback is zero. Provider tests cover protected
trim writes, cache publication and failed rollback.

Mock register behavior cannot qualify the physical analog path. RAM testing finds
an unresolved idle charging-stop discrepancy: BMS reports about +155 mA while
manual IADC reports zero, and its relative counter also integrates that suspect
sample. A later input/load transition restores agreement. Discharge response
passes, but this candidate must remain experimental until transition behavior,
current accuracy, temperature/profile policy, capacity and suspend are qualified.
See the [battery work record](../../docs/battery-bringup.md) and
[native driver evidence](../../evidence/2026-10-30-native-bms-prototype.json).
