# Bounded CPU SPM and CPU-idle admission/error handling

A mode write that never reads back leaves the old void SPM setter retrying
forever. The exact parent helper passes 101 synthetic dropped writes without
returning, where a logical watchdog stops observation. This is an observed
unbounded software loop, not a claim that the helper returned a timeout or that
a real device hang/bus fault was reproduced. The original introduction commit
7ce75bb2c05ef6949ab0b93633e052f46855690d and its added loop are verified against
public upstream patch data and local Git metadata for the Fixes reference.

Return mode errors after at most fifty write/readback attempts per command.
Before a mode error returns, disable and verify EN while preserving inherited
bypass and all non-INDEX bits. INDEX can reset after END and has no meaning
while disabled. Retry one failed disable and stop fatally after a second
unverified attempt so generic WFI cannot execute an unknown collapse mode.
This bounds software attempts, not MMIO bus response time or bus exceptions.
Readback already matching an idempotent write succeeds even if that write was
dropped. All other successful SoC mode fields are retained. Only MSM8226 v2
gains PC index 5, sharing its unchanged identical 20-byte vendor SPC program.

CPU-idle checks SPC before cpu_suspend and attempts standby after either wake
or abort. Retain the suspend error or report restore failure after successful
wake. A failed restore leaves SPM disabled before returning. The actual CPU-PM
macro keeps notifications and context tracking balanced on nonfatal paths.
Publish controller drvdata after standby and regulator setup succeed. Preflight
all present suppliers before warm-vector setup or any CPU-idle registration.
Available unready suppliers defer before consumers are registered; unsupported
or disabled CPU nodes skip. Temporary OF/device references balance. Existing
per-CPU allocation/DT/registration failure policy is unchanged. CPU-idle requires
built-in SPM, whose lifetime persists with bind attributes suppressed.

Twelve exact functions, two actual CPU-PM macros, actual SoC catalogues, match
tables and idle template compose 1198 passing cases / 1184094 checks. Cases
cover all declared SoCs, each mode, unsupported/out-of-field requests, dropped
and corrupt writes, stale applied readback, idempotent writes, index reset,
both recovery attempts and fatal policy, suspend wake/abort, failed CPU-PM
admission, supplier/resource/probe failures, all sixteen readiness combinations
and balanced references. Twenty-three mutants fail intended assertions with
normal LSan and fail-fast ASan/UBSan; compiler errors, crashes and sanitizer
faults do not count. Isolated PC-alias and retry positives precede their mutant
checks so a legitimate fatal policy cannot be mistaken for control success.

MMIO, delays, CPU suspend/SCM, warm-resume outcomes, CPU-PM notifications,
context tracking, OF/devres, regulator registration and CPU-idle registration
services are synthetic. Fatal policies use caught logical fatal paths; no real
panic or firmware call is executed. Real concurrency, MMIO bus exceptions,
electrical effects and physical acceptance remain unqualified.

Four native ARM/ARM64 ordinary/RT profiles compile 42 SPM/PM/regmap objects,
including the ARM-only CPU-idle caller on ARM. Exactly reproduced parent RPMsg
documentation warnings remain: two per profile, no new diagnostics, no category
suppression. Both formatted patches pass strict checkpatch. The complete
incremental development kernel and 459 modules build; signatures, ELF32 ARM,
release and dependencies pass. Module paths are preserved. Clean maintained-LTS
reproducibility, normal package update/recovery and phone acceptance remain
pending. Prior L2 and sleep-voter generated models are byte-identical; those
suites are retained without rerunning. No DT/schema inputs change; the prior
twenty validated DTB artifacts are hash-verified and are not claimed rebuilt.

Run `python3 -B replay.py /path/to/fresh-private-output` with clang-21 and patch
outside ptrace for normal LSan. Replay verifies every input, observes the
parent retry loop, applies source and runtime patches without offset or fuzz,
runs both source compositions and rejects all 23 controls with no Git/network
or device. Compiler temporaries stay in output. Source/runtime SCM headers are
separate pinned prerequisites: only the same exact L2_ON constant is used by
this model. Full native/kernel/module builds require complete pinned trees.

Full CPU/APC/MX/clock preparation, CPR quiescence, CPU program/state validation,
L2 cache clean, SCM L2_OFF and warm resume, RPM freeze/drain/context ownership
and MPM wake topology remain incomplete. The checked CPU and L2 backends still
have no full system-collapse caller. Keep the CPR deep-suspend guard and the
covering SO ceiling. No low CPU sleep floor is installed by this change.

All seven original requirements and existing attribution remain intact,
including the original r2 display/IOMMU issue, all hardware/interactions and
physical acceptance, maintained-LTS public-source packaging/update/recovery
and attributed review. Independent SLIMbus hardware-stop, PM rollback and
endpoint recovery remain open. Codex generated this source, tests, audit and
draft without inventing a Signed-off-by. Human review and DCO remain pending.
All new heads are local/unpublished and the draft is unsent. No phone, radio,
audio, WiFi scan or network-configuration operation occurred. Only public
upstream source/history was downloaded over the existing connection.
