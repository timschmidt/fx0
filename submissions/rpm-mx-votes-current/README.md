# Paired PM8226 L3 / MX votes

Pronto-v2 requests a fixed 1.2875 V on Madai's L3 rail. Regulator core includes
that voltage constraint even after its local enable reference is released.
CPR needs floors up to 1.3375 V, so putting both consumers on the same regulator
device rejects higher CPU floors. The exact core model reproduces eight such
rejections across enabled and disabled Pronto references.

Add an optional PM8226 l3-ao voter with its own core constraint domain. Combine
the normal and active-only cached voltage floors with MAX, enables with OR,
and loads with a saturating sum. Keep disabled voltage requests, following the
vendor RPM aggregation policy. The normal voter alone defines SLEEP. Initialize
that sleep set before the first paired ACTIVE write because RPM otherwise
inherits ACTIVE; invalidate its cache after an uncertain/partial write or a
cached normal change. Reject suspend settings on l3-ao and preserve explicit
normal sleep settings during active updates. Parent-owned inline slots exist
before either regulator registration and never dereference a peer rdev.

Only the experimental Madai CPU/CPR device tree selects l3-ao. Pronto remains
on l3, its voltage limits are unchanged, and the ordinary board source/DTB is
unchanged. The driver and binding are opt-in features, not a claimed existing
upstream CPR regression; the experimental board correction identifies its
introducing commit. MX-consumer-source-audit.json corrects the previous audit's
mistaken SDHCI consumer attribution to Pronto/WCNSS. The sealed parent archive
and audit are retained unchanged.

The host model composes 25 exact functions, five exact operations tables and
the exact PM8226 catalogue, including core constraint checks, provider writes,
probe/initialization, correlated RPM replies and CPR voltage sequencing. It
passes 3,726 cases / 202,962 checks with both applied and unapplied timeouts,
allocation/send failures, NACKs, stale replies, boundary replies, two voter
orders, registration failures, callbacks during first registration, cached
disabled requests, sleep overrides, partial failures, reverse lifetime release,
load overflow and retained CPU floor recovery. Sixteen fault controls fail.
The legacy regulator suite passes 6,310 cases / 77,934 checks and fourteen
controls; all 1,280 active trace bytes match the previous provider.

These are deterministic logical OF/devres, registration, regulator service,
locking, completion, allocation, firmware-state and RPMsg models. Normal LSan
and fail-fast ASan/UBSan are enabled. They do not execute real kernel concurrency
or establish firmware, boot handover or electrical behavior. The source/runtime
callbacks and catalogue are byte-identical. The exact probe differs only in
the runtime's preexisting allocator spelling, recorded and modeled explicitly.
The native ARM/ARM64 provider/core builds use actual headers with ARCH_QCOM,
COMPILE_TEST off, LLVM21 W=1 and strict callback checking: four objects, zero
diagnostics. The full combined development kernel and 459 modules build; module
CMS, ELF32 ARM, release and dependency checks pass. The incremental build has no
new diagnostics; inherited whole-kernel warnings remain. This is not clean
maintained-LTS packaging, installed update/recovery or physical acceptance.

Binding examples and all twenty full board DTBs pass schema validation. The
nineteen outside the experimental CPU target are byte-identical. The same sixty
inherited DTC warnings remain, with no new ones. Compiled CPR/Pronto supplier
phandles and retained CPU/CPR OPPs pass; six invalid binding instances are
rejected. Ten earlier non-regulator model source dependencies are unchanged by
the three-path runtime change. Earlier DTB outputs and module stages remain.

Run `python3 -B replay.py /tmp/new-mx-voter-replay` with clang-21 and patch,
outside ptrace for normal LSan. It verifies all pinned files, applies both
source patches and three runtime patches without fuzz/offset, runs source and
runtime compositions and the legacy before/after suite, and rejects thirty
controls. It needs no Git, network or device. The source-before provider includes
the parent's standard sleep callbacks; the RPM transport and CPR header are
explicitly borrowed runtime prerequisites, not unmodified official source.
Full native/kernel/DTB rebuilding needs the pinned complete trees described in
dependencies.json; the focused offline model replay does not rebuild them.

Multi-message ACTIVE/SLEEP updates are not atomic. Complete prepare/abort/reentry
rollback, inherited live APC/MX boot ordering, CPR feedback/IRQ quiescence,
CPU/L2 SPM/SCM entry/exit, RPM message/IRQ ownership and MPM wake topology remain
required. The CPR deep-suspend guard remains. SLIMbus hardware stop, suspend
rollback and endpoint recovery, all other nonaudio hardware and interactions,
physical acceptance, current maintained-LTS packages/update/recovery, source
currency and all seven original bring-up requirements remain open as applicable.

Codex generated these changes, audit and host qualification. Existing authorship
and copyright remain; no Signed-off-by was invented. Human review/DCO remain
pending. These heads are local and unpublished and the draft is unsent. No phone,
firmware, audio, radio, WiFi scan or network configuration operation occurred.
