# Fx0 maintained kernel gaps

## Installed r4 console warnings

The owner's October 30 photograph matches the installed r4 build5 kernel log.
Text is physically readable, SSH works, and UPower/Sxmo are active. These narrow
observations do not qualify suspend or every subsystem implicated by a warning.
The photograph stays private; selected messages and source findings are recorded
in [console evidence](../evidence/2026-10-30-tty-warning-audit.json).

| Message | Current finding and remaining work |
| --- | --- |
| CPU `missing clock-frequency property` | ARM topology's legacy capacity calculation skips nodes without this property. Do not add guessed frequencies to suppress it; audit CPU capacity/OPP/cpufreq support separately. |
| I2C `tx channel not available` | QUP probe falls back to non-DMA transfers for this error. Touch works through that path; DMA wiring/performance remain to assess. |
| SMSM cannot parse `mboxes` | The common DTS contains a null host entry and the driver tries mailbox then legacy syscon IPC. Capture per-host use/binding before deciding whether any required messaging route is missing. |
| USB supplier device-link failures | USB networking works, but inferred supplier ordering/cycles and suspend behavior remain unqualified. |
| WLED `IRQ ovp not found` | The driver explicitly treats this IRQ as optional and disables automatic string detection. Missing IRQ logging does not mean the backlight probe failed. |
| `no GPU device was found` | GPU support is disabled; the working Sxmo session uses software rendering. Hardware acceleration remains required. |
| MDP5 `errors: 04000000` | The MDP5 register definition identifies bit26 as INTF1 underrun. Observed at startup; investigate display initialization/bandwidth and monitor recurrence. Readable output does not establish a complete fix. |
| L20 `voltage operation not allowed` | Both observed L20 regulators are enabled at the DTS-fixed 3.075 V. USB PHY code first requests 3.3 V, then accepts 3.05–3.3 V through `regulator_set_voltage_triplet()`. This is consistent with a failed preferred request followed by fallback; the emitting callsite is not traced. |
| systemd `bpf-restrict-fs` failure | The running kernel has the BPF LSM active but no `/sys/kernel/btf/vmlinux`. Check kernel BTF/package configuration and capture the verifier failure before claiming causality or a fix. |

## Maintained source target

