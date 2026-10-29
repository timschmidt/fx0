# Fx0 maintained kernel gaps

## Maintained source target

The initial maintained target is Linux 6.18.59 LTS, pinned to [`1253a6aa5d104312bf0992afacc15220ae35bdf9`](https://github.com/gregkh/linux/commit/1253a6aa5d104312bf0992afacc15220ae35bdf9). The recovered Fx0 UART/USB description compiles against it. A separate binding patch documents the `lg,madai`, `qcom,msm8926`, `qcom,msm8226` tuple.

The original source subset covered DTB compilation only. Full Linux/module builds and schema checks have since succeeded, and the owner observed Linux diagnostic userspace on the inherited framebuffer. USB diagnostic enumeration remains unresolved. See the newer image/schema records in `evidence/` and the development log; the [earlier DTB record](../evidence/2026-10-29-maintained-device-tree-build.json) retains its original narrower scope.

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

The third image inherits the correct SoC sequence, carries the count fix, describes verified L10/L20 supplies, and selects peripheral mode matching the stock DTS. The framebuffer now reports UDC state, deferred probes and recent USB messages. Physical enumeration is still pending. Do not treat these source fixes as proof that the actual USB failure is solved.
