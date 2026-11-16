# SLIMbus synchronous response, TID and PM ownership

Publish response readiness only after its pointers are initialized. Serialize
response lookup, bounded copy, TID removal and completion with cancellation.
A cancellation retires only its own transaction, preserving a replacement
that reused the numeric TID. Both response and cancellation release the response
PM reference only after winning retirement. The sender retains a separate PM
reference through its entire call, including an early reply before DMA completion.

The NGD ACK path retires locally owned TIDs before its stack buffers return.
The synchronous helper balances its caller reference on success and every error.
Generic submission errors propagate before DMA is issued and use the previously
qualified unsubmitted-reservation rollback and completion cleanup.

The maintainer series has thirteen patches on official SLIMbus base
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4, including twelve prerequisites.
One runtime patch applies the followup to integration 25. Source identities,
full snapshots and manifest hashes are pinned. Runtime changes are limited to
messaging.c, qcom-ngd-ctrl.c and the private slimbus.h header.

## Qualification

Thirteen byte-exact core, NGD TX and message-helper functions run with logical
services. Their 1,022 cases and 41,774 checks pass after 2,061 pre-change failures.
All sixteen response controls are rejected. Cases cover early publication,
response copy racing timeout, duplicate/oversized replies, software TID owner
replacement, distinct sender/response PM references, external references,
PM and controller errors, and multiple submission errors.

The prior TX suite also passes 1,093 cases/47,497 checks with twelve controls.
Its 41,147 packet-trace bytes remain identical. This packet replays 28 controls
in total. Six earlier generated model programs remain byte-identical; their
original synthetic-service qualifications are preserved without rerunning every
prior control in this packet.

Eight native ARM/ARM64 NGD/core/messaging/stream objects build with LLVM21, W=1,
strict callback diagnostics, ARCH_QCOM enabled and COMPILE_TEST disabled,
without diagnostics. The incremental full ARM kernel and 459 signed modules
build, stage and pass CMS, ELF32 ARM, release and dependency checks. Module paths
and twenty prior DTB hashes are preserved. This does not prove clean package
reproducibility, a warning-free whole kernel or physical acceptance; the initial
full build had inherited warnings.

## Offline replay

Run `python3 -B replay.py /tmp/fx0-response-replay-UNUSED` using Python, clang-21,
patch and sanitizer runtimes. Choose a nonexistent output path outside this
packet. Replay validates manifest hashes, applies fourteen patches without fuzz
or offsets, verifies both prerequisite prefixes and final snapshots, then runs
the response and TX baselines/candidates and all 28 controls. Maintainer/runtime
models must match, and TX packet streams must be byte-identical. Git, Internet,
phones and devices are unnecessary. Native/full kernel, module, DTB and schema
builds are recorded separately and are not repeated by replay.

## Limits and remaining work

IDR operations, PM, DMA, responses and completion tokens are synthetic services.
Actual callback bodies and message types/constants are extracted without logic
rewriting. Request storage stays physically live through the logical lifetime
audit. Invalid response copies and completions are logged without accessing
retired memory; completion addresses are never dereferenced. Pthreads force
specific schedules rather than executing Linux scheduling or real DMA callbacks.
Normal LeakSanitizer and fail-fast ASan/UBSan remain enabled.

The exported asynchronous path still retains its internal stack transaction
past return. No current in-tree asynchronous caller was found by symbol audit,
but external users are not excluded and that path remains unqualified. The API
has not been disabled or converted into a synchronous API. Software cancellation
identity does not distinguish an old wire reply after the same eight-bit TID is
reassigned; wire-generation handling also remains open.

RX resubmission, master and external transfer admission/quiescence, attached
hardware/remote-firmware shutdown ordering and full transport recovery remain
required. Initial DSP bootstrap, registered-client endpoint generation and
maintained-LTS recovery remain open. No physical DMA, firmware, audio, phone or
network operation runs in this qualification, and no phone update is performed.

Codex generated the fix, fixtures and evidence. Genuine prior authorship/history
remain intact. Human review and DCO certification remain pending; no agent
Signed-off-by is added. The draft is unsent and heads remain unpublished.
Private keys, boot images, credentials, firmware blobs and per-device data are
excluded. Source/model license text is retained in LICENSES.
