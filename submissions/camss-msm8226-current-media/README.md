# MSM8226 CAMSS: unsigned current-media support draft

The local three-patch series is based on official media `next`
`3fc9303dba01676c2090768126e5327e341b7761`, rechecked on 2026-11-15 before
this refresh. Its source head is `d1eaeaee06f7b1977e563034b9ae1f021b8c0752`
on `development/camss-msm8226-media-next-02`.

1. Retain the separately qualified ARM32 DMA dependency change
   `2f2e63bfa2902eb11bab4f4107a274e2ed6a8368`.
2. Add the existing MSM8226 binding at
   `015aa2b549fb3a6357d808aa0969ee55b120468a`.
3. Add MSM8226 resources, the later VFE AXI rate and its clock-name matcher at
   `d1eaeaee06f7b1977e563034b9ae1f021b8c0752`.

The binding is byte-identical to the existing integration binding. The resource
tables retain two CSIPHYs, two CSIDs, ISPIF and one VFE, omit MSM8916's separate
CAMSS AHB clock, and retain MSM8226 clock levels. The regulator entries use the
current `regulator_bulk_data.supply` representation with default zero load,
preserving the integration's unspecified load. No load setting is copied from a
different SoC.

The first resource draft alone would lose the integration's later 266.67 MHz VFE
AXI setting. This series retains both that rate and the matcher change that uses
it. Inspection of all seven current `vfe_axi` resource entries found only the new
MSM8226 entry has a nonzero rate; the existing clock-level guard excludes the
other zero-only entries.

## Host evidence

[The evidence record](../../evidence/2026-11-15-camss-msm8226-current-media.json)
binds the final source tree, source files, configurations, patches, compiled
objects and checks.

- Complete native ARM and ARM64 CAMSS components built with `COMPILE_TEST=n`,
  LLVM 21, `W=1`, and `-Werror=incompatible-function-pointer-types`. Both have
  28 object files, zero warning/error lines and unchanged native configurations.
  Neither build generated a private signing key.
- The ordinary kernel `dt_binding_check` target passed and compiled the actual
  example. Its first run skipped optional yamllint. A pinned checker was then
  installed privately in a separate local directory; direct yamllint,
  `dt-doc-validate`, `dt-validate` and kernel `dt-check-style` checks all passed
  with empty output. The retained schema environment was unchanged.
- The actual compiled example validates. Ten malformed examples are rejected:
  truncated clocks/names, interrupts/names and registers/names; missing IOMMU,
  supply and power domain; and an incorrect clock name. The driver tables' union
  of 18 clock, nine register and six interrupt names matches the binding.
- The separate VFE saved-completion fix passes `git apply --check` against this
  tree. It was not applied or included in these builds. This establishes textual
  compatibility only.

The [previous ARM32 report](../camss-arm32-native-dma/README.md) contains the
seven baseline/candidate Kconfig cases, seed configs and complete component build
commands. Use this series' final source tree with those native configurations
to reproduce the component builds. Run binding checks with dtschema 2026.9 and
yamllint 1.37.1 on PATH:

```sh
make -C <linux> O=<arm-out> ARCH=arm LLVM=-21 -j4 \
  DT_SCHEMA_FILES=media/qcom,msm8226-camss.yaml dt_binding_check
python3 diagnostics/camss-msm8226/check-contract.py \
  --source <linux> --build <arm-out> --output <fresh-result.json>
```

The contract entry needs dtschema and PyYAML (tested with 2026.9 and 6.0.3).
Its source is an exact copy of the executed checker. Initial checker launch
failures from a missing Python module and resolving the venv interpreter symlink
to the host interpreter remain preserved locally; the successful run uses the
venv entry and pinned isolated style-tool site. No semantic assertion was relaxed.

## Review and remaining dependencies

Strict checkpatch with `--no-signoff` passes for patches 1 and 3. Patch 2 has only
the generic new-file MAINTAINERS advisory: its path is already covered by
`Documentation/devicetree/bindings/media/qcom,*camss*` in the existing QUALCOMM
CAMERA SUBSYSTEM DRIVER section. Reviewing that coverage requires no MAINTAINERS
edit. Ignoring only `FILE_PATH_CHANGES` gives zero errors/warnings for patch 2.
Unfiltered submission checks report a missing human Signed-off-by on each patch
and the same advisory on patch 2. Agents must not add the human DCO tag.
The [maintainer lookup](maintainers.txt) was generated in the actual source tree.

Original authored work remains credited to Timothy Schmidt and Claude Opus 5.5
<noreply@anthropic.com>. Provenance includes binding `0d9976327548`/`9900b4eca49e`,
resources `f8a7ccc43396`/`680a10f798d0`, and AXI follow-up `d1f8047db385`.
This refresh and qualification used OpenAI Codex assistance. Earlier source
heads and failed style checks remain preserved; final message corrections changed
no compiled bytes. These are platform-support changes with no invented Fixes tag.

The old common-DTS patch `8203cfa85fce` references a VFE IOMMU node absent from
this media base. No dangling phandle or substitute display/GPU IOMMU was added.
The foundation review must cover the VFE IOMMU binding/configuration and stream
IDs, MMCC M/N and AXI propagation changes, common DTS, Fx0 board and sensor
support, and integration DMA/frame-geometry dependencies on their appropriate
current maintainer bases. Old integration hardware results do not qualify this
base. The separate VFE bug-fix branch remains unchanged at `032b7e62149c`.

This series has no board DTB qualification, complete kernel/package build,
module-load test, hardware DMA/capture acceptance, or new RAM image. The phone
was not accessed. Publication and human review/DCO remain pending; no maintainer
was contacted. All existing physical trial and publication approval gates remain.
