NGD persistent QMI readiness and startup admission
=================================================

QMI discovery now publishes a readiness predicate and a serialized endpoint.
Startup waits on that predicate instead of consuming a completion. A late server
announcement requeues an UP request whose earlier wait expired. Repeated UP uses
the same readiness until the matching endpoint disappears. Deleting an older
node/port leaves a newer endpoint intact, and the worker rechecks readiness under
ssr_lock after waiting before initializing a client.

The wait predicate also observes DOWN and child closure. Lifecycle changes notify
waiters. Parent removal, parent probe unwind and child removal close admission
before synchronously cancelling startup, with the worker mutex released. This
also excludes QMI discovery as a new startup producer before parent IRQ shutdown.
Child rebind starts a fresh readiness/endpoint session and preserves last UP/DOWN.

Ten maintainer patches start at SLIMbus for-next
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4. Nine prior bookkeeping, lifetime, DMA
and resume-error prerequisites precede this fix. One matching integration patch
advances runtime21 to runtime22. Final driver bytes match; all other integrated
features and platform descriptions are unchanged.

Qualification
-------------

* The composed model executes 22 exact driver/core callbacks plus the actual QMI
  ops table. Fifty-two cases execute 653 checks. The immediate parent fails 67 checks;
  the candidate passes all. Coverage includes discovery before/during/after child
  probe, expired/interrupted waits, repeated UP, matching/stale deletion, endpoint
  changes across a positive wait or admitted initialization, failed discovery,
  child rebind, producer events during cancellation, parent errors and PDR cycles. Valid zero node/port components are covered.
* Sixteen independent controls fail: lost late retry, consumed readiness, missing
  post-wait readiness, unlocked endpoint updates, stale deletion or missing either
  endpoint component, open admission, cancellation under the mutex, producer
  guards removed, missing notifications and parent cancellation before QMI closure.
* QMI transport/handles, PM, DMA, device enumeration, completions and wait/work
  scheduling are logical services. Old completion tokens are consumed; new wait
  predicates are re-evaluated with controlled pthread interleavings and virtual
  deadlines. Notification events are counted, including completion notifications.
  The Linux scheduler/waitqueue/QRTR/device machinery and real DMA do not execute.
* Fixture allocations stay physically live through logical ownership audits.
  Deliberately invalid cancellation under a worker mutex is recorded instead of
  performing a deadlock. Normal LeakSanitizer and fail-fast ASan/UBSan protect the
  fixture. No sockets, firmware, DMA callbacks, audio, phone or radio operations run.
* The earlier admission fixture's forced wait-result service is superseded by
  this composed QMI event/predicate model. Prior power-error tests retain 626 cases
  per PM profile: current PM passes 13,284 checks, and the separate cached 6.18.63
  callback contrast passes 12,708 while retaining its hard-error latch and blocked
  retry. Full LTS driver/build/recovery remains unqualified. DMA (85/1,150),
  bookkeeping (21/152) and ownership (10/114) suites also pass with exact callbacks.
* Thirty-seven earlier independent controls remain effective. One historical
  bookkeeping interruption control is redundant: an unavailable service now also
  blocks at the post-wait readiness guard. The real wait premise is preserved and
  the redundant control retired; the driver retains its ret <= 0 guard. The
  audit is included. All 53 current controls run during packet replay.
* Eight native ARM/ARM64 NGD/core/messaging/stream objects build with LLVM21, W=1,
  strict callback diagnostics, ARCH_QCOM enabled and COMPILE_TEST disabled, with
  zero warnings/errors. Final source hashes bind compilation to the commit.
* The integrated development ARM kernel and all 459 modules build and stage.
  CMS signatures, ELF32 ARM, release and dependency metadata pass. All module
  paths and prior 20 DTB hashes remain intact. This incremental build has zero
  new diagnostics; documented inherited full-tree warnings remain. Clean builds,
  maintained-LTS packaging/install/update/recovery and physical acceptance remain.
* The patch passes strict checkpatch without signoff checking. Only shallow
  UNKNOWN_COMMIT_ID lookup is excluded. Cached original driver and SSR-introduction
  evidence verify Fixes targets. Current routing is included; nothing was sent.
  QMI dispatch/release and wait/completion API evidence explains lock/lifetime
  assumptions. Discovery release remains outside ssr_lock; client handles have
  no server callbacks. Full API source snapshots are supplied for review.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python3, clang-21,
patch and pthread support outside a ptrace sandbox for normal leak checking.
Replay validates manifest hashes and all eleven patch applications without Git,
fuzz or offsets, including the seven/eight/nine-patch DMA/power/QMI baselines.
Five current before/after suites, the separate LTS PM contrast and all 53 controls
execute. Maintainer/integration generated models must match byte for byte. Native
and full builds are represented by source-bound receipts, not repeated.

Remaining work and attribution
------------------------------

Registered-client recovery when endpoints change without a normal PDR DOWN cycle,
parent readiness against concurrent child binding, master/external TX/DMA
quiescence, RX resubmission and timeout lifetime, complete failed-start/LTS error
recovery and the original initial DSP bootstrap remain required. This qualifies
initial/repeated-UP readiness and startup producer closure, not complete physical
transport recovery or whole-device acceptance. No live device/network changes.

Codex generated the fix, models, changelog, integration and packet. Prior human
attribution/dates remain. Human review and DCO certification are pending; no agent
sign-off was added. Everything remains local and unpublished, with no maintainer
contact. Private keys, credentials, boot material and per-device data are excluded.
