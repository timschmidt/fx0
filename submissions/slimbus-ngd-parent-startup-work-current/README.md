NGD parent startup work cleanup
===============================

Queued or running NGD startup work must finish while its child device still
exists. The normal parent remove path now stops PDR/SSR callbacks, drains
startup work, then unregisters the child. The parent probe error path releases
PDR and drains startup work before child removal, releasing each provider once.

Four patches are included on the advertised SLIMbus maintainer snapshot
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4: the two earlier bookkeeping
prerequisites followed by these two cleanup fixes. The runtime topic adds only
the two cleanup patches to runtime16-v2. The final driver bytes match. Only the
parent probe and parent remove function bodies change in this step; all other
functions, including bookkeeping, wakeup, channel removal/reconfigure/reset,
child-only remove, master work and DMA/IRQ paths, retain their previous bytes.

Qualification
-------------

* Seven exact parent, startup and notification callbacks execute in twelve
  synthetic cases with 72 checks. The unchanged parent paths fail 20 checks.
  The detach-only prefix fixes its six cases, leaving ten probe-unwind failures.
  The final candidate has no failures. Four independently broken ordering
  variants fail 10, 7, 6 and 6 checks respectively.
* The model uses pthreads and barriers to hold startup work running while
  teardown begins. It also covers queued work and provider callbacks finishing
  during release. Synthetic child state records bad ownership ordering; every
  fixture allocation remains live until all threads join, so no freed memory
  is accessed. PDR, SSR, QMI, workqueues, child devices, DMA and IRQ services are
  models. Source hashes bind the provider/cancellation API contracts reviewed.
  This does not execute Linux workqueues, a real provider or physical hardware.
* Fail-fast ASan/UBSan and normal LeakSanitizer report no diagnostics. The earlier
  bookkeeping suite still passes its 21 cases and 152 checks; its unchanged
  upstream baseline fails 48 checks and seven regression controls are rejected.
* Eight native ARM/ARM64 NGD/core/messaging/stream objects compile with LLVM 21,
  W=1 and strict callback diagnostics, without warnings or errors. ARCH_QCOM is
  enabled, COMPILE_TEST disabled, and native module dependencies retained.
* The integrated ARM development kernel and 459 modules build. Normal private
  modules_install staging checks every CMS signature, ELF32 ARM architecture,
  release and module dependency entry. NFC and all earlier source features are
  retained. This incremental build does not prove clean reproducibility or final
  maintained-LTS package install, update, recovery or physical acceptance.
* Both new patches pass strict checkpatch without signoff checking. The shallow
  UNKNOWN_COMMIT_ID check is excluded; exact primary upstream API metadata and
  diffs verify both Fixes targets. Current MAINTAINERS routing is captured with
  historical Fixes lookup disabled. No messages were sent.

Replay
------

Run `python3 -B replay.py /absolute/path/to/new-output` with Python 3, clang-21,
patch and pthread development support, outside a ptrace sandbox so normal
LeakSanitizer works. All manifest hashes and six patch applications are checked,
with no Git, fuzz or offsets. Candidate source snapshots and the generated
runtime/maintainer models must match byte for byte. Both baseline/candidate
suites and all eleven regression controls execute. Native, full kernel/module
and schema builds are not repeated; their source-bound receipts and public
configurations are included.

Remaining work and attribution
------------------------------

The original Timothy Schmidt startup fallback is not yet integrated. Child-only
unbind and rebind, new notification admission during that lifecycle, master work,
IRQ/DMA quiescence, late QMI service arrival, completion consumption, repeated
DOWN, power-up failure propagation, firmware concurrency and physical bus
acceptance remain open. These fixes establish parent startup-work ordering only.
No audio, firmware, device or phone execution was performed.

OpenAI Codex implemented these fixes, changelogs, models, integration and review
packaging. Existing upstream authors and human trailers remain in source and
Fixes evidence. Human review and DCO certification are pending; no agent
Signed-off-by was added. This packet is unpublished and no maintainer contact
occurred. Private boot images, keys, credentials and per-device data are absent.
