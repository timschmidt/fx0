# Native VFE IRQ capture and timing correction

The corrected five-session worker validates all 120 requested buffers against
unique core done/dequeue timestamps and byte sizes. It enables only the four
core event families emitted by the installed kernel, and captures a lossless
trace. One IRQ-status dynamic-debug site is enabled under an exclusive lock
with a private pre-write recovery claim. Native empty-trace normal and injected
setup-failure probes verify exact restoration before camera use.

The camera worker still exits **1**: the strict classifier rejects another
`Missing ready buf 1 4!`. There are 239 IRQ-status prints and one warning. All
240 journal source timestamp/message pairs match retained `/dev/kmsg` records,
whose sequence numbers are contiguous. The warning is adjacent to status
`0x00000120` / `0x20000000`, 156 microseconds later **within printk's clock**.
Status0 includes RDI0 REG_UPDATE and WM0 ping/pong completion. The warning
reports IDLE (4). Journal reception places it in the second front case.

This strengthens the finite-drain ordering hypothesis: the pinned VFE41
handler processes register-update before WM completion, and gen1 register-update
can release the last buffer and change STOPPING to IDLE. It does not directly
trace callback entry, state transitions or the WM-to-line map, so it is not yet
a verified cause or fix. Core tails independently reach driver-owned count
zero with one buffer still queued for dequeue. No driver patch is applied.

The earlier sub-millisecond emission-order claim is withdrawn.
[`__MONOTONIC_TIMESTAMP`](https://www.freedesktop.org/software/systemd/man/latest/systemd.journal-fields.html)
is journal reception time. The installed journal also retains original kernel
timestamps, but those must not be mixed directly with ftrace's selected mono
clock: a later 12-marker calibration across all four CPUs measures printk
roughly 1.814 seconds behind CLOCK_MONOTONIC. That later offset is not applied
retroactively. The analysis keeps log intervals within printk time, core
intervals within mono time, and reception only as a coarse session label.
The original private data, failed worker and first analysis remain preserved;
the earlier report and helper now label reception differences explicitly.

The four relevant function bodies match upstream Linux at
[23c62304dde29](https://github.com/torvalds/linux/tree/23c62304dde29abe92013d85910d03a77dada35d/drivers/media/platform/qcom/camss).
This is a function-body comparison, not current stable/edge acceptance or a
complete maintainer-tree review.

All 100 exported host checks pass, including clock-domain separation and
rejection of missing source records, trace loss and kernel sequence gaps. The
exported analyzer exactly replays the retained native evidence. Both debug and
trace settings are restored, sensor patterns are off and PM suspended, frames
are deleted on the phone, and the owned service is inactive. Independent
postflight verifies the accepted boot/package/config hashes, taint zero and
healthy services. Raw frames are never transferred; raw traces and owner tokens
remain private.

Next diagnosis should observe VFE IRQ boundaries/callbacks in the same trace
clock before selecting a patch. The clean camera gate, full hardware acceptance
and broader bringup goal remain open. No new publication, maintainer contact,
package update or boot trial occurs.

[Sanitized observations](../../evidence/2026-11-14-camera-vfe-irq-warning.json)
