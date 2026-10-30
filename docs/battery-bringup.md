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
   The read-only diagnostic deliberately does not latch output: multi-byte
   counter data is not an atomic measurement and cannot establish state of charge.
4. Implement a focused native BMS driver and binding after comparing those
   observations with the stock implementation. Use regmap and IIO consumers,
   check the peripheral revision, and handle absent/invalid calibration with
   errors. Serialize coherent snapshots using the documented output-hold bit;
   restore the previous control state even when a read fails. Do not clear
   coulomb counters merely to obtain telemetry.
5. Validate signed 36-bit counter decoding, rollover and charge conversion with
   independent vectors and stock observations. Check raw battery voltage against
   calibrated VADC references, and establish the current direction relative to
   actual charging/discharging. Audit the board's effective resistance and vendor
   compensation rather than keeping the mainline external-channel 10 mΩ default.
6. Expose real voltage, current, temperature and counter data through power_supply.
   Add capacity estimation only with an identified profile, valid initial OCV,
   appropriate rest/temperature handling and counter integration. Distinguish
   nominal capacity, learned usable capacity and remaining charge. Missing data
   must not become a fabricated 0% or 100% reading. Test partially initialized
   attributes and ENODATA through UPower before enabling a new battery interface;
   attribute presence alone does not establish a valid measurement. The existing UPower incomplete-
   interface fix remains useful while telemetry is incomplete.
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
