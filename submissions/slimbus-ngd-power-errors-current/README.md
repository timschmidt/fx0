NGD resume-error propagation and ownership
==========================================

Runtime resume now returns the actual power-up error. Controller enable checks
both its direct callback and PM framework paths before registering the bus or
consuming the bootstrap PM reference. A failed initial wake releases the newly
created QMI client and retains bootstrap ownership. A failed wake of an existing
controller retains that controller, its children and its existing client.
Nonnegative PM success, including the positive already-active result, is accepted.
Prepared DMA resources retain their bounded ownership for retry or normal teardown.

Nine maintainer patches start at SLIMbus for-next
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4. Eight previously qualified bookkeeping,
parent/child lifetime and DMA setup prerequisites precede this fix. One matching
integration patch advances runtime20 to runtime21. Final driver bytes match;
all other integrated features and platform descriptions are unchanged.

Qualification
-------------

* The composed model executes 15 exact driver/core/PM callback bodies: DMA setup
  and power-up, runtime resume, controller enable, child removal, core bookkeeping
  and the PM core's rpm_callback. QMI, MMIO, DMA, completion, child enumeration,
  runtime-PM scheduling/state and devres services are logical. The full Linux PM
  engine, supplier/locking machinery and DMA callbacks do not execute.
* Each PM profile exercises 626 cases. Current PM passes 13,284 checks after
  2,435 parent failures. The actual cached 6.18.63 rpm_callback passes 12,708
  checks after 2,652 failures. That contrast verifies its hard-error latch and
  blocked retry. It does not qualify an LTS driver port, kernel build or recovery.
  Source hashes and cached-tree version metadata identify that limited profile.
* Cases include every RX descriptor prepare/submit position through initial and
  registered wake, channel/allocation faults, QMI wait/request and capability
  errors, PM framework errors, direct versus framework resume, positive success,
  initial versus existing ownership, explicit retry and removal. Registered wake
  tests verify that existing parent buffers avoid fresh allocation failures.
* Twelve deliberate regressions are rejected: swallowed runtime/direct/framework
  errors, leaked new or dropped existing clients, early bootstrap release,
  registration after failed wake, positive success treated as error, skipped
  registered wake, flattened errno at either layer and lost prepared DMA reuse.
* Logical allocations remain physically live through the audit; baseline leaks
  are recovered afterward. Normal LeakSanitizer and fail-fast ASan/UBSan protect
  the fixture. No actual DMA, DMA callbacks, firmware, audio, phone or network
  operations occur in tests. Explicit retry tests invoke enable directly;
  service discovery and worker retry scheduling remain separate work.
* Prior DMA (85 cases/1,150 checks), admission (42/462), bookkeeping (21/152) and
  resource ownership (10/114) suites pass, together with their 38 controls. The
  admission fixture now obtains an existing registration before injecting its
  failed wake; it no longer requires the false initial registration being fixed.
  Its baseline still fails 57 checks. Unchanged DMA/ownership generated models
  were byte-verified against earlier receipts, then freshly executed by replay.
* Eight native ARM/ARM64 NGD/core/messaging/stream objects compile with LLVM21,
  W=1, strict callback diagnostics, ARCH_QCOM enabled and COMPILE_TEST disabled,
  without warnings/errors. Candidate hashes bind compilation to the final commit.
* The integrated ARM development kernel and all 459 modules build and stage.
  CMS signatures, ELF32 ARM architecture, release and dependency metadata pass.
  All module paths and prior 20 DTB hashes remain intact. This incremental build
  has zero new diagnostics; documented inherited full-tree warnings remain.
  Clean reproducibility, maintained-LTS packaging, normal install/update/recovery
  and physical acceptance remain required.
* The new patch passes strict checkpatch without signoff checking. Shallow
  UNKNOWN_COMMIT_ID lookup alone is excluded; cached original upstream driver
  and registration-change evidence verify both Fixes targets. Current maintainer
  routing is included. Nothing was sent.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python3, clang-21,
patch and pthread support outside a ptrace sandbox for normal leak checking.
Replay checks every manifest hash, all ten patch applications without Git/fuzz/
offsets, and the six/seven/eight-patch admission/DMA/power baselines. Five current
before/after suites, the separate LTS PM contrast and all 50 controls execute.
Generated maintainer/integration models must match byte for byte in both PM
profiles. Native/full builds are represented by source-bound receipts, not rerun.

Remaining work and attribution
------------------------------

Full failed-start recovery, master-work and external-transfer admission/quiescence,
RX callback resubmission and timeout lifetime, late QMI arrival/completion
consumption, parent readiness and the original initial DSP bootstrap still need
work. In particular, cached LTS hard-error recovery needs qualification beyond
this callback contrast. Physical startup, resume and whole-device acceptance
remain open. No new live device or network configuration changes were made.

Codex generated the fix, models, changelog, integration and review packet. Prior
human attribution and dates are retained. Human review and DCO certification
remain pending; no agent sign-off was added. All heads remain local and
unpublished. No maintainer contact occurred. Private keys, credentials, boot
material and per-device data are excluded.
