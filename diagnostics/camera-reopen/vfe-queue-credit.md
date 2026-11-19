# Queue ownership during front-camera capture gaps

Two temporary boots of the same signed 6.18.64 CAMSS image ran four-second
capture windows after eight initial buffers. The comparison included two
unperturbed front-camera runs, a confirmed 250 ms stop of the owned front-camera
client, two front-camera suspend attempts and one rear-camera suspend attempt.
The suspend attempts received `-EBUSY` from CAMSS prepare before machine sleep.
The client-pause control confirmed that both live threads stopped and resumed.
[RAM image and CAMSS source](../../evidence/2026-11-19-fx0-camss-stopping-completion-handset.json)

Every delivered frame in the corrected run matched a single VB2 completion by
timestamp and byte count. All 403 matched completions were inside VFE interrupts.
The trace recorded queue and done events for the same VB2 owner, with the buffer
count measured after handing a buffer to the driver and after getting it back.
No trace events were lost. The first run's VB2 evidence also passed, but its
hard-coded IRQ 95 filter caught no interrupts. The corrected run identified the
live interrupt by the VFE handler name and rejected any window that lacked
interrupt coverage for a delivered buffer.

The front camera's median interval was 69.6 ms. Its approximately 2.088 and
2.158 second intervals appeared with and without a suspend request. The first
completion left three buffers owned by the driver and the next enqueue raised
the count to four. The count stayed above zero throughout each long interval.
The corrected run observed 31 or 32 intervening VFE IRQ entries in those
intervals. Distinct intervals of roughly 0.49 to 0.57 seconds during the suspend
cases included roughly 0.39 to 0.50 seconds with zero driver-owned buffers.

Two additional unperturbed front-camera sessions traced the exact VFE callbacks.
Both captures completed. One produced gaps of 2.088 and 2.157 seconds, with a
register-update callback 58 and 119 microseconds after the preceding completion.
In each gap the write-master callback entered only near the next delivered
buffer, 15–16 microseconds before that completion. The transient service hit its
time limit during the final health snapshot. A subsequent same-boot read verified
both sensors suspended, the trace instance removed, the service stopped and the
display session's supporting services active.

The long gaps are consistent with the VFE 30/31 frame-drop period programming.
The VB2 timestamps mark driver buffer completions. The trace did not read the
hardware pattern or its phase, and a register-update callback alone does not
identify which programmed pattern the hardware accepted. The exact cause of
the missed write-master completions remains open.
[Gen1 frame-drop programming](https://github.com/timschmidt/fx0-linux/blob/2150f900adaf27c32a5bd620bd12ab04345aa99b/drivers/media/platform/qcom/camss/camss-vfe-gen1.c)

Each temporary boot returned to the installed kernel. The independent return
audits verified all 482 installed module files, the protected files, and the
charger timer and control registers. The run collected frame metadata only.
[Sanitized trace results](../../evidence/2026-11-19-fx0-camss-vfe-queue-credit.json)
