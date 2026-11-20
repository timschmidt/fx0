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

## Register writes and saved IRQ status

Another boot of the same signed image captured the operands of the period,
pattern and update stores. It also captured both status words after the VFE
4.1 IRQ routine read them and before it cleared them. The four probes used
instruction offsets checked against the signed ARM module and resolved the
matching symbols on the running kernel. They read CPU registers and the
driver's saved IRQ status words. An initial buffered append failed with
`EINVAL` before probe registration. The tracefs writer used by the RTC test
registered and removed the probes successfully in a new transient service.
[Kernel probe interface](https://docs.kernel.org/6.18/trace/kprobetrace.html)

Five bounded captures matched all 288 delivered frames in VFE interrupts.
One uninstrumented front run and the rear probe run had no two-second gaps.
Each of the three instrumented front runs produced one long interval.

| Frame gap | Period field | RDI0 frame starts inside gap | First RDI0 update acknowledgement after preceding completion |
| ---: | ---: | ---: | ---: |
| 2.157393 s | 31 | 31 | 23 µs |
| 2.087908 s | 30 | 30 | 56 µs |
| 2.157684 s | 31 | 31 | 59 µs |

For each gap, the preceding completion's handler programmed WM0 pattern `3`
and wrote RDI0 update bit `0x2`. At least three VB2 buffers remained owned.
The saved IRQ words report continued RDI0 frame starts and no WM0 completion
between the endpoint handlers. The next WM0 completion arrived in the final
handler, where the next period, pattern and update writes also took place.
An independent replay verified that none of those writes occurred between the
endpoint handlers. The earlier acknowledgement confirms an update interrupt.
The probes did not expose the active hardware frame-drop phase.

Ordinary front-camera intervals can also have an early acknowledgement. Among
95 ordinary front intervals with the same pattern, 59 had an acknowledgement
between the endpoints, with observed delays of 22–148 µs. All 128 ordinary rear
intervals with that pattern had one at 16.726–16.990 ms. The three front stalls
are therefore tied to an entire programmed frame-drop period despite an early
acknowledgement and continuing frame starts. The hardware's phase-reset rules
remain to be established.
[Register and IRQ evidence](../../evidence/2026-11-19-fx0-camss-vfe-pattern-trace.json)

## Timing comparison with front-sensor vertical blanking

Six eight-second observation windows on the same RAM image used VBLANK
values 26, 154, 410, 410, 154 and 26. Each window followed a short settling
period and used the same RAW10 resolution. The live control readback and the
median RDI start-of-frame interval verified the sensor cadence. Each capture
restored VBLANK to 26 before closing the sensor. [IMX132 control implementation](https://github.com/timschmidt/fx0-linux/blob/2150f900adaf27c32a5bd620bd12ab04345aa99b/drivers/media/i2c/imx132.c)

| VBLANK | Measured frame period | Median time from WM completion to RDI update acknowledgement | Frame starts across both windows | Gaps over ten frame periods |
| ---: | ---: | ---: | ---: | ---: |
| 26 | 69.597 ms | 0.122–0.132 ms | 231 | 4 |
| 154 | 76.862–76.863 ms | 7.398–7.401 ms | 209 | 0 |
| 410 | 91.395–91.396 ms | 21.933–21.935 ms | 176 | 0 |

Both default windows reproduced two 31-period gaps with queued buffers.
All four longer-blanking windows delivered completions at the measured frame
cadence. The start and completion counts for each longer window agree to
within one at the endpoints. The timing change moved the update away from
the next frame boundary and the stalls disappeared in this comparison. The
internal latch timing still needs qualification. The same-boot repetition
used a compressed dispatch after the longer SSH command failed to start the
worker. The installed return and sensor default were verified independently.
[Vertical-blanking trial](../../evidence/2026-11-19-fx0-camss-vblank-timing.json)

The MSM8226 candidate queues a continuous RDI rearm when the write master
completes and writes it at the next start-of-frame interrupt. It clears the
pending rearm when the queue drains or the output is disabled. The ARM CAMSS
component compiled with `W=1`, and 114 host executions and 33 negative
controls passed. [Candidate source](https://github.com/timschmidt/fx0-linux/commit/ecf268bf5d66c17e545a1a06792ec679cdaf3eaa)

## Frame-start rearm handset qualification

The signed source candidate kept the front sensor's default blanking of 26.
Four eight-second front windows recorded 460 RDI frame starts and 460
write-master completions. The nominal frame period was 69.597 ms and the
largest delivered interval was 69.847 ms. Both rear RAW10 windows, at
1640×1232 and 3280×2464, held their 33.272 ms cadence. Frame-start and
write-master counts across the six windows agreed to within one completion
at the endpoints. Each delivered buffer matched a VFE interrupt with no
trace loss. The test collected metadata without saving sensor frames.

All 727 observed steady-state pattern-3 writes occurred in an RDI frame-start
interrupt, including 171 interrupts with coalesced write-master status. Both
finite captures returned all 24 requested buffers and released the sensors.
The active-stream CAMSS guard returned `-EBUSY` on each sensor and each stream
delivered at least six more verified buffers after refusal. With both cameras
closed, the RTC woke the phone after 14.114 seconds. No camera warning was
reported during the run. Active-stream suspend and resume remain open.

The scheduled return restored the installed kernel. The independent audit
verified 482 installed module files, the protected files, and the charger
timer and control registers. [Signed RAM qualification](../../evidence/2026-11-19-fx0-camss-rdi-sof-rearm-handset.json)

## Signed 6.18.64-r3 package candidate

The r3 kernel recipe starts with the installed r2 source and carries the
three tested CAMSS changes. Its in-tree CAMSS source and the executable
`.text` section of its module match the RAM-tested revision. The complete
module payload differs in ELF build metadata, read-only data and symbols.
The build kept all 65 packaged DTBs, the configuration and the installed
module certificate, and verified signatures for all 468 loadable modules.
[Release source](https://github.com/timschmidt/fx0-linux/commit/539a7cccccac57f48e112bf5f8b6b95eca91cc5a)
[Package recipe](https://github.com/timschmidt/fx0-pmaports/commit/d1fc4d4d5e993116bee3706494a1d5f78b1e9065)

The paired DMP reader keeps its r2 payload and pins the r3 kernel. A shadow
transaction rejected the kernel alone because of the existing r2 reader
dependency. Upgrading the pair changed two of 776 records and left the
device package at 1-r3. Rollback restored the original database and world
selection byte for byte and checked the restored package files. The isolated
root required explicit permission for local APK files on tmpfs. The APKs and
repository index passed verification with the existing trusted public key.

[Signed build and file-only rollback evidence](../../evidence/2026-11-19-fx0-camss-r3-package.json)

### Package-exact handset trial

The temporary image booted the signed r3 APK's kernel and Madai DTB, with
21 exact early modules and all 482 module files verified in the RAM overlay.
Software checks found one active Sway output and one touch input.

Four front runs at default vertical blanking and both rear RAW10 modes
produced 760 steady frame starts and 760 write-master completions. All
818 delivered frames, including the capture boundaries, matched VFE IRQs.
The longest front interval was 69.848 ms, and none of the runs missed a
frame period. Each of the 706 continuous pattern-3 writes occurred in the
frame-start IRQ. Both finite captures drained all 24 buffers.

CAMSS refused suspend while each camera was streaming. Both streams delivered
six more buffers after refusal. With both sensors closed, the RTC woke the
phone after 14.409 seconds. The automatic return restored r2. An independent
audit matched the camera report to the journal and verified the installed
files, charger controls and sensor defaults.

Two native initramfs previews agreed byte for byte. The 247-entry archive
preserved the device's early module list and differed from r2 only in the
21 signed module bodies. In an isolated handset overlay, native APK hooks
produced those same r3 initramfs bytes. Rollback reproduced the installed
r2 initramfs and all 776 original package records. The harness restored the
saved world ordering after confirming that APK preserved its selections.
The trial module staging and native rehearsal workspaces were removed.
The installed phone continues to run r2. Active-stream suspend and resume
remain open.
[Exact handset and native package qualification](../../evidence/2026-11-19-fx0-camss-r3-native-qualification.json)
