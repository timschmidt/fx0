# MSM8226 APR, SLIMbus and QDSP6 descriptions

These four common-DTS patches carry the existing APR core, SLIMbus NGD/BAM,
QDSP6 services and ASM front-end DAIs onto the current Qualcomm ARM32 chain.
They preserve Timothy Schmidt's original work and Claude Opus 5.5 assistance,
with Codex assistance disclosed in the adapted changelogs. Human DCO remains
pending; no maintainer contact or publication occurred.

The parent is the qualified PM8226 source
`3c4dccb16e558b2100fdfb79cea0933cc8d223c7`. The resulting head is
`a7ba24173e4618ace25b68ec36991fb08b7b552e`, tree
`22df3e856839a75623e38153f935aa25f4e03f7f`. Its four intermediate trees are
identical to the compiled series ending at `f2441b94`; only metadata changed
after compilation. The underlying official Qualcomm ARM32 base remains
`ae2005cea2e4f84692268e54199bb03f5c6f4558`.

All 18 inherited boards and the complete unchanged Fx0 board compile through
ordinary Kbuild. Every existing inherited node, property and reserved-memory
range is preserved. Each inherited board gains exactly 14 nodes, with the
three common controllers disabled until a board enables them. The original
56 DTC warnings remain, with none added on inherited boards. The full Fx0
has two additional known efuse unit-address warnings.

The complete Fx0 DTB matches a separate compiler pipeline byte for byte. Its
SHA256 is `c9cba4a019eb80eb5baddd366cefc9ec2f2bb89616d3d47a6ee99dc55498db65`.
The unchanged full board source is retained in the validation patch, with
SHA256 `36b2a733ba62b94371e018f20f3b318bd57732a3469c1db0a85428f196ca4c0a`.
The malformed board hunk from the early APR experiment is not carried.
Hardware and audio descriptions were preserved; no audio execution test ran.

## Rebuild and check

The source patches affect only `qcom-msm8226.dtsi`. The separate
[validation patch](validation/schema-and-complete-board.patch) imports five
previously qualified schemas and adds the complete Fx0 board and its Kbuild
target. It is a validation dependency, not part of the common-DTS submission.
Its imported source hashes are recorded in [qualification.json](qualification.json).

For a complete rebuild, use separate full kernel checkouts for the parent
and final head. In a disposable copy of the final checkout, apply the
validation patch. Copy [native-arm.config](validation/native-arm.config) to
each new output directory as `.config`, and run `olddefconfig` with
`ARCH=arm LLVM=-21`. Build the 18 inherited targets listed in
[DTB-build-controller.json](validation/DTB-build-controller.json) on the
parent, retaining the complete build log. Build those targets plus
`qcom/qcom-msm8926-lg-madai.dtb` in the validation checkout, also retaining
the complete log. Use `W=1`; no phone or boot image is involved.

On the validation checkout, run ordinary `dt_binding_check` with the recorded
`schema_filters`, then build the targets with `CHECK_DTBS=1` and the same
`DT_SCHEMA_FILES` selection. This produces the processed schema used below.
The target list and hashes are public; generated DTBs and processed schemas
must be supplied or rebuilt. They are not embedded in this review package.

Place the provided `DTB-build-controller.json` in the parent of the candidate
output directory. With `dtschema`, its `dt-validate` executable and `fdtput`
available, run the checker using the Python interpreter beside `dt-validate`:

```sh
python3 -B check-DTBs.py \
  --source source \
  --build CANDIDATE_OUTPUT \
  --baseline BASELINE_OUTPUT \
  --baseline-log BASELINE_BUILD_LOG \
  --candidate-log CANDIDATE_BUILD_LOG \
  --output NEW_CHECK_DIRECTORY
```

The included `source` directory contains the exact common file for artifact
replay. This is a Git-free file-hash check with prebuilt artifact inputs; that
single source file cannot rebuild a kernel. Alternatively, `--source` may
point to a clean full checkout at the final head, enabling Git metadata checks.

The checker compares all inherited state, validates the enabled common nodes
on a real inherited board and checks the new prerequisites on the full Fx0.
Ten malformed schema controls must be rejected. Three platform controls
cover the exact BAM window, SLIM IRQ type and core service ID. The generic
schemas accept those three mutations; the independent exact platform
contract rejects them. No broad schema claim substitutes for that distinction.

## Remaining work

The retained [unfiltered diagnostics](validation/full-Fx0-unfiltered.txt)
record full-board schema gaps from this validation snapshot. They include
board identification, touch-panel sequencing, USB power-supply linkage,
charging policy, panel/camera compatibles and raw QFPROM. The subsequent
[RMI draft](../rmi4-input-current/README.md) separately qualifies the touch
binding and runtime source; it is not imported into this DTS snapshot.

Ordinary PM8941 and PM8226 charger-parent controls prove that the existing
parent routing is correct. Custom charging-policy properties still need
their actual implementations and bindings carried forward. No parent-routing
fix was invented and no full-board properties were removed to suppress errors.
Compilation and selected schema checks do not establish complete board
schema, platform, audio or hardware runtime qualification.
