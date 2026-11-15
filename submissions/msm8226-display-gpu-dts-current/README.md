# MSM8226 display/GPU IOMMU DTS: unsigned current Qualcomm draft

These two patches restore the existing display and GPU IOMMU descriptions on
the current Qualcomm ARM32 base. They retain the complete platform data:
MDP's non-secure scanout bank and two secured banks, SCM device ID 1, clocks
and GDSC; GPU's user/privileged banks, three clocks, GDSC and context-zero
attachment. Both IOMMUs and the GPU remain disabled for boards to enable.

| Patch | Local source commit | Original changes |
| --- | --- | --- |
| Describe the display IOMMU | `3379290a7d7fa2ac831e13b66b21be26d41eabed` | `6c99f0648715`, `abe11294089a` |
| Describe the GPU IOMMU | `6155789433f4c828677b67b9d47c22b2a8547aba` | `dad2d15ff6ba` |

The parent is the [qualified common camera DTS draft](../msm8226-camera-dts-current/README.md)
at `92faf0cd70bcf96a71cd554e64a87670a0b70a9f`, on official Qualcomm
`arm32-for-7.5` base `ae2005cea2e4f84692268e54199bb03f5c6f4558`. The official
ref was reverified unchanged on 2026-11-15. Each new node is byte-identical to
its complete existing integration description. MDP's initial node and secured
bank follow-up are combined; the original board edits remain in the complete
Fx0 board awaiting its other prerequisites.

## Qualification and dependencies

All 18 actual upstream boards inheriting MSM8226 leave the GPU and display
subsystem disabled. The new GPU reference therefore does not enable either
consumer or provider on those boards. The [inventory](affected-boards.json)
follows includes and actual Makefile targets, covering APQ8026/MSM8226/MSM8926.

The validation checkout imports only the exact IOMMU schema from qualified
source `1d1963872f0f38d2c78aba1c97dc3ba01d6bbf23` and CAMSS schema from
`d1eaeaee06f7b1977e563034b9ae1f021b8c0752`. Its head is
`aef6a192d40ab543206b0b7a3557bb7d8a90879f`; its common DTS is identical to
the source draft. These schema imports do not combine or qualify runtime
drivers. Real use still requires the separately tested
[IOMMU foundation](../iommu-msm8226-current-next/README.md), relevant display/GPU
drivers and complete board support.

The 18 new candidate DTBs build with LLVM 21 and `W=1`. The retained 18-board
camera-DTS baseline is reused after checking every recorded DTB hash; it is
not counted as a new build. Both produce the same 56 pre-existing DTC warnings,
with none added. Configurations match and remain unchanged during the build.
Ordinary kernel checks pass for IOMMU, CAMSS and Adreno GPU bindings/examples
and the affected board DTBs. Direct validation of all 18 candidate DTBs emits
no targeted schema diagnostics.

A schema-typed phandle comparison preserves reference argument cells and null
slots. Every existing node/property is unchanged except the expected IOMMU
attachment on the disabled GPU. Seven nodes are added: MDP IOMMU and its three
contexts, GPU IOMMU and its two contexts. Existing common camera nodes remain
unchanged.

The independent platform checks verify the register/context ranges, actual
clock IDs, interrupt tuples, MDP security layout and SCM ID against the retained
description and qualified driver. The GPU uses stream/context pairs `(0, 0)`
and `(1, 1)` from the driver's table; the MDP mappings remain firmware-managed.
All 12 GPU and 18 MDP prefetch entries fit the declared global windows. This
is a description/driver contract check, not execution of IOMMU hardware.

Five malformed actual-Falcon DTB controls produce schema diagnostics: wrong
MDP/GPU-IOMMU clock names, wrong context compatible, wrong IOMMU cell count,
and wrong Adreno clock count. Four further decoded platform controls are
rejected: nonexistent GPU context, lost MDP secured-bank flag, insufficient
global register window and wrong context offset. A copied actual-board DTB
with both IOMMUs enabled also passes the schemas. That modified input tests
required properties; it is not physical board enablement or acceptance.

One retained malformed-DTB control exposes a schema coverage limit. Replacing
the GPU context interrupt with a string decodes as two uint32 cells, and the
generic IOMMU schema accepts it even with its parent enabled. The independent
MSM8226 platform check rejects that actual decoded input because the GIC tuple
must be `(0, 241, 4)`. The initial checker stopped on its incorrect assumption
that the generic schema would reject this input. The control remains present;
no binding was weakened and no claim of complete IRQ validation is made.
`dt-validate` also returns zero for reported schema failures, so diagnostic
streams are checked explicitly.

The [evidence](../../evidence/2026-11-15-msm8226-display-gpu-dts-current.json)
pins source trees, schema imports, configs, DTBs, driver hash and all controls.

## Reproduction

Build the listed targets in a separate output directory, using the archived
native ARM config at `submissions/camss-arm32-native-dma/configs/arm.config`,
`olddefconfig`, then these common settings:

```sh
make O=<candidate-build> ARCH=arm LLVM=-21 W=1 -j2 CHECK_DTBS=1 \
  DT_SCHEMA_FILES=media/qcom,msm8226-camss.yaml:iommu/qcom,iommu.yaml:display/msm/gpu.yaml \
  dt_binding_check
```

Use the same settings to build every target in `affected-boards.json`. Retain
the binding and DTB logs. The preceding camera-DTS draft documents the baseline
build. Use a matching dtschema/Python libfdt environment (recorded version
2026.9), yamllint and kernel DT-style dependencies. Run the portable
[diagnostic](../../diagnostics/msm8226-display-gpu-dts/check-DTBs.py):

```sh
python diagnostics/msm8226-display-gpu-dts/check-DTBs.py \
  --inventory submissions/msm8226-display-gpu-dts-current/affected-boards.json \
  --baseline-build <camera-DTS-build> --candidate-build <candidate-build> \
  --baseline-log <camera-DTBs.log> --candidate-log <candidate-DTBs.log> \
  --binding-log <candidate-bindings.log> --iommu-source <qualified-IOMMU-source> \
  --output <fresh-directory>
```

The diagnostic pins the recorded qualified IOMMU source head. It was also run
successfully from an independent source-only export using the same build
artifacts, verifying portability without counting an additional build.

## Complete Fx0 and submission status

The unchanged complete Fx0 board now resolves both display/GPU IOMMU labels.
Its current-include compilation still fails on six immediately missing nodes;
nine unresolved labels remain including the dependent QDSP6 phandles. The
[remaining dependency inventory](remaining-board-dependencies.json) preserves
original authors and commits. WCNSS, PMIC PON/torch, APR/QDSP6/SLIMbus and
further panel/sensor/power/raw-QFPROM support remain to be refreshed and
qualified. Audio testing is excluded; existing board content was preserved.

Both patches pass strict checkpatch with `--no-signoff` and their binding
dependency: zero errors, warnings or checks. On the unextended SoC base, each
correctly reports its missing compatible documentation. Full dependency-aware
checks require only human Signed-off-by. Kernel guidance prohibits agents
adding that human DCO certification. Timothy Schmidt's authorship and the
GPU change's original Claude Opus 5.5 credit are preserved. This refresh and
qualification used OpenAI Codex; human review/DCO remain pending.

The new source/review heads remain local and unpublished. No maintainer contact,
phone access, boot image, full combined current kernel/package, runtime IOMMU
translation or Fx0 display/GPU acceptance occurred. The failed r2 boot remains
unresolved and its repeat/verified-return/operator gates remain unchanged.
