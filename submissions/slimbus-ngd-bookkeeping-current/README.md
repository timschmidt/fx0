SLIMbus NGD registration bookkeeping preparation
================================================

This local review packet contains two fixes on the current advertised SLIMbus
maintainer for-next snapshot 6628e7d4c6b25c8d18f1345e3a20d21829aae7e4,
and the same two patches on the Fx0 runtime15 integration. Only the NGD
controller source changes. All other functions and source bytes, including
channel removal/reconfigure/reset, DMA, master-work, probe and teardown code,
remain unchanged apart from two callback bodies and one ownership field.

The worker proceeds only after a positive bounded QMI wait. Registration
bookkeeping reuses an existing QMI client, retains runtime wakeup on repeated
UP, registers/unregisters each owned controller once, and drops the bootstrap
PM reference only after successful registration. Failed registration releases
its QMI client and retains the bootstrap reference for retry.

Evidence
--------

* Ten exact NGD and SLIMbus-core function bodies run across 21 synthetic cases
  and 152 checks. The unchanged baseline fails 48 checks; the final candidate
  fails none. Cases cover interrupted/timed-out/completed waits, duplicate UP,
  PM enabled/suspended combinations, registered-controller runtime wakeup,
  QMI and registration failures, retry, disable and an SSR cycle.
* Seven independently broken variants are rejected: interrupted wait accepted,
  duplicate registration, unowned unregister, early PM put, missing QMI unwind,
  duplicate QMI client and suppressed runtime wakeup. Fail-fast ASan/UBSan and
  normal LeakSanitizer run without diagnostics. Allocation/ownership counts are
  instrumented service models; fixture cleanup recovers every mock allocation
  even after a baseline mismatch. This is not real QMI or kernel PM execution.
* Review caught an overly broad first guard that skipped runtime wakeup. Two
  additional cases reproduce that regression and pass on the final source.
  The discarded version remains a regression control, with a retained receipt.
* Eight native ARM/ARM64 NGD, core, messaging and stream objects compile with
  LLVM 21 and W=1 without diagnostics. ARCH_QCOM is enabled, COMPILE_TEST is
  disabled, and the actual NGD and remoteproc dependencies remain modules.
  The initial preparation incorrectly required these module dependencies to
  become built-ins and stopped before compilation. The corrected profiles
  retain the native module configuration. A final message-only rewrite keeps
  the exact source tree used for the successful builds.
* The corrected integrated ARM development kernel and 459 modules build.
  Normal private modules_install staging verifies every CMS signature, ELF32
  ARM architecture, release and module dependency entry. NFC remains enabled.
  This is an incremental build, not proof of clean reproducibility, final
  maintained stable packaging, installation or update/recovery acceptance.
* Both source patches pass strict checkpatch with signoff checking disabled.
  UNKNOWN_COMMIT_ID is excluded because the source snapshot is shallow; exact
  primary upstream API metadata and diffs verify both Fixes targets. Routing
  comes from current MAINTAINERS with historical Fixes lookup disabled.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python 3, clang-21
and patch, outside a ptrace sandbox so normal LeakSanitizer can run. The replay
verifies every manifest hash, applies four patches without Git, fuzz or offsets,
compares all candidate snapshot bytes and runs the baseline, candidate and seven
regression controls. Runtime and maintainer generated models must match exactly.
Native and full kernel/module builds are not repeated by this host replay;
their source-bound receipts and public configurations are included.

Remaining work
--------------

The original Timothy Schmidt startup fallback fe063af17b09 is not yet carried
forward. Queued/running work cancellation, child/parent/provider lifetime,
late service arrival, interrupted wait retry, completion consumption, repeated
DOWN notifications, firmware concurrency and power-up error propagation remain
open. Existing runtime_resume return behavior is retained. These two fixes
qualify bookkeeping prerequisites and do not establish complete SLIMbus startup
or teardown acceptance. No DMA, audio, modem firmware or physical bus operation
was executed. The phone and its installed image remain untouched.

Attribution and publication
---------------------------

These fixes, changelogs, host models, integration and packet used OpenAI Codex
assistance. Upstream authors and existing human trailers remain in source and
Fixes evidence. Human review and DCO certification are pending; no agent
Signed-off-by was added. The original Timothy startup commit and its Claude
credit remain preserved in the project history and will be retained when that
feature is reconciled. This packet is unpublished and no maintainer messages
were sent. Credentials, private keys, boot images and per-device data are absent.
