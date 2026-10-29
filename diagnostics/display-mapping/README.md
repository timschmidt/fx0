# Fx0 active-display mapping diagnostics

These temporary GPL-2.0-only modules inspect a specific pinned RGB diagnostic
framebuffer. They are development instruments, not upstream driver changes or
general arbitrary-memory tools. Both build with W=1 and pass checkpatch against
kernel 39. Their published sources have run on that kernel without force-loading.

Before use, verify the selected Fx0, kernel/artifact hashes and trusted signature.
Hold the native display and IOMMU runtime power active using the diagnostic
workaround. Keep the fresh DRM dumb-buffer process alive and verify that DRM's
active framebuffer and `gem` debugfs entry identify the same buffer/IOVA. The
hardcoded layout is 720×1280, XR24 with opaque RGB bars, pitch 2944, allocation
3768320 bytes. Do not use another layout or free/change the buffer during a query.
The sample IOVA on the qualified boot is 0x39a000; it is not a permanent address.

Build with the exact running kernel output and its matching toolchain:

```sh
make -C /private/exact-kernel-output ARCH=arm LLVM=1 \
  M="$PWD/diagnostics/display-mapping" W=1 modules
```

Sign both modules with a key trusted by the running kernel, and transfer and
verify them in RAM. Example commands on that verified diagnostic boot:

```sh
insmod /tmp/fx0_scanout_map.ko iova=0x39a000
rmmod fx0_scanout_map
insmod /tmp/fx0_hw_translate.ko iova=0x39a000
rmmod fx0_hw_translate
```

`fx0_scanout_map` reads the active MDP device's software IOMMU mappings and
samples twelve RGB positions through normal RAM pages. It rejects unmapped or
invalid PFNs. It also reads the known MSM8226 DMA0 register block while the MDP
is already active. It does not write framebuffer, MDP or IOMMU registers. On
this boot all 12 samples match; DMA0 source/current source both identify 0x39a000,
size 720×1280 and pitch 2944. This proves the inspected mapping/data/register state,
not that the display hardware has fetched and shown those pixels.

`fx0_hw_translate` issues **hardware translation requests** by writing only the
ARM32 context's ATS1PR register. It requires the known active display IOMMU,
context 0 resource 0xfd930000 and enabled translation, then compares three page
translations with the software walk. Each request has a bounded 1 ms status poll.
It reads PAR and logs fault/match status; it does not change page tables,
translation configuration, TLB policy or pixel memory. All 3 hardware translations
match on this boot. The implementation follows the ARM32 privileged-read ATOS
operation used by the maintained ARM SMMU code and original MSM IOMMU driver.

Review the logged values and match counts; module insertion status alone is not
a verification result. A successful ATOS query does not prove that the MDP uses
the queried context for every transaction, that pixel unpacking/routing is
correct, or that the panel shows pixels. Visible output, error recovery,
power-management correctness and full display/touch acceptance remain separate.
