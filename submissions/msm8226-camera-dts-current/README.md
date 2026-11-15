# MSM8226 camera DTS: unsigned current Qualcomm draft

The two patches add disabled CAMSS and VFE-IOMMU nodes to the common MSM8226
description. They refresh Timothy Schmidt's existing changes `4245f34dee3c`
and `4968a6ce0788`; each node's contents are byte-identical to that implementation.
Placement follows the current source's address order. Sensor graphs, analog
supply and enablement remain board-specific.

The official Qualcomm `arm32-for-7.5` ref was observed and fetched on
2026-11-15 from `https://git.kernel.org/pub/scm/linux/kernel/git/qcom/linux.git`.
The base is `ae2005cea2e4f84692268e54199bb03f5c6f4558`.

| Patch | Local source commit |
| --- | --- |
| Describe the VFE IOMMU | `62b844e0f29455515f4fafd0803914f08af06128` |
| Describe the CAMSS | `92faf0cd70bcf96a71cd554e64a87670a0b70a9f` |

## Dependencies and validation scope

Schema validation uses a separate checkout with the exact qualified IOMMU
binding from `1d1963872f0f38d2c78aba1c97dc3ba01d6bbf23` and the CAMSS binding
from `d1eaeaee06f7b1977e563034b9ae1f021b8c0752`. The pristine IOMMU binding on
this SoC base matches that dependency's upstream base byte-for-byte; the CAMSS
binding is new. This validation checkout imports only the two schemas. It does
not combine the separately qualified runtime driver series.

The schema imports produce validation head
`1ac12dcd0ecd3a21c655fd61ac12cbf1953d4848`. Its common DTS is identical to the
source draft. Runtime dependencies remain the separately documented
[IOMMU](../iommu-msm8226-current-next/README.md),
[CAMSS](../camss-msm8226-current-media/README.md) and
[clock](../mmcc-camera-clocks-current/README.md) drafts, plus sensor and board
support. The VFE completion fix is separate.

The [affected-board inventory](affected-boards.json) follows transitive includes
and checks actual Makefile targets. It covers 18 APQ8026/MSM8226/MSM8926 boards,
including watches and tablets that a filename search for MSM8226 would miss.
All 18 pristine and candidate board DTBs build with LLVM 21 and `W=1` using the
retained native ARM config. Both versions produce the same 56 pre-existing DTC
warnings; the candidate adds none.

Ordinary kernel binding/example checks and targeted board schema checks pass.
A direct targeted schema invocation over all 18 candidate DTBs emits no
diagnostics. A decoded comparison resolves only schema-typed phandle reference
positions to node paths, preserving argument cells and null reference slots.
Every existing node/property matches upstream. Only CAMSS, its ports container,
VFE IOMMU and three context banks are added.

Six controls mutate a copy of the actual Falcon DTB: incorrect CAMSS/VFE clock
names, incorrect context compatible, too few CAMSS register blocks, incorrect
IOMMU cell count, and enabled CAMSS without its board supply. All produce schema
diagnostics. `dt-validate` returns zero even for these rejected inputs, so the
diagnostic stream is checked explicitly. Disabled common nodes may omit required
board wiring under the validator's ordinary rules. The enabled-node control
confirms that `vdda-supply` is still required; no binding requirement was relaxed.

The [evidence](../../evidence/2026-11-15-msm8226-camera-dts-current.json) records
source/build hashes, all board results, controls, provenance and limitations.

## Reproduction

Use separate baseline and candidate output directories. Copy the archived
`submissions/camss-arm32-native-dma/configs/arm.config` native config to each
`.config`, then run `olddefconfig`. On the candidate validation checkout, run:

```sh
make O=<candidate-build> ARCH=arm LLVM=-21 W=1 -j2 CHECK_DTBS=1 \
  DT_SCHEMA_FILES=media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml \
  dt_binding_check
```

Build every target listed in `affected-boards.json` on both checkouts with
`ARCH=arm LLVM=-21 W=1 -j2`, retaining their logs. Add the same `CHECK_DTBS` and
`DT_SCHEMA_FILES` settings to the candidate invocation. Use a dtschema environment
with its matching Python libfdt, `dt-validate`, yamllint and the kernel's style
dependencies. The recorded dtschema version is 2026.9. Then run the portable
[diagnostic](../../diagnostics/msm8226-camera-dts/check-DTBs.py):

```sh
python diagnostics/msm8226-camera-dts/check-DTBs.py \
  --inventory submissions/msm8226-camera-dts-current/affected-boards.json \
  --baseline-build <baseline-build> --candidate-build <candidate-build> \
  --baseline-log <baseline-DTBs.log> --candidate-log <candidate-DTBs.log> \
  --binding-log <candidate-bindings.log> --output <fresh-directory>
```

The diagnostic was also executed successfully from an independent source-only
export, using the same qualified build artifacts. This is interface/portability
verification, not an additional independent build.

## Fx0 board and submission status

The complete existing Fx0 board is preserved, with its original BSD license and
Masanori Ogino copyright. It still has 11 unresolved labels after adding these
common camera nodes. Actual compilation against the verified current includes
fails on eight immediately referenced missing nodes; the three QDSP6 phandle
references also require the missing APR services. The
[dependency inventory](remaining-board-dependencies.json) pins the original
prerequisite commits and their authors, including Bartosz Dudziak's WCNSS work.
Further binding/driver and DMA/RDI review remains open. Audio testing is excluded;
existing board descriptions have not been trimmed to obtain a passing DTB.

An initial board probe accidentally used the original integration include
directory because the C preprocessor searches beside the input file first.
That attempt was excluded. A byte-identical board input placed in the isolated
probe directory uses verified current include paths and reproduces the missing
dependencies. The comparison checker also initially rejected a legitimate null
SMSM mailbox slot; its corrected comparison preserves null slots. Both preflight
failures remain recorded privately.

Strict checkpatch with `--no-signoff` passes both patches in the dependency-aware
validation checkout, with zero errors/warnings/checks. Without the binding
dependencies, each patch reports its undocumented compatible, as expected.
Full submission checks additionally require human Signed-off-by. Kernel guidance
prohibits agents adding human DCO tags. Original Timothy Schmidt authorship and
Claude Opus 5.5 credit are preserved; this refresh and qualification used OpenAI
Codex assistance. Human review and DCO certification are pending.

These new source and review heads remain local and unpublished. No maintainer
contact, full current combined kernel/package, Fx0 DTB acceptance, phone access,
boot image, runtime IOMMU translation or camera hardware acceptance occurred.
