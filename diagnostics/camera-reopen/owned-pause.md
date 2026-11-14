# Recovery from a known camera-client pause

On the accepted installed r1 boot, six full-resolution rear RAW10 sessions
alternate unpaused controls and a 250 ms stop of the owned `cam` process after
at least eight delivered buffers. Every session requests and delivers 24 buffers,
144 total. No frame file is written; pixel content is not validated here.

The client is identified by its `Popen` handle, parent, private session/process
group and process start identity, then pinned with a Linux pidfd. Stop/continue
signals target that pinned process and its threads. This first worker observes
the primary task's stopped state before timing; it does not independently sample
every live thread or a completed group-stop wait notification. A stronger
all-thread acknowledgement and matched repetition are required before treating
this as a fully confirmed thread-group stop window. Cleanup resumes a stopped client,
then interrupts or kills its verified private group and reaps the primary child
within a deadline. A failed resume/identity check uses the pinned primary handle
for continue/kill rather than signaling an unverified group.

## Physical observations

| Case | Client pause | Maximum completion interval (ms) | First new completion after resume (ms) |
| --- | --- | ---: | ---: |
| 0 | none | 33.374 | — |
| 1 | 250.536 ms | 199.641 | 61.576 |
| 2 | none | 33.489 | — |
| 3 | 250.493 ms | 199.641 | 63.980 |
| 4 | none | 33.392 | — |
| 5 | 250.266 ms | 199.559 | 60.033 |

In each paused case, buffers with delivered sequence numbers 8–11 complete while
the primary task is observed stopped. The next new completion is sequence 12, about
60–64 ms after resume acknowledgement. Already-completed buffers are available
when the client resumes; the table is not application-dequeue latency. Each
paused case has one interval above 1.5 times its roughly 33.3 ms median. Controls
have none. These are driver completion timestamps, not an independent sensor
frame counter.

All clients recover and exit 0. No kernel message appears in the full independent
preflight/launch/capture/cleanup window. The original `Missing ready buf 1 4!`
warning does not recur and remains unresolved. These pauses also do not reproduce
the approximately one-second intervals from frame-file writing. Known pauses
therefore do not establish the cause of either earlier observation.

## Source and cleanup checks

```sh
python3 diagnostics/camera-reopen/check-owned-client.py
python3 diagnostics/camera-reopen/check-pause-evidence.py
python3 diagnostics/camera-reopen/check-current-discovery.py \
  --worker diagnostics/camera-reopen/pause-queue-test.py
python3 diagnostics/camera-reopen/check-timed-evidence.py \
  --worker diagnostics/camera-reopen/pause-queue-test.py
```

Eight checks execute the actual ownership helper against disposable Linux child
processes. They verify stop/resume, an exception while stopped, forced group
termination, shared-session rejection, a reaped child, incorrect start identity,
resume-failure fallback and a parent's cleanup of its own grandchild. An unrelated
session continues to run during the targeted pause. Seven checks validate the
pause-window classification, ten sensor discovery and fourteen metadata timing.
All 39 checks also pass from a five-file export without ignored local helpers.

The exact native worker is `pause-queue-test.py`. Its separately owned service
has a 90-second runtime cap, a 15-second stop cap and a 512 MiB memory limit.
Exit 0 reports completion of the planned experiment, separate from kernel-window
cleanliness or complete camera acceptance. New diagnostics other than the known
IDLE missing-ready message stop subsequent cases.

The service is stopped and its cgroup is empty. Both sensors suspend after every
case, both pattern controls return to zero, and no temporary case directory
remains. Independent postflight verifies the accepted boot file, package database,
world and repository hashes; taint remains zero, systemd and selected services
are healthy, and Sway/gesture processes are unchanged. USB is configured at high
speed in each sample. The battery reports discharging with Good health afterward.
There is no reboot, module, package, firmware or boot change.

## Next evidence needed

A read-only inventory finds mounted tracefs, an instances directory, and the
existing `vb2_qbuf`, `vb2_dqbuf`, `vb2_buf_queue` and `vb2_buf_done` events. Their
runtime formats expose `queued_count` and `owned_by_drv_count`. No tracing state
was changed, no instance was created and no trace data was collected. Instance
creation/configuration/cleanup still needs validation before a capture run.

An owned instance can support a queue-credit diagnostic without a kernel patch.
It must preserve existing global/other-instance settings, check for lost events,
disable and remove its own instance, and keep raw pointer-bearing traces private.
The original warning appeared during a front/rear binned/full switching sequence;
that workload needs matching timing and queue evidence rather than assuming that
full-resolution rear pauses reproduce it.

The original warning, frame-file timing gaps, every-pixel integrity, sustained
video, sensor-delay metadata, active charging, system suspend, lens/flash functions
and final combined-image acceptance remain open. The separate r2 repeat and r6
physical gates are unchanged.
[Sanitized measurements](../../evidence/2026-11-14-camera-owned-pause.json)
