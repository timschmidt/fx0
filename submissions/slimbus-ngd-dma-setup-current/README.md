NGD reusable DMA setup and error propagation
============================================

DMA setup now prepares TX before issuing RX descriptors, because an RX master
capability can immediately queue TX work. Partial RX preparation/submission
failures terminate queued descriptors and release both channel resources. Released
channel pointers are cleared. Existing complete channel pairs are reused after a
capability timeout rather than overwritten by another initialization attempt.

Message buffers are allocated once using the controller parent's managed DMA
allocation and reused across channel sessions. Their bounded parent lifetime
matches their allocation device and outlives child binding and runtime sessions.
The parent drains its controller work before devres cleanup. Setup errors reach
both power_up branches before the queue-enable write.

Eight maintainer patches start at SLIMbus for-next
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4. Seven previously qualified bookkeeping,
parent lifetime and child admission prerequisites precede the new DMA setup fix.
One corresponding integration patch advances runtime19 to runtime20. Final
source bytes match; all other features and platform descriptions are unchanged.

Qualification
-------------

* Seven exact driver callbacks execute 85 cases and 1,150 checks. The immediate
  parent fails 479 checks; the candidate passes all. Every one of 32 RX prepare
  and 32 submit failure positions is exercised, together with request/allocation
  failures, persistent failure, both power-up branches, ASLEEP wake, repeated
  setup, capability-timeout retry and ten channel restart sessions.
* Thirteen independent controls fail: unmanaged buffers, repeated allocation,
  RX before TX, missing TX unwind, stale RX/TX pointers, queued RX not terminated,
  ignored submit errors, setup errors discarded, either power-up branch
  discarding errors, loss of live-pair reuse and incorrect allocation errno.
* DMA channels, descriptors, MMIO, QMI, completions and devres are logical
  services. Logical ordering is audited while all fixture allocations remain
  physically live; baseline resource leaks are recovered only after the audit.
  No DMA callbacks, actual DMA, hardware, firmware, audio or phone operations run.
  Normal LeakSanitizer and fail-fast ASan/UBSan protect the host model. The
  managed allocation service models the documented parent devres contract;
  it does not execute Linux devres or prove concurrent transfer teardown.
* The composed child/parent admission suite (42 cases/461 checks), bookkeeping
  suite (21/152), and device/descriptor ownership suite (10/114) still pass.
  Their 25 controls remain effective. The older partial parent fixture is
  historical; current admission evidence invokes actual child removal from the
  parent unregister service. Every extracted callback body is preserved.
* Eight native ARM/ARM64 NGD/core/messaging/stream objects compile with LLVM21,
  W=1, strict callback diagnostics, ARCH_QCOM enabled and COMPILE_TEST disabled,
  with zero warnings/errors. Candidate-byte hashes bind the pre-commit native
  compilation to the final source commit.
* The integrated development ARM kernel and all 459 modules build. Normal private
  staging verifies CMS signatures, ELF32 ARM architecture, release and dependency
  metadata. Module paths and the prior 20 DTB hashes remain intact. This is an
  incremental build with zero new diagnostics; documented inherited full-tree
  warnings remain. Clean reproducibility and maintained-LTS normal packaging,
  install, update, recovery and physical acceptance remain open.
* The new patch passes strict checkpatch without signoff checking. Only shallow
  UNKNOWN_COMMIT_ID lookup is excluded. Cached original upstream driver functions
  verify the Fixes target. Current MAINTAINERS routing is included; nothing sent.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python3, clang-21,
patch and pthread support outside a ptrace sandbox for normal leak checking.
Replay checks manifest hashes and all nine patch applications without Git, fuzz
or offsets. Six- and seven-patch prefixes must match the admission and DMA
baselines. Four before/after suites and all 38 controls execute; generated
maintainer/integration models must match byte for byte. Native/full builds are
represented by source-bound receipts, not rerun by this entry.

Remaining work and attribution
------------------------------

Returning a DMA setup error from power_up is one prerequisite for full startup
recovery. Runtime resume and controller enable still discard these errors and
must be fixed after their resource/lifetime implications are qualified. No
complete error recovery or physical DMA acceptance is claimed. Master work,
external TX admission, RX callback resubmission and DMA teardown concurrency,
late QMI arrival/completion consumption and initial already-running-DSP startup
remain required work. Avoid introducing frees before transfer quiescence.

Codex generated this fix, models, changelog, integration and packet. Prior human
attribution and dates are preserved. Human review and DCO certification remain
pending; no agent sign-off was added. All heads remain local and unpublished.
No maintainer contact occurred. Private keys, boot material and device data are
excluded. No live device or network configuration changed.
