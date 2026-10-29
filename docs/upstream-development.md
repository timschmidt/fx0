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

- [Linux development fork](https://github.com/timschmidt/fx0-linux), branch `integration/fx0-lts`: maintained Linux 6.18.59 with initial binding and UART/USB board commits. Physical boot qualification remains pending.
- [lk2nd development fork](https://github.com/timschmidt/fx0-lk2nd), branch `integration/fx0`: Fx0 DTB selection. Diagnostic image builds; physical handoff qualification remains pending.

These are development branches, not submission-ready or fully functional releases. Upstream patch sending and PR creation have not occurred.
