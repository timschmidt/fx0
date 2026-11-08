# LG Fx0 upstream development

## Repository ownership and layout

Use public repositories from the start of implementation so that reviewable history, reproducible bases, and attribution develop with the port. This document specifies intended destinations; remote URLs under the owner's account must be recorded when repositories are provisioned.

| Repository | Contents and branch purpose | Upstream destination |
| --- | --- | --- |
| Root `fx0` project | Plans, hardware inventory, source manifests, reproducible helpers, sanitized evidence, submission dependency records | Project coordination and installation documentation |
| Linux development repository | Shared SoC integration branch, maintained-kernel branch, separate submission branches based on current subsystem trees | Linux Qualcomm/ARM, DRM, input, power supply, ASoC, media, IIO, NFC, networking, and other affected subsystems |
| pmaports fork | Minimal Fx0/generic package integration, firmware loading, initramfs and deployment configuration | Nura pmaports |
| lk2nd fork | Fx0 detection/DTB selection and verified bootloader fixes | lk2nd |
| Userspace forks as needed | ALSA UCM, libcamera, Mesa, ModemManager or other actual changes | Each project's own upstream |

Do not copy full kernel history into the coordination repository. Keep independent repositories in ignored `src/` and worktrees in ignored `worktrees/`. Add a source manifest containing remote URL, branch/tag, full commit, toolchain, local patch series, and package version. A branch name alone is not a reproducible source lock.

The root Git working tree is initialized following the host permission update. The earlier restricted-environment observations in the development log are historical. Record public URLs and pushed revisions below as they become available.

## Integration and submission branches

Maintain separate purposes for branches:

- `integration/fx0`: the complete working system, with explicit external patch dependencies.
- `maintenance/fx0-<kernel-series>`: the maintained release used on the installed device, with current fixes and the minimum outstanding patches.
- `submit/<subsystem>-<topic>-vN`: a focused series based on that subsystem's current expected tree.

Names are project conventions and can be adjusted to an upstream's workflow. Record actual bases and dependencies. Keep public version tags for tested images and exported series; do not silently rewrite an already referenced release or submission tag. Regenerate the integration branch from documented components when practical.

Do not make production operation depend indefinitely on the old 3.4 kernel, an obsolete experimental branch, a held-back broken package, or a private patch that cannot be reviewed. A temporary workaround needs an issue, explanation, removal condition, and upstream destination.

## Patch routing and authorship

Recover original commits where possible. Preserve authorship, copyright, license notices, and legitimate review/sign-off history. Separate new work and substantial adaptations clearly. Use the real contributor identity and only sign off contributions when the contributor can make the project's required certification. Never invent consent, review tags, test tags, or an identity.

Choose the destination from the changed component, rather than putting every fix into Nura packaging. Hardware descriptions and drivers belong in Linux; distro integration belongs in pmaports; general userspace fixes belong in the affected project. Shared MSM8226 changes should remain reusable by other boards.

