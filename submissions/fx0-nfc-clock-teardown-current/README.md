NXP NCI clock and removal preparation for Fx0
============================================

This local review packet carries four attributed NFC patches on the NFC
maintainer for-next snapshot 36aa7a403154e93c8d39dc07e87ef650e5a131fe,
and six integration patches on the prior Fx0 runtime14. The driver and binding
bytes match across the two final topics. The runtime adds only the original
48-line PN547 board description and retains all prior charging, USB and CPU
properties. No hardware interaction is part of this packet.

The removal patches keep receive available for the closing CORE_RESET, then
stop and drain the IRQ before releasing NCI state. Unregister and IRQ drain
run outside the mode mutex. The optional clock patch balances its vote across
cold, NCI and firmware modes and propagates lookup/enable errors before GPIO
changes. Failed open leaves the core cold and allows retry.

Qualification
-------------

* The unchanged maintainer baseline fails nine synthetic removal cases.
  The final candidate passes ten lifecycle cases and nine clock/probe cases.
  Six teardown and three clock regression controls reject broken variants.
  Extracted callback bodies and transport wiring remain intact. Kernel clocks,
  GPIOs, IRQs, workqueues, packet delivery, waits and firmware services are
  models. Concurrent firmware timing and physical NFC are unqualified.
* Eighteen native ARM/ARM64 driver and NCI objects compile with LLVM 21, W=1,
  QCOM enabled and COMPILE_TEST disabled, with no diagnostics. A message-only
  rewrite retains the exact whole source tree used for those builds.
* The incremental integrated ARM kernel and 459 modules build with NFC enabled.
  Private normal modules_install staging verifies every module's CMS signature,
  ELF32 ARM architecture, release and dependency metadata. This is a development
  build; clean reproducibility, final maintained stable packaging, installation,
  update/recovery and phone acceptance remain open. Build keys are excluded.
* All 20 complete platform DTBs pass unfiltered schema validation, with empty
  validation output. Eighteen other boards are byte-identical. Both Madai
  descriptions pass wiring, optional-clock negative controls and unchanged CPU
  OPP checks. Sixty inherited DTC warnings exactly match the prior run; no new
  DTC diagnostics appear. A stale pre-integration configuration hash gate failed
  after successful compilation; the retained receipt explains and verifies the
  two expected earlier display/CAMSS configuration changes before acceptance.
* All ten patches pass strict checkpatch without signoff checking. The shallow
  history UNKNOWN_COMMIT_ID check is excluded; the two NFC Fixes commit objects
  are verified in cached public history. Current MAINTAINERS routing uses
  --no-fixes to avoid historical-author lookup in shallow history, with
  no messages sent.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` from an untraced process
with Python 3, clang-21 and patch installed. Normal LeakSanitizer cannot run
under a ptrace sandbox. The replay checks every manifest hash, applies all ten
patches without Git, fuzz or offsets, compares candidate snapshots, and runs
fail-fast address/undefined/leak checks with the baseline and regression controls.
It also proves the generated runtime and maintainer models are byte-identical.
It does not repeat native, kernel, module or schema builds; their source-bound
receipts and public configurations are included for review.

Attribution and status
----------------------

Timothy Schmidt's original driver and board commits, author timestamps, messages
and prior tool credits are retained in evidence. Kees Cook's typed allocation
conversion is credited in the runtime prerequisite. OpenAI Codex assisted the
current-source port, changelogs, integration, models and review packaging. A legacy
nonstandard Assisted-by trailer is represented as prose with unchanged source.
Human review and DCO certification are pending; no agent Signed-off-by is added.
Source, configurations and sanitized evidence only are included. This packet is
unpublished and has not been sent to maintainers. Private boot material, device
records, credentials, keys and raw phone logs are excluded.
