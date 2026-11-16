NGD child notification admission
===============================

UP/DOWN providers belong to the NGD parent and can outlive a child driver
binding. Startup now records the last requested state under ssr_lock and only
queues a successfully prepared child. The worker checks admission before its
bounded QMI wait and again afterward. Child removal closes admission, cancels
startup outside the mutex, then tears down its resources. Rebind resets state
and completions and replays an observed UP unless DOWN superseded it.

The driver owns one bootstrap runtime-PM reference until registration succeeds.
It now balances that reference on discovery failure and removal, and avoids
reacquiring an already owned reference on DOWN. DOWN also tears down a registered
controller whose existing resume error path left its state DOWN.

Seven maintainer patches start at SLIMbus for-next
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4. The first six are previously qualified
bookkeeping, parent-work and resource ownership prerequisites. The final patch
adds child admission and PM ownership. One corresponding patch advances the
integrated development tree from runtime18 to runtime19. Final driver bytes match;
all other integrated features and platform descriptions are unchanged.

Qualification
-------------

* The composed model executes 17 exact NGD/core callbacks, including actual child
  probe/remove and parent probe/remove. Its platform unregister service invokes
  the actual child remove callback. Forty-two cases execute 461 checks. The
  immediate-parent baseline fails 57 checks; the final candidate fails none.
* Cases cover UP before/during/failed child probe, last-state replay after
  unbind, queued work, interrupted/timed-out waits, repeated notifications,
  external PM references, registration/discovery errors and registered DOWN
  cleanup after power-up failure. Controlled pthread interleavings cover a worker
  waiting for QMI or initializing under ssr_lock against child removal, DOWN and
  parent removal, plus six parent detach and six probe-error schedules.
* Twelve independent negative controls fail as expected: missing worker pre/post
  checks, unbound queueing, removal admission/cancellation, lost replay, probe or
  remove PM leaks, stale PM ownership, skipped registered-DOWN cleanup, stale
  completions and retained power state across rebind.
* PM, QMI discovery/client/power-up, DMA, providers, children and device lifetime
  are synthetic services. Completion waiting has explicit fixture results and
  barriers; it does not implement kernel completion consumption. Work queueing
  and cancellation use a bounded pthread service, not Linux workqueues. No QMI
  packets, hardware, firmware, audio or phone operations occur. Normal
  LeakSanitizer and fail-fast ASan/UBSan protect the host fixture.
* This composed model supersedes the earlier partial parent fixture for current
  child lifecycle qualification. That historical fixture did not execute child
  removal. Its old negative-control counts cannot be treated as current proof
  once child admission and cancellation change the composition.
* Earlier bookkeeping (21 cases/152 checks) and resource ownership (10/114)
  suites and their seven/six controls still pass. Their modeled layouts/services
  alone were extended for the new fields and operations; extracted source bodies
  are unchanged. Actual device/devres/refcount wrappers remain covered separately.
* Eight native ARM/ARM64 NGD/core/messaging/stream objects compile with LLVM21,
  W=1, strict callback diagnostics, ARCH_QCOM enabled and COMPILE_TEST disabled,
  with zero warnings/errors. Compilation used candidate bytes before commit;
  exact hashes bind those bytes to the final commit.
* The integrated development ARM kernel and all 459 modules build. Private normal
  modules_install staging verifies CMS signatures, ELF32 ARM architecture,
  release and dependencies. The incremental build has zero new diagnostics;
  earlier inherited full-tree warnings remain documented. It does not establish
  clean reproducibility, maintained-LTS packaging, install/update/recovery or
  physical acceptance. Prior 20 DTB hashes and every module path remain intact.
* The new patch passes strict checkpatch without signoff checking. Only shallow
  UNKNOWN_COMMIT_ID lookup is excluded; cached primary upstream evidence verifies
  both Fixes targets. Current MAINTAINERS routing is included. No message was sent.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python3, clang-21,
patch and pthread support outside a ptrace sandbox for normal leak checking.
Replay validates manifest hashes, applies all eight patches without Git, fuzz or
offsets, verifies the six-patch admission baseline, and compares every candidate
snapshot. The admission, bookkeeping and ownership before/after suites and all
25 controls execute. Maintainer/runtime generated models must match byte for
byte. Native/full builds are represented by source-bound receipts, not repeated.

Remaining work and attribution
------------------------------

Initial already-running-DSP bootstrap is still absent. Late QMI arrival, consumed
completion semantics, runtime power-up error propagation, master-work and DMA
transfer admission/quiescence remain open. Resource identity, notification
admission and PM ownership do not establish complete physical unbind/rebind or
whole-device acceptance. This work made no live device or radio changes.

Codex generated this fix, models, changelogs, integration and review packet.
Existing human authors, dates and trailers in prior patches are retained.
Human review and DCO certification remain pending; no agent sign-off was added.
Everything remains local and unpublished. No maintainer contact occurred.
Private boot images, raw logs, keys, credentials and per-device data are excluded.
