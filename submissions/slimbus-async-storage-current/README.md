# SLIMbus owned asynchronous response storage

The TID table owns a separately allocated response record. Buffer, length and
completion are captured before readiness publication; late responses never
read the sender's returned transaction frame. Existing response/cancel locking,
software owner identity and separate sender/response PM references are retained.

`slim_cancel_msg()` retires an asynchronous request after its submission call
returns. Cancellation serializes with response copy/completion, matches the
original descriptor and does not fabricate reply completion. One asynchronous
request may use a descriptor at a time. Keep the descriptor, buffers and completion
valid until both submission returns and response completion or cancellation.
A lost reply requires explicit cancellation. There is no automatic timeout or
success/error completion on cancellation or controller shutdown; the client
owns its wait/teardown policy.

Controller unregister closes TID admission and drains prepared/unprepared
records before removing clients, balancing only response PM references. The
empty IDR tree is destroyed. Initialization precedes NGD RX publication and
registration preserves an initialized transaction domain. Transport producers
and active calls still require their own admission and quiescence protocol.

The fourteen-patch maintainer series applies to official SLIMbus base
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4. One runtime patch applies to integration
26. Full snapshots, source identities, configs, receipts and hashes are pinned.
The runtime changes only core.c, messaging.c, qcom-ngd-ctrl.c, private slimbus.h
and the public slimbus.h header.

## Qualification

Twenty-two byte-exact callback/helper bodies pass 1,149 cases and 44,419 checks.
The pre-change storage model has 102 failures across the same 1,149 cases and
44,421 checks (conditional API checks differ). All 21 ownership controls fail
at their expected assertions. Cases cover responses after sender return, sender
metadata reuse, early replies, explicit cancellation, duplicate active
submissions, allocation/PM/DMA failures, response-copy races with cancellation
and unregister, all 255 TIDs occupied, IDR exhaustion and full-table drain.

Readiness/parent-child lifecycle (71/1,079; 29 controls), power (626/13,284;
12 controls), bookkeeping (21/152; six controls) and TX (1,093/47,497; twelve
controls) pass again. This packet replays 80 controls. Power with the recorded
6.18.63 PM implementation passes 626/12,708 within the synthetic PM fixture;
this is not a complete LTS backport or recovery test. Lifecycle fixtures use
synthetic transaction services; actual transaction helpers execute separately
in the response model. Three older DMA/ownership/BAM generated programs remain
byte-identical within their original synthetic-service scope. The 41,147 TX
packet bytes remain identical.

Eight native ARM/ARM64 NGD/core/messaging/stream objects build with LLVM21 W=1,
strict callback diagnostics, QCOM enabled and COMPILE_TEST disabled, without
compiler diagnostics. The incremental full ARM kernel and 459 modules build,
stage and pass CMS, ELF32 ARM, release and dependency checks. Module paths and
20 prior DTB hashes are preserved. This is not clean package reproducibility
or physical acceptance. The first full build had inherited warnings.

Unfiltered patch checkpatch reports two warnings: the existing IDR initializer
moved to the new initialization helper is deprecated, and the shallow checkout
lacks the Fixes commit object. The latter is verified against the cached public
primary commit diff; with that metadata warning excluded only the inherited
IDR warning remains. There are no other style diagnostics. The existing IDR
API is retained; no compiler warnings are added. Agent Signed-off-by is omitted
as required by kernel policy. Human review and DCO remain pending.

## Offline replay

Run `python3 -B replay.py /tmp/fx0-async-replay-UNUSED` with Python, patch,
clang-21 and sanitizer runtimes. Choose a nonexistent output directory outside
this packet. Replay verifies manifest hashes, applies fifteen patches without
fuzz or offsets, verifies both prerequisite prefixes and final snapshots, then
runs the response baseline/candidate, lifecycle/PM/TX regressions and 80 controls.
Maintainer/runtime generated models and TX packet streams must match. Git,
Internet, phones and devices are unnecessary. Native/full-kernel/module/DTB and
schema builds are separate recorded evidence, not repeated by replay.

All IDR, PM, allocator, device, completion, response and DMA services are
synthetic. Kernel callback bodies, message types and constants are extracted
without rewriting their logic. Fixture record allocations remain physically
live through each logical lifetime audit; logical frees and leaks are counted
before cleanup. Completion addresses are logical tokens, never dereferenced.
Baseline returned stack pointers are detected without dereferencing them or
attempting actual stale memory access. Pthreads force selected schedules rather
than executing Linux scheduling. Normal LeakSanitizer and fail-fast ASan/UBSan
remain enabled. The fixture accepts inherited partial initializers as the
kernel does; other enabled diagnostics remain errors.

Late old wire replies after numeric TID reuse remain indistinguishable. RX
resubmission, master/external transfer admission, attached hardware/remote
firmware stop ordering, full recovery, initial DSP bootstrap, endpoint generation
and maintained-LTS packaging/recovery remain open. No physical DMA, firmware,
audio, phone or radio operation runs here. Public source metadata was downloaded
over the existing connection without scans or network configuration changes.

Codex generated the fix, fixtures and evidence. Prior human authorship/history
and attribution remain intact. The draft is unsent, and heads are unpublished.
Private keys, boot material, credentials, firmware blobs and per-unit data are
excluded. Public source/model license text is retained in LICENSES.