Write each commit around one reviewable change, with the concrete failure or missing behavior, the implementation, and useful evidence. Keep debug prints, bulk source imports, formatting churn, and unrelated cleanup out of submission series. Explain cross-tree dependencies and preserve buildability through the series. Follow the [kernel patch guide](https://docs.kernel.org/process/submitting-patches.html).

## Kernel and device tree checks

Before freezing a series:

1. Select its current target tree using `MAINTAINERS` and subsystem guidance. Record the exact base commit and any prerequisite series.
2. Build the affected ARM configuration with the required LLVM toolchain. Where relevant, also compile with GCC to catch portability regressions. Review compiler warnings and run targeted static analysis or sparse when the subsystem warrants it.
3. Run `scripts/checkpatch.pl` on the exported patches and `git diff --check`; resolve errors and justify any remaining relevant warnings.
4. For bindings, run `make dt_binding_check` with the appropriate schema selection. For board descriptions, run `make dtbs_check` covering affected schemas and inspect warnings against the unmodified base.
5. Keep bindings, drivers, and board DTS changes logically separate, with dependency order appropriate to the receiving maintainers. Document new compatibles; use appropriate SPDX identifiers and binding licenses. Follow the [DT submission rules](https://docs.kernel.org/devicetree/bindings/submitting-patches.html) and [schema guidance](https://docs.kernel.org/devicetree/bindings/writing-schema.html).
6. Build and test the actual submitted revision on the Fx0. If an integration-only prerequisite is needed for hardware testing, disclose it and distinguish its build from the standalone submission build.
7. Test likely shared-driver regressions on available related hardware, or clearly identify the limit of physical coverage and provide relevant compile coverage.

Prepare `git format-patch --cover-letter --base=<base-commit>` output and identify recipients with the current tree's `scripts/get_maintainer.pl`. The cover letter should summarize behavior, tested hardware, series order, prerequisites, and measured results. Preserve a base commit, exported patch hashes, and exact test references. Do not send mail as part of preparation.

## Nura and bootloader checks

For pmaports, verify current packaging documentation and repository CI rules when implementation starts. Build changed packages with pmbootstrap, check source checksums, run relevant package lint/CI checks, and run `pmbootstrap kconfig check` for kernel changes. Use the community check when pursuing that category. Test image creation, DTB/initramfs deployment, first boot, and kernel upgrades on the actual device.

Prefer generic MSM8226 integration when it can describe the hardware without board-specific hacks. Explain any new device package or forked dependency. A testing-category port is an initial upstream landing point; the project's all-hardware endpoint is stricter than that category's minimum. Community promotion has additional release-testing and upgrade-history requirements. See [Nura device categorization](https://docs.nura.eco/pmaports/main/packaging/device-categorization.html).

For lk2nd, build the actual MSM8226 output variant, test stock bootloader handoff, confirm Fx0 recognition and Linux DTB selection, and verify key handling, fastboot, cold boot, and image-offset behavior. Ensure shared matching changes do not accidentally select the Fx0 configuration for another device.

For userspace changes, run the affected project's checks and attach physical results for the changed behavior. Keep Nura packaging patches traceable to upstream commits or prepared series.

## Public commit contents

Commit source, reproducible build descriptions, human-readable manifests, sanitized hardware facts and logs, and useful measurements. Do not commit raw flash dumps, calibration/provisioning, private identifiers, credentials, or firmware without confirmed redistribution rights. The root ignore rules protect known local locations, but staging review remains necessary.

Retain device-specific firmware extraction and loading procedures so another owner can reproduce the port from their own hardware. Preserve existing licenses on recovered files; choose licenses suitable for the receiving projects for new material. Do not apply a root license to third-party material indiscriminately.

## Submission readiness checklist

The per-change inventory, with targets, prepared material and dependencies, is in
[upstream status](upstream-status.md).

- [ ] Public repository URLs, contributor identity, and maintenance contact are recorded.
- [ ] Tested source manifests identify exact bases and artifacts.
- [ ] All required hardware acceptance entries pass on the final image.
- [ ] Current stable Nura and a maintained kernel are installed and updated.
- [ ] Installation, recovery, and kernel/userspace updates have been demonstrated.
- [ ] Each series is focused, attributed, appropriately licensed, and based on its current target tree.
- [ ] Relevant builds, static checks, schemas, package checks, and physical tests pass.
- [ ] Cover letters and merge-request descriptions contain scope, dependencies, and validation.
- [ ] Kernel recipients are derived from current maintainer information.
- [ ] Public evidence and staged content have been reviewed for unit data and credentials.
- [ ] Remaining downstream patches each have prepared upstream material and a maintenance/removal plan.
- [ ] Sending submissions is left pending explicit instruction; readiness is not reported as acceptance or merge.

Published development history and ready-to-send material meet the submission-preparation objective. Actual mailing-list posts, issue comments, and merge requests are separate external communications.

## Provisioned development repositories

- [Coordination repository](https://github.com/timschmidt/fx0), branch `main`: reviewed plans, tools, pinned sources and sanitized evidence.

- [Linux development fork](https://github.com/timschmidt/fx0-linux), branch `integration/fx0-lts`: maintained Linux 6.18.59 with binding, board, PHY, SMEM, firmware memory and regulator fixes. Four-CPU diagnostic boot, USB and initial eMMC reads/writes are physically verified; full hardware qualification remains pending.
- [lk2nd development fork](https://github.com/timschmidt/fx0-lk2nd), branch `integration/fx0`: Fx0 DTB selection. Diagnostic image builds; physical handoff qualification remains pending.

These are development branches, not submission-ready or fully functional releases. Upstream patch sending and PR creation have not occurred.

## Runtime integration history checkpoint (2026-11-08)

The complete runtime candidate now has a local 35-commit review history at
`57e61d7961e7367d24b65b7969bdfe6f652b85bc`, based on
`4b800b920c7db82e8012a580a17cc2d8ff9d5e66`. Its final tree exactly matches the
39-patch source composition already built and tested. The original 39-commit
draft is retained: four intermediate prefixes require clocks absent from their
qualification DTB. Grouping source patches 33–35 and 37–39 into atomic
integration transitions removes those failures without changing any final
source blob. Every exposed CPR DTB prefix validates against its own binding.

All 35 prefixes pass the 20 affected ARM object targets with `W=1` and no
compiler warnings. These are object checks, not complete intermediate links.
The [exported mail patches](../submissions/linux-runtime-integration/series)
replay from the exact base to the same commit ID, tree and 48 source hashes;
the local thin bundle also verifies and unbundles. The
[history manifest](../manifests/kernel-runtime-history.json) maps the 35 commits
back to all 39 source patches. The frozen source checkout, HEAD and original
index remain unchanged.

The [cover letter](../submissions/linux-runtime-integration/0000-cover-letter.patch)
states the measured build/RAM scope and remaining gates. Tentative routing uses
the integration tree's `MAINTAINERS`; current receiving-tree bases and contacts
must be revalidated before submission. Raw diffs contain no author or sign-off
headers, so reconstruction uses the existing repository identity, preserves
file notices and base history, and adds no DCO/review/test trailers. Contributor
certification, maintainer-base splitting/rebases, complete intermediate links
and physical qualification remain open. The Linux review series remains local;
no mail or PR has been sent. After the owner explicitly authorized GitHub pushes
for all fx0 development, the prepared pmaports package branch was published at
[`4f17b6905c75`](https://github.com/timschmidt/fx0-pmaports/tree/integration/fx0-cpu-runtime-package).
Its remote ref matches the reviewed local commit. See
[history evidence](../evidence/2026-11-08-runtime-integration-history.json) and
[package publication evidence](../evidence/2026-11-08-runtime-kernel-source-package.json).

- [Nura pmaports development fork](https://github.com/timschmidt/fx0-pmaports), branch `integration/fx0-v26.06`: maintained-kernel package/configuration integration. This is an Fx0 development branch; the shared MSM8226 upgrade is not proposed upstream until its external dependencies and regressions are qualified.

The later [CPR startup follow-up](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-cpr-disabled-reference)
is published at `86a9e78ce4b645f6df46d97d165c18875042595f`, after the original
[XO candidate](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-cpr-xo)
at `a9c68b1b25b6`. Both remote refs are independently verified. Their 41/42 raw
patch profiles extend the preserved 35-commit review history; the latter
passes one moduleless 300 MHz startup RAM gate. These development publications
do not claim receiving-tree/DCO readiness or runtime DVFS/feedback qualification.
The r54 pmaports branch still packages the earlier 39-patch source and requires
a separate update and independent Alpine RAM trial.

The [observation source branch](https://github.com/timschmidt/fx0-linux/tree/integration/fx0-cpr-observe)
is published and independently verified at
`b721ebaecd7dc60bbdb1f10c1eb08577f77e0cb8`. Its 43 raw patches replay to the
exact tree, with only read-only debug output added after the qualified startup
source. The host-built family passes signed-module registration and the first
300–384 MHz fixed-corner requests; the original 35-mail review export remains
a separate frozen 39-patch source and must not inherit these later results.
DCO, receiving-tree rebases/routing and broad runtime qualification remain open.
