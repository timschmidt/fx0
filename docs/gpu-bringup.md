# Fx0 GPU acceleration

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

## First accelerated rendering

`integration/fx0-gpu` adds four schema-clean commits: the binding for
`qcom,msm8226-gpu-iommu` with an optional `tbu` clock, an `msm8226_gpu_cfg` with
stock BFB values and halt, the SoC GPU IOMMU node, and the Fx0 enable. The node
follows the MSM8974 series' GPU IOMMU (`OXILI_GFX3D_CLK` as `tbu`, two
non-secure contexts, IRQ 241).

A RAM boot of that kernel with the installed r6 initramfs gives the following
results:

- The GPU joins its IOMMU group and reports **3.0.5.18 (A305B)** on the MSM8926.
- `eglinfo` shows **freedreno FD305, OpenGL ES 3.0 / GL 3.1, Mesa 26.1.6**.
- `kmscube` renders **299 frames in 4.98 s at 60.00 fps**, locked to vsync on
  the DSI panel, with no IOMMU faults, hangs or underruns.

Firmware fails to load at the first bind from the initramfs, because the root
filesystem is not mounted yet, but loads on first use: PM4 330043, PFP 330020.
GPU devfreq does not initialise. The owner has not yet confirmed the picture
physically. See [GPU evidence](../evidence/2026-10-30-gpu-freedreno.json).

## Work required

1. Done in RAM: GPU IOMMU, probe, firmware and `kmscube`. Physical
   confirmation by the owner is pending.
2. Done in installed r7: devfreq (the configuration lacked `CONFIG_PM_DEVFREQ`)
   now runs simple-ondemand at 19–450 MHz. Next, run a compositor (Sway/Phosh)
   on Freedreno instead of the Sxmo wrapper's Pixman, and measure correctness,
   memory and stability.
3. Qualify GPU power collapse, runtime PM and resume together with the display
   IOMMU, then package it and remove the obsolete carveout parameters.


