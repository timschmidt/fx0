# Native VFE callback order at final drain

All 120 buffers in the original five-session workload match unique core
done/dequeue timestamps and sizes; 87 frames pass sampled sensor-bar checks.
The camera worker still exits **1**, because strict full-window classification
rejects `Missing ready buf 1 4!`. This revision records IRQ95 boundaries,
selected function entries and core events in one mono trace clock.

The lossless trace has 236 IRQ spans and exactly 236 VFE41 status prints.
All 237 source timestamp/message pairs match contiguous kernel-ring records.
Each span has one handler entry, and register-update/WM callback counts match
its saved status bits. The sole VFE41 handler prints once at entry, so complete
serial streams can be associated by ordinal without converting clock domains.
All 120 core completions occur inside the recorded IRQ95 spans on CPU0.

The warning-associated snapshot is `0x120` / `0x20000000` in the second front
session. It includes RDI0 register-update and WM0 completion. The matching
IRQ has this order (times relative to IRQ entry, all in the trace's mono clock):

| Event | Relative time, microseconds |
| --- | ---: |
| IRQ handler entry | 0 |
| VFE41 handler entry | 13 |
| Register-update callback entry | 121 |
| Final buffer core completion | 139 |
| Write-master callback entry | 219 |
| IRQ handler exit | 374 |

The final completion has buffer index 3, queued count 1 and driver-owned count
0. The warning reports IDLE (4). Within printk's separate clock, the warning
is the next kernel record after this status print, 202 microseconds later;
that interval is not placed on the trace-time axis.

This observes the dispatch path behind the warning. In the pinned gen1 source,
register-update releases a deferred last buffer in STOPPING, clears that
pointer, then changes the output to IDLE. The IRQ dispatcher subsequently
processes the saved WM completion bit, reaching the missing-ready path on the
drained output. Callback entries and core completion are directly traced;
VFE memory state transitions and MMIO writes are inferred from the source and
warning, not directly sampled. There are 121 WM callback entries for 120 core
completions. A fixed driver and full camera acceptance remain unverified.

The next source-level regression must cover both an empty drain and buffers
requeued during STOPPING. A fix must preserve the hardware-idle acknowledgment
before buffer return and must not treat a newly queued buffer as completion of
the old saved WM bit. Blanket IRQ reordering or simply suppressing IDLE
diagnostics would not demonstrate these ownership properties. No driver
source replacement or new kernel boot is performed by this diagnostic.

Before capture, normal and injected setup-failure native probes verify the
owned function tracer, exact 12-symbol filter (including duplicate static
names), IRQ filters, debug-site restoration and preservation of global/other
filters and options. Shared function flags are read only. All 130 exported
host checks pass. Raw frames remain on phone tmpfs and are deleted per case;
raw trace and owner tokens stay private. Independent postflight confirms the
accepted installed hashes, taint zero, healthy services, idle sensors with
patterns off, restored settings and inactive owned service.

[Sanitized observations](../../evidence/2026-11-14-camera-vfe-callback-order.json)
