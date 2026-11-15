# Native ARM32 CAMSS selection: unsigned review draft

The existing integration change now has a separately qualified refresh on media
`next`, observed on 2026-11-15 at
`3fc9303dba01676c2090768126e5327e341b7761`. The draft source commit is
`2f2e63bfa2902eb11bab4f4107a274e2ed6a8368` on
`development/camss-arm32-dma-media-next-01`. It changes one Kconfig dependency:

```diff
- depends on (ARCH_QCOM && IOMMU_DMA) || COMPILE_TEST
+ depends on (ARCH_QCOM && (IOMMU_DMA || ARM_DMA_USE_IOMMU)) || COMPILE_TEST
```

ARM32 uses `ARM_DMA_USE_IOMMU`; its native configuration cannot provide the
existing `IOMMU_DMA` alternative. Accepting that backend permits native CAMSS
selection without enabling `COMPILE_TEST`. This is additional configuration
support, with no claim of a newly introduced upstream regression and no invented
`Fixes` tag. It does not add MSM8226 platform resources or board support.

## Qualification

The complete current-tree Kconfig engine passed all seven cases. Each started
from the corresponding archived seed, requested `VIDEO_QCOM_CAMSS=m`, and ran
`olddefconfig` after applying the options below. The baseline ran before the
source change; the other five cases ran after it.

| Case | Options | DMA backend | CAMSS result |
| --- | --- | --- | --- |
| Baseline ARM | `-d COMPILE_TEST` | ARM IOMMU | disabled |
| Baseline ARM64 | `-d COMPILE_TEST` | IOMMU DMA | module |
| Candidate ARM | `-d COMPILE_TEST` | ARM IOMMU | module |
| Candidate ARM64 | `-d COMPILE_TEST` | IOMMU DMA | module |
| ARM without DMA | `-d COMPILE_TEST -d IOMMU_SUPPORT` | neither | disabled |
| ARM compile test without DMA | `-e COMPILE_TEST -d IOMMU_SUPPORT` | neither | module |
| ARM64 without Qualcomm | `-d COMPILE_TEST -d ARCH_QCOM` | IOMMU DMA | disabled |

ARM64's normalized configuration is byte-identical before and after the change.
ARM32 adds only `VIDEO_QCOM_CAMSS`, `VIDEOBUF2_CORE`, `VIDEOBUF2_DMA_SG`,
`VIDEOBUF2_MEMOPS`, and `VIDEOBUF2_V4L2`, each as a module.

Both native candidate configurations completed `modules_prepare` and the full
`drivers/media/platform/qcom/camss/qcom-camss.o` target with LLVM 21, `W=1`,
`KCFLAGS=-Werror=incompatible-function-pointer-types`, and four build jobs.
Each produced 28 object files, with zero warning/error lines. The final config
hashes remained unchanged, and neither build generated a private signing key.
These are component builds, with no full kernel, package, module-load, runtime
CFI, or hardware qualification.

The [evidence record](../../evidence/2026-11-15-camss-arm32-native-dma.json)
contains source, seed, configuration and component hashes. To reproduce a case,
use a clean checkout of the recorded base (baseline) or apply
[maintainer-draft.patch](maintainer-draft.patch) to that base (candidate), copy
`configs/arm.config` or `configs/arm64.config` to a fresh output directory as
`.config`, then run the source tree's `scripts/config --file <out>/.config` with
the case's options and `-m VIDEO_QCOM_CAMSS`. Run:

```sh
make -C <linux> O=<out> ARCH=<arm-or-arm64> LLVM=-21 olddefconfig
make -C <linux> O=<out> ARCH=<arm-or-arm64> LLVM=-21 W=1 \
  KCFLAGS=-Werror=incompatible-function-pointer-types -j4 modules_prepare
make -C <linux> O=<out> ARCH=<arm-or-arm64> LLVM=-21 W=1 \
  KCFLAGS=-Werror=incompatible-function-pointer-types -j4 \
  drivers/media/platform/qcom/camss/qcom-camss.o
```

The build commands apply to the two native candidate cases. They do not belong
to cases whose expected CAMSS selection is disabled. Recorded builds used
`KBUILD_BUILD_USER=fx0-review`, `KBUILD_BUILD_HOST=source-check`, and
`KBUILD_BUILD_TIMESTAMP="2026-11-15 00:00:00 UTC"`.

## Attribution and submission status

The source preserves Timothy Schmidt's authorship and credits the original
integration commit `9d46e4575ea176699386bbb0dc988c6abbf26705`, whose original
trailer credits Claude Opus 5.5 <noreply@anthropic.com> as co-author. This refresh
and qualification used OpenAI Codex assistance. Two intermediate attribution
trailer spellings were rejected by checkpatch and remain preserved locally,
including their source heads and receipts. The final draft retains the credit in
prose; all three trees are identical, so no compiled code changed.

Strict checkpatch with `--no-signoff` passes with zero errors or warnings. The
full check reports exactly one error, missing human `Signed-off-by`. The kernel's
`Documentation/process/coding-assistants.rst` says: “AI agents MUST NOT add
Signed-off-by tags.” Human review and DCO certification are required before
submission. The [maintainer lookup](maintainers.txt) was generated in the actual
source checkout. No maintainer has been contacted and neither new branch has
been published.

The separate saved-completion VFE fix remains at
`032b7e62149cd493fef5a46a448c8c46d7b20816` on media `fixes`. Its patch passes
`git apply --check` against this configuration-support tree. It was not applied
or included in these builds. That check establishes textual compatibility only.

Remaining work includes refreshing the existing MSM8226 resource/binding/board
changes against current appropriate bases, validating their schemas and builds,
and obtaining physical acceptance under the existing trial gates. The phone,
installed packages, boot images, r7 artifact qualification, and pending approvals
are unchanged.
