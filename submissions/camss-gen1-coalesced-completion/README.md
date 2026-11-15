# CAMSS gen1 saved completion draft

The unsigned draft `032b7e62149cd493fef5a46a448c8c46d7b20816` is based on
verified official media `fixes` commit
`b1466305390c6368148cf456278139ef4deebe89`. It contains only the six-file
camera fix, with a verified historical `Fixes` tag and AI assistance disclosure.

[Patch](0001-media-qcom-camss-consume-saved-completions.patch) and
[plain-text report](report.txt) are prepared for human review. The recipient
list comes from this exact base's `get_maintainer.pl`; nothing has been sent.

ASan/UBSan passes 84 extracted-function executions and 15 controls on this
base. The complete ARM CAMSS component builds warning-free with `W=1`, KCFI
and fatal incompatible callback types under `COMPILE_TEST`. Provider/caller
CFI types match. A separate warning-free ARM64 component build uses the
native IOMMU_DMA Kconfig path with COMPILE_TEST disabled; both provider type
words match the new ARM32 ISR type. This is component/API coverage. Native ARM32 CAMSS is
excluded by the current `IOMMU_DMA` dependency, and patched hardware behavior
remains unqualified.

The code-style check passes with `--strict --no-signoff`. The full submission
check has exactly one error: missing human DCO certification. The tree's
[AI contribution instructions](https://github.com/torvalds/linux/blob/b1466305390c6368148cf456278139ef4deebe89/Documentation/process/coding-assistants.rst)
state: “AI agents MUST NOT add Signed-off-by tags.” The draft has no such tag.
Human review and certification, physical qualification and publication remain
open.

[Sanitized maintainer-base evidence](../../evidence/2026-11-15-camera-vfe-media-fixes-port.json)
