# CAMSS ARM32 DMA prerequisite and runtime assembly

The current ARM32 CAMSS proposal now includes the DMA prerequisites that
its Kconfig-only predecessor lacked. ARM's mapper defaults to 64 KiB DMA
segments, and separately allocated chunks may have IOVA gaps. VFE uses a
base address per plane. The patch raises the segment limit and checks that
adjacent mapped segments cover the negotiated image size. It accepts
adjacent imports and unused noncontiguous tails.

The source proposal is 053ff674a48f79e6ee414f4da7135aff3437099a on the
observed official media-committers next base
48fe5a7834cc10081887d7bcd9ff0a4cadc3fa8c. It replaces the Kconfig-only
2f2e63bfa290 proposal and credits both original integrations. This is a
feature introduction, so no upstream Fixes tag is invented. The exact
unsigned patch passes strict 80-column checkpatch with --no-signoff; the
ordinary check reports only the missing human DCO certification.

The host fixture executes the actual platform DMA defaults, DMA parameter
helpers, ARM scatterlist mapper and CAMSS initialization/preparation
callbacks. Only the probe's segment-limit statement is executed. Core
structures, SG traversal, VB2 lookup and IOMMU services are synthetic. The
allocator intentionally leaves legal gaps between separately mapped
chunks. Seven frame sizes are synthetic examples, not negotiated capture
layouts. Full probe/allocation, real DMA, V4L2 IOCTLs, physical image
integrity and camera/lens/flash interactions are unqualified.

There are 46 modeled checks: baseline 14 failures, candidate zero. Removing
the segment limit produces six failures, removing the range guard eight,
and imposing a one-segment restriction three. Cases include adjacent,
gapped and overlapping imported mappings, sufficient prefixes, independent
planes, NV chroma offsets, offset-driven mapper splits, and mapper errors.
ASan, UBSan and LeakSanitizer remain enabled. Source-bound extraction and
frozen executed bodies are supplied for independent replay.

Run `python3 replay.py /tmp/camss-dma-replay` from this directory with
Clang 21 and host Linux UAPI headers installed. The output directory must
not already exist. The replay uses neither Git nor network/device access.
It verifies the manifest, re-extracts the supplied source and reproduces
all five expected result sets. It is a host check, not a native kernel run.

Native W=1 CAMSS component builds produce 28 objects each for ARM and
ARM64. The assembled integration fdadb178ffed6ad81148bd7bc300ff46cbc220c2
also builds 87 ARM and 84 ARM64 objects with COMPILE_TEST disabled. This
includes IOMMU/page tables, CAMSS/VFE, clocks on native ARM, PMIC/MFD,
wireless, panel, raw QFPROM, Sony sensors, charging, USB and RMI components.
ARM CAMSS uses Kbuild's built-in archive; ARM64 uses its module component.
MMCC's native Kconfig is ARM-only and is not forced on ARM64.

The combined ARM run has five inherited kernel-doc warning occurrences
in untouched ARM DMA code. A comparison build on source identical to the
pristine media base reproduces the same five. There are no new diagnostics;
no warning suppression or unrelated documentation edit was used. Initial
fixture mistakes and build launcher failures remain in private evidence.

The complete arch and binding trees remain identical to frontend 0996a0f,
whose 19 full DTBs and unfiltered Fx0 schema were already validated. Those
checks were retained without redundant DTB rebuilding. Source assembly is
recorded in assembly-plan.json; current-feature-inventory.json preserves
all 89 LTS paths and unresolved semantic comparisons. Differing whole files
on different kernel bases do not prove a missing feature. NFC is an
additional route outside this LTS r7 delta. Motion/DMP, CPU/CPR, display,
IADC, vibrator, USB PHY, RDI geometry, shared SLIMbus and scan handling
still require comparison or current qualification. Audio execution remains
excluded; full board descriptors are retained.

This current development assembly is not a complete qualified kernel or a
replacement for the maintained LTS phone baseline. Full linking, module
and package reproducibility, update/recovery, all required nonaudio
hardware/interactions and final release/package currency remain open.
The original r2 display-IOMMU failure is not proved fixed. This work made
no phone changes, publication or maintainer contact. Human review and DCO
certification are pending.
