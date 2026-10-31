# Fx0 GPU acceleration assessment

The plan's [phase 3](bringup-plan.md#phase-3-make-the-local-interface-usable)
requires Freedreno acceleration with a measured renderer, correctness, memory
use and stability. The installed session uses software rendering (Pixman), and
the GPU is disabled. This is a source-only assessment.

## What exists

| Piece | State |
| --- | --- |
| GPU node | Mainline `qcom-msm8226.dtsi` has `gpu@fdb00000` (`qcom,adreno-305.18`) with Oxili clocks, the OXILICX GDSC and a 450/320 MHz OPP table. It is `disabled` and has **no `iommus`** |
| Firmware | A305.18 (chip id 0x03000512) uses `a330_pm4.fw`/`a330_pfp.fw`; Nura's `firmware-qcom-adreno-a330` already installs both |
| Carveout fallback | **Gone in 6.18**: `msm.allow_vram_carveout` no longer exists, and DRM_GPUVM needs an IOMMU. The installed command line still passes `msm.allow_vram_carveout=1 msm.vram=192m`; both are obsolete and should be removed during packaging |
| Display IOMMU | Done earlier: secured MDP IOMMU contexts let native DRM scan out (see [kernel gaps](kernel-gaps.md)). It is the template for the GPU |

## Stock GPU IOMMU

Vendor `msm-iommu-v1.dtsi` and `msm8226-iommu.dtsi` describe `kgsl_iommu` at
0xfdb10000 (`qcom,msm-smmu-v1`, IRQ 38). It is supplied by the Oxili CX GDSC
with Oxili GX as alternate supply, and uses `qcom,iommu-enable-halt`, an
alternate core clock and MSM8226-specific BFB prefetch register/value pairs.

## Work required

1. Describe the GPU IOMMU in the MSM8226 SoC DT using the mainline
   `qcom_iommu` (msm-iommu-v1) binding. Map the GPU user/privileged contexts,
   supplies, clocks and BFB values as for the MDP IOMMU, and attach `iommus` to
   the GPU node. Keep this SoC change separate from the Fx0 board enable.
2. Enable the GPU on the Fx0, RAM-test probe, firmware load and context faults,
   then measure with `kmscube` and `glmark2-es2` (renderer string, correctness,
   frame rate, memory) and run a compositor (Sway/Phosh) on Freedreno.
3. Qualify GPU power collapse, runtime PM and resume together with the display
   IOMMU, then package it and remove the obsolete carveout parameters.

The GPU IOMMU description is the blocking piece. The rest reuses existing
mainline drivers.
