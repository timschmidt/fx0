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

## Native measurement prototype

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

**Unresolved transition failure:** after charging stops under the unchanged
conservative comparator, manual IADC current becomes zero while BMS current
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