The initial maintained target is Linux 6.18.59 LTS, pinned to [`1253a6aa5d104312bf0992afacc15220ae35bdf9`](https://github.com/gregkh/linux/commit/1253a6aa5d104312bf0992afacc15220ae35bdf9). The recovered Fx0 UART/USB description compiles against it. A separate binding patch documents the `lg,madai`, `qcom,msm8926`, `qcom,msm8226` tuple.

The original source subset covered DTB compilation only. Full Linux/module builds and schema checks have since succeeded, and the owner observed Linux diagnostic userspace on the inherited framebuffer. USB NCM/ACM diagnostics and initial installed Nura networking now work; reliability qualification remains open. See the newer image/schema records in `evidence/` and the development log; the [earlier DTB record](../evidence/2026-10-29-maintained-device-tree-build.json) retains its original narrower scope.

## Shared SoC support to carry forward

A comparison of the pinned MSM8226 development tree with the LTS tree identifies missing WCNSS descriptions in the latter: the reserved region, SMP2P edge, and Pronto remote-processor hierarchy, including Wi-Fi and Bluetooth child nodes. Sources: [development SoC tree](https://github.com/msm8226-mainline/linux/blob/57a693c8bfc6ba8dd9f737b10b8fff2c6d3484c8/arch/arm/boot/dts/qcom/qcom-msm8226.dtsi) and [LTS SoC tree](https://github.com/gregkh/linux/blob/1253a6aa5d104312bf0992afacc15220ae35bdf9/arch/arm/boot/dts/qcom/qcom-msm8226.dtsi).

Recover the original wireless commits and their driver prerequisites, compare them with current upstream support, and port only the necessary pieces. Validate reserved memory, firmware lookup, supplies, interrupts, and board wiring against the actual Fx0 before enabling the remote processor. A board DTS that merely compiles does not close this gap.

## Camera infrastructure assessment

The LTS [CAMSS driver](https://github.com/gregkh/linux/blob/1253a6aa5d104312bf0992afacc15220ae35bdf9/drivers/media/platform/qcom/camss/camss.c) has an MSM8916 compatible match but no `qcom,msm8226-camss` match. The SoC description includes CCI, which does not establish a working complete camera/ISP pipeline.

Inspect the actual MSM8926 camera hardware, CSI/ISP blocks, sensor models, and downstream drivers. Determine whether existing CAMSS support can be extended or other infrastructure is required. Sensor enumeration and a generic camera application cannot substitute for this driver work. Both cameras, video capture, and verified codec hardware remain within the completion goal.

## Board work requiring stock inventory

Storage supplies and pin configuration, panel and touch revision, battery/charger configuration, audio routing, sensors, GNSS/modem firmware, and calibration depend on the actual unit. Preserve the minimal UART/USB candidate until inventory and recovery are established. Do not transplant another board's configuration to make these entries appear enabled.

The [source assessment record](../evidence/2026-10-29-maintained-kernel-gaps.json) distinguishes direct observations from remaining investigations. No hardware support is marked passed by this assessment.

## USB diagnostic findings

The first two images reached diagnostic userspace but exposed no host USB interface. Recovered Fx0 PHY initialization used the downstream value/absolute-address format; the current driver/binding expects offset/value pairs. The stock settings translate to the existing SoC sequence. A separate driver issue uses offset zero as a sentinel, skipping that valid entire sequence; an explicit count fix is prepared and compiled. It remains present in the current upstream file inspected during bringup.

The third image inherits the correct SoC sequence, carries the count fix, describes verified L10/L20 supplies, and selects peripheral mode matching the stock DTS. The framebuffer now reports UDC state, deferred probes and recent USB messages. Those source-only candidates were followed by physical SMEM/extcon fixes and verified NCM/ACM enumeration; see the later findings below. Sustained reconnect/power qualification remains open.

## Recovered wireless patch dependencies

The shared reference branch is still `qcom-msm8226-6.16.y` at `57a693c8bfc6ba8dd9f737b10b8fff2c6d3484c8`. A shallow sparse checkout on Disk B now exposes the original commit history. The following changes are absent from the inspected maintained tree and form a concrete source-recovery starting point:

| Original commit | Author(s) | Purpose |
| --- | --- | --- |
| `2b383aec7100c4a6a418dec2830c0b8e4831be3c` | Matti Lehtimäki | WCN3660A binding compatible |
| `5a913a2171d19ed8f40b2060cfb68ef782cd3e8d` | Matti Lehtimäki | WCN3660A Iris regulator profile selection |
| `79400b6f70016fbd41c9c79a1ff3f6beefca0330` | Matti Lehtimäki | WCN3660A wcn36xx variant selection |
| `a7a188d31f0597f5f667a2c448ea87bbfdf737fa` | Bartosz Dudziak; co-developed by Matti Lehtimäki | MSM8226 WCNSS reserve, SMP2P, remoteproc and wireless children |

The later `bec415715639199854739bb4cc1c8e847a0f9c8b` fixup touches a Sony board only. Do not transplant it into the Fx0. The shared tree also contains an explicitly marked HTC firmware-loader hack; inspect that context before assuming all firmware images load correctly. Preserve the original authors/sign-offs when recovering legitimate commits and keep any new adaptation distinct.

Next, review the complete dependency set against current upstream, validate the live Fx0 carveout and firmware type, extract this unit's firmware privately, and describe its supplies/48 MHz oscillator. A shared compatible name is not sufficient to identify this unit's exact radio variant. Keep remoteproc disabled until those prerequisites pass; compare wireless behavior and schema results on the maintained branch after enabling it. These dependencies have been researched, not enabled on this phone.

## Physical dependency and memory fixes

The Fx0's SMEM is at 0x0fa00000, not the inherited 0x03000000. Stock DT, the firmware pointer and read-only header checks agree. Correcting it permits RPM/clocks to initialize. USB additionally needs the board's PMIC VBUS/extcon wiring, after which NCM/ACM enumeration works.

Preserve the complete stock memory holes: 0x08000000–0x0f500000 and 0x0fa00000–0x0ff00000. Reserving only SMEM and selected remote processors was insufficient under memory pressure. The extra four MiB after SMEM must remain unavailable to the allocator. With the full holes reserved, two 1 GiB reads match; broader memory/thermal/soak testing remains open.

The stock charging code uses the LGE thermistor conversion table and software derating. Generic SMBB normal comparator limits report Overheat near a stock-table estimate of 34 °C. The extended-range flag explicitly requires external voltage/current policy, so enabling that flag alone is not a valid completion. Port and test the actual policy and battery reporting. The first full Sxmo session also exposes missing fuel-gauge telemetry: smbb-bif has no capacity/voltage_now/charge/energy fields; UPower logs NaN percentages and requests a normal power-off. Native BMS support and correct handling of unavailable telemetry are prerequisites for reliable full UI operation. This failure is not evidence of a kernel panic or a measured empty battery.

## Native display IOMMU dependency

Controlled loading on kernel `6.18.59-00016-g9ff315ebc274` establishes that MDP5 removes simpledrm, identifies display hardware v1.1, then fails with `no IOMMU, bailing out`. WLED probes and the panel module loads, but native panel attachment consequently returns -ENODEV. This is a shared SoC/IOMMU dependency; schema success alone did not reveal it. The controlled RAM kernel remains responsive after that failure. Repeated normal Nura starts are independently recorded in persistent journals; their reset cause is still unproven.

The [upstream MSM8974 QSMMU series](https://lore.landau.one/lkml/20260809-msm8974-iommu-upstream-v1-9-87f5cd492560%40oss.qualcomm.com/T/) describes the same DRM_GPUVM requirement, short-descriptor tables, secured global configuration and context restoration. Its dependency is the [ARM32 DMA-domain detach fix](https://lore.landau.one/lkml/20260730-fix-qcom-smmu-v2-3-18e0daf2d836%40oss.qualcomm.com/). Evaluate these with MSM8226-specific prefetch values and clock/power behavior; do not substitute the MSM8974 tuning table. An isolated integration candidate is building, with targeted binding and DTB validation passed. Hardware mapping/scanout and suspend remain unqualified.

Read-only stock inspection now finds split `image/wcnss.mdt` firmware on the original modem filesystem. Its loadable addresses start at 0x0d200000 and fit the reserved 10 MiB region. The retained stock boot log explicitly reports WCN v2.0 / Iris_TSMC_3.0 with a 48 MHz XO. Stock NV is a symlink into persist, so preserve and use calibration rather than substituting a generic NV blob.

There is an unresolved supply-profile mismatch: compiled stock DT and vendor source give IRIS RFA and digital the same supplier, while vendor digital voltage range 1.225–1.8 V can coexist with RFA at 1.3 V. The recovered WCN3660A mainline profile instead fixes digital at 1.8 V. Do not enable that profile unchanged against shared L24. Confirm the physical variant and stock regulator state, then prepare the appropriate shared-driver/binding adaptation. Wireless firmware startup remains untested.

## Touch reset and in-cell scanning

The inspected 6.18.59 transport and mainline at `c339f4010dea8b0d754f84ace70cd1b089878ef8` do not consume the documented reset GPIO. The Fx0 describes active-low GPIO16, with a stock 10 ms reset pulse and 60 ms boot wait. Earlier live deassertion alone did not exercise a reset pulse. The experimental branch now carries Roman Vivchar's [proposed reset support](https://lore.landau.one/lkml/20260912-rmi4-reset-v1-1-4a3fc8856830@protonmail.com/) with original authorship/sign-off, followed by reset assertion during regulator cleanup. Kernel 39 builds, passes targeted checks and boots from RAM on Fx0. Its RMI transport probes the controller and owns GPIO16, deasserted raw high. Gesture capture starts before native DRM takeover to separate reset handling from the display path. Physical gestures, reset/display ordering and suspend/resume remain open.

Current dtschema also exposed a malformed maintainer address in the LTS RMI binding. Carrying the existing upstream `c75afcb4a8e7` metadata correction resolves that validation diagnostic. This is an upstream backport dependency, not a new Fx0 driver contribution.

Stock production code separately enables in-cell scanning through generic-long `EC 29` and `B0 03` panel packets after touch power changes. Its RAM baseline log confirms the notifier sequence. A signed module built against the exact running kernel 35 transmitted those packets successfully, with valid DCS replies at power 0x1c/pixel format 0x77 before the later reset/replay experiment. This is transport evidence, not a physical touch/display pass. That pre-DRM kernel39 capture was later saved as incomplete before image25; a new native capture is open. No permanent panel sequencing change has been claimed from those live experiments.

A separate live kernel-35 diagnostic uses the RMI suspend/reset-handler/resume interfaces around a GPIO pulse and the stock in-cell commands. Controller configuration returns successfully, but subsequent combined panel replay loses DCS replies. fbdev blanking does not perform the intended power cycle while a separate DRM master owns scanout; issuing a real CRTC disable subsequently loses USB and returns to fastboot. Streamed and retained logs are preserved privately. Neither reset-pulse causality nor the shutdown reset cause is established. See the [sanitized experiment record](../evidence/2026-10-29-live-touch-reset-diagnostic.json).

## Camera source and calibration findings

The [camera work record](camera-bringup.md) pins the actual stock IDs and production source wiring. The selected vendor configuration uses CSI3.0 headers and VFE4.0; resource/register similarities to newer CAMSS variants need complete review before reuse. The camera IOMMU has its own contexts, clocks/power and prefetch table. Current mainline match/Makefile inspection and the LTS tree still lack the dedicated pieces identified in the audit. Two diagnostic tools now decode settings and prepare calibration capture, with compile/ABI/negative guards checked. A temporary GPIO reader has since captured every16-bit word address at0x50 three times with matching private copies on two host filesystems. Observed8KiB aliasing does not establish physical capacity/other-bank coverage; calibration integrity and all sensor streaming remain unqualified.


## Display-link isolation instruments

The [timed DSI video-pattern diagnostic](../diagnostics/dsi-video-pattern/README.md)
has now run on native39. Its corrected register map, active preflight and timed
restoration preserve DCS/USB operation; the timed fixed-red visual interval was
not observed and error-worker activity increases. The owner subsequently
confirms returned RGB from the independently allocated framebuffer. Mapping,
DMA and hardware translation checks support that observed scanout. Full runtime
power, default probe, installed-system and reliability acceptance remain open.


Native camera control preparation now exists on the separate
[camera branch](camera-bringup.md#native-cci-and-shared-io-preparation): shared
I/O regulation, CCI enable/clock description and a guarded native read diagnostic.
The camera-DT RAM image now boots; native preflight, a short read and two full
reads match the independent GPIO capture. Shared supply and CCI runtime suspend/
resume succeed for these reads. Sensor streaming, CAMSS and error/system-PM
qualification remain open. See [runtime evidence](../evidence/2026-10-29-camera-native-cci-qualification.json).


On the same native39 boot, a new opaque RGB framebuffer has matching software
mappings/data at12 samples and matching hardware IOMMU translations at3 pages.
DMA0 source/current source, size and stride match it. The corrected timed DSI
pattern helper restores its registers and preserves DCS/USB operation, but no
owner visual response has arrived; error-worker activity rises during the test.
This narrows mapping faults without proving actual fetch or visible pixels.
See [the native39 evidence](../evidence/2026-10-29-native39-display-mapping.json).


The owner subsequently confirms visible native39 RGB and controlled two-contact
input. Display shutdown then reproducibly resets at the final PHY vddio release.
Stock sources show that RPM L8 also supplies the CPU PLL, whose native supply
vote is absent. The display-power branch keeps L8 enabled and moves panel off
commands into disable(). RAM image26 uses the original MSM39 module and the
fixed-order panel; visible RGB returns after a complete CRTC off/on cycle. Three
further cycles complete with MDSS/IOMMU power/control auto and no temporary
supply/PLL helper. Transient MDP error04000000 during repeated enable, system
suspend, reliability and installed-Nura qualification remain open. See
[power-transition evidence](../evidence/2026-10-29-native39-display-power-transitions.json).


## Current native package and startup fault

The exported native r1 APK now boots from RAM with its own signed modules,
USB, RMI probe and owner-confirmed RGB after a five-second display off/on.
Initial MDSS/IOMMU references are still needed for that baseline. They are
released before the cycle, and all four display devices suspend automatically
while off. The installed Nura system has not yet received this package.

Repeated C6 startup without userspace holds remains intermittent. Persistent
per-CPU traces now identify the first DSI version read at unshifted offset0x1f0;
one run enters do_DataAbort immediately afterward. Other runs stop there without
a complete exception report. Added core,MMSS and escape-clock variants do not
eliminate resets. Five runs with a read-only pre-read power snapshot succeed,
including cases with MDP/escape clocks gated. Barrier-only and delay-only
diagnostics are being compared; none is promoted as a final fix. See the
[current evidence](../evidence/2026-10-29-display-start-persistent-trace.json).

Separately, an identity-checked USB bus reset restores lk2nd commands when
software reboot leaves it enumerated but unresponsive. This is a verified host
transport workaround; final reboot/update/recovery reliability remains open.


Isolated write/full barriers and100us delay also fail on repeat or first startup;
none is promoted. A RAM-only ARM fault-value recorder passes its synthetic
encoder and probe-registration checks. Four instrumented starts fail/pass/pass/
fail, with no retained value markers in either failure. The normal error path
may never be reached, or its trace may not survive; real fault arguments remain
unknown. See [recorder limits](../diagnostics/abort-value-trace/README.md).


Native r1 now also boots from the installed eMMC filesystem with its matching
on-disk modules and the temporary initial-power prefix. SSH, native console and
two-contact input are tested; all display controls return to auto and taint is 0.
This permits broader hardware/userspace work while the first-read startup defect
remains unresolved. It is not evidence that the bounded C6 candidates or the
userspace workaround are ready as an upstream kernel fix.
