# Finite capture and VFE queue timing on installed r1

The earlier five-session r1 regression found `Missing ready buf 1 4!` in the
independent kernel window. That unresolved diagnostic still prevents a clean
camera regression pass. This follow-up retains per-case timing and `cam` stdout
to avoid relying on delivered sequence numbers alone.

Six full-resolution rear sessions alternate frame-file writing and discard,
three of each, with 24 delivered RAW10 buffers per session. Every mode uses
3280×2464 pixels and a 4104-byte stride. The same pinned r1 kernel, package
database, sensor controls and raw stream configuration are checked before/after.
Only `-F` changes between conditions. The pinned
[libcamera camera-session source](https://github.com/libcamera-org/libcamera/blob/v0.7.1/src/apps/cam/camera_session.cpp)
creates its file sink only when that option is set; sink processing precedes
printing and recycling the completed request.

## Results

All six sessions complete, delivering another 144 buffers. The original warning
does **not** recur; the full preflight/launch/capture/cleanup kernel window has no
messages. This does not explain or erase the earlier diagnostic.

Each session has 23 intervals between delivered buffer-completion timestamps.
The median is about 33.3 ms in all cases. The threshold below is descriptive:
1.5 times that session's median, rather than a sensor timing specification.

| Case | Frame files | Delivered buffers | Intervals above threshold | Largest interval (ms) |
| --- | --- | ---: | ---: | ---: |
| 0 | yes | 24 | 7 | 1031.539 |
| 1 | no | 24 | 1 | 998.392 |
| 2 | yes | 24 | 8 | 1031.361 |
| 3 | no | 24 | 0 | 33.574 |
| 4 | yes | 24 | 8 | 1064.842 |
| 5 | no | 24 | 0 | 33.481 |

The writing cases have 23/69 intervals above threshold; discard cases have 1/69.
All three writing cases include approximately one-second gaps. Buffer-completion
timestamps and source queue policy are consistent with backpressure, but this
small fixed-order experiment does not establish runtime queue state or a driver
defect. Gen1 code alternates frame-drop period 30/31 and changes patterns when
buffers run out; a matching IRQ/queue trace has not been collected. These are
driver completion timestamps, not an independent sensor frame counter.

The three writing cases validate 19, 16 and 16 consecutive patterned frames
using the existing sampled RGGB checks. Discard cases retain metadata, with no
pixel-content validation. Full `cam` stdout also retains warnings that IMX132
static properties and sensor delays are unavailable; its delay defaults remain
explicitly unverified. No property table was invented to silence those warnings.

## Procedure and evidence checks

`timed-queue-test.py` is the exact worker used here. It retains monotonic events
for process start/exit, observed completions, pattern enable/restore and analysis.
It preserves raw `cam` text in its private JSON report and retains prioritized
kernel messages per case and across discovery/capture. A known IDLE missing-ready
message is recorded without calling the kernel clean; a different diagnostic
stops the remaining cases. Exit 0 means the planned diagnostic completed,
separate from its `clean_kernel_window` field.

```sh
python3 diagnostics/camera-reopen/check-current-discovery.py \
  --worker diagnostics/camera-reopen/timed-queue-test.py
python3 diagnostics/camera-reopen/check-timed-evidence.py
```

The actual discovery function passes 10 cases; the actual metadata parser and
correlation functions pass 14, including timestamp/sequence/size corruption and
warnings before, during and after delivered buffers. Both suites also pass from
a three-file export without ignored local helpers. The worker runs on the phone
in a separately owned service with a 90-second runtime cap, 15-second stop cap
and 512 MiB memory limit. Each output path and service attempt is new; a completed
or uncertain launch must never be resubmitted.

Both sensors suspend after every case, pattern controls return to zero, and
temporary frames are deleted from phone RAM. No raw frame is transferred.
The service exits 0 and is stopped; taint is zero and Sway/gesture processes and
normal services are unchanged. Independent postflight matches the accepted boot
file, package database, world and repository hashes. USB is configured at high
speed in each case sample, with the battery discharging and postflight health
Good. There is no reboot, package, firmware or boot write.

[Sanitized measurements](../../evidence/2026-11-14-camera-queue-timing.json)
include relative event/frame timestamps and every completion interval. Private
stdout and source/controller evidence remain separate from the deleted frames.

The next useful control is known consumer backpressure without file writing,
using an explicitly owned and bounded client pause plus matched no-pause cases.
Its resume/kill cleanup must be verified before use. The original warning,
every-pixel integrity, sustained video, active charging, system suspend,
sensor delays, lens/flash functions and final combined-image acceptance remain
open. No new kernel patch or r2/r6 physical qualification follows from this run.
