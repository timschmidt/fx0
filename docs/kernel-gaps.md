# Fx0 maintained kernel gaps

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

The stock charging code uses the LGE thermistor conversion table and software derating. Generic SMBB normal comparator limits report Overheat near a stock-table estimate of 34 °C. The extended-range flag explicitly requires external voltage/current policy, so enabling that flag alone is not a valid completion. Port and test the actual policy and battery reporting.

## Native display IOMMU dependency

Controlled loading on kernel `6.18.59-00016-g9ff315ebc274` establishes that MDP5 removes simpledrm, identifies display hardware v1.1, then fails with `no IOMMU, bailing out`. WLED probes and the panel module loads, but native panel attachment consequently returns -ENODEV. This is a shared SoC/IOMMU dependency; schema success alone did not reveal it. The controlled RAM kernel remains responsive after that failure. Repeated normal Nura starts are independently recorded in persistent journals; their reset cause is still unproven.

The [upstream MSM8974 QSMMU series](https://lore.landau.one/lkml/20260809-msm8974-iommu-upstream-v1-9-87f5cd492560%40oss.qualcomm.com/T/) describes the same DRM_GPUVM requirement, short-descriptor tables, secured global configuration and context restoration. Its dependency is the [ARM32 DMA-domain detach fix](https://lore.landau.one/lkml/20260730-fix-qcom-smmu-v2-3-18e0daf2d836%40oss.qualcomm.com/). Evaluate these with MSM8226-specific prefetch values and clock/power behavior; do not substitute the MSM8974 tuning table. An isolated integration candidate is building, with targeted binding and DTB validation passed. Hardware mapping/scanout and suspend remain unqualified.

Read-only stock inspection now finds split `image/wcnss.mdt` firmware on the original modem filesystem. Its loadable addresses start at 0x0d200000 and fit the reserved 10 MiB region. The retained stock boot log explicitly reports WCN v2.0 / Iris_TSMC_3.0 with a 48 MHz XO. Stock NV is a symlink into persist, so preserve and use calibration rather than substituting a generic NV blob.

There is an unresolved supply-profile mismatch: compiled stock DT and vendor source give IRIS RFA and digital the same supplier, while vendor digital voltage range 1.225–1.8 V can coexist with RFA at 1.3 V. The recovered WCN3660A mainline profile instead fixes digital at 1.8 V. Do not enable that profile unchanged against shared L24. Confirm the physical variant and stock regulator state, then prepare the appropriate shared-driver/binding adaptation. Wireless firmware startup remains untested.
