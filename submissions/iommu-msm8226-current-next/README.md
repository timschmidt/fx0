# MSM8226 IOMMU foundation: unsigned current-next draft

The 20-patch series is based on official IOMMU `next`
`2cf4be57b301ed2d7af82e70cff5dfd96894d8de`, observed and fetched from
`https://git.kernel.org/pub/scm/linux/kernel/git/iommu/linux.git` on 2026-11-15.
The source head is `1d1963872f0f38d2c78aba1c97dc3ba01d6bbf23`, branch
`development/iommu-msm8226-current-next-03`. No publication or maintainer contact
has occurred.

This refresh includes the full integration prerequisites: shared register
definitions, cached context programming, ARMv7s tables, global register access,
OS-managed stream mapping, context restoration, halt/no-stall controls, prefetch
tables, and MSM8974/MSM8226 display/GPU/VFE configurations. The VFE retains its
later stream IDs 0/1/2 and all 18 prefetch entries. Adding just the original VFE
configuration would leave its required infrastructure absent.

The current upstream runtime-PM guard around legacy context access is preserved.
The integration's global-instance guard is combined with it. Upstream already
supports the optional TBU clock, so that binding support is retained rather than
duplicated. The binding also documents global resources, requires `reg` for the
new per-instance compatibles, and compiles the integration VFE node alongside the
legacy example. Explicit MMCC indices in the VFE example avoid conflicting SoC
clock-header namespaces while preserving clock IDs 90/91/85 and GDSC 3.

## Verified host results

[The evidence record](../../evidence/2026-11-15-iommu-msm8226-current-next.json)
pins the source tree, all four changed files, patches, configurations, objects
and checks.

- Final native ARM32 and ARM64 configurations have `QCOM_IOMMU=y`,
  `IOMMU_IO_PGTABLE_ARMV7S=y`, `ARCH_QCOM=y` and `COMPILE_TEST=n`. Both complete
  driver and backend objects compile with LLVM 21, `W=1` and
  `-Werror=incompatible-function-pointer-types`, with no warnings/errors. No
  private signing key was generated.
- Ordinary `dt_binding_check`, including YAML lint and compiled examples,
  passes without diagnostic output beyond normal build progress. Direct YAML,
  document, DT style and example validators also pass with empty output.
- Three positive schema cases pass: the existing example, VFE example without
  a secure-world ID, and legacy example without its optional local region.
  Eight malformed cases are rejected. The actual VFE example has three context
  banks matching stream IDs 0/1/2; its declared global window contains all 18
  prefetch register accesses.
- Extracted production halt helpers pass four ASan/UBSan cases: absent config,
  disabled halt, enabled read/modify/write preserving unrelated bits, and the
  timeout diagnostic. Two controls reproduce the original null-offset behavior.

The sanitizer check found that the imported halt helpers derived a pointer from
a NULL global base before checking whether they were needed. The final patch
moves that calculation behind the guards in both helpers. Its `Fixes` tag names
the original integration feature `5ec3d506e602`, not a feature claimed to exist
in this upstream base. This is treated as a regular robustness defect in the
imported feature, with no security-impact claim. The correction and executed
helper bodies are bound to the final source. Later formatting changes outside
those helpers changed no C tokens; final native objects were rebuilt afterward.

The [halt diagnostic](../../diagnostics/iommu-msm8226/check-halt.py) needs Clang 21
and runs host executables under ASan/UBSan. It emulates MMIO in owned memory with
minimal structs; it does not validate the kernel ABI, real polling latency or
hardware. The [binding diagnostic](../../diagnostics/iommu-msm8226/check-binding.py)
needs dtschema (tested with 2026.9). Both sources are exact copies of the executed
checkers. From this repository, with a prepared output tree:

```sh
python3 diagnostics/iommu-msm8226/check-halt.py \
  --source <linux> --output <fresh-halt-result-directory>
python3 diagnostics/iommu-msm8226/check-binding.py \
  --source <linux> --build <arm-out> --output <fresh-binding-result.json>
```

Component checks used the archived native seeds from
`submissions/camss-arm32-native-dma/configs`, enabled `QCOM_IOMMU`, normalized
with `olddefconfig`, ran `modules_prepare`, and built
`drivers/iommu/arm/arm-smmu/qcom_iommu.o` and
`drivers/iommu/io-pgtable-arm-v7s.o`. Binding validation used
`DT_SCHEMA_FILES=iommu/qcom,iommu.yaml`. Build identity was `fx0-review`,
`source-check`, with timestamp `2026-11-15 00:00:00 UTC`.

## Attribution, review and remaining work

Original authorship remains attributed to Dmitry Baryshkov and Timothy Schmidt.
Original Claude assistance credits remain in the refreshed commit descriptions.
New adaptations and host qualification used OpenAI Codex. Original signed-off
history remains untouched; these refreshed commits contain no Signed-off-by
tags. Human review and DCO certification are required.

All 20 strict style checks pass with `--no-signoff --ignore CAMELCASE`. Only
architectural `ARM_SMMU` register names following the existing shared-header
convention are excluded. Unfiltered strict checks have no errors or warnings,
but retain those naming advisories. Full checks with that reviewed naming
exclusion report only missing human Signed-off-by. The
[maintainer lookup](maintainers.txt) was generated in the actual source tree.

The initial missing-header compile failure, merge conflicts, Python/YAML
preflight warnings, example-header collisions and earlier style drafts remain
preserved locally. None are counted as successful qualification.

There is no common-DTS/Fx0 board qualification, full kernel/package build,
module load, real translation/stream mapping, GDSC/context restoration or
suspend/resume acceptance on this base. The remaining foundation review must
cover current MMCC M/N/AXI propagation, common DTS and board/sensor dependencies,
plus the integration camera DMA and RDI geometry changes. The separate CAMSS
and VFE bug-fix drafts stay unchanged. No phone access or new boot image occurred;
existing physical trial and exact publication approval gates remain in force.
