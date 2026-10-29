# Fx0 maintained kernel gaps

## Maintained source target

The initial maintained target is Linux 6.18.59 LTS, pinned to [`1253a6aa5d104312bf0992afacc15220ae35bdf9`](https://github.com/gregkh/linux/commit/1253a6aa5d104312bf0992afacc15220ae35bdf9). The recovered Fx0 UART/USB description compiles against it. A separate binding patch documents the `lg,madai`, `qcom,msm8926`, `qcom,msm8226` tuple.

The source subset and patches are sufficient for the recorded DTB checks, not a complete kernel build or a verified boot image. Full binding/schema validation is pending because dtschema is not installed. The [build evidence](../evidence/2026-10-29-maintained-device-tree-build.json) records this scope.

## Shared SoC support to carry forward

A comparison of the pinned MSM8226 development tree with the LTS tree identifies missing WCNSS descriptions in the latter: the reserved region, SMP2P edge, and Pronto remote-processor hierarchy, including Wi-Fi and Bluetooth child nodes. Sources: [development SoC tree](https://github.com/msm8226-mainline/linux/blob/57a693c8bfc6ba8dd9f737b10b8fff2c6d3484c8/arch/arm/boot/dts/qcom/qcom-msm8226.dtsi) and [LTS SoC tree](https://github.com/gregkh/linux/blob/1253a6aa5d104312bf0992afacc15220ae35bdf9/arch/arm/boot/dts/qcom/qcom-msm8226.dtsi).

Recover the original wireless commits and their driver prerequisites, compare them with current upstream support, and port only the necessary pieces. Validate reserved memory, firmware lookup, supplies, interrupts, and board wiring against the actual Fx0 before enabling the remote processor. A board DTS that merely compiles does not close this gap.

## Camera infrastructure assessment

The LTS [CAMSS driver](https://github.com/gregkh/linux/blob/1253a6aa5d104312bf0992afacc15220ae35bdf9/drivers/media/platform/qcom/camss/camss.c) has an MSM8916 compatible match but no `qcom,msm8226-camss` match. The SoC description includes CCI, which does not establish a working complete camera/ISP pipeline.

Inspect the actual MSM8926 camera hardware, CSI/ISP blocks, sensor models, and downstream drivers. Determine whether existing CAMSS support can be extended or other infrastructure is required. Sensor enumeration and a generic camera application cannot substitute for this driver work. Both cameras, video capture, and verified codec hardware remain within the completion goal.

## Board work requiring stock inventory

Storage supplies and pin configuration, panel and touch revision, battery/charger configuration, audio routing, sensors, GNSS/modem firmware, and calibration depend on the actual unit. Preserve the minimal UART/USB candidate until inventory and recovery are established. Do not transplant another board's configuration to make these entries appear enabled.

The [source assessment record](../evidence/2026-10-29-maintained-kernel-gaps.json) distinguishes direct observations from remaining investigations. No hardware support is marked passed by this assessment.
