# Remoteproc draft submission

One fix for Bjorn Andersson's
[remoteproc tree](https://git.kernel.org/pub/scm/linux/kernel/git/remoteproc/linux.git).
Its base is `for-next`, pinned on October 30, 2026 to
`23d0516587f896f5f16a47c97ddb41d28e6289ff` (7.3-rc1). It doesn't depend on any Fx0
board or WCNSS device-tree patches.

## Pronto v1/v2 regulator selection

Mainline `3dbc90b9c22e` fixed out-of-bounds regulator names on Pronto v3. It also
sends Pronto v1/v2 down the v3 path, so `wcnss_init_regulators()` requests only
`vddcx`. In-tree, that drops MX and PX on MSM8974 boards (FP2, HTC M8, OnePlus
One) and PX on MSM8916/MSM8939. The bug is also in 6.18.59 stable, where the Fx0
found it. The [patch](0001-remoteproc-qcom_wcnss-Fix-PD-regulator-selection-on-.patch)
tests whether a table has PD regulators, rather than comparing counts.

The [submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-wcnss-pd-regulators)
is `44a445091d29`. Checks on the maintainer base:

- The [source-extracting model](../../diagnostics/wcnss-regulators/README.md)
  fails 6 of 10 cases on the base and passes all 10 with the fix.
- LLVM W=1 builds of the object for ARM `multi_v7_defconfig` and arm64
  `defconfig` produce no warnings.
- `git am` of the exported file reproduces the branch tree exactly.
- Strict checkpatch reports only the expected items: no Signed-off-by, a
  `Fixes` id unknown to the shallow fetch (confirmed in mainline), and an
  unwrapped quoted log line kept intact for grep.
- `get_maintainer.pl` lists Bjorn Andersson, Mathieu Poirier,
  linux-arm-msm, linux-remoteproc and linux-kernel.

The physical test used the same change on the Fx0's 6.18.59 kernel; see
[wireless evidence](../../evidence/2026-10-30-wcnss-first-start.json). A kernel
built from the maintainer tree has not run on hardware. The patch file lists
these limits below `---`.

The patch carries `Assisted-by` under the kernel's
coding-assistants rules. It has no Signed-off-by: only the owner can certify
the DCO, after reviewing the change. Under the threat model this is an ordinary
functional regression, not a vulnerability. Nothing has been sent.

## Not yet submittable

The MSM8226 DXE interrupt-trigger fix belongs in the MSM8226 WCNSS node series.
That node is not in mainline yet, so the fix should be folded into that series
when it is prepared. MSM8974 declares the same rising-edge specifier upstream,
but this project cannot test it.
