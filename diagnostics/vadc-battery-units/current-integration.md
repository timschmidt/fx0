# Battery telemetry prerequisites on Linux 6.18.63

The isolated source revision in the [manifest](../../manifests/power-telemetry-prerequisite-6.18.63.json)
carries the processed VADC voltage prerequisite onto reproducible base
`e7c72f8cb3c50a1ec089f96277b7d4b469212ba9`. It changes one driver: VBAT_SNS
and LR_MUX1_BAT_THERM gain processed millivolt interfaces while retaining raw
reads and prescale ratios. Absolute results use a denominator of 1000 so a
processed-scale consumer can recover microvolt precision. Other processed
channels retain their existing behavior. The driver bytes match the preserved
`2457eebe0bb6` prototype and its freshly retrieved public source.

Both host contexts pass 84 actual-callback/IIO-consumer cases. Compiled channel
tables retain all 94 registered channels, add the two processed interfaces and
preserve the other 92 records. The original callback fails the unit contract;
missing advertisement, changed battery prescale and unrelated-channel mutations
fail metadata checks. A seven-file source-only export needs no ignored local
programs. The W=1 ARM object builds without warnings using the retained audited
Alpine Clang 22.1.3 toolchain and prepared kernel mounted read-only. This is an
object compatibility check, not a complete package or physical boot result.

The first sanitizer run cannot execute LeakSanitizer under sandbox tracing.
Its baseline also stops at an unused-parameter compilation warning. Those runs
are excluded. The fixture now permits unused plumbing parameters so the actual
original callback executes and fails normally. ASan/UBSan remain enabled in the
successful runs outside tracing. The first ARM container stops on missing
temporary device nodes and an external-target path; the corrected fresh attempt
passes. Original failed attempts remain preserved.

## Remaining integration and physical gates

Six relevant driver, Kconfig, USB and board-source files in the installed-r1
source are byte-identical to the reproducible base. Twelve preserved policy and
firmware source/patch files match their original checkpoint manifest. Their
historical source directory is now an unavailable symlink; the preserved files
are used without repairing or overwriting it.

| Requirement | Installed/base source and remaining work |
| --- | --- |
| Voltage provider | Battery VADC channels are raw-only. This isolated candidate adds their processed ABI; actual voltage accuracy and supplier behavior still need qualification on the combined candidate. |
| Live current and BMS | The earlier signed IADC conversion fix is present, but the experimental non-VM PM8226 BMS driver is absent. Its calibration, live/background-current discrepancy and relative counter remain unresolved integration and electrical-measurement work. No SOC estimate is added. |
| Pack identity and early inhibition | SMBB lacks the prototype handoff/profile consumers and the board lacks its opt-in. Firmware must supply an identified runtime pack profile and a verified inhibited/conservative handoff; this pass does not requery runtime firmware properties. Do not add an unconditional removable-pack capacity model. |
| Temperature and charging policy | Generic ADC thermal is disabled and the managed child is absent. Port and qualify supplier lifetime, thermal conversion/faults, fresh-sample limits, hysteresis, pack-loss and suspend handling together with the early gate. The conservative comparator must not be widened merely to clear a status flag. |
| USB input budgeting | Board source lacks the opt-in. Each older actuator/binding/gadget patch fails a standalone applicability check against the current base. They depend on the managed foundation and need an ordered rebase, normal builds and physical enumeration/suspend/source-loss/current checks. This is not a claim that an ordered port is impossible. |
| UPower and user interface | The installed missing-telemetry guard avoids a false empty battery. New consumers still require valid/stale/fault/recovery handling and complete physical voltage/current/temperature/SOC qualification. |
| Acceptance | Build the combined source through normal signed packaging and qualify RAM boot, return, installation/recovery, electrical accuracy, charge completion, thermal boundaries, charger-only startup and reliability. The unchanged-r2 repeat and existing passive trial gates remain separate. |

No phone access, image assembly, firmware/profile change, charging-policy change,
package installation or physical acceptance occurs in this pass. The source
branch and review evidence remain local. The complete bringup goal remains open.

## Reproduce the source checks

Use a fresh checkout at the manifest's public base and save its original driver
before applying the [patch](../../patches/linux-integration/vadc-processed-battery-voltages.patch).
Here `FX0_LINUX` names that fresh kernel checkout; run the Python commands from
this repository.

```sh
git -C "$FX0_LINUX" show e7c72f8cb3c50a1ec089f96277b7d4b469212ba9:drivers/iio/adc/qcom-spmi-vadc.c > /path/to/vadc-before.c
git -C "$FX0_LINUX" apply /path/to/fx0/patches/linux-integration/vadc-processed-battery-voltages.patch
python3 diagnostics/vadc-battery-units/check.py "$FX0_LINUX"
python3 diagnostics/vadc-battery-units/check-channel-metadata.py "$FX0_LINUX" --before-driver /path/to/vadc-before.c
```

Clang and its sanitizer runtimes are required. Run without a tracing wrapper;
use a writable temporary directory with sufficient quota. These fixtures mock
hardware conversion/calibration plumbing and do not execute the full probe,
actual PMIC transactions or physical battery measurements.

[Qualification evidence](../../evidence/2026-11-14-power-telemetry-prerequisite.json)
