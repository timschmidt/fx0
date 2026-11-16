# NGD software DMA admission and shutdown

Close RX rearm and master-work production under the same buffer lock that
covers prepare/submit/issue. Serialize setup and release with a lifecycle mutex.
Reject new TX after closure, including non-TID messages, and drain admitted
senders through their transfer mutex before terminating channels. RX cookies
stay in client-owned storage; a failed RX submission is never issued.

Master handshake work no longer invokes PM-dependent slave notification inline.
Notification uses a guarded system work item, separate from the single-thread
master queue needed by resume. Runtime DMA stop drains the PM-free handshake;
SSR and child removal additionally drain notification work and observe the PM
callback barrier before releasing QMI/client resources. Closed parent, child,
UP or QMI admission prevents setup/resume from reacquiring DMA.

The SLIMbus series contains fifteen patches on official base
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4. One runtime patch applies to integration
27. Runtime changes are limited to qcom-ngd-ctrl.c; prior features, all module
paths and 20 DTB hashes are preserved.

The separate BAM synchronization patch at
111abac8b92bce58b7fee7c9cc80a4e1498fe3c0 is a required provider prerequisite.
It is already present in the runtime. This packet includes that source topic,
its one patch, baseline/candidate snapshots and offline callback-barrier model.
There are three source topics and seventeen patches in total.

## Qualification

Twenty-one exact NGD/helper bodies pass 96 cases and 1,375 checks, after 241
pre-change failures across the same 96 cases and 1,369 checks. Conditional API
checks differ. All 28 transport fault controls are rejected at their expected
assertions. Schedules cover RX callback rearm racing close, master work and
postprocessing, an active non-TID sender, setup/release and overlapping stops.
PM notification remains independent of the handshake and can wait for runtime
PM progress without blocking DMA shutdown. Callback allocation/submission
errors preserve ownership and do not issue DMA.

Prior regressions pass again: response 1,149/44,419; readiness 71/1,079; PM
626/13,284; DMA 85/1,150; bookkeeping 21/153; device reference lifetime 10/114;
TX 1,093/47,497. The bookkeeping SSR cycle now delivers the UP notification
before enabling again, adding one assertion. Two earlier reuse mutations are
redundant under the new setup-ready guard and are retired; positive repeat
setup, timeout retry and buffer-reuse assertions remain. Their evidence and
scope changes are recorded. Normal PM and recorded 6.18.63 PM callback profiles
both pass within synthetic services; this does not qualify a full LTS backport.
All 41,147 TX packet bytes remain identical.

The caller/regression fixtures reject 125 controls. Offline replay also reruns
the unchanged BAM provider model (256/3,328; eight controls), for 133 controls
in this packet. Models for maintainer/runtime source match. Caller/provider
models execute separately with synthetic services; they do not execute a real
kernel DMA/workqueue/PM composition.

Eight native ARM/ARM64 NGD/core/messaging/stream objects build with LLVM21 W=1,
strict callback diagnostics, QCOM enabled and COMPILE_TEST disabled, without
compiler diagnostics. The incremental full ARM kernel and 459 signed modules
build, stage and pass CMS, ELF32 ARM, release and dependency checks. This does
not prove clean package reproducibility, a warning-free whole kernel or physical
acceptance. The original full build had inherited warnings. Current development
source is not maintained-LTS acceptance.

The latest fix passes strict checkpatch with the shallow checkout's missing
Fixes object verified from the cached public primary commit. Earlier prerequisite
style qualifications retain their recorded scope, including the prior IDR
initializer deprecation. Codex generated the fix, fixtures and evidence. Human
review/DCO remain pending; no agent Signed-off-by is added.

## Offline replay

Run `python3 -B replay.py /tmp/fx0-dma-admission-replay-UNUSED` using Python,
patch, clang-21 and sanitizer runtimes. Choose a nonexistent output directory
outside this packet. Replay verifies manifest hashes, applies all seventeen
patches without offsets/fuzz, verifies prerequisite prefixes and final snapshots,
then runs transport, response, lifecycle, PM, DMA, ownership, TX and BAM models
and all 133 controls. Git, Internet, phones and devices are unnecessary. Native,
full kernel/module and DTB/schema builds are separate recorded evidence.

DMA, MMIO, TID, PM, workqueue, device and lifetime services are synthetic. Actual
callback bodies and message types/constants are extracted without rewriting
logic. Pthreads force selected schedules; they do not execute Linux scheduling.
Descriptor/channel/buffer/token storage remains physically live for logical
lifetime audits. Invalid service arguments and unsafe lock waits from deliberate
controls are logged without stale-memory access or performing a deadlock.
Completion addresses are tokens and are never dereferenced. Normal LeakSanitizer
and fail-fast ASan/UBSan remain enabled. Concurrent mutant failure counts need
not be identical between runs; each must fail its named assertion without
sanitizer diagnostics. Valid candidate checks must all pass.

## Remaining work

The attached hardware engine must be proven stopped before BAM reset. No new
hardware stop sequence is guessed or physically tested here. Failed runtime
suspend rollback, complete failed-start/endpoint recovery, initial DSP bootstrap,
late old wire replies after numeric TID reuse, maintained-LTS packaging/recovery
and physical acceptance remain open. Core client callers still must obey device
and asynchronous-buffer lifetime contracts. No physical DMA, firmware, audio,
phone, radio scan or network-configuration operation runs in this qualification.

The draft is unsent and heads remain unpublished. Prior human attribution and
history are preserved. Private keys, boot material, credentials, firmware blobs
and per-unit data are excluded. Source/model licenses are retained in LICENSES.
