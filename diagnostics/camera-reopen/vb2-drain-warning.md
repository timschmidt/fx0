# Native vb2 trace localizes the missing-ready warning

The original five-session workload (front, binned rear, front, binned rear,
full rear; 24 buffers each) reproduces `Missing ready buf 1 4!` during the
second front session. All 120 requested buffers arrive, including 87 frames
whose sampled RGGB bars pass. The lossless trace contains 120 events in each
of the four vb2 core families and 37 markers. Raw frames are deleted on the
phone; raw trace/owner tokens and stdout remain private.

The as-tested worker exits **1**, because it incorrectly requires the two
V4L2 vb2 families to appear. Those events are defined and exported, but no
explicit queue/done call sites are found in the pinned source. Their absence
does not establish that the minor filter is wrong. This source is preserved
as tested. `analyze-core-trace.py` separately checks unique timestamp/byte-size
matches for every delivered frame against core done and dequeue events. Its
post-hoc result does not turn the failed worker into a passing qualification.

The warning occurs 0.441 ms after the final core completion and 4.523 ms before
its dequeue. At that completion the driver-owned count is zero and the queued
count is one. The final four completions show owned counts 3, 2, 1, 0; no new
buffer is queued to the driver after the warning. The last frame's stored
timestamp precedes its actual core completion by 69.601 ms, so a printed camera
frame timestamp must not be mistaken for a userspace delivery time.

The pinned VFE41 handler dispatches register-update before write-master-done.
The gen1 register-update callback releases a deferred last buffer and changes
STOPPING to IDLE. A late/coalesced write-master completion after that transition
is a concrete hypothesis, not a proven cause: this trace does not include IRQ
status words or VFE state transitions. The warning itself reports IDLE (4),
while the core counters alone cannot identify that state. No driver patch or
diagnostic suppression is justified by this observation alone.

The full-rear session also has a 1,031.451 ms final timestamp interval, about
31 median periods, plus seven double-period intervals. This is evidence from
a finite file-writing workload; it does not establish steady-state camera
throughput or explain all earlier file-output gaps.

Independent full-window classification rejects the actual warning. Both
sensors return to suspended with patterns off, the instance and frames are
removed, and global/other trace settings match their initial snapshots. The
owned failed flag is cleared only after preserving its status and cleanup
receipts. Independent postflight verifies the accepted boot/package/config
hashes, taint zero, healthy services, unchanged UI/gesture processes, and no
owned camera process. The clean camera gate and full bringup remain open.

A read-only inventory finds one disabled VFE41 IRQ-status dynamic-debug call
site. A further diagnostic should first qualify exclusive ownership and exact
restoration of that setting, correct the unsupported V4L2 event expectation in
a fresh source revision, and capture status words alongside the core trace.
No dynamic-debug setting has been changed.

[Sanitized observations](../../evidence/2026-11-14-camera-vb2-drain-warning.json)
