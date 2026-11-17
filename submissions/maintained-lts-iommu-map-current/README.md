# Maintained LTS IOMMU errors and mapping audit

Two additional local repairs prevent partial context programming and release an
unpublished page table after failed secure initialization, clear failed domain
associations, and unwind clocks after failed runtime resume. The source-extracted
52-case model changes from 23 wrong baseline cases to zero; three deliberately
regressed variants fail their intended contracts. The baseline fixture explicitly
cleans its observed retained allocation afterward, so normal LSan stays enabled.
Kernel allocation/firmware/context services are modeled; this is not actual secure
firmware, full driver-core or physical IOMMU execution. Source credits/licenses
are preserved. New local repair commits are authored by Codex without sign-off.

All 21 audited original changes are already present: four common board nodes,
14 IOMMU feature changes, two MMCC changes and the DSI lane fix. Exact feature
comparisons preserve LTS allocator/OF/PM APIs and upstream device support. These
equivalence audits are separate from the two new repairs and retain all 147
original origins. Remaining probe-time manual PM cleanup needs a separate audit.

Thirteen selected native objects pass on ARM, ARM64 and ARM64 RT with
nonpermissive CFI. MMCC is native ARM32 only; invalid attempts to force its
selection on ARM64 are excluded. Every ELF source checksum matches current
source. Real LTS Kbuild generates the DSI header used byte-for-byte by the host
PHY model. Earlier fixture/compiler/configuration limitations remain local.

The MMCC model checks 50 rate cases, programming errors, missing M/N widths and
AXI propagation. The PHY model passes 192 cases/1,056 checks; unconditional and
wrong-lane regressions each fail 144 checks. Four retained halt cases plus two
UB controls and five legacy/OS-managed probe cases pass. Three positive/eight
negative IOMMU schema examples and VFE three-stream/prefetch bounds pass.
Compiled mappings retain eight banks across MDP/VFE/GPU; CAMSS uses VFE bank 0.
Unchanged DTS/schema inputs retain the prior maintained 19-board full-schema
result. DSI timing/PLL, actual streams, power collapse and r2 remain unqualified.

Run `python3 -B replay.py --output /absolute/new/private/output` with clang-21.
The manifest is checked first; all ten generated fixtures in eleven selected
suites must match qualified bytes. Normal LSan and fail-fast ASan/UBSan remain
enabled. No Git checkout, network, phone, radio, USB device or actual hardware is
accessed. Native objects/schema validations are archived evidence, not replayed
builds. The two source patches pass strict checkpatch; human DCO/security review
remains pending. This source-only review packet is local and unpublished.

Complete maintained integration, normal trusted reproducible APK/update/recovery,
all seven bringup requirements and physical acceptance remain open. No Wi-Fi
scan, Replimat3 interaction, network change or maintainer contact occurred.
