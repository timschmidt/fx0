# Fx0 battery and charging bringup

The owner identifies this unit's pack as the original LG Fx0 battery.
[LG's supplied manual](https://gscs-b2c.lge.com/open/downloadFile?fileId=KROWM000605066.pdf)
names the pack LGL25UAA, and
[KDDI's product specification](https://news.kddi.com/kddi/corporate/english/newsrelease/2014/12/23/besshi844.html)
provides the advertised 2,370 mAh capacity. Neither source establishes a measured
present-day capacity or the label's maximum charging voltage.

The preserved stock boot log selects `TOCAD_MADAI_2440mAh` for battery ID 5.
The pinned vendor source selects that profile through `qpnp-bms.c`; its
`bms-batterydata-LGE_BL_59UH_2440mAh_TOCAD_MADAI_Final.c` contains a nominal
2440 mAh parameter and a temperature-dependent measured full-charge table
(2301 mAh at 25°C). Those characterization values are distinct from the marketed
capacity. Do not choose an unrelated BL-59UH profile based on the filename.
The board DTS uses 4.35 V maximum, 3.40 V cutoff and effective sense resistances
of 10.8 mΩ, or 11.4 mΩ while charging. The separate IADC node also uses 10.8 mΩ.
These are source references to validate, not proof of an aged pack's accuracy.

The original stock kernel has now been booted from RAM with its unchanged QCDT
and a small diagnostic initramfs, without mounting disk filesystems. Its gauge
reports Charging/Good, 31°C and 76% during the three-sample comparison. This is a
stock baseline, not a native capacity result or a factory restoration rehearsal.
The stock kernel initializes volatile PMIC/gauge state, so comparisons across
that boot must account for initialization effects.

Native coherent output capture now passes: two three-sample sets show changing
latched counters, matching repeated reads and independently verified release of
the output hold. The companion sense configuration differs from stock, and trim
values also change. Readback equality between conversion-ADC and companion trim
banks does not establish that both addresses accept protected writes. Calibration
ownership and the supported write path were unresolved at that diagnostic stage;
the native prototype below implements provider-owned writes at the primary IADC.

Three focused commits on
[integration/fx0-bms](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-bms)
add IADC raw calibration references and calibrated VADC battery/thermistor voltage
reads. Each passes a W=1 ARM module build and a brief RAM-only hardware test;
the installed r4 package is unchanged. The initial VADC patch retained
microvolts for absolute calibration and millivolts for ratiometric calibration.
The measured thermistor input is 660–661 mV, approximately 31.3°C under the vendor
LG table; physical temperature accuracy is not yet qualified. A generic ADC
thermal consumer must use lookup values in the actual input units.
The follow-up deec41b85 corrects the two new battery inputs to standard IIO
millivolts, using a fractional value for absolute calibration. A consumer scaling
by 1000 retains microvolt precision. Its 84 actual-callback/core-conversion cases
and RAM reads pass; legacy channels retain their previous interfaces. Firmware
consumer lookup was not exercised by those diagnostics; the native prototype
below now verifies it. External voltage accuracy remains unqualified.

Stock uses extended hardware comparator limits plus the LG software temperature
policy. At a nominal 1.8 V reference, the LG table maps the normal 35%/70% limits
to approximately 34.3°C/-5.4°C and extended 25%/80% to 62.8°C/-15.9°C. These are
model estimates, not measured trip points. Stock software stops below -10°C or
above 55°C and also applies current reduction, voltage-dependent stopping and
hysteresis. The madai configuration selects its V1_8 variant, including a 52°C
transition. Enabling extended hardware range alone would omit those protections;
native comparator settings remain conservative until the software policy and
sensor-fault/wake behavior are implemented and tested.

The subsequent configuration experiment proves the stock protected trim-write
path at 0x3600. An attempted write at the apparent 0x3800 mirror fails, and the
original controls/trim are restored exactly. Sense-only and trim-only phases
separate their effects. A 2 ms conversion-delay experiment does not resolve the
observed near-zero manual current and is not promoted. Under a configured
500 mA USB supply, that near-zero battery current can reflect the supply powering
the system; an actual input-budget/load transition is needed to test response.

With USB temporarily limited to 100 mA and a bounded single-core load, battery
voltage drops about 30 mV, manual IADC reports roughly -0.20 to -0.24 A and BMS
VSENSE/counter increments respond with the opposite sign. The input limit returns
to 500 mA afterward. Provisional BMS conversion and resistor-adjusted manual IADC
agree around -0.2 A during that discharge window. They share calibration and sense
hardware, so agreement is not external accuracy qualification. Charging/idle
accuracy, compensation and capacity remain open.

The stock counter restart after sense reconfiguration is also tested explicitly.
Counters stay flat through the attempted restart with optimized regmap updates,
despite zero control readback. Forced assertion/deassertion writes produce a new
epoch with both counters advancing under load. Source inspection and a regression
model identify how optimized deassertion can be skipped; the cause of the initial
stopped counter state is not established. The 238 actual-helper cases include read-zero command
behavior, rollback and bus faults. Counter contents are intentionally reset only
in that explicit configuration-epoch test; they cannot be restored. Routine
snapshot reads never reset them. See [calibration/epoch evidence](../evidence/2026-10-30-bms-calibration-epoch.json).

## Initial native measurement prototype

The later stock charge-only comparison now has two successful RAM captures.
The factory `bms/charge` API clears only charge enable, leaving forced-battery
mode off; register readbacks verify `0x80 → 0x00 → 0x80`. BATFET opens during
the stop, manual IADC becomes zero, and background readings settle within about
3 mA of zero. Both stock counter properties reset. Charging restarts, and health
remains Good at approximately 31°C. Charger voltage/current/thermal limits and
disk filesystems are untouched by the diagnostic script.

Targeted stock debug output confirms a Charging-to-Full transition, IADC
calibration/trim writes and the EOC path in `read_soc_params_raw()` shortly after
stopping. In the pinned vendor source, Full sets `done_charging`, whose EOC path
clears both counters; SOC recalculation also recalibrates while cached BATFET is
open. These runtime messages support that source interpretation without proving
every call relationship or exact source/binary identity. A stock counter reset
is therefore not evidence that native should reset on every charging stop.
The next controlled native experiment isolates recalibration while retaining
the relative counter. Absolute current accuracy still requires independent
measurement; the owner has no current fixture or oscilloscope available.
See [stock transition evidence](../evidence/2026-10-30-stock-charge-only.json) and
the [reproducible diagnostic](../diagnostics/pm8226-bms-stock-stop/README.md).

Candidate
[`35743f1984fc7b9863224856dca0aa148e832be5`](https://github.com/timschmidt/fx0-linux/commit/35743f1984fc7b9863224856dca0aa148e832be5)
adds provider-owned calibration, a binding, the actual non-VM BMS driver and Fx0
firmware references as four focused commits. It is RAM-tested with the installed
r4 kernel/initramfs and unsigned candidate modules; test taint is 12288. The
installed package and boot files are unchanged. This is experimental source,
not a promoted package or a submission-ready gauge.

The driver registers `pm8226-bms`, reads voltage/current and a relative charge
counter through actual firmware-resolved IIO channels, and uses managed supplier
links. Unbinding the IADC provider removes the consumer before releasing provider
resources; rebinding recovers the consumer and starts a new counter epoch. A
five-minute periodic calibration runs successfully. Optional temperature is
implemented but not wired or physically tested; capacity and remaining charge
are deliberately absent. UPower remains finite with no critical warning and
continues to treat this measurement-only interface as incomplete.

The host checks cover 20,033 arithmetic cases, 70 actual BMS I/O-helper fault
cases, 34 actual provider calibration/rollback cases and 27 reference/cache
cases under ASan/UBSan. ARM LLVM22 W=1 module builds, checkpatch and targeted
binding/DTB checks pass. These do not replace full upstream binding checks,
subsystem ABI review or physical accuracy measurements.

**Unresolved transition discrepancy:** when the charger reports
Discharging/Overheat under the unchanged conservative comparator, manual IADC
current becomes zero while BMS current
remains about +155 mA and the relative counter continues accumulating that
suspect value. Recalibration does not resolve it. This observation does not
establish whether the cause is stale sampling, analog coupling, BATFET state or
another missing configuration/transition requirement.

A subsequent bounded 100 mA input-budget/single-core load produces BMS current
about -190 to -222 mA versus manual IADC about -185 to -212 mA. The counter-derived
average is -208.6 mA. Restoring 500 mA input returns manual current to zero and
BMS current to about -0.5 to -1.0 mA. No kernel warning occurs, and no charger
voltage/current/temperature threshold changes. This qualifies discharge response
and exposes a charging-stop defect; it does not qualify general current accuracy
or reliable accumulated charge. Keep this driver outside the installed package
until the discrepancy is understood and the affected transition tests pass.

Next, record BATFET/charger state alongside BMS sample freshness around an actual
charging stop, compare the stock driver's behavior under matching conditions,
and determine the required PM8226 sampling/transition handling. Preserve raw
evidence privately and reject suspect gauge data during further development.
Complete pack identification, temperature/fault handling, compensation and
capacity work before claiming fuel-gauge or charging acceptance. See the
[native prototype evidence](../evidence/2026-10-30-native-bms-prototype.json).

## Distinct current sources and rejected BATFET IRQ experiment

Candidate
[`31061619c6a1ec6579b07ecbd3303614899d116b`](https://github.com/timschmidt/fx0-linux/commit/31061619c6a1ec6579b07ecbd3303614899d116b)
reports the live IADC sample as `current_now` and the BMS background VSENSE
measurement as `current_avg`. Errors are independent; a failed BMS snapshot
does not overwrite a successful IADC reading. This makes the discrepancy
observable without silently choosing one source as electrical ground truth.
Both values use µA with positive charging. Neither is independently validated
with current-measurement equipment.

The exact unsigned module passes a RAM bind and bounded 500/100/500 mA response
test. In the initial USB-idle window, live/manual current becomes 0 while the BMS
average remains about 212 mA and its counter accumulates. Under 100 mA input and a
bounded CPU load, both readings become negative, about 0.2 A discharge. Returning
to 500 mA yields live 0 and background about 1.5–2.1 mA. This is functional response
evidence, not proof of absolute accuracy or trustworthy whole-cycle integration.
Thirty-three actual-getter cases verify routing, independent errors, status
fallback and caching under ASan/UBSan. W=1 ARM/checkpatch and UPower checks pass;
capacity remains unavailable and the installed signed r4 package is unchanged.

A separate attempted guard used the instantaneous BATFET status and a both-edge
IRQ. Its test exceeded the 100-events/second guard and the driver was unloaded.
A controlled variant with automatic polling disabled and no IRQ-triggered refresh
still generates 13,616 interrupts in 2.0025 seconds (about 6,799/second), with edge
mode and both polarities read back enabled. No IADC current-debug entries or
external calibration commits occur in the next three seconds. Thus IRQ refresh
and periodic BMS sampling are not necessary causes of that observed flood; its
electrical/controller cause is unresolved. The guard and IRQ changes are removed
from the integration candidate. A single raw BATFET sample cannot be treated as
a proven stable isolation indication in these conditions.

The [failed experiment patches](../experiments/pm8226-batfet-irq/README.md) retain
the exact tested source. Initial stock comparison captures showed charging with
BATFET reported closed, while native USB-idle captures reported it open; those
different operating states alone did not establish causality. The subsequent
stock charge-only test above adds a controlled open-BATFET comparison and runtime
calibration/reset messages. Continue by isolating native recalibration effects,
pack temperature/profile integration and independent electrical measurements
when available.
Keep the background counter discrepancy, absolute accuracy and final gauge policy
open. See [current observation evidence](../evidence/2026-10-30-bms-current-observations.json).

The provider-only recalibration test now separates that operation from stock's
Full-triggered counter reset. With USB input temporarily set to 500 mA, live
IADC remains zero while background current stays around -220 mA and the relative
counter continues integrating discharge. A single successful calibration does
not correct the discrepancy. The original 100 mA input limit is restored and
normal installed r4 returns. A subsequent fresh/cached-reference comparison runs
both variants with a final unchanged-driver reload control. After the first
reprobe, both variants settle within about 7.3 mA of zero at 500 mA input; the
unchanged driver also behaves near zero. The large frozen-current symptom is
not reproduced by those arms, so cached references are not established as a fix.
Capture the first-probe transition before reinitialization and examine initial
sense/calibration/counter ordering. The diagnostic source remains separate from
integration; see [reference-cache evidence](../evidence/2026-10-30-bms-reference-cache.json).
See [recalibration-only evidence](../evidence/2026-10-30-bms-recalibration-only.json).

## Native battery temperature

**Known integration limitation:** the native 35%/70% BTC comparator window
produces hardware HOT at a stock-reported 31.6°C on this unit. The original
stock kernel reproduces it when temporarily given the same tighter settings;
restoring stock's 25%/80% window clears HOT and charging resumes. This is not a
native VADC-specific conversion failure. Stock combines that wider window with
LG software temperature policy. Native must implement that policy, sensor-fault
handling, charging inhibition, hysteresis and suspend/wake protection before
adopting the wider window. Successful measurement conversion alone does not
qualify charging integration.

| Original stock-kernel setting | Reported temperature | Raw comparator | Charging current, normalized positive |
| --- | --- | --- | --- |
| Stock `0x82`, 25%/80% | 31.6°C | Normal `0x80` | About 76–114 mA |
| Temporarily tightened `0x81`, 35%/70% | 31.6°C | HOT `0x40` by 2 seconds | About zero |
| Restored stock `0x82` | 31.6–32.1°C | Normal `0x80` | About 150 mA by 5 seconds |

Stock's supply `health` remains Good during the tightened-window hardware trip;
the matching source reports LG software-policy health. Raw status is therefore
necessary for this comparison. The DT's `btc-disabled` property alone also does
not establish runtime disablement: the factory-pseudo-battery build path enables
the comparator in normal mode, consistent with observed `0x82`.
See [stock-window evidence](../evidence/2026-10-30-stock-BTC-window.json).

Earlier isolation confirms that an isolated thermistor read can expose the
native trip with no BMS/thermal consumer. Reference mode is already forced
`0xc0`; requesting it again does not help. Switching the mux back to battery
voltage also does not clear the trip. Five minutes with the backlight off changes
the inferred temperature by less than 1°C, insufficient to rule out hysteresis.
No reference-mode or VADC mux cleanup fix is justified by these experiments.

The experimental
[temperature branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-battery-temperature)
adds a binding allowance for the generic ADC thermal driver's existing IIO
temperature output, plus a GPL-2.0-only board include containing the attributed
LG thermistor lookup data. It exposes standard millivolt VADC input as thermal
and IIO milliCelsius, and as the BMS optional deciCelsius `temp` property.
It does not select a capacity profile or change charger temperature limits.

The exact RAM image reports approximately 32.6–32.7°C consistently across all
three interfaces. Three temperature-supplier unbind/rebind cycles remove the BMS
before its provider disappears and restore it after explicit consumer reprobe.
Automatic consumer rebinding is not claimed. The interpolation check executes
the actual generic-driver function for 1,803 inputs under sanitizers and verifies
all 83 LG table entries/units. The BMS getter check now passes 37 cases including
negative temperature and independent temperature errors. The module and DTB
build, modified binding and targeted compiled-DTB schemas pass.

Installed r4 remains unchanged and is restored with taint 0 and active Sxmo.
The next package will need the generic ADC thermal module/configuration after
qualification. Generic interpolation clamps out-of-table input to endpoints;
open/short discrimination, independent accuracy, software thermal policy,
hysteresis, charging inhibition and suspend/wake protection remain open.
See [temperature evidence](../evidence/2026-10-30-battery-temperature.json) and
the [host check](../diagnostics/battery-thermistor/README.md).

## Standard charge inhibition

The separate [charge-control branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-charge-control)
adds `auto` and `inhibit-charge` through the standard `charge_behaviour` API.
It changes only charge enable, preserving USB power, forced-battery mode and
all other control bits. This supplies an actuator for future temperature policy;
it does not implement that policy or widen hardware protection limits.

A full candidate ARM kernel boots from RAM with the original r4 DTB/initramfs.
The running GNU build ID matches, and all 14,228 shared module symbol CRCs match
the prepared module build. Three inhibit/resume cycles pass: USB stays online,
status becomes Not charging, charge enable clears, and live IADC falls from
249 mA to 18.4 mA before returning to 230–290 mA on resumption. Independent
electrical accuracy and zero-current qualification remain open. Unsupported
modes are rejected without changing control. Cleanup restores the observed
initial 100 mA input budget; reset behavior must be measured for each boot.

The actual helper/callback suite passes 1,051 sanitizer cases, including all
initial control bytes and register errors. The full LLVM22 W=1 build and strict
checkpatch pass. The patch applies to pinned current upstream SMBB source; a
full current-upstream build is still required. Installed r4 remains unchanged
and returns with taint zero, native framebuffer and active UPower/Sxmo. See
[control evidence](../evidence/2026-10-30-smbb-charge-control.json) and
[reproduction instructions](../diagnostics/smbb-charge-control/README.md).

The pinned upstream [Charger Manager](https://github.com/torvalds/linux/blob/d89e1d186ec9271bf78e62771779e9fc03bf0fc3/drivers/power/supply/charger-manager.c)
already has temperature limits, hysteresis and suspend alarm monitoring, but
cannot be adopted unchanged. Its thermal-check function returns success when
temperature acquisition fails; its enable path controls charger regulators,
not a power-supply `charge_behaviour` actuator. Initialization also permits
thermal setup failure to disable measurement. A suitable native policy must
inhibit charging until a valid sample, keep sensor/actuator failures inhibited,
preserve user inhibition independently of thermal inhibition, verify hardware
readback, and cover supplier removal, boot, shutdown and suspend. A periodic
userspace read loop alone does not satisfy those requirements. No replacement
policy or wider comparator configuration has yet been enabled.

## Implementation sequence

1. Preserve exact current boot files, modules, package, configurations, raw boot
   and GPT fingerprints on both host filesystems. Retain stock charger/BMS
   observations and the exact vendor revision. The pre-r4 checkpoint preserves
   installed r3. Factory restoration remains a separate gate before repartition.
2. Correct signed subtraction and current units in the existing IADC driver.
   The actual function regression and a RAM-only module test pass; a signed r4
   package has built and installed. The exact packaged module, native taint 0, both channel readings and normal
   package/boot behavior now pass; physical accuracy remains open.
3. Observe BMS1 identity and a bounded register list without writes. PM8226 uses
   the non-VM BMS1 at 0x4000 (type 0x0d/subtype 1), with an IADC companion at 0x3800
   and a separate conversion ADC at 0x3600. Do not claim PM8916 VM compatibility.
   The initial read-only diagnostic deliberately does not latch output. A later
   focused diagnostic validates coherent output hold/release without counter
   resets or charger writes; neither diagnostic establishes state of charge.
4. Implement a focused native BMS driver and binding after comparing those
   observations with the stock implementation. Use regmap and IIO consumers,
   check the peripheral revision, and handle absent/invalid calibration with
   errors. Serialize coherent snapshots using the documented output-hold bit;
   restore the previous control state even when a read fails. Do not clear
   coulomb counters merely to obtain telemetry.
   Keep protected trim writes inside the IADC provider, serialized with conversions
   and its software calibration cache. The BMS mirror is not a working write path.
   Test supplier removal and consumer lifetime before freezing the interface.
5. Validate signed 36-bit counter decoding, rollover and charge conversion with
   independent vectors and stock observations. Check raw battery voltage against
   calibrated VADC references, and establish the current direction relative to
   actual charging/discharging. Audit the board's effective resistance and vendor
   compensation rather than keeping the mainline external-channel 10 mΩ default.
   Invert the measured BMS VSENSE/counter direction to the native positive-charging
   convention, and keep CURRENT_NOW in µA and relative CHARGE_COUNTER in µAh.
   Check 64-bit intermediate overflow, invalid gain and ambiguous counter rollover.
   If configuration requires a counter restart, use forced command writes and
   verify subsequent counting; zero command-register readback is insufficient.
6. Expose real voltage, current, temperature and counter data through power_supply.
   Add capacity estimation only with an identified profile, valid initial OCV,
   appropriate rest/temperature handling and counter integration. Distinguish
   nominal capacity, learned usable capacity and remaining charge. Missing data
   must not become a fabricated 0% or 100% reading. Test partially initialized
   attributes and ENODATA through UPower before enabling a new battery interface;
   attribute presence alone does not establish a valid measurement. The existing UPower incomplete-
   interface fix remains useful while telemetry is incomplete.
   The upstream battery binding reserves fixed battery nodes for hardware whose
   battery cannot be replaced by another type. The Fx0 has a removable pack:
   identify its profile at runtime or through a suitable firmware handoff, rather
   than placing an unconditional stock-pack model in the upstream board DTS.
7. Convert the actual LG thermistor table and stock temperature policy into a
   maintained implementation. Compare readings through warming/cooling and check
   fault/open/short behavior. Qualify charger temperature boundaries, hysteresis,
   derating and stop/restart behavior before changing comparator settings.
   Preserve effective hardware and software protection throughout the work.
8. Implement USB input-current negotiation. The current development link is
   configured for 500 mA, and earlier boots were observed with a 100 mA request; a later warm boot
   retained 500 mA. Do not assume a reset supplies either value.
   A prior supervised 500 mA runtime request produced Charging/Good;
   that observation is not thermal or battery-current qualification. Follow actual
   configured/suspended/disconnected USB state and the available source budget;
   an unconditional boot-time 500 mA setting is insufficient.
9. Compare stock and native telemetry at several charge levels, on/off USB and
   under known idle/display loads. Verify trends and counter integration, then
   compare absolute voltage/current with appropriate measurement equipment.
   Test low-battery handling, charging completion, unplug/replug, reboot,
   suspend/resume, and charger-only startup. Record failures and exact versions.
10. Package the final driver, profile and policy; validate power_supply/UPower/UI
    behavior together and repeat the affected reliability tests. Prepare focused
    IIO, power-supply, DT and Nura series with reviewed provenance, tests and
    maintainer routing. Submissions and personal DCO certification remain open.

The first IADC correction and the recovery rehearsal are recorded separately in
[evidence](../evidence/2026-10-29-iadc-current-conversion.json) and
[recovery results](../evidence/2026-10-29-native-recovery-rehearsal.json).
Later [coherent/stock comparison](../evidence/2026-10-30-bms-coherent-stock-comparison.json)
and [ADC reference evidence](../evidence/2026-10-30-battery-adc-references.json) record
the current development results. The signed installed r4 kernel is restored after
the unsigned module tests; normal eMMC boot, taint 0, native framebuffer and active
Sxmo/UPower pass. Native fuel-gauge and charging qualification remain unfinished.
