# Qualcomm BAM callback synchronization

Register device_synchronize with a per-channel vchan_synchronize callback.
BAM's existing cancellation can remove submitted descriptors while a virt-dma
completion tasklet already owns a detached completed list and is executing a
client callback. The added operation lets dmaengine_synchronize and
combined dmaengine_terminate_sync wait for that channel's callback tasklet.
No existing hardware reset, cancellation or descriptor ownership logic changes.

The source base is official DMAengine next/fixes/master at
6628e7d4c6b25c8d18f1345e3a20d21829aae7e4, verified at preparation. One
maintainer patch and one runtime patch are included. source-topics.json pins
full identities; the runtime patch changes only drivers/dma/qcom/bam_dma.c.

## Qualification

The host model executes eight byte-exact BAM, virt-dma and DMA API function
bodies plus two exact probe operation assignments. Its 256 cases and 3,328
checks pass after 536 pre-change failures. All eight controls are rejected.
Cases cover both selected channels, combined and split termination APIs,
allocated/submitted/issued/completed/hardware-active descriptors, a callback
already running, and an unrelated channel's active callback. Controls check
registration, waiting, channel scope, locking, descriptor cancellation and
termination-before-synchronization ordering.

Six native ARM/ARM64 BAM, virt-dma and DMAengine objects build with LLVM21,
W=1, strict callback diagnostics, ARCH_QCOM enabled and COMPILE_TEST disabled,
without diagnostics. The incremental runtime ARM kernel and 459 signed modules
build, stage and pass CMS, ELF32 ARM, release and dependency checks. All module
paths and the twenty previously qualified DTB hashes remain intact. This does
not establish clean package reproducibility, a warning-free complete kernel,
or physical hardware acceptance. The initial full build had inherited warnings.

Previous NGD source snapshots are byte-identical; earlier startup, QMI, power,
DMA setup and ownership qualifications retain their original synthetic-service
scope. Those models never executed the real BAM provider. This new provider
qualification supplies one prerequisite for real transport teardown; it does
not establish that the NGD client already obeys every cancellation obligation.

## Offline replay

Run `python3 -B replay.py /tmp/fx0-bam-replay-UNUSED` with clang-21, Python,
patch and sanitizer runtimes installed. Select a nonexistent output directory
outside the packet. Replay checks all manifest hashes, applies both patches
without fuzz or offsets, compares candidate snapshots and runs baseline,
candidate and eight controls. Generated maintainer/runtime models must match.
Git, Internet, hardware, audio and phone access are unnecessary. Native/full
builds are recorded separately and are not repeated by replay.

## Limits and remaining transport work

Tasklet scheduling, DMA hardware/reset, spinlocks, lists and callbacks are
logical services. The actual virt-dma completion routine was inspected for
its detached-list lifetime; it is not executed in the model. Pthreads model
an already detached running callback. All descriptor and owner storage stays
physically live through the logical audit. Unsafe lock controls are recorded
without deliberately blocking forever. Normal LeakSanitizer and fail-fast
ASan/UBSan are enabled. No real stale-memory access or kernel callback runs.

Clients must stop the attached hardware and prevent new submissions, including
RX callback resubmission, before synchronization. They must not synchronize
from atomic context, a callback on the same channel, or while holding a lock
needed by that callback. The provider fix does not close NGD master/external
transfer admission, its RX resubmission race, TX stack completion ownership,
response/TID lifetime or firmware-specific hardware shutdown ordering. Those
remain required before broad transport teardown is accepted. Initial DSP
bootstrap, registered-client endpoint recovery and full LTS recovery also
remain open. No phone update, publication or maintainer contact is performed.

Codex generated the fix, model and evidence. Genuine prior authorship and
history remain intact; human review and DCO certification are pending. No
agent Signed-off-by is added. GPL-2.0 license text is in LICENSES. Private
keys, boot images, credentials, firmware blobs and per-device data are excluded.
