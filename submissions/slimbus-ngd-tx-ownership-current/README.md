# NGD TX reservation and completion ownership

Reserve and assemble each TX message while holding the transfer mutex. Clear
the descriptor's on-stack completion reference under the callback spinlock
before every return after reservation. Return never-submitted slots on local
errors; keep submitted slots reserved until the DMA callback advances the
head. Store the submission cookie in client-owned storage, without writing
through the DMA descriptor after handoff to its engine.

The maintainer series contains twelve patches on pinned official SLIMbus base
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4, including the earlier lifecycle,
DMA setup, power, QMI and parent readiness fixes. The runtime patch applies
this TX followup to integration 24, preserving its BAM callback barrier and
all other features. Source identities and snapshots are in source-topics.json.

## Qualification

Seven exact TX/message helper function bodies run in a host model. The final
1,093 cases and 47,497 checks pass after 2,757 pre-change failures. Twelve
controls are rejected. Cases cover all 32 ring positions, failed reservations
with older DMA pending, bounded timeouts, callback retirement and full-ring
recovery, concurrent callers, and return racing an active callback.

All 41,147 bytes of the baseline and candidate synthetic packet traces match.
Their recorded SHA256 is checked by replay. An exploratory capture adapter
produced empty traces; those were rejected and the corrected runner requires
more than 10,000 captured bytes before qualification.

Eight native ARM/ARM64 objects build with LLVM21, W=1, strict callback diagnostics,
ARCH_QCOM enabled and COMPILE_TEST disabled, without diagnostics. The full
incremental ARM integration kernel and 459 modules build, stage and pass CMS,
ELF32 ARM, release and dependency checks. Module paths and twenty previously
qualified DTB hashes are preserved. This is not clean package reproducibility,
a warning-free complete kernel, or physical acceptance; the first full build
had inherited warnings.

Six previous generated model programs remain byte-identical on the runtime
source, including QMI, power, DMA setup, ownership, bookkeeping and BAM provider
models. Their earlier results keep their original synthetic-service scope.
This packet does not rerun all prior controls or claim physical acceptance.

## Replay

Run `python3 -B replay.py /tmp/fx0-ngd-tx-replay-UNUSED` with Python, clang-21,
patch and sanitizer runtimes installed. Use a nonexistent output path outside
this packet. Replay checks manifest hashes, applies thirteen patches without
fuzz or offsets, verifies the immediate pre-TX prerequisite snapshot and final
candidate bytes, then runs the TX baseline, candidate and twelve controls.
Generated maintainer/runtime model programs and both packet traces must be
identical. Git, Internet and devices are unnecessary. Native/full kernel,
module, DTB and schema builds are not repeated by replay.

## Limits and required followup

DMA, completion tokens, TID allocation and response waits are synthetic services.
Actual function bodies and message constants/types are extracted without changing
their logic. The fixture never dereferences completion addresses; it audits
logical frame liveness in stable storage. Nonexistent callback tokens in unsafe
controls are logged without executing a nonexistent callback or stale-memory
access. Pthreads force specific interleavings rather than Linux scheduling.
Normal LeakSanitizer and fail-fast ASan/UBSan remain enabled.

The current BAM provider uses virt-dma's positive cookie assignment. Generic
submission errors still require coordinated response/TID and PM ownership
changes before adding new driver error returns. The core response lookup and
transaction timeout retirement, ACK response storage, RX resubmission,
master/external transfer admission and teardown, attached-engine/firmware stop
ordering and full transport recovery remain unqualified. Initial DSP bootstrap,
registered-client endpoint recovery and maintained-LTS recovery remain open.
No real DMA, firmware, audio, phone or network operations execute here.

Codex generated the fix, models and evidence. Genuine prior history remains
intact. Human review and DCO remain pending; no agent Signed-off-by is added.
The draft is unsent and these heads remain unpublished. Private keys, boot
images, credentials, firmware blobs and per-device data are excluded.
