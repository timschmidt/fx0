# Boot APC protection for paired PM8226 MX voters

Pronto and regulator registration can request a lower normal L3 voltage before
CPU-domain attachment enables CPR's retained AO vote. The inherited APC rail is
already live, so an empty AO voter leaves a boot-order gap despite the preceding
constraint-domain fix. The pinned before model reproduces 2,180 failed checks.

An optional qcom,boot-apc-supply makes the RPM provider resolve and read APC
before registering either voter. Validate the readable positive APC voltage
and the supported AO bounds, then hold an ACTIVE enable and the AO maximum.
Registration clamps, disabled cached requests and early Pronto startup cannot
lower this temporary floor. Reject unreadable/out-of-range APC and automatic
AO boot-on/always-on enables before publication or RPM writes. Read APC only in
probe: nested regulator-dependent locks make cross-provider reads from vote
callbacks unsafe. No APC pointer is stored in the pair or used by its callbacks.

Remove the hold only after an enabled AO request covers the rounded-up boot
APC voltage and receives an acknowledgment. Keep it after failed or uncertain
handoff, including both applied and unapplied timeout outcomes. The existing
real CPU attach callback rechecks current APC against its calibrated plan
before establishing/enabling MX and switching the clock. A stale plan fails
before changing MX. CPR retains its MX reference while APC can remain live.
After handoff, lower CPU requests can lower MX again: the boot maximum is not
a permanent floor. This adds no SLEEP policy for the live APC rail.

Only the experimental CPU board names the boot APC supplier. The ordinary
board and nineteen other DTBs are byte-identical. CPU/CPR OPPs and all earlier
CPU, display, IIO, NFC, camera, power and SLIMbus dependencies are retained.

The boot model composes 28 exact functions, five operation tables and one
PM8226 catalogue, including machine voltage constraints, probe/registration,
the paired provider, correlated RPM replies, CPR voltage sequencing and the
real CPU clock handoff callback. It passes 317 cases / 57,600 checks after
2,180 failures / 34,699 checks in the same before model. Cases include both
voter orders, 88 synthetic APC values, non-grid handoff thresholds, deferred
CPR, early Pronto start/stop, stale CPU plans, invalid policy/readings,
registration failures, failed handoff, applied/unapplied timeouts and dynamic
voltage scaling after successful handoff. Eleven boot controls are rejected.
The unguarded paired-voter suite remains at 3,726 cases / 202,962 checks and
sixteen controls; the legacy suite remains at 6,310 cases / 77,934 checks and
fourteen controls. All 1,280 active-request trace bytes match the predecessor.

OF/devres, registration, regulator services, APC reads, clocks, register reads,
locks, allocation, completions and firmware-state/RPMsg endpoints are logical
services. Calibration plans are synthetic; no fuse contents are read. Normal
LSan and fail-fast ASan/UBSan are enabled. These tests do not execute kernel
concurrency, firmware or electrical hardware. Source/runtime callback bodies
and catalogue match. Their exact probes differ only in the runtime's existing
allocator spelling. Both variants are replayed, with that difference explicit.

Native ARM/ARM64 provider/core builds use ARCH_QCOM, COMPILE_TEST off, LLVM21
W=1 and strict callback checking: four objects, zero diagnostics. The full
development kernel and 459 modules build; CMS, ELF32 ARM, release and dependency
checks pass. The incremental stage adds no diagnostics; inherited whole-kernel
warnings remain. Twenty DTBs pass full schema validation with the same sixty
inherited DTC warnings and no new ones. Eleven invalid binding instances are
rejected. Compiled boot APC/CPR supplier phandles and existing OPPs match. Forty
prior DTB artifacts and the previous module stage remain untouched. This is
not clean maintained-LTS packaging, installed update/recovery or a phone trial.

Run `python3 -B replay.py /tmp/new-boot-apc-replay` with clang-21 and patch,
outside ptrace for normal LSan. It verifies all pinned inputs, reproduces the
before failure, applies two source and three runtime patches without fuzz or
offset, checks both boot compositions and retained paths, and rejects all
forty-one controls. It needs no Git, network or device. Source-before includes
the earlier paired provider; its correlated RPM transport and CPR driver/header
are explicitly borrowed runtime prerequisites. Full native/kernel/DTB rebuilds
need the complete pinned trees in dependencies.json. Binding patches use U2
context to avoid checkpatch interpreting an unchanged YAML standby field as an
email signature; no source/message or diagnostic-category suppression is used.

Actual boot compatibility, bootloader/firmware electrical behavior and kernel
concurrency remain unqualified. APC outside the supported AO ceiling fails
closed. Global preparation/abort/reentry rollback and CPU/L2 SPM/SCM/RPM/MPM
entry/wake topology remain incomplete; the CPR deep-suspend guard remains.
SLIMbus hardware stop, suspend rollback and endpoint recovery, the original r2
display/IOMMU fault, maintained-LTS public-source packages/update/recovery,
physical hardware/interactions and all seven original requirements remain in
scope. The preceding audit's Pronto/WCNSS correction remains authoritative.

Codex generated the source, tests, audit and draft. Existing attribution is
retained; no Signed-off-by was invented. Human review/DCO remain pending.
All new heads are local/unpublished, the draft is unsent, and no phone, firmware,
audio, radio, WiFi scan or network configuration operation occurred.
