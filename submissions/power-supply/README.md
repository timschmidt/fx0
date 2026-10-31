# Power-supply draft submissions

Three independent draft series target Sebastian Reichel's
[power-supply tree](https://git.kernel.org/pub/scm/linux/kernel/git/sre/linux-power-supply.git),
`for-next` pinned on October 30, 2026 to
`f0f400459bf6a037e70768de623fff3f8920b8bb` (7.3-rc1). Each applies directly to
that base. They do not depend on the Fx0 board or experimental BMS patches.
Exact source, configuration and object hashes are in the
[submission manifest](../../manifests/power-supply-submissions.json).

## Charge-control series

One patch exposes standard `auto` and `inhibit-charge` modes on SMBB. Charge
inhibition preserves the USB power path, forced-battery mode and other control
bits. Online healthy inhibited charging reports Not charging. Unsupported modes
and register failures return errors.

The [submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-charge-control-v2)
passes 1,051 actual helper/property/status/fault cases under ASan/UBSan and an
ARM LLVM22 W=1 object build on the maintainer tree, with no warnings. Its LTS
counterpart also passes a full kernel build and three RAM-only inhibit/resume
cycles on the Fx0. The current maintainer-tree kernel has not been booted on the
Fx0. The observed residual IADC reading is not independently measured zero
current. See [hardware evidence](../../evidence/2026-10-30-smbb-charge-control.json).

## Charger Manager thermal series

Two patches prevent a duration expiry from bypassing a thermal stop and inhibit
monitored charging on runtime temperature-read errors. Health becomes Unknown
until a valid sample clears the existing hysteresis. Legacy configurations with
temperature monitoring disabled retain their behavior.

The [submission branch](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-charger-manager-v2)
passes 8,330 cases executing the actual decision, regulator and property
functions under ASan/UBSan. The two original failures reproduce on unmodified
upstream code. ARM LLVM22 W=1 object compilation on the maintainer tree and
strict checkpatch pass without diagnostics. The LTS module also builds, but
Charger Manager is not enabled on the phone. Probe-time sensor requirements,
actuator errors and complete policy qualification remain separate work. See
[regression evidence](../../evidence/2026-10-30-charger-manager-thermal.json).

## Battery description binding

The third [binding-only series](https://github.com/timschmidt/fx0-linux/tree/submission/fx0-smbb-battery-info-v2)
permits SMBB's standard `monitored-battery` reference. The existing supply core
already reads the selected constant data. Modified documentation and a generated
device DTB pass on the maintainer tree with all referenced schemas available.
The existing r4 kernel also consumes firmware-selected data on the phone. This
adds no gauge estimator or charging policy. See
[handoff evidence](../../evidence/2026-10-30-battery-profile-handoff.json).

## Reproduce and review

Apply only the desired directory's patches to a clean branch at the pinned
base with `git am`. Run the corresponding host test from
[charge control](../../diagnostics/smbb-charge-control/README.md) or
[Charger Manager](../../diagnostics/charger-manager-thermal/README.md).

For ARM compilation use `ARCH=arm LLVM=1 LLVM_IAS=1 LOCALVERSION= W=1` with
LLVM22. Start from `multi_v7_defconfig`, enable POWER_SUPPLY, REGULATOR, SPMI and
MFD_SPMI_PMIC, and select the relevant driver as a module with `scripts/config`:
CHARGER_QCOM_SMBB or CHARGER_MANAGER. Run `olddefconfig`, verify that module
selection survived dependency resolution, then build
`drivers/power/supply/qcom_smbb.o` or
`drivers/power/supply/charger-manager.o`. These are current-tree object checks,
not a full current-upstream kernel/module link or hardware boot.

Drafts remain unsent and have no invented Signed-off-by or Tested-by trailers.
Full checkpatch on the draft mail patches reports the missing author sign-off;
the strict source/style pass uses `--no-signoff` and has zero other diagnostics.
Author sign-off, final recipient/base review and broader configuration checks
remain before submission. Source-review readiness does not establish complete
Fx0 charging protection or close the all-hardware bringup goal.

## AI-assistance disclosure

On October 31, 2026 the commit messages were updated to follow
`Documentation/process/coding-assistants.rst` and `generated-content.rst` in the
target tree: a paragraph stating that Claude Opus 5.5 found the problem, wrote
the change and the message and ran the tests, plus an `Assisted-by: LLM`
trailer. The earlier form, `Assisted-by: Claude:claude-opus-5-5`, does not
match the documented format. The code is unchanged (identical trees). The
rewritten commits are on the `-v2` branches; the original branches remain
as published.
